#!/usr/bin/env python3
"""run_guards.py — changed-files-aware guard runner (audit B2).

সমস্যা (2026-11-26 ডিপ অডিট, B2):
  ৬১টা guard আছে, কিন্তু PR-এর জন্য প্রতিবার রোস্টারের বড় অংশ চলে — অনেক guard
  যে ফাইলে হাত দেওয়া হয়নি সেগুলো পড়েই সময় নষ্ট করে। `guard_inventory.py` আছে
  কিন্তু inventory পড়ে না।

সমাধান:
  python scripts/ci/run_guards.py --tier fast|full|emergency [--changed <files>]

  - GUARDS registry হলো `run_all_guards.py`-এর GUARDS-এর রেফারেন্স (DRY — নিজস্ব
    কপি নয়), tier split একই সেমেন্টিক্স (fast/full/emergency)।
  - `--changed` দিলে path-filter চলে: guard-এর watch_path-এর সাথে overlap না থাকলে
    সেই guard স্কিপ হয় (ছাড়া constitution-critical ALWAYS_RUN guards —
    `mcp_access_policy_guard`, `wiring_integrity_guard`, `generate_agents_md`,
    `validate_config_registry` ইত্যাদি path-filter নয়, প্রতিবার চলবে)।
  - প্রতিটি guard subprocess-এ চলে — fail semantics `run_all_guards.py`-এর সমান
    (exit code প্রথম fail = non-zero, লিস্টে সব fail)।

Regression-safe:
  - কোনো guard মোছে না; শুধু orchestration কেন্দ্রীয়।
  - `--changed` ছাড়া চালালে = full lane একদম `run_all_guards.py --full`-এর মতো।
  - ALWAYS_RUN সেট সংকুচিত রাখা — false-skip এড়াতে প্রথমেই ছোট, ধীরে বাড়ানো।

Usage:
  python scripts/ci/run_guards.py --tier fast --changed a.py b.py
  python scripts/ci/run_guards.py --tier fast --from-git          # git diff-থেকে
  python scripts/ci/run_guards.py --tier emergency               # pre-push
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

# বাংলা মন্তব্য: DRY — run_all_guards.py-ই GUARDS রোস্টারের একমাত্র SSOT।
from run_all_guards import GUARDS, is_emergency, is_fast  # noqa: E402

# বাংলা মন্তব্য: constitution-critical guards — এরা কখনো path-filter দিয়ে skip হবে না।
# সংকুচিত সেট: ভাঙলে constitution/gate নিজেই অন্ধ হয়ে যায়।
ALWAYS_RUN = {
    "wiring_integrity_guard.py",      # রোস্টার wiring — সবার আগে
    "mcp_access_policy_guard.py",     # constitution access plane
    "generate_agents_md.py",          # AGENTS.md SSOT drift
    "validate_config_registry.py",    # config registry validator
    "guard_inventory.py",             # no guard without a caller (self-ratchet)
    "workflow_validity_guard.py",     # GitHub-structural validation
    "check_actions_pinning.py",       # supply-chain pinning
}

# বাংলা মন্তব্য: guard → watch path (prefix match, ফাইল/ডিরেক্টরি দুটোই চলে)।
# এটি সচেতনভাবে সংকুচিত: যে guard পুরো ট্রি স্ক্যান করে তার watch root ।/ রাখা
# মানে সে সবসময় চলবে — সে ক্ষেত্রে ALWAYS_RUN-এ না রেখেও একই ফল।
WATCH_PATHS: dict[str, tuple[str, ...]] = {
    "openapi_breaking_guard.py": ("api-schemas/", "gateway/", "core/"),
    "contract_codegen_guard.py": ("api-schemas/", "core/", "gateway/"),
    "contract_parity_guard.py": ("core/", "gateway/"),
    "core_gateway_parity_guard.py": ("core/", "gateway/"),
    "skill_conformance_guard.py": ("scripts/", ".agents/", "skills/"),
    "docs_link_integrity_guard.py": ("docs/", "README.md", ".github/"),
    "generate_agents_md.py": (".github/constitution/", "AGENTS.md", ".github/"),
    "generate_env_example.py": ("core/", "gateway/"),
    "env_mode_guard.py": ("core/", "gateway/"),
    "check_migration_safety.py": ("core/alembic_migrations/", "gateway/"),
    "migration_contract.py": ("core/alembic_migrations/", "gateway/"),
    "check_database_schema.py": ("core/", "supabase/"),
    "check_frontend_secrets.py": ("studio/", "frontend/", "src/", "public/"),
    "check_react_cleanup.py": ("studio/", "frontend/", "src/"),
    "check_single_frontend.py": ("studio/", "frontend/", "src/"),
    "check_gateway_bypass.py": ("gateway/", "core/"),
    "check_import_budget.py": ("core/", "gateway/"),
    "check_singleton_inits.py": ("core/", "gateway/"),
    "check_truthy_env_var.py": ("core/", "gateway/", "scripts/"),
    "check_self_heal_token_usage.py": ("core/", "gateway/", "scripts/"),
    "check_config_control_plane.py": ("core/", "gateway/", "scripts/"),
    "check_config_contract.py": ("core/", "gateway/", "scripts/"),
    "check_dockerfile_security.py": ("Dockerfile", "infrastructure/"),
    "check_i18n_keys.py": ("studio/", "frontend/", "src/"),
    "check_commit_sizing.py": ("core/", "gateway/", "scripts/", "studio/"),
    "check_free_tier_limits.py": ("core/", "gateway/"),
    "workflow_job_name_guard.py": (".github/workflows/",),
    "workflow_validity_guard.py": (".github/workflows/",),
    "sarif_permission_guard.py": (".github/workflows/",),
    "check_actions_pinning.py": (".github/",),
    "satellite_trigger_integrity_guard.py": (".github/workflows/",),
    "satellite_board_guard.py": (".github/", "core/", "gateway/"),
    "satellite_residue_guard.py": ("vscode/", ".github/", "docs/"),
    "satellite_parity_gate.py": ("vscode/", "core/"),
    "satellite_ci_sentinel.py": (".github/workflows/", "vscode/"),
    "radar_index_freshness_guard.py": ("docs/", "scripts/ops/", "scripts/ci/"),
    "verdict_plane_age_guard.py": ("docs/", "scripts/"),
    "license_ssot_guard.py": ("LICENSE", "core/", "gateway/"),
    "js_dep_cve_guard.py": ("package.json", "package-lock.json", "browser/", "infrastructure/"),
    "npm_dep_cve_guard.py": ("package.json", "package-lock.json", "browser/", "infrastructure/"),
    "py_dep_cve_guard.py": ("core/requirements", "gateway/requirements"),
    "bandit_sast_guard.py": ("core/", "gateway/", "scripts/"),
    "security_gate.py": ("core/", "gateway/", "scripts/", ".github/"),
    "mcp_registry_catalog.py": ("infrastructure/mcp-control-plane/",),
    "ghost_host_guard.py": ("core/", "gateway/", "scripts/", ".github/"),
    "public_surface_guard.py": ("core/", "gateway/"),
    "skill_plane_parity_guard.py": ("scripts/", ".agents/"),
    "dependency_parasite_guard.py": ("core/requirements", "gateway/requirements"),
    "vendored_tree_guard.py": ("core/", "gateway/", "browser/", "infrastructure/"),
    "lockfile_promise_guard.py": ("core/requirements", "gateway/requirements"),
    "line_budget_guard.py": ("core/", "gateway/", "scripts/"),
    "pipeline_timeout_guard.py": (".github/workflows/", "config/ci/"),
    "pr_improvement_regression_guard.py": (".github/", "scripts/"),
    "render_build_quota_guard.py": ("render.yaml", ".github/workflows/"),
    "test_parity_guard.py": ("tests/", "core/tests/", "gateway/tests/"),
    "hollow_read_guard.py": ("core/", "gateway/", "scripts/"),
    "runner_hierarchy_guard.py": (".github/workflows/",),
    "sprawl_guard.py": ("core/", "gateway/", "scripts/", "studio/"),
    "build_secret_registry.py": ("core/", "gateway/", "scripts/"),
    "schema_contract.py": ("core/", "gateway/"),
    "pii_redaction_gap_probe.py": ("core/", "gateway/"),
    "annotations_census_guard.py": ("core/", "gateway/", "scripts/"),
    "workflow_hardening_census_guard.py": (".github/workflows/",),
    "frontend_performance_guard.py": ("studio/", "frontend/", "src/"),
    "boundary_contract_sentinel.py": ("core/", "gateway/"),
    "boundary_sanitization_guard.py": ("core/", "gateway/"),
    "cross_platform_invariant_guard.py": ("core/", "gateway/", "scripts/"),
    "admin_sovereignty_guard.py": ("core/", "gateway/", "scripts/"),
    "issue_template_guard.py": (".github/",),
    "constitution_pointer_guard.py": ("AGENTS.md", ".github/constitution/", "docs/"),
    "deploy_preflight_guard.py": ("render.yaml", ".github/workflows/", "infrastructure/"),
    "bridge_landing_watchdog.py": ("scripts/", ".github/"),
    "bridge_intake_gate_watchdog.py": ("scripts/", ".github/"),
    "pr_preflight_guard.py": ("scripts/", ".github/"),
    "pr_landing_age_guard.py": ("scripts/", ".github/"),
    "radar_pointer_pin_guard.py": ("docs/", "scripts/ops/", "scripts/ci/"),
    "closure_live_state_gate.py": ("scripts/", "docs/"),
    "open_core_sync_staleness_watchdog.py": ("scripts/", ".patches/"),
    "bump_candidate_probe.py": ("core/requirements", "gateway/requirements"),
    "secondary_service_probes.py": ("core/", "gateway/"),
    "fleet_contract_probe.py": ("core/", "gateway/", "infrastructure/"),
    "check_critical_invariants.py": ("core/", "gateway/", "scripts/"),
    "service_entrypoint_census.py": ("core/", "gateway/", "scripts/"),
    "contract_fuzz_guard.py": ("api-schemas/", "core/", "gateway/"),
    "check_hardcoded_deployment_config.py": ("core/", "gateway/", "scripts/"),
}


def _paths_for(cmd: list[str]) -> tuple[str, ...]:
    """roster entry-এর script name → watch paths; অজানা হলে ('',) = always-run।"""
    script = next((arg for arg in cmd[1:] if arg.endswith(".py")), "")
    name = Path(script).name
    if name in ALWAYS_RUN:
        return ("",)
    return WATCH_PATHS.get(name, ("",))


def _matches(changed: list[str], watch: tuple[str, ...]) -> bool:
    if ("",) in watch or not changed:
        return True
    return any(c.startswith(p) or c == p for c in changed for p in watch)


def changed_from_git(base: str = "origin/main") -> list[str]:
    """git diff থেকে changed files (local dev সুবিধা)।"""
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True, check=False,
    )
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


def select(tier: str, changed: list[str]) -> tuple[list[list[str]], int]:
    if tier == "emergency":
        base = [c for c in GUARDS if is_emergency(c)]
    elif tier == "fast":
        base = [c for c in GUARDS if is_fast(c)]
    else:
        base = list(GUARDS)
    if not changed:
        return base, len(base)
    relevant = [c for c in base if _matches(changed, _paths_for(c))]
    return relevant, len(base)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="changed-files-aware guard runner")
    parser.add_argument("--tier", choices=("fast", "full", "emergency"), default="fast")
    parser.add_argument("--changed", default="", help="space/comma-separated changed file paths")
    parser.add_argument("--from-git", action="store_true", help="derive changed files from git diff vs origin/main")
    parser.add_argument("--base", default="origin/main", help="git diff base ref for --from-git")
    parser.add_argument("-j", "--jobs", type=int, default=1)
    parser.add_argument("--list", action="store_true", help="print selected commands only")
    args = parser.parse_args(argv)

    changed: list[str] = []
    if args.from_git:
        changed = changed_from_git(args.base)
    elif args.changed:
        changed = [p.strip() for p in args.changed.replace(",", " ").split() if p.strip()]

    selected, total = select(args.tier, changed)
    label = f"{args.tier} lane (changed-filtered {len(selected)}/{total}, changed={len(changed)})"

    if args.list:
        for cmd in selected:
            print(" ".join(cmd))
        return 0

    print(f"=== run_guards: {label} ===")

    failed: list[str] = []
    for cmd in selected:
        run = [sys.executable, *cmd[1:]] if cmd[0] == "python" else cmd
        r = subprocess.run(run, cwd=REPO_ROOT, check=False)
        if r.returncode != 0:
            failed.append(" ".join(cmd[1:]))
            print(f"FAIL (exit {r.returncode}): {' '.join(cmd[1:])}")
        else:
            print(f"OK: {' '.join(cmd[1:])}")

    print(f"\n{len(selected) - len(failed)}/{len(selected)} guards exited 0 ({label}; inspect output for skipped checks)")
    if failed:
        print("FAILED:")
        for n in failed:
            print(f"  - {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
