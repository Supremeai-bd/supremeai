"""Tests for continuous_agent_loop.py."""

from __future__ import annotations

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
        assert has_open_issues() is False


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
