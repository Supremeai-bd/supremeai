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
