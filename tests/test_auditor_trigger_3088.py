# বাংলা মন্তব্য: #3088 §6 — claimable-count + auditor-trigger চুক্তি টেস্ট।
"""agent_claimable_issue_count + auditor_evaluation_eligibility (#3088 §6)।"""
import json
from unittest.mock import MagicMock, patch

from scripts.agents.continuous_agent_loop import (
    agent_claimable_issue_count,
    auditor_evaluation_eligibility,
    build_task_contract,
    has_unclaimed_work_issues,
)


def _labels(*names):
    return [{"name": n} for n in names]


class TestClaimableCount:
    """#3088 §6: claimable গণনা + blocking-reason বিভাজন (queue-health)।"""

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_counts_only_claimable(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([
            {"number": 1, "labels": _labels("status:in-progress", "group:pipeline")},
            {"number": 2, "labels": _labels("has-pr")},
            {"number": 3, "labels": _labels("type:ledger")},
            {"number": 4, "labels": _labels("template:violating")},
            {"number": 5, "labels": _labels("gate:admin-approval")},
            {"number": 6, "labels": _labels("gate:admin-approval", "approved-by:admin")},  # অনুমোদিত → claimable
            {"number": 7, "labels": _labels("P1-high")},  # ফাঁকা-claimable
        ]))
        count, reasons = agent_claimable_issue_count()
        assert count == 2  # #6 (approved-gated) + #7 (plain)
        assert reasons == {"in_progress": 1, "has_pr": 1, "ledger": 1,
                           "template_violating": 1, "admin_gated": 1}

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_lookup_failure_fail_open_zero(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        count, reasons = agent_claimable_issue_count()
        assert count == 0 and reasons == {"lookup_failed": 1}

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_has_unclaimed_wrapper_unchanged(self, mock_run):
        # বাংলা মন্তব্য: legacy-wrapper চুক্তি — আগের 64-টেস্টের আচরণ হুবহু।
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(
            [{"number": 1, "labels": _labels("P0-critical")}]))
        assert has_unclaimed_work_issues() is True
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(
            [{"number": 1, "labels": _labels("status:in-progress")}]))
        assert has_unclaimed_work_issues() is False


class TestAuditorEligibility:
    """#3088 §6: claimable==0 → controlled auditor evaluation (anti-storm)।"""

    @patch("scripts.agents.continuous_agent_loop.agent_claimable_issue_count")
    def test_not_eligible_when_claimable_work_exists(self, mock_count):
        mock_count.return_value = (3, {"in_progress": 2})
        verdict = auditor_evaluation_eligibility()
        assert verdict["eligible"] is False
        assert verdict["reason"] == "claimable_work_exists" and verdict["claimable"] == 3

    @patch("scripts.agents.continuous_agent_loop._should_run_task", return_value=False)
    @patch("scripts.agents.continuous_agent_loop.agent_claimable_issue_count")
    def test_cooldown_blocks_storm(self, mock_count, mock_should):
        # বাংলা মন্তব্য: anti-storm — cooldown-উইন্ডোর ভিতরে পুনরায় audit নয়।
        mock_count.return_value = (0, {"in_progress": 5})
        verdict = auditor_evaluation_eligibility()
        assert verdict["eligible"] is False and verdict["reason"] == "audit_cooldown_active"

    @patch("scripts.agents.continuous_agent_loop._should_run_task", return_value=True)
    @patch("scripts.agents.continuous_agent_loop._mark_task_run")
    @patch("scripts.agents.continuous_agent_loop.agent_claimable_issue_count")
    def test_eligible_on_empty_queue(self, mock_count, mock_mark, mock_should):
        mock_count.return_value = (0, {"in_progress": 4, "has_pr": 2})
        verdict = auditor_evaluation_eligibility()
        assert verdict["eligible"] is True and verdict["reason"] == "queue_empty"
        assert "ACTIONABLE_FINDINGS" in verdict["verdict_hint"]
        mock_mark.assert_called_once_with("auditor_evaluation")  # cooldown-রেকর্ড

    @patch("scripts.agents.continuous_agent_loop._should_run_task", return_value=True)
    @patch("scripts.agents.continuous_agent_loop._mark_task_run")
    @patch("scripts.agents.continuous_agent_loop.agent_claimable_issue_count")
    def test_all_admin_gated_blocks_new_issues(self, mock_count, mock_mark, mock_should):
        # বাংলা মন্তব্য: সব-ইস্যু admin-gated → BLOCKED_BY_ADMIN — নতুন issue নয়,
        # বিদ্যমান Admin Decision ইস্যুর আপডেট (infinite-generator নয়)।
        mock_count.return_value = (0, {"admin_gated": 3})
        verdict = auditor_evaluation_eligibility()
        assert verdict["eligible"] is True and verdict["reason"] == "blocked_by_admin"
        assert "BLOCKED_BY_ADMIN" in verdict["verdict_hint"]


class TestCanonicalEnvelopeInLoopContract:
    """#3088 §1/§8: loop-চুক্তিতে canonical envelope + hash যুক্ত হয়েছে।"""

    def test_contract_carries_canonical_block(self):
        task = {
            "issue": 3088,
            "title": "feat(governance): standardize task templates",
            "labels": ["group:governance", "P1-high", "seq:2"],
        }
        contract = build_task_contract("supremeai-coder-1-bot", "coder", task, "coder-1-3088-x")
        assert "task_contract" in contract
        canonical = contract["task_contract"]
        assert canonical["group"] == "governance"
        assert canonical["priority"] == "P1"
        assert canonical["sequence"] == 2
        assert canonical["task_type"] == "IMPLEMENT"
        assert canonical["task_id"] == "task-issue-3088"
        assert "standard_output_steps" in canonical
        # provenance-ভিত্তি (#3088 §5)
        assert contract["task_contract_hash"]
        assert contract["instruction_envelope"].startswith("SUPREMEAI TASK CONTRACT")
        # legacy ফিল্ড অক্ষত (backward-compat)
        assert contract["agent"]["name"] == "supremeai-coder-1-bot"
        assert contract["role"] == "coder"
        assert "on_complete" in contract

    def test_contract_envelope_admin_gated(self):
        task = {
            "issue": 9, "title": "chore(security): rotate keys",
            "labels": ["group:security", "gate:admin-approval", "P1-high"],
        }
        contract = build_task_contract("agent-x", "coder", task, "b")
        gate = contract["task_contract"]["admin_gate"]
        assert gate["required"] is True and gate["status"] == "WAITING"


class TestRoleRulesFallbackAliases:
    """#3095-রির্স্ট্রাকচার-পরবর্তী আবিষ্কার: প্রতিটি রোল মেশিন-রুল পায় (নীরব শূন্য নয়)।"""

    def test_every_live_role_gets_rules(self):
        # বাংলা মন্তব্য: ci-fixer আগে ci_devops কী-মিসে ০-রুল পাচ্ছিল —
        # এখন কী-অ্যালায়াস-চেইন প্রতিটি পরিচিত রোলে অ-শূন্য রুল নিশ্চিত করে।
        from scripts.agents.continuous_agent_loop import _load_agent_rules
        for role in ("coder", "ci-fixer", "auditor", "planner", "pr-helper",
                     "watcher", "human-eyes", "breaker", "platform"):
            applicable, prohibited = _load_agent_rules(role)
            assert applicable or prohibited, f"role {role} got zero machine rules"
