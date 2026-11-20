"""The guard roster must be *executed* by CI, not merely maintained.

Why this file exists
--------------------
`scripts/ci/run_all_guards.py` documents its purpose as "the same list CI runs in
Tier 1/2". On 2026-11-20 that was false: ``grep -rn run_all_guards .github/``
returned zero hits. Fifty-six guards were written, reviewed, listed — and never
run. Every one of them passed locally and gated nothing.

That is a specific, repeatable failure mode: an artifact that looks like a gate
(a name containing "guard", a roster entry, a Makefile target) while the wiring
that would make it a gate is absent. It is invisible in review because reviewers
read the guard, not the workflow.

These tests pin the wiring. They fail if somebody removes the CI step, renames
the script, or adds a lane that nothing invokes.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ROSTER = REPO_ROOT / "scripts/ci/run_all_guards.py"
WORKFLOWS = REPO_ROOT / ".github/workflows"


def _workflow_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted(WORKFLOWS.glob("*.yml"))
    )


def _roster_source() -> str:
    return ROSTER.read_text(encoding="utf-8")


def test_roster_exists_and_defines_guards():
    assert ROSTER.exists(), "the guard roster was deleted or moved"
    assert "GUARDS" in _roster_source(), "roster no longer defines GUARDS"


def test_some_workflow_actually_invokes_the_roster():
    """The regression this file was written for.

    A roster that no workflow calls is documentation. This assertion is the only
    thing standing between "74 guards" and "74 files".
    """
    text = _workflow_text()
    assert "run_all_guards.py" in text, (
        "No workflow invokes scripts/ci/run_all_guards.py — the roster is "
        "documentation again, not a gate. Wire it into unified-pipeline.yml "
        "(fast lane) and ops-maintenance.yml (full lane)."
    )


def test_fast_lane_runs_on_pull_requests():
    """The PR lane must exist, or the roster only runs after a merge."""
    unified = (WORKFLOWS / "unified-pipeline.yml").read_text(encoding="utf-8")
    assert "run_all_guards.py --fast" in unified, (
        "unified-pipeline.yml no longer runs the fast roster lane on PRs"
    )


def test_full_lane_runs_on_schedule():
    """Whole-tree guards (CVE scans, fleet probes) belong to the nightly lane."""
    ops = (WORKFLOWS / "ops-maintenance.yml").read_text(encoding="utf-8")
    assert "run_all_guards.py --full" in ops, (
        "ops-maintenance.yml no longer runs the full roster lane nightly"
    )


def test_every_roster_entry_points_at_a_real_file():
    """A roster entry naming a deleted script fails the whole lane."""
    source = _roster_source()
    referenced = set(re.findall(r'"(scripts/[a-zA-Z0-9_/]+\.py)"', source))
    assert referenced, "could not parse any script paths out of the roster"
    missing = sorted(r for r in referenced if not (REPO_ROOT / r).exists())
    assert not missing, f"roster references scripts that do not exist: {missing}"


def test_fast_lane_is_a_strict_subset_and_non_empty():
    """Fast must never be everything; otherwise the split is decorative."""
    out = subprocess.run(
        [sys.executable, str(ROSTER), "--list"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert out.returncode == 0, out.stderr[-500:]
    full = [ln for ln in out.stdout.splitlines() if ln.strip()]

    fast = subprocess.run(
        [sys.executable, str(ROSTER), "--list", "--fast"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert fast.returncode == 0, fast.stderr[-500:]
    fast_lines = [ln for ln in fast.stdout.splitlines() if ln.strip()]

    assert fast_lines, "fast lane selected no guards"
    assert len(fast_lines) < len(full), (
        "fast lane equals the full roster; the --fast split does nothing"
    )
    assert set(fast_lines).issubset(set(full)), "fast lane invented entries"


@pytest.mark.parametrize(
    "flag,should_be_fast",
    [
        ("--self-test", True),
        ("--check", True),
        ("--check-required-names", True),
        ("--from-strict", True),
    ],
)
def test_cheap_checks_are_classified_fast(flag: str, should_be_fast: bool):
    """Classification is by flag, so a new cheap guard is picked up for free."""
    tree = ast.parse(_roster_source())
    fast_suffixes = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "FAST_SUFFIXES":
                    fast_suffixes = ast.literal_eval(node.value)
    assert fast_suffixes is not None, "FAST_SUFFIXES is gone"
    assert (flag in fast_suffixes) is should_be_fast


def test_roster_reports_which_guards_failed():
    """`N failed` with no names makes a 20-minute log unusable."""
    source = _roster_source()
    assert "FAILED:" in source, (
        "the roster no longer prints the names of failing guards; a CI log that "
        "says only '1 failed' forces the reader to grep thousands of lines"
    )
