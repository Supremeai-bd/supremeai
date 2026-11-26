#!/usr/bin/env python3
"""Run all CI guards in one pass (dispatcher; guards stay as separate modules)."""

from __future__ import annotations

import concurrent.futures
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

GUARDS: list[list[str]] = [
    # Wiring integrity FIRST (#3316): every later roster entry is asserted to
    # reference a script that actually exists in the tree — wiring must not
    # outrun implementation (live instance 2026-10-30: #3268 wiring merged
    # while carrying PR #3257 still waited in the gate).
    ["python", "scripts/ci/wiring_integrity_guard.py", "--self-test"],
    ["python", "scripts/ci/wiring_integrity_guard.py", "--check"],
    ["python", "scripts/ci/boundary_sanitization_guard.py", "--self-test"],
    ["python", "scripts/ci/cross_platform_invariant_guard.py", "--self-test"],
    ["python", "scripts/ci/admin_sovereignty_guard.py", "--self-test"],
    ["python", "scripts/ci/satellite_board_guard.py", "--self-test"],
    ["python", "scripts/ci/deploy_preflight_guard.py", "--step1-syntax"],
    ["python", "scripts/ci/deploy_preflight_guard.py", "--self-test"],
    ["python", "scripts/ci/issue_template_guard.py", "--self-test"],
    ["python", "scripts/ci/constitution_pointer_guard.py", "--self-test"],
    ["python", "scripts/ci/constitution_pointer_guard.py"],
    ["python", "scripts/ci/openapi_breaking_guard.py", "--check"],
    ["python", "scripts/ci/security_gate.py", "--self-test"],
    ["python", "scripts/ci/mcp_access_policy_guard.py", "--check"],
    ["python", "scripts/ci/contract_fuzz_guard.py", "--self-test"],
    ["python", "scripts/ci/boundary_contract_sentinel.py", "--self-test"],
    ["python", "scripts/ci/fleet_contract_probe.py", "--self-test"],
    ["python", "scripts/ci/bridge_landing_watchdog.py", "--self-test"],
    ["python", "scripts/ci/bridge_intake_gate_watchdog.py", "--self-test"],
    # open→core sync staleness guard (#2756): self-test only in the roster —
    # the live check reads two external commit planes and belongs to the
    # cadence lane, not the per-PR roster.
    ["python", "scripts/ci/open_core_sync_staleness_watchdog.py", "--self-test"],
    # PR-lane strand tripwire (post-#3418 landing family): self-test only in
    # the roster — the live check reads the tower PR plane and belongs to the
    # cadence lane, same doctrine as the watchdogs above.
    ["python", "scripts/ci/pr_preflight_guard.py", "--self-test"],
    ["python", "scripts/ci/pr_landing_age_guard.py", "--self-test"],
    # Radar pointer⇄pin co-obligation guard (#3624 class): self-test only in
    # the roster — --check/--check-ref read the git/index planes and belong
    # to the registration-PR author's pre-push step (#3483 literal rule).
    ["python", "scripts/ci/radar_pointer_pin_guard.py", "--self-test"],
    ["python", "scripts/ci/closure_live_state_gate.py", "--self-test"],
    ["python", "scripts/ci/license_ssot_guard.py", "--check"],
    ["python", "scripts/ci/contract_codegen_guard.py", "--check"],
    ["python", "scripts/ci/bandit_sast_guard.py", "--check"],
    ["python", "scripts/ci/js_dep_cve_guard.py", "--check"],
    ["python", "scripts/ci/py_dep_cve_guard.py", "--check"],
    ["python", "scripts/ci/check_dockerfile_security.py", "--from-strict"],
    ["python", "scripts/ci/npm_dep_cve_guard.py", "--self-test"],
    ["python", "scripts/ci/npm_dep_cve_guard.py", "--check"],
    ["python", "scripts/ci/bump_candidate_probe.py", "--self-test"],
    ["python", "scripts/ci/mcp_registry_catalog.py", "--self-test"],
    ["python", "scripts/ci/docs_link_integrity_guard.py", "--self-test"],
    ["python", "scripts/ci/docs_link_integrity_guard.py"],
    # Architecture reachability from live entrypoints (import-graph, not a list).
    ["python", "scripts/ci/architecture_gap_guardian.py", "--self-test"],
    ["python", "scripts/ci/architecture_gap_guardian.py", "--check"],
    ["python", "scripts/ci/radar_index_freshness_guard.py", "--check"],
    ["python", "scripts/ci/verdict_plane_age_guard.py", "--self-test"],
    ["python", "scripts/agents/check_loop_contract_parity.py"],
    ["python", "scripts/ci/test_parity_guard.py"],
    ["python", "scripts/ops/generate_script_index.py", "--check"],
    ["python", "scripts/ci/skill_conformance_guard.py", "--self-test"],
    ["python", "scripts/ci/skill_conformance_guard.py", "--check"],
    ["python", "scripts/ci/ghost_host_guard.py", "--self-test"],
    ["python", "scripts/ci/ghost_host_guard.py", "--check"],
    # Config-plane guards. Both existed but were never in this roster AND both
    # crashed on the post-flattening path (backend/core/config_classification.py),
    # so `config/service_registry.yaml` had no working validator at all until
    # 2026-11-19. They are ~0.4 s each and stdlib-only.
    ["python", "scripts/ci/generate_agents_md.py", "--check"],
    ["python", "scripts/ci/validate_config_registry.py"],
    ["python", "scripts/ci/check_config_contract.py"],
    # env SSOT contract: .env.example must equal CONFIG_SPECS-derived output.
    # This was the missing third sibling — the generator kept the pre-flatten
    # `backend/core/...` literal, crashed with FileNotFoundError on every run,
    # and .env.example drifted 57 vars behind the registry unnoticed.
    ["python", "scripts/ci/generate_env_example.py", "--check"],
    ["python", "scripts/ci/service_entrypoint_census.py", "--self-test"],
    ["python", "scripts/ci/service_entrypoint_census.py", "--check"],
    # satellite_residue_guard: #1676 satellite nested-anchor residue detection
    ["python", "scripts/ci/satellite_residue_guard.py", "--self-test"],
    # A SARIF upload without `security-events: write` fails only on main (the
    # step is main-only, so PRs stay green) — it did, twice, on 2026-11-19.
    ["python", "scripts/ci/sarif_permission_guard.py", "--self-test"],
    ["python", "scripts/ci/sarif_permission_guard.py", "--check"],
    # ── Adopted 2026-11-20: written, working, and never executed ─────────────
    # These four were already correct and already passing; they simply had no
    # caller, so every rule they encode was unenforced. Adopted only after
    # running each one — a guard that fails on the current tree would make the
    # roster permanently red, which is how rosters get deleted.
    #   actions_pinning  — every actions/* must be SHA-pinned (supply chain)
    #   migration_safety — alembic revisions must keep upgrade+downgrade
    #   truthy_env_var   — "false"/"0" must not be read as truthy
    #   singleton_inits  — no duplicate module-scope client init
    ["python", "scripts/ci/check_actions_pinning.py", "--check"],
    ["python", "scripts/ci/check_migration_safety.py", "--check"],
    ["python", "scripts/ci/check_truthy_env_var.py", "--check"],
    ["python", "scripts/ci/check_singleton_inits.py", "--check"],
    # Inventory itself: every guard must have a caller (see the tool's docstring).
    ["python", "scripts/ci/guard_inventory.py", "--check"],
    # 2026-11-20: GitHub enforces structural rules that PyYAML does not. A 26th
    # `workflow_dispatch` input (the limit is 25) made GitHub reject the whole of
    # ops-maintenance.yml — zero jobs on push and on the nightly cron, with no
    # failing step to point at, so the breakage was invisible to the PR that
    # caused it. This guard validates the rules GitHub actually enforces.
    ["python", "scripts/ci/workflow_validity_guard.py", "--check"],
    # 2026-11-20: 67 security-sensitive env vars were read in code but absent
    # from the config SSOT. Registered (350 -> 417 keys), so this gate passes
    # now and can hold the line going forward.
    ["python", "scripts/ci/check_config_control_plane.py", "--check"],
    # Path resolver: `backend/` has never existed here; the package is `core/`.
    # 101 scripts still hardcode the dead path (measured by --check), so only the
    # self-test gates for now — the resolver's own logic is what needs pinning.
    ["python", "scripts/ci/repo_paths.py", "--self-test"],
    # ── Adopted 2026-11-20 (batch 2): proven green on the current tree ───────
    # Each was executed before adoption; all exit 0 on main today, so adding
    # them cannot make the roster red. They were written, merged and never
    # called — the exact pattern `guard_inventory.py` now prevents.
    ["python", "scripts/ci/check_critical_invariants.py", "--check"],
    ["python", "scripts/ci/check_frontend_secrets.py", "--check"],
    ["python", "scripts/ci/check_gateway_bypass.py", "--check"],
    ["python", "scripts/ci/check_import_budget.py", "--check"],
    ["python", "scripts/ci/check_react_cleanup.py", "--check"],
    ["python", "scripts/ci/check_self_heal_token_usage.py", "--check"],
    ["python", "scripts/ci/check_single_frontend.py", "--check"],
    ["python", "scripts/ci/contract_parity_guard.py", "--check"],
    ["python", "scripts/ci/core_gateway_parity_guard.py", "--check"],
    ["python", "scripts/ci/env_mode_guard.py", "--check"],
    ["python", "scripts/ci/satellite_trigger_integrity_guard.py", "--check"],
    ["python", "scripts/ci/secondary_service_probes.py", "--check"],
    ["python", "scripts/ci/skill_plane_parity_guard.py", "--check"],
    # ── Adopted 2026-11-20 (batch 3): proven green on the current tree ───────
    # The register claimed 56 of the 72 orphans were "crashed". That was my
    # own measurement error: the probe tried only `--check` and read exit 2
    # ("unknown flag") as "broken". Re-probed with four invocations —
    # `--check`, `--self-test`, `--advisory`, and no args — the real split is
    # 45 working, 19 that find genuine violations, 8 genuinely broken.
    #
    # Rule applied here: adopt a guard only in a mode that is READ-ONLY and
    # exits 0 today. Measured, not assumed — each no-arg candidate was run in
    # a throwaway copy of the tree to see whether it writes. A self-test is
    # read-only by construction (it exercises the tool, not the repo).
    #
    # read-only --check, green now:
    ["python", "scripts/ci/build_secret_registry.py", "--check"],
    ["python", "scripts/ci/migration_contract.py", "--check"],
    ["python", "scripts/ci/pii_redaction_gap_probe.py", "--check"],
    ["python", "scripts/ci/schema_contract.py", "--check"],
    #
    # --self-test only: the live check needs repo state a runner lacks, but the guard's own logic is fully exercised:
    ["python", "scripts/ci/annotations_census_guard.py", "--self-test"],
    ["python", "scripts/ci/bridge_opener_hardening_reference.py", "--self-test"],
    ["python", "scripts/ci/check_database_schema.py", "--self-test"],
    ["python", "scripts/ci/dependency_parasite_guard.py", "--self-test"],
    ["python", "scripts/ci/frontend_performance_guard.py", "--self-test"],
    ["python", "scripts/ci/line_budget_guard.py", "--self-test"],
    ["python", "scripts/ci/lockfile_promise_guard.py", "--self-test"],
    ["python", "scripts/ci/mcp_tower_conformance_probe.py", "--self-test"],
    ["python", "scripts/ci/memory_consolidation_guard.py", "--self-test"],
    ["python", "scripts/ci/mission_control_status.py", "--self-test"],
    ["python", "scripts/ci/pipeline_timeout_guard.py", "--self-test"],
    ["python", "scripts/ci/pr_improvement_regression_guard.py", "--self-test"],
    ["python", "scripts/ci/rejected_wo_rescue.py", "--self-test"],
    ["python", "scripts/ci/render_build_quota_guard.py", "--self-test"],
    ["python", "scripts/ci/satellite_ci_sentinel.py", "--self-test"],
    ["python", "scripts/ci/satellite_parity_gate.py", "--self-test"],
    ["python", "scripts/ci/secret_scanner_policy.py", "--self-test"],
    ["python", "scripts/ci/tower_read_file_artifact_probe.py", "--self-test"],
    ["python", "scripts/ci/vendored_tree_guard.py", "--self-test"],
    ["python", "scripts/ci/verdict_plane_gap_probe.py", "--self-test"],
    ["python", "scripts/ci/workflow_hardening_census_guard.py", "--self-test"],
    #
    # report-only audits: exit 0, findings printed, ci-reports/ is gitignored:
    ["python", "scripts/ci/check_commit_sizing.py"],
    ["python", "scripts/ci/check_free_tier_limits.py"],
    ["python", "scripts/ci/check_i18n_keys.py"],
    ["python", "scripts/ci/hollow_read_guard.py"],
    ["python", "scripts/ci/runner_hierarchy_guard.py"],
    ["python", "scripts/ci/sprawl_guard.py"],
]


#: Guards that are cheap (sub-second, stdlib + PyYAML only) and catch the classes
#: of breakage a PR actually introduces: wiring, config plane, architecture
#: reachability, docs/index freshness. Everything else is a repo-wide audit whose
#: findings change on merge to main, not on a feature branch — those belong to the
#: nightly lane (``--full``), not to every PR.
#:
#: Measured: the whole roster is ~31 s, so this split exists to keep a PR's
#: feedback loop honest (a 5-minute Tier 1 that always times out gets skipped by
#: humans), not because the full set is expensive.
FAST_SUFFIXES = (
    "--self-test",
    "--check",
    "--check-required-names",
    "--step1-syntax",
    "--from-strict",
    "--verify-client-contracts",
)


def is_fast(cmd: list[str]) -> bool:
    """A roster entry is fast when it only runs a self-test or a read-only check.

    Entries with no flag at all are live generators (``generate_env_example.py``
    with no ``--check`` writes files); they stay in the full lane so a PR cannot
    be blocked by a step whose job is to *produce* output.
    """
    return any(arg in FAST_SUFFIXES for arg in cmd[1:])


# বাংলা মন্তব্য: ভারী হোল-ট্রি অডিট ও বাহ্যিক নেটওয়ার্ক গেটগুলো সিআই/নাইটলির জন্য বরাদ্দ, লোকাল প্রি-পুশে নয়
HEAVY_OR_NETWORK = {
    "architecture_gap_guardian.py",
    "deploy_preflight_guard.py",
    "py_dep_cve_guard.py",
    "npm_dep_cve_guard.py",
}


def is_emergency(cmd: list[str]) -> bool:
    """Emergency checks for local pre-push: real integrity & security checks only.

    Excludes self-test test fixtures of the guard scripts themselves and heavy whole-tree sweeps.
    """
    if not is_fast(cmd):
        return False
    if any(arg == "--self-test" for arg in cmd[1:]):
        return False
    if any(h in cmd[1] for h in HEAVY_OR_NETWORK):
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="self-tests and read-only checks only (PR lane)",
    )
    parser.add_argument(
        "--full", action="store_true", help="every guard (nightly / main lane)"
    )
    parser.add_argument(
        "--emergency",
        "--pre-push",
        action="store_true",
        help="critical integrity & security checks for fast local pre-push (<15s)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=1,
        help="number of parallel processes to run guards (default 1 for sequential)",
    )
    parser.add_argument("--list", action="store_true", help="print the selected commands")
    parser.add_argument(
        "--no-path-filter",
        action="store_true",
        help="disable changed-files path-filter on --fast (full fast lane)",
    )
    args = parser.parse_args(argv)

    if args.emergency:
        # Emergency lane stays UNFILTERED (fail-closed): critical integrity
        # checks must all run on every pre-push regardless of changed paths.
        selected = [c for c in GUARDS if is_emergency(c)]
        label = "emergency pre-push lane"
    elif args.fast:
        selected = [c for c in GUARDS if is_fast(c)]
        label = "fast lane"
        # G1 (reaudit 2026-11-26): path-filter the PR fast lane when we can
        # derive changed files. Fail-OPEN to the full fast lane on any error
        # so a git hiccup never weakens the gate. run_guards.py stays the
        # filter SSOT (it imports GUARDS from this module — lazy import here
        # avoids a circular import at module load).
        if not args.no_path_filter:
            try:
                import run_guards as _rg

                _changed = _rg.changed_from_git()
                if _changed:
                    selected, _total = _rg.select("fast", _changed)
                    label = (
                        f"fast lane (path-filtered {len(selected)}/{_total}, "
                        f"changed={len(_changed)})"
                    )
            except Exception as _exc:  # fail-open by design
                print(
                    f"path-filter unavailable ({_exc}); running full fast lane",
                    file=sys.stderr,
                )
    else:
        selected = GUARDS
        label = "full roster"

    if args.list:
        for cmd in selected:
            print(" ".join(cmd))
        return 0

    print(f"=== {label}: {len(selected)}/{len(GUARDS)} guards ===")

    failed = 0
    failures: list[str] = []

    if args.jobs > 1 and len(selected) > 1:
        # বাংলা মন্তব্য: থ্রেডপুল এক্সেকিউটর দিয়ে ইন্ডিপেনডেন্ট গার্ডগুলোকে সমান্তরালে দ্রুত চালানো
        def _exec_cmd(cmd_item: list[str]) -> tuple[list[str], int, str]:
            c = [sys.executable, *cmd_item[1:]] if cmd_item[0] == "python" else cmd_item
            r = subprocess.run(
                c,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return cmd_item, r.returncode, out

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(_exec_cmd, c) for c in selected]
            for fut in concurrent.futures.as_completed(futures):
                c_item, ret, output = fut.result()
                name = " ".join(c_item[1:])
                if ret != 0:
                    failed += 1
                    failures.append(name)
                    print(f"FAIL (exit {ret}): {name}")
                    if output.strip():
                        for line in output.strip().splitlines()[:10]:
                            print(f"    {line}")
                else:
                    print(f"OK: {name}")
    else:
        for cmd in selected:
            cmd = [sys.executable, *cmd[1:]] if cmd[0] == "python" else cmd
            print(f"=== {' '.join(cmd)} ===")
            r = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
            if r.returncode != 0:
                failed += 1
                failures.append(" ".join(cmd[1:]))
                print(f"FAIL (exit {r.returncode})")
            else:
                print("OK")

    print(f"\n{len(selected) - failed}/{len(selected)} guards passed ({label})")
    if failures:
        print("\nFAILED:")
        for name in failures:
            print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
