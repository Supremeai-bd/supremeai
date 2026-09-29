"""End-to-end integration test for the Task Engine (#2573).

Simulates:
1. Task detection from an issue
2. Task routing to an agent
3. Task state transitions (READY -> ASSIGNED -> EXECUTING -> VERIFYING -> DONE)
4. Task timeout recovery for stuck tasks
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.task_detector import detect_tasks_from_issues
from scripts.ci.task_router import route_single_task
from scripts.ci.task_state_machine import (
    Task,
    TaskPriority,
    TaskState,
    TaskType,
    apply_task_to_issue,
    create_task,
    fetch_tasks_by_state,
    transition_task,
)
from scripts.ci.task_timeout_recovery import recover_timeout_tasks


class TestEndToEndTaskEngine:
    @patch("scripts.ci.task_detector.get_open_issues")
    def test_full_workflow(self, mock_get_issues):
        mock_get_issues.return_value = [
            {
                "number": 10,
                "title": "Fix critical bug",
                "body": "There is a critical bug in the system",
                "labels": [{"name": "P0-critical"}],
                "createdAt": "2026-09-01T00:00:00Z",
            }
        ]
        tasks = detect_tasks_from_issues(mock_get_issues.return_value)
        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_type == TaskType.FIX
        assert task.priority == TaskPriority.P0_CRITICAL
        assert task.state == TaskState.READY
        with patch("scripts.ci.task_state_machine.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"labels": []}))
            transitioned = transition_task(task, TaskState.WAITING_FOR_AGENT)
            transitioned = transition_task(transitioned, TaskState.ASSIGNED, agent_name="coder-1")
            assert transitioned.state == TaskState.ASSIGNED
            assert transitioned.assigned_agent == "coder-1"
            apply_task_to_issue(transitioned, 10)

    @patch("scripts.ci.task_timeout_recovery.add_timeout_comment")
    @patch("scripts.ci.task_timeout_recovery.transition_task")
    @patch("scripts.ci.task_timeout_recovery.apply_task_to_issue")
    @patch("scripts.ci.task_timeout_recovery.get_issue_updated_at")
    @patch("scripts.ci.task_timeout_recovery.fetch_tasks_by_state")
    def test_timeout_recovery_integration(self, mock_fetch, mock_get_updated, mock_apply, mock_transition, mock_comment):
        task = Task(
            task_id="task-10",
            task_type=TaskType.FIX,
            state=TaskState.ASSIGNED,
            priority=TaskPriority.P0_CRITICAL,
            title="Fix critical bug",
            issue_number=10,
            assigned_agent="coder-1",
        )
        past = datetime.now(UTC) - timedelta(minutes=45)
        mock_get_updated.return_value = past
        def state_filter(state):
            return [task] if task.state == state else []
        mock_fetch.side_effect = state_filter
        recovered = recover_timeout_tasks(dry_run=False)
        assert len(recovered) == 1
        assert recovered[0]["previous_state"] == "assigned"
        assert recovered[0]["issue_number"] == 10

    def test_task_state_machine_lifecycle(self):
        task = create_task("task-1", TaskType.FIX, TaskPriority.P1_HIGH, "Fix bug", issue_number=10)
        assert task.state == TaskState.READY
        task = transition_task(task, TaskState.WAITING_FOR_AGENT)
        assert task.state == TaskState.WAITING_FOR_AGENT
        task = transition_task(task, TaskState.ASSIGNED, agent_name="agent-1")
        assert task.state == TaskState.ASSIGNED
        assert task.assigned_agent == "agent-1"
        task = transition_task(task, TaskState.EXECUTING)
        assert task.state == TaskState.EXECUTING
        task = transition_task(task, TaskState.VERIFYING)
        assert task.state == TaskState.VERIFYING
        task = transition_task(task, TaskState.DONE)
        assert task.state == TaskState.DONE
        with pytest.raises(ValueError):
            transition_task(task, TaskState.READY)
