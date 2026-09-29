"""Tests for task_dashboard.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.task_dashboard import (
    get_agent_workload,
    get_all_tasks,
    render_dashboard,
    dashboard_to_json,
    Task,
    TaskPriority,
    TaskState,
    TaskType,
)


class TestGetAgentWorkload:
    @patch("scripts.ci.task_dashboard.run")
    def test_returns_workload(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([
            {"assignees": [{"login": "agent-1"}]},
            {"assignees": [{"login": "agent-1"}, {"login": "agent-2"}]},
        ]))
        workload = get_agent_workload()
        assert workload.get("agent-1") == 2
        assert workload.get("agent-2") == 1

    @patch("scripts.ci.task_dashboard.run")
    def test_returns_empty_on_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        workload = get_agent_workload()
        assert workload == {}


class TestRenderDashboard:
    def test_renders_tasks(self):
        tasks = [
            Task("task-1", TaskType.FIX, TaskState.READY, TaskPriority.P1_HIGH, "Fix bug", issue_number=1),
            Task("task-2", TaskType.FIX, TaskState.ASSIGNED, TaskPriority.P0_CRITICAL, "Critical fix", assigned_agent="agent-1", issue_number=2),
        ]
        workload = {"agent-1": 1}
        output = render_dashboard(tasks, workload)
        assert "Total Tasks: 2" in output
        assert "Fix bug" in output
        assert "Critical fix" in output
        assert "agent-1" in output

    def test_renders_empty_dashboard(self):
        output = render_dashboard([], {})
        assert "Total Tasks: 0" in output


class TestDashboardToJson:
    def test_json_structure(self):
        tasks = [
            Task("task-1", TaskType.FIX, TaskState.READY, TaskPriority.P1_HIGH, "Fix bug", issue_number=1),
        ]
        workload = {"agent-1": 1}
        result = dashboard_to_json(tasks, workload)
        assert result["total_tasks"] == 1
        assert "ready" in result["by_state"]
        assert result["agent_workload"]["agent-1"] == 1
