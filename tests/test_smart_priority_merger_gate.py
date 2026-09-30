"""Tests for scripts/ci/smart_priority_merger.py — required-gates merge contract (#2571).

বাংলা মন্তব্য: merge-before-gates regression guard — গেট ফাঁকি দিয়ে merge হওয়া
যাবে না: zero-check, skipped, pending, missing — কোনোটাই ready নয়।
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_MERGER = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "smart_priority_merger.py"
_spec = importlib.util.spec_from_file_location("smart_priority_merger", _MERGER)
spm = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("smart_priority_merger", spm)
_spec.loader.exec_module(spm)

evaluate_pr_checks = spm.evaluate_pr_checks

# বাংলা মন্তব্য: pr.yml-এর বাস্তব job নাম — merger-এর _DEFAULT_REQUIRED_CHECKS-এর সঙ্গে হুবহু মেলে।
GATE = "🚦 Unified PR Gate (Security, Scope & Policy Orchestrator)"
TESTS = "🧪 Test & Build Verification"
CONSTITUTION = "🛡️ Constitutional System Gates"
CONTEXT = "🔍 Resolve PR Context"
BRANCH = "Branch Naming Guard"

EVIDENCE_BODY = (
    "## সারসংক্ষেপ\nকিছু পরিবর্তন।\n\n"
    "## Test Evidence\n"
    "pytest tests/ -q → 12 passed in 0.5s; সব গেট লোকালি সবুজ, কোনো skip নেই।"
)


def _all_success_rollup() -> list[dict]:
    return [
        {"name": GATE, "conclusion": "SUCCESS"},
        {"name": TESTS, "conclusion": "SUCCESS"},
        {"name": CONSTITUTION, "conclusion": "SUCCESS"},
        {"name": CONTEXT, "conclusion": "SUCCESS"},
        {"name": BRANCH, "conclusion": "SUCCESS"},
    ]


def _pr(**over) -> dict:
    base = {
        "number": 1,
        "title": "test pr",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "labels": [],
        "body": EVIDENCE_BODY,
        "statusCheckRollup": _all_success_rollup(),
    }
    base.update(over)
    return base


class TestRequiredGatesContract:
    def test_all_gates_success_is_ready(self):
        # বাংলা মন্তব্য: সব required gate SUCCESS → কেবল তখনই ready।
        summary, ready, held, _, reasons = evaluate_pr_checks(_pr())
        assert ready is True
        assert summary == "GREEN"
        assert reasons == []
        assert held is False

    def test_zero_check_rollup_is_blocked(self):
        # বাংলা মন্তব্য: #2571 মূল ফাঁক — zero check = "NO_CHECKS" সত্ত্বেও ready হয়ে যেত।
        summary, ready, _, _, reasons = evaluate_pr_checks(_pr(statusCheckRollup=[]))
        assert ready is False
        assert summary == "NO_CHECKS"
        assert any("NO_CHECKS" in r for r in reasons)

    def test_skipped_required_gate_is_blocked(self):
        # বাংলা মন্তব্য: SKIPPED আগে নীরবে green ধরা হতো — এখন non-green।
        rollup = _all_success_rollup()
        rollup[1]["conclusion"] = "SKIPPED"  # Test & Build skipped
        summary, ready, _, _, reasons = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is False
        assert any("Required gates not all-passed" in r for r in reasons)
        assert "Test & Build Verification" in " ".join(reasons)

    def test_missing_required_gate_is_blocked(self):
        # বাংলা মন্তব্য: required gate রোলআপেই নেই → non-green।
        rollup = [c for c in _all_success_rollup() if c["name"] != CONSTITUTION]
        _, ready, _, _, reasons = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is False
        assert any("Required gates not all-passed" in r for r in reasons)

    def test_failing_gate_is_blocked(self):
        rollup = _all_success_rollup()
        rollup[0]["conclusion"] = "FAILURE"
        _, ready, _, _, reasons = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is False
        assert any("CI Failing" in r for r in reasons)

    def test_pending_gate_is_blocked(self):
        rollup = _all_success_rollup()
        rollup[2]["conclusion"] = "IN_PROGRESS"
        _, ready, _, _, _ = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is False

    def test_queue_hold_blocks_by_default(self):
        _, ready, held, _, _ = evaluate_pr_checks(_pr(labels=[{"name": "queue:hold"}]))
        assert held is True
        assert ready is False

    def test_optional_skipped_check_still_blocked_when_required_missing(self):
        # বাংলা মন্তব্য: non-required check skipped হলে সেটি নিজে বাধা নয়,
        # কিন্তু required সেট ছাড়া ready হয় না — এখানে has-pr labeler skip করা।
        rollup = _all_success_rollup() + [{"name": "🏷️ Auto-add has-pr to linked issues", "conclusion": "SKIPPED"}]
        summary, ready, _, _, _ = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is True  # required সব SUCCESS; optional skip নিরীহ
        assert summary == "GREEN"

    def test_env_override_off_disables_required_contract(self, monkeypatch):
        # বাংলা মন্তব্য: Admin escape hatch — MERGE_TRAIN_REQUIRED_CHECKS=off।
        monkeypatch.setenv("MERGE_TRAIN_REQUIRED_CHECKS", "off")
        rollup = _all_success_rollup()
        rollup[1]["conclusion"] = "SKIPPED"
        _, ready, _, _, _ = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is True  # স্পষ্ট off-এ skipped আর বাধা নয় (ডকুমেন্টেড আচরণ)

    def test_env_override_custom_list(self, monkeypatch):
        # বাংলা মন্তব্য: env দিয়ে কাস্টম required তালিকা সেট করা যায়। বিভাজক `|` —
        # গেটের নামে নিজেই কমা থাকে, তাই কমা-বিভাজন নাম ভাঙত।
        monkeypatch.setenv("MERGE_TRAIN_REQUIRED_CHECKS", f"{GATE}|{TESTS}")
        rollup = [
            {"name": GATE, "conclusion": "SUCCESS"},
            {"name": TESTS, "conclusion": "SUCCESS"},
            {"name": "🛡️ Constitutional System Gates", "conclusion": "SKIPPED"},
        ]
        _, ready, _, _, _ = evaluate_pr_checks(_pr(statusCheckRollup=rollup))
        assert ready is True  # তালিকার বাইরের gate আর required নয়

    def test_evidence_missing_blocks(self):
        # বাংলা মন্তব্য: Verification Gate — Test Evidence ছাড়া merge নয় (অপরিবর্তিত নীতি)।
        _, ready, _, _, reasons = evaluate_pr_checks(_pr(body="no evidence here"))
        assert ready is False
        assert any("Evidence" in r for r in reasons)

    def test_draft_blocks(self):
        _, ready, _, _, _ = evaluate_pr_checks(_pr(isDraft=True))
        assert ready is False


@pytest.mark.parametrize("value", ["off", "none", "disabled"])
def test_env_override_values(value, monkeypatch):
    monkeypatch.setenv("MERGE_TRAIN_REQUIRED_CHECKS", value)
    assert spm._required_check_names() == []
