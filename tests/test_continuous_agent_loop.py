"""Tests for continuous_agent_loop.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.agents.continuous_agent_loop import has_open_issues, run_audit


class TestHasOpenIssues:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_true_when_issues_exist(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"number": 1}]')
        assert has_open_issues() is True

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_false_when_no_issues(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert has_open_issues() is False

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_returns_false_on_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")

    # ── #2928: type:ledger চির-open ড্যাশবোর্ড বাদ — নইলে smart-fallback মৃত-কোড ──

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_ledger_only_issues_mean_no_work_issues(self, mock_run):
        """PRIORITY-QUEUE-LEDGER-এর মতো ড্যাশবোর্ড open থাকলেও fallback চলবে।"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"labels": [{"name": "type:ledger"}]},
                {"labels": [{"name": "P0-critical"}, {"name": "type:ledger"}]},
            ]),
        )
        assert has_open_issues() is False

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_mixed_ledger_and_work_issues_mean_work_exists(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"labels": [{"name": "type:ledger"}]},
                {"labels": [{"name": "P1-high"}]},
            ]),
        )
        assert has_open_issues() is True

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_unparsable_output_falls_back_to_bool(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not-json")
        assert has_open_issues() is True


class TestRunAudit:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_runs_audit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        run_audit()
        assert mock_run.called


# ═══════════════════════════════════════════════════════════════════════
# #2745 — Admin-Approval Gate (সংবেদনশীল ইস্যুতে অ্যাডমিন-অনুমোদন বাধ্যতামূলক)
# ═══════════════════════════════════════════════════════════════════════

from scripts.agents.continuous_agent_loop import (
    _AWAITING_MARKER,
    admin_approval_gate,
)


def _issue_view_payload(labels, comments=None):
    import json as _json

    return _json.dumps({
        "labels": [{"name": l} for l in labels],
        "comments": comments or [],
    })


class TestAdminApprovalGate:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_ungated_issue_passes(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_issue_view_payload(["P1-high"]))
        allowed, reason = admin_approval_gate(100)
        assert allowed is True
        assert reason == ""

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gated_without_approval_blocks_and_notifies_once(self, mock_run):
        """গেটেড ইস্যু ব্লক হবে + প্রথমবার মার্কার-কমেন্ট (নোটিফিকেশন) যাবে।"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=_issue_view_payload(["gate:admin-approval"])
        )
        allowed, reason = admin_approval_gate(101)
        assert allowed is False
        assert "gate:admin-approval" in reason
        # নোটিফিকেশন-কমেন্ট পোস্ট হয়েছে — run() একটি লিস্ট-আর্গিউমেন্ট নেয়
        commented = any(
            c.args
            and isinstance(c.args[0], list)
            and c.args[0][:3] == ["gh", "issue", "comment"]
            for c in mock_run.call_args_list
        )
        assert commented

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gated_with_dedup_marker_does_not_renotify(self, mock_run):
        """আগেই নোটিফাই হয়ে থাকলে আর কমেন্ট যাবে না (dedup)।"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_issue_view_payload(
                ["gate:admin-approval"],
                comments=[{"body": f"{_AWAITING_MARKER}\nalready notified"}],
            ),
        )
        allowed, _ = admin_approval_gate(102)
        assert allowed is False
        # শুধু view-কল — comment-কল নেই
        assert all("comment" not in (c.args[3] if len(c.args) > 3 else "") for c in mock_run.call_args_list)

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gated_with_approved_label_releases(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=_issue_view_payload(["gate:admin-approval", "approved-by:admin"]),
        )
        allowed, reason = admin_approval_gate(103)
        assert allowed is True
        assert "admin-approved" in reason

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_gh_failure_fail_closed(self, mock_run):
        """gh-ব্যর্থতায় fail-closed — অনুমোদন-বাইপাসের অজুহাত নয়।"""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        allowed, reason = admin_approval_gate(104)
        assert allowed is False
        assert "fail-closed" in reason


# ═══════════════════════════════════════════════════════════════════════
# Issue #2944 — acquire_next_issue, claim_issue, get_effective_role
# ═══════════════════════════════════════════════════════════════════════

from scripts.agents.continuous_agent_loop import (
    acquire_next_issue,
    claim_issue,
    get_effective_role,
)


class TestAcquireNextIssue:
    @patch("scripts.agents.continuous_agent_loop.run")
    def test_acquire_next_issue_json_format_passed_and_parsed(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"issue": 2902, "role": "coder", "branch_name": "coder-2-2902"}',
        )
        task = acquire_next_issue("coder", "coder-1")
        assert task is not None
        assert task["issue"] == 2902
        assert task["branch_name"] == "coder-2-2902"
        # Check that --format json was passed
        cmd = mock_run.call_args[0][0]
        assert "--format" in cmd
        idx = cmd.index("--format")
        assert cmd[idx + 1] == "json"

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_acquire_next_issue_mixed_stdout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Notice: slot fetched\n{"issue": 2944, "role": "coder"}\nEnd of line',
        )
        task = acquire_next_issue("coder", "coder-1")
        assert task is not None
        assert task["issue"] == 2944

    @patch("scripts.agents.continuous_agent_loop.run")
    def test_acquire_next_issue_text_regex_fallback(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "⚡ [Autonomous Queue Resolver] Next priority issue: #2902 (feat...)\n"
                "🎯 Assigned Role: coder\n"
                "🌿 Acquired Slot: coder-2-2902-p0-group\n"
            ),
        )
        task = acquire_next_issue("coder", "coder-1")
        assert task is not None
        assert task["issue"] == 2902
        assert task["branch_name"] == "coder-2-2902-p0-group"


class TestClaimIssue:
    @patch("scripts.agents.continuous_agent_loop.run")
    @patch("sys.platform", "win32")
    def test_claim_issue_uses_bash_on_win32(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success = claim_issue(2944, "coder-1")
        assert success is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "bash"
        assert "./scripts/ci/atomic_claim.sh" in cmd[1]


class TestGetEffectiveRole:
    @patch("scripts.agents.smart_dispatcher.SmartDispatcher._should_switch_role")
    def test_get_effective_role_switches_when_needed(self, mock_switch):
        mock_switch.return_value = ("ci-fixer", "CI RED on main")
        role = get_effective_role("coder")
        assert role == "ci-fixer"

    @patch("scripts.agents.smart_dispatcher.SmartDispatcher._should_switch_role")
    def test_get_effective_role_keeps_role_when_healthy(self, mock_switch):
        mock_switch.return_value = ("coder", "")
        role = get_effective_role("coder")
        assert role == "coder"

