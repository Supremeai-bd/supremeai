"""Retiring the `scripts/ops/` mirror twins (scripts/ci/retire_ops_mirrors.py).

WHY THIS EXISTS
---------------
`scripts/ops/` was a reorganisation that never finished, leaving 107 same-path
`scripts/` ↔ `scripts/ops/` pairs that had DRIFTED: two files that both look
authoritative and disagree. An agent reading one while CI runs the other burns a
full context window and still answers wrong.

The tool that retires them decides *which copy is live* from evidence, and the
cost of getting that wrong is deleting the wired-up file. So these tests are
about the decision rules, not the file I/O:

* never delete a file that has no twin (the ops-only cohort is the real
  reorganisation and must survive),
* never delete a copy that is still referenced,
* treat reference matching as path-exact (``scripts/x.py`` must not be considered
  referenced by a mention of ``scripts/ops/x.py``),
* default to dry-run semantics — `plan()` must not touch the tree.

The synthetic tree mirrors the real repo's shape exactly: 173 CI references to
`scripts/...` versus 16 to `scripts/ops/...`, every one of which is an ops-only
file, which is what makes "root wins for genuine twins" a measured rule rather
than a preference.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import retire_ops_mirrors as rom  # noqa: E402


def _build_tree(tmp: Path) -> Path:
    (tmp / ".github" / "workflows").mkdir(parents=True)
    (tmp / "scripts" / "ci").mkdir(parents=True)
    (tmp / "scripts" / "ops" / "sub").mkdir(parents=True)
    (tmp / "scripts" / "sub").mkdir(parents=True)
    (tmp / "Makefile").write_text("gates:\n\tpython scripts/ci/x.py\n", encoding="utf-8")
    (tmp / "scripts" / "ci" / "x.py").write_text("x\n", encoding="utf-8")
    (tmp / "scripts" / "ci" / "run_all_guards.py").write_text(
        '["python", "scripts/sub/wired.py"]\n["python", "scripts/ops/sub/opswired.py"]\n',
        encoding="utf-8",
    )
    return tmp


def test_self_test_passes() -> None:
    """The tool ships its own end-to-end assertions; run them."""
    assert rom.self_test() == 0


def test_plan_is_pure_and_never_deletes(tmp_path: Path) -> None:
    root = _build_tree(tmp_path)
    (root / "scripts" / "sub" / "a.py").write_text("A\n", encoding="utf-8")
    (root / "scripts" / "ops" / "sub" / "a.py").write_text("A-drift\n", encoding="utf-8")

    data = rom.plan(root)

    assert "scripts/ops/sub/a.py" in data["delete"]
    # Nothing on disk changed: planning is not applying.
    assert (root / "scripts" / "ops" / "sub" / "a.py").is_file()
    assert (root / "scripts" / "sub" / "a.py").is_file()


def test_ops_only_files_are_never_deleted(tmp_path: Path) -> None:
    """The 91 ops-only scripts are the real reorganisation cohort."""
    root = _build_tree(tmp_path)
    (root / "scripts" / "ops" / "sub" / "solo.py").write_text("S\n", encoding="utf-8")

    data = rom.plan(root)

    assert "scripts/ops/sub/solo.py" not in data["delete"]
    assert "scripts/ops/sub/solo.py" in data["ops_only"]


def test_referenced_copy_is_the_survivor(tmp_path: Path) -> None:
    root = _build_tree(tmp_path)
    (root / "scripts" / "sub" / "wired.py").write_text("W\n", encoding="utf-8")
    (root / "scripts" / "ops" / "sub" / "wired.py").write_text("W-old\n", encoding="utf-8")

    data = rom.plan(root)

    assert "scripts/ops/sub/wired.py" in data["delete"]
    assert "scripts/sub/wired.py" not in data["delete"]


def test_ops_side_can_win_when_it_is_the_wired_one(tmp_path: Path) -> None:
    root = _build_tree(tmp_path)
    (root / "scripts" / "sub" / "opswired.py").write_text("O-old\n", encoding="utf-8")
    (root / "scripts" / "ops" / "sub" / "opswired.py").write_text("O\n", encoding="utf-8")

    data = rom.plan(root)

    assert "scripts/sub/opswired.py" in data["delete"]
    assert "scripts/ops/sub/opswired.py" not in data["delete"]


def test_reference_matching_is_path_exact() -> None:
    """The bug class: a substring match would treat ops/x.py as wired by scripts/x.py."""
    assert rom.is_referenced("python scripts/x.py", "scripts/x.py")
    assert not rom.is_referenced("python scripts/x.py", "scripts/ops/x.py")
    assert rom.is_referenced("python scripts/ops/x.py", "scripts/ops/x.py")
    # A longer sibling must not satisfy a shorter path either.
    assert not rom.is_referenced("python scripts/x_extra.py", "scripts/x.py")


def test_ambiguous_pair_is_skipped_not_guessed(tmp_path: Path) -> None:
    """If BOTH copies are wired, a human must decide — never auto-delete."""
    root = _build_tree(tmp_path)
    (root / "scripts" / "ci" / "run_all_guards.py").write_text(
        '["python", "scripts/sub/both.py"]\n["python", "scripts/ops/sub/both.py"]\n',
        encoding="utf-8",
    )
    (root / "scripts" / "sub" / "both.py").write_text("B\n", encoding="utf-8")
    (root / "scripts" / "ops" / "sub" / "both.py").write_text("B2\n", encoding="utf-8")

    data = rom.plan(root)

    assert "scripts/sub/both.py" not in data["delete"]
    assert "scripts/ops/sub/both.py" not in data["delete"]
    assert any("both.py" in item["ops"] for item in data["skipped"])


def test_apply_removes_only_the_planned_losers(tmp_path: Path) -> None:
    root = _build_tree(tmp_path)
    (root / "scripts" / "sub" / "a.py").write_text("A\n", encoding="utf-8")
    (root / "scripts" / "ops" / "sub" / "a.py").write_text("A2\n", encoding="utf-8")
    (root / "scripts" / "ops" / "sub" / "solo.py").write_text("S\n", encoding="utf-8")

    data = rom.plan(root)
    removed = rom.apply_plan(root, data)

    assert removed == 1
    assert not (root / "scripts" / "ops" / "sub" / "a.py").exists()
    assert (root / "scripts" / "sub" / "a.py").is_file()
    assert (root / "scripts" / "ops" / "sub" / "solo.py").is_file()


# ── the live repo ────────────────────────────────────────────────────────────
def test_live_repo_has_no_drifted_same_path_twins() -> None:
    """Ratchet: the 107 deleted pairs must not come back.

    This is the reason the repo shipped a report-only guard for months while 107
    drifts sat ignored. The check is now fail-closed in the test suite.
    """
    data = rom.plan(REPO_ROOT)
    regrown = [pair for pair in data["pairs"] if pair["ops"].startswith("scripts/ops/")]
    # Files may legitimately be re-added WITH their ops twin absent; what must not
    # happen is a same-relative-path pair reappearing under scripts/ops/.
    drifted_twins = [
        pair for pair in regrown
        if (REPO_ROOT / pair["root"]).is_file() and (REPO_ROOT / pair["ops"]).is_file()
    ]
    assert drifted_twins == [], (
        "same-path scripts/ ↔ scripts/ops/ twins reappeared; retire them with "
        f"scripts/ci/retire_ops_mirrors.py: {drifted_twins[:5]}"
    )


def test_live_repo_mirror_guard_reports_zero_drift() -> None:
    """Independent confirmation via the repo's own guard."""
    proc = subprocess.run(
        [sys.executable, "scripts/ci/mirror_drift_guard.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    last = [ln for ln in proc.stdout.splitlines() if "Total mirror groups" in ln]
    assert last, proc.stdout[-500:]
    groups = int(last[-1].split("groups:")[1].split(",")[0])
    drifted = int(last[-1].split("drifted:")[1].strip())
    assert drifted <= 10, (
        f"{drifted} drifted groups remain (expected <=10 cross-directory, none "
        "same-path). Baseline after the 2026-11-20 cleanup was 10."
    )
    assert groups < 120, f"{groups} mirror groups — the cleanup regressed"
