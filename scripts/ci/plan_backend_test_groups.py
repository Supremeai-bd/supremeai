#!/usr/bin/env python3
"""Per-group backend test planner (issue #470 — Phase 1).

বাংলা: backend টেস্ট ম্যাট্রিক্সের গ্রুপ-লেভেল সিদ্ধান্ত ইঞ্জিন। changed
ফাইলগুলোকে শ্রেণীবদ্ধ করে (core-trigger / backend-source / backend-tests /
অপ্রাসঙ্গিক) প্রতিটি ম্যাট্রিক্স গ্রুপের জন্য run/skip সিদ্ধান্ত নেয় এবং
`strategy.matrix` এর জন্য সম্পূর্ণ JSON emit করে — ci.yml-এ আর কোনো স্ট্যাটিক
ম্যাট্রিক্স নেই, এই স্ক্রিপ্টই single source of truth।

WHY FULL-MODE BY DEFAULT (coverage-gate contract, DO NOT "optimize" away):

  The Backend Aggregate Gate (coverage_quality_gate.py) is FAIL-CLOSED and
  its critical/important thresholds are calibrated on the honest FULL-suite
  combined numerator (coverage_policy.yaml ratchet 40→50→60, incident
  PR #343: a targeted run collapsed the numerator 64.72%→21.68% and the
  gate correctly failed). Skipping any group whose tests exercise
  --cov=core,api,services,tools,runs,memory removes those packages from the
  combined coverage.json → tier files go missing → gate fails closed.

  Therefore group-level skipping is ONLY legal when the skipped groups'
  coverage data still reaches the gate. That requires a coverage-persistence
  layer (cache per-group `.coverage.<group>` keyed by backend-source hash +
  group test-file hash — coverage data is additive, so reusing byte-identical
  inputs' coverage yields the exact same combined numerator).

  That layer is issue #471 (scripts/ci/coverage_cache_keys.py + ci.yml
  actions/cache wiring): every run saves each group's `.coverage.<group>`
  under a content-derived key; in scoped mode the skipped groups' data is
  restored into the aggregate so the gate still sees the FULL numerator.
  `scoped` mode stays gated behind `CI_COVERAGE_CACHE_ENABLED` (repo
  variable) until the cache has proven itself on consecutive green runs.

  force_run contract (cache can never hide a live regression):
    - full mode (main, force-overall, source/core-trigger change) → every
      matrix entry force_run=true → pytest always runs; the cache is only
      WARMED (saved), never consumed. Reason: full mode can be triggered by
      diffs (scripts/**, backend non-measured files) that the cache key
      does not capture — skipping on a hit there would be a false green.
    - scoped mode → entries respect the cache (identical-input reuse),
      EXCEPT groups forced back in by previous-failure memory, which must
      re-run to prove the fix.
    - if key computation fails (empty cache_key), the job ignores the
      cache entirely → behaves exactly like pre-#471 CI.

Decision logic (priority order):
  1. main branch / run_backend_overall force / planner can't classify
     (empty diff, unknown base) → FULL (all groups).
  2. Core-trigger files changed (deps, conftest, app entrypoints, CI
     workflow, this planner, migrations) → FULL.
  3. Any backend source (non-test) file changed → FULL (coverage gate).
  4. Test-only change AND CI_COVERAGE_CACHE_ENABLED == 'true' → SCOPED
     (owning groups of the changed tests + previously-failed groups).
  5. Test-only change without coverage cache → FULL (contract above).
  6. Previous per-group failure (failure/cancelled/timed_out in the most
     recent prior run on this branch) → force that group into the plan.

Failure semantics: unexpected error → FULL matrix (fail-safe), never a
silent skip. If the JOB itself fails, backend-tests `needs` turns red —
visible, never a false green.

Usage (CI):
  python scripts/ci/plan_backend_test_groups.py \
    --base "$BACKEND_TEST_BASE" [--is-main] \
    --previous-group-failures "fast,services"
Usage (local dry-run):
  python scripts/ci/plan_backend_test_groups.py --dry-run \
    --changed-files backend/tests/api/test_x.py backend/core/config.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ─────────────────────────────────────────────────────────────────────────────
# Single source of truth: matrix group definitions.
# ci.yml consumes this via `strategy.matrix: ${{ fromJSON(...matrix_json) }}`.
# Each entry's `paths` value is passed to pytest verbatim (same format the
# static matrix used before the #470 refactor), so detect_changed_tests.py
# target filtering and the per-group `--ignore=` flags keep working.
#
# core split (issue #470 Phase 2): tests/core (215+ files — the wall-clock
# bottleneck) gets its own runner; the 18 support dirs move to core-support.
# ─────────────────────────────────────────────────────────────────────────────
FAST_PATHS = (
    "tests/core/security tests/security tests/core/test_core_rate_limiter.py "
    "tests/tools/test_tenant_rate_limiter_contract.py "
    "tests/core/test_multi_tenant_isolation.py tests/api tests/runs"
)
CORE_UNIT_PATHS = (
    "tests/core "
    "--ignore=tests/core/security "
    "--ignore=tests/core/test_core_rate_limiter.py "
    "--ignore=tests/core/test_multi_tenant_isolation.py"
)
CORE_SUPPORT_PATHS = (
    "tests/brain tests/adaptive_engine tests/llm tests/database "
    "tests/orchestration tests/learning tests/rag tests/runtime "
    "tests/workers tests/middleware tests/monitoring tests/verification "
    "tests/unit tests/engine tests/utils tests/test_evolution "
    "tests/test_strategic_patches tests/p2p_tests"
)
SERVICES_PATHS = (
    "tests/agents tests/ai tests/byoc tests/tools tests/unit_light "
    "tests/test_*.py tests/scripts tests/services tests/memory "
    "tests/scout_tests tests/missions"
)

# Group key → (matrix group name, pytest paths). Order matters ONLY for
# readability; runners are independent.
GROUPS: dict[str, tuple[str, str]] = {
    "fast": ("fast", FAST_PATHS),
    "core_unit": ("core-unit", CORE_UNIT_PATHS),
    "core_support": ("core-support", CORE_SUPPORT_PATHS),
    "services": ("services", SERVICES_PATHS),
}
ALL_GROUP_KEYS = list(GROUPS)

# Directories (relative to backend/tests) owned by each group, used for
# test-file → group mapping in scoped mode. tests/core has file-level
# exceptions owned by fast (rate limiter, multi-tenant).
GROUP_TEST_DIRS: dict[str, set[str]] = {
    "fast": {
        "core/security",
        "security",
        "api",
        "runs",
    },
    "core_unit": {"core"},
    "core_support": {
        "brain",
        "adaptive_engine",
        "llm",
        "database",
        "orchestration",
        "learning",
        "rag",
        "runtime",
        "workers",
        "middleware",
        "monitoring",
        "verification",
        "unit",
        "engine",
        "utils",
        "test_evolution",
        "test_strategic_patches",
        "p2p_tests",
    },
    "services": {
        "agents",
        "ai",
        "byoc",
        "tools",
        "unit_light",
        "scripts",
        "services",
        "memory",
        "scout_tests",
        "missions",
    },
}

# File-level exceptions inside tests/core owned by fast (mirror the
# --ignore flags + explicit fast paths above).
FAST_OWNED_CORE_FILES = {
    "core/test_core_rate_limiter.py",
    "core/test_multi_tenant_isolation.py",
}

# Any of these changed → every group must run (dependency/app/CI contract).
CORE_TRIGGERS = {
    "backend/pyproject.toml",
    "backend/poetry.lock",
    "backend/tests/conftest.py",
    "backend/core/config.py",
    "backend/core/app.py",
    "backend/main.py",
    "backend/database/session.py",
    ".github/workflows/ci.yml",
    ".github/actions/setup-backend/action.yml",
    "scripts/ci/plan_backend_test_groups.py",
    "scripts/ci/detect_changed_tests.py",
    "scripts/ci/coverage_policy.yaml",
    "scripts/ci/coverage_quality_gate.py",
}

BACKEND_TESTS_PREFIX = "backend/tests/"
BACKEND_SOURCE_PREFIX = "backend/"
TESTS_ROOT_LEVEL_FILE_PREFIX = "backend/tests/test_"


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def get_git_diff_files(base: str | None) -> list[str]:
    """Changed files base...HEAD; [] when base is unusable (caller fail-safes)."""
    if not base or not base.strip():
        return []
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", base],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        return []
    res = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        res = subprocess.run(
            ["git", "diff", "--name-only", base],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
    if res.returncode != 0:
        return []
    return [normalize(line) for line in res.stdout.splitlines() if line.strip()]


def map_test_file_to_groups(rel: str) -> set[str]:
    """Map a backend/tests/** path to owning group keys.

    Returns an empty set for unmapped test paths (caller fail-safes to FULL) —
    mirrors the #343 lesson: never let an unmapped path silently drop coverage.
    """
    sub = rel[len(BACKEND_TESTS_PREFIX) :]
    if not sub or sub == "conftest.py":
        return set()  # root conftest affects every group → full
    parts = sub.split("/")
    if len(parts) == 1:
        # tests/test_*.py style root-level files → services owns tests/test_*.py
        if sub.startswith("test_") and sub.endswith(".py"):
            return {"services"}
        if sub.endswith(".py"):
            return set()  # helper file at tests/ root — fail-safe to full
        return set()
    first = parts[0]
    two = "/".join(parts[:2])
    # Two-level ownership wins (tests/core/security/* → fast, not core_unit).
    groups = {key for key, dirs in GROUP_TEST_DIRS.items() if two in dirs}
    if not groups:
        groups = {key for key, dirs in GROUP_TEST_DIRS.items() if first in dirs}
    # File-level fast exceptions inside tests/core/
    if two in FAST_OWNED_CORE_FILES:
        return {"fast"}
    return groups


def classify(changed: list[str]) -> dict:
    """Classify changed files → plan decision.

    Returns {mode, reason, groups} where groups ⊆ ALL_GROUP_KEYS.
    """
    if not changed:
        return {
            "mode": "full",
            "reason": "empty-or-unusable-diff",
            "groups": set(ALL_GROUP_KEYS),
        }

    touched_core_trigger = False
    touched_source = False
    test_groups: set[str] = set()

    for raw in changed:
        rel = normalize(raw)
        # Core triggers take precedence over the tests-prefix branch so that
        # e.g. backend/tests/conftest.py reports the accurate reason.
        if rel in CORE_TRIGGERS or rel.startswith("backend/migrations/"):
            touched_core_trigger = True
            continue
        if rel.startswith(BACKEND_TESTS_PREFIX):
            mapped = map_test_file_to_groups(rel)
            if not mapped:
                # conftest.py / helper file / unmapped test path → full
                return {
                    "mode": "full",
                    "reason": f"unmapped-test-path:{rel}",
                    "groups": set(ALL_GROUP_KEYS),
                }
            test_groups |= mapped
            continue
        if rel.startswith(BACKEND_SOURCE_PREFIX):
            touched_source = True
            continue
        # Non-backend paths (scripts/**, packages/**, docs, .github…) reach the
        # matrix only because paths-filter routes them to backend=true; they do
        # not touch measured packages or tests. v1 contract: still FULL —
        # scripts/** may be imported by tests (tests/scripts) and the gate is
        # fail-closed. Narrowing this is part of the coverage-cache follow-up.
        continue

    if touched_core_trigger:
        return {
            "mode": "full",
            "reason": "core-trigger-files",
            "groups": set(ALL_GROUP_KEYS),
        }
    if touched_source:
        return {
            "mode": "full",
            "reason": "backend-source-change-coverage-gate",
            "groups": set(ALL_GROUP_KEYS),
        }
    if test_groups:
        # Test-only change. Contract: FULL unless the coverage-persistence
        # layer is explicitly enabled (CI_COVERAGE_CACHE_ENABLED == 'true').
        if os.environ.get("CI_COVERAGE_CACHE_ENABLED", "").strip().lower() == "true":
            return {
                "mode": "scoped",
                "reason": "test-only-with-coverage-cache",
                "groups": test_groups,
            }
        return {
            "mode": "full",
            "reason": "test-only-coverage-cache-disabled-contract",
            "groups": set(ALL_GROUP_KEYS),
        }
    return {
        "mode": "full",
        "reason": "no-relevant-classification",
        "groups": set(ALL_GROUP_KEYS),
    }


def apply_previous_group_failures(plan: dict, failed_groups: list[str]) -> dict:
    """Force groups whose most recent prior run failed (failure memory)."""
    forced = {g for g in failed_groups if g in ALL_GROUP_KEYS}
    if not forced:
        return plan
    groups = set(plan["groups"]) | forced
    reason = plan["reason"] + f"+previous-failure:{','.join(sorted(forced))}"
    return {"mode": plan["mode"], "reason": reason, "groups": groups}


def build_matrix_json(
    group_keys: list[str],
    cache_keys: dict[str, str] | None = None,
    force_run_groups: set[str] | None = None,
) -> str:
    """Emit strategy.matrix JSON with #471 cache fields.

    Each entry carries `cache_key` (content-derived; empty string when key
    computation failed → job must ignore the cache) and `force_run`
    ("true" → run pytest even on a cache hit; see the force_run contract
    in the module docstring).
    """
    cache_keys = cache_keys or {}
    force_run_groups = force_run_groups or set()
    include = [
        {
            "group": GROUPS[key][0],
            "paths": GROUPS[key][1],
            "cache_key": cache_keys.get(key, ""),
            "force_run": "true" if key in force_run_groups else "false",
        }
        for key in group_keys
        if key in GROUPS
    ]
    return json.dumps({"include": include})


def emit_outputs(
    plan: dict,
    matrix_json: str,
    failed_groups: list[str],
    cache_keys: dict[str, str] | None = None,
) -> None:
    cache_keys = cache_keys or {}
    github_output = os.environ.get("GITHUB_OUTPUT")
    lines = [
        f"matrix_json={matrix_json}",
        f"plan_mode={plan['mode']}",
        f"plan_reason={plan['reason']}",
        *(
            f"run_{key}={'true' if key in plan['groups'] else 'false'}"
            for key in ALL_GROUP_KEYS
        ),
        # #471: keys for ALL groups (not just matrix ones) — backend-aggregate
        # restores skipped groups' cached .coverage data via these outputs.
        *(f"cache_key_{key}={cache_keys.get(key, '')}" for key in ALL_GROUP_KEYS),
        f"previous_failed_groups={','.join(sorted(failed_groups))}",
    ]
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    for line in lines:
        print(f"OUTPUT: {line}")


def main_inprocess(
    *,
    is_main: bool,
    force_overall: bool,
    changed_files: list[str] | None,
    base: str = "",
    previous_group_failures: str = "",
    boom: bool = False,
) -> int:
    """Core planner flow, parameterized for unit tests (issue #470).

    `boom=True` forces the fail-safe path so tests can prove the planner
    never emits an empty/skipped matrix on internal errors.
    """
    failed_groups = [g.strip() for g in previous_group_failures.split(",") if g.strip()]

    try:
        if boom:
            raise RuntimeError("injected failure for fail-safe test")
        if is_main or force_overall:
            plan = {
                "mode": "full",
                "reason": "main-branch-or-forced-overall",
                "groups": set(ALL_GROUP_KEYS),
            }
        else:
            changed = (
                [normalize(f) for f in changed_files or []]
                if changed_files is not None
                else get_git_diff_files(base)
            )
            plan = classify(changed)
        plan = apply_previous_group_failures(plan, failed_groups)
    except Exception as exc:  # noqa: BLE001 — planner must never break the matrix
        print(f"Planner error ({exc!r}) — fail-safe FULL matrix.", file=sys.stderr)
        plan = {
            "mode": "full",
            "reason": f"failsafe:{type(exc).__name__}",
            "groups": set(ALL_GROUP_KEYS),
        }

    group_keys = sorted(plan["groups"])
    if not group_keys:  # defensive: never emit an empty matrix
        group_keys = list(ALL_GROUP_KEYS)
        plan["groups"] = set(group_keys)

    # #471: compute per-group coverage cache keys. Any failure → empty keys
    # (fail-safe: jobs ignore the cache, CI behaves exactly like pre-#471).
    cache_keys: dict[str, str] = {}
    try:
        script_dir = str(Path(__file__).resolve().parent)
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        from coverage_cache_keys import compute_all_group_keys  # noqa: PLC0415

        cache_keys = compute_all_group_keys()
    except Exception as exc:  # noqa: BLE001 — cache is an optimization, never a gate
        print(
            f"Coverage cache key computation failed ({exc!r}) — "
            "continuing WITHOUT cache (fail-safe).",
            file=sys.stderr,
        )

    # force_run contract (module docstring): full mode always runs pytest;
    # scoped mode consumes the cache except for previous-failure forced
    # groups, which must re-run to prove their fix.
    if plan["mode"] == "scoped":
        force_run_groups = set(failed_groups) & set(group_keys)
    else:
        force_run_groups = set(group_keys)
    matrix_json = build_matrix_json(group_keys, cache_keys, force_run_groups)

    print(f"Plan: mode={plan['mode']} reason={plan['reason']} groups={group_keys}")
    emit_outputs(plan, matrix_json, failed_groups, cache_keys)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan backend test matrix groups (issue #470)."
    )
    parser.add_argument("--base", default="", help="Base SHA/ref for git diff")
    parser.add_argument(
        "--is-main", action="store_true", help="Running on main (always full)"
    )
    parser.add_argument(
        "--force-overall",
        action="store_true",
        help="workflow_dispatch run_backend_overall (always full)",
    )
    parser.add_argument(
        "--previous-group-failures",
        default="",
        help="Comma-separated group keys with recent failures (fast,core_unit,…)",
    )
    parser.add_argument(
        "--changed-files",
        nargs="*",
        default=None,
        help="Explicit changed-file list (overrides git diff; testing/dry-run)",
    )
    args = parser.parse_args()
    return main_inprocess(
        is_main=args.is_main,
        force_overall=args.force_overall,
        changed_files=args.changed_files,
        base=args.base,
        previous_group_failures=args.previous_group_failures,
    )


if __name__ == "__main__":
    sys.exit(main())
