"""Tests for scripts/agents/create_blocker_issue.py.

Verifies:
1. Formatting of blocker issue body and parent cross-reference comments.
2. Label assignment (type:blocker, status:unclaimed, handoff:<role>).
3. Dry run simulation and real CLI subprocess mocking.
4. CLI interaction (text and json output).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.agents.create_blocker_issue import (
    create_blocker_issue,
    format_blocker_body,
    format_parent_comment,
    main,
)


class TestFormatters:
    def test_format_blocker_body(self):
        body = format_blocker_body(
            parent_issue=1690,
            description="Tenant isolation middleware missing in endpoint",
            role="platform",
        )
        assert "#1690" in body
        assert "Tenant isolation middleware missing" in body
        assert "`platform`" in body
        assert "**Blocks:** #1690" in body

    def test_format_parent_comment(self):
        comment = format_parent_comment(
            new_issue_number=1799,
            title="fix(api): Missing tenant check",
            role="coder",
        )
        assert "#1799" in comment
        assert "fix(api): Missing tenant check" in comment
        assert "`coder`" in comment


class TestCreateBlockerIssue:
    def test_dry_run_simulation(self):
        result = create_blocker_issue(
            parent_issue=1690,
            title="fix(core): Missing lock",
            body="Deadlock occurs under load",
            role="coder",
            dry_run=True,
        )
        assert result.success is True
        assert result.is_dry_run is True
        assert result.new_issue_number == 9999
        assert "type:blocker" in result.labels
        assert "status:unclaimed" in result.labels
        assert "handoff:coder" in result.labels

    @patch("subprocess.run")
    def test_execute_issue_creation_success(self, mock_subproc):
        # 1st call for gh issue create -> returns URL
        # 2nd call for gh issue comment -> returns 0
        mock_create = MagicMock(returncode=0, stdout="https://github.com/SaifulHaqueNiloy/supremeai/issues/1795\n")
        mock_comment = MagicMock(returncode=0, stdout="")
        mock_subproc.side_effect = [mock_create, mock_comment]

        result = create_blocker_issue(
            parent_issue=1690,
            title="fix(mesh): Heartbeat timeout",
            body="Heartbeat expires prematurely",
            role="platform",
            extra_labels=["priority:high"],
            dry_run=False,
        )

        assert result.success is True
        assert result.new_issue_number == 1795
        assert result.parent_issue_number == 1690
        assert "handoff:platform" in result.labels
        assert "priority:high" in result.labels
        assert mock_subproc.call_count == 2

    @patch("subprocess.run", side_effect=Exception("gh CLI failed"))
    def test_execute_issue_creation_failure(self, mock_subproc):
        result = create_blocker_issue(
            parent_issue=1690,
            title="fix(mesh): Heartbeat timeout",
            body="Error description",
            role="coder",
            dry_run=False,
        )
        assert result.success is False
        assert result.new_issue_number is None
        assert "gh CLI failed" in result.error_message


class TestMainCli:
    def test_main_dry_run_json(self, capsys):
        with patch(
            "sys.argv",
            [
                "create_blocker_issue.py",
                "--parent-issue",
                "1690",
                "--title",
                "fix(core): Worker timeout",
                "--body",
                "Worker timeout missing",
                "--role",
                "coder",
                "--dry-run",
                "--format",
                "json",
            ],
        ):
            code = main()

        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["parent_issue_number"] == 1690
        assert data["is_dry_run"] is True
        assert "handoff:coder" in data["labels"]

    def test_main_dry_run_text(self, capsys):
        with patch(
            "sys.argv",
            [
                "create_blocker_issue.py",
                "--parent-issue",
                "1690",
                "--title",
                "fix(ci): Pipeline timeout",
                "--body",
                "Pipeline times out",
                "--role",
                "ci",
                "--dry-run",
            ],
        ):
            code = main()

        assert code == 0
        captured = capsys.readouterr()
        assert "Prerequisite Blocker Issue Processed Successfully!" in captured.out
        assert "Blocks Parent:   #1690" in captured.out
        assert "Target Lane:     ci" in captured.out
