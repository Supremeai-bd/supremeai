"""Auto-approval must never fire on a pending or red check.

`ai_auto_approver._checks_green` is the gate that decides whether a bot merges
without a human. Three fail-open shapes matter and each is pinned here:

  * an empty rollup (nothing ran) — not green;
  * a check with no conclusion yet (still running) — not green;
  * an ordinary failure — not green.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import ai_auto_approver as approver  # noqa: E402


def _pr(*checks):
    return {"statusCheckRollup": list(checks)}


def test_green_rollup_is_green():
    assert approver._checks_green(_pr({"conclusion": "SUCCESS"}, {"conclusion": "SKIPPED"}))


def test_empty_rollup_is_not_green():
    assert not approver._checks_green(_pr())


def test_pending_check_is_not_green():
    assert not approver._checks_green(_pr({"conclusion": "SUCCESS"}, {"conclusion": None}))


def test_failure_blocks_approval():
    assert not approver._checks_green(_pr({"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}))
    assert not approver._checks_green(_pr({"conclusion": "CANCELLED"}))


def test_neutral_and_skipped_are_accepted_but_timed_out_is_not():
    assert approver._checks_green(_pr({"conclusion": "NEUTRAL"}))
    assert not approver._checks_green(_pr({"conclusion": "TIMED_OUT"}))
