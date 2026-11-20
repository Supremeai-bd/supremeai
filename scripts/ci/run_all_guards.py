#!/usr/bin/env python3
"""Run all CI guards in one pass (dispatcher; guards stay as separate modules)."""

from __future__ import annotations

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
    parser.add_argument("--list", action="store_true", help="print the selected commands")
    args = parser.parse_args(argv)

    selected = [c for c in GUARDS if is_fast(c)] if args.fast else GUARDS
    if args.list:
        for cmd in selected:
            print(" ".join(cmd))
        return 0

    label = "fast lane" if args.fast else "full roster"
    print(f"=== {label}: {len(selected)}/{len(GUARDS)} guards ===")

    failed = 0
    failures: list[str] = []
    for cmd in selected:
        # Run every guard with the interpreter that is executing THIS script:
        # a bare `python` can resolve to a different install (and then a guard
        # that needs PyYAML fails for reasons the operator cannot see).
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
        # Named, not just counted: a CI log that says "1 failed" makes the reader
        # grep 3 000 lines. The whole point of wiring the roster in is that the
        # failure is actionable.
        print("\nFAILED:")
        for name in failures:
            print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
