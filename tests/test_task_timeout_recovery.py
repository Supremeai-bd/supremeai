"""Tests for task_timeout_recovery.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.task_timeout_recovery import (
    add_timeout_comment,
    get_issue_updated_at,
    recover_timeout_tasks,
)


class TestGetIssueUpdatedAt:
    @patch("scripts.ci.task_timeout_recovery.run")
    def test_returns_datetime(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"updatedAt": "2026-09-29T20:00:00Z"}))
        result = get_issue_updated_at(100)
        assert result is not None
        assert result.year == 2026

    @patch("scripts.ci.task_timeout_recovery.run")
    def test_returns_none_on_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = get_issue_updated_at(100)
        assert result is None


class TestRecoverTimeoutTasks:
    @patch("scripts.ci.task_timeout_recovery.add_timeout_comment")
    @patch("scripts.ci.task_timeout_recovery.transition_task")
    @patch("scripts.ci.task_timeout_recovery.apply_task_to_issue")
    @patch("scripts.ci.task_timeout_recovery.get_issue_updated_at")
    @patch("scripts.ci.task_timeout_recovery.fetch_tasks_by_state")
    def test_recover_timed_out_task(self, mock_fetch, mock_get_updated, mock_apply, mock_transition, mock_comment):
        from scripts.ci.task_state_machine import Task, TaskPriority, TaskState, TaskType
        past = datetime.now(UTC) - timedelta(minutes=45)
        mock_get_updated.return_value = past
        task = Task(
            task_id="task-1",
            task_type=TaskType.FIX,
            state=TaskState.ASSIGNED,
            priority=TaskPriority.P1_HIGH,
            title="Fix bug",
            issue_number=100,
        )
        def state_filter(state):
            return [task] if task.state == state else []
        mock_fetch.side_effect = state_filter
        recovered = recover_timeout_tasks(dry_run=False)
        assert len(recovered) == 1
        assert recovered[0]["issue_number"] == 100
        assert recovered[0]["previous_state"] == "assigned"

    @patch("scripts.ci.task_timeout_recovery.add_timeout_comment")
    @patch("scripts.ci.task_timeout_recovery.transition_task")
    @patch("scripts.ci.task_timeout_recovery.apply_task_to_issue")
    @patch("scripts.ci.task_timeout_recovery.get_issue_updated_at")
    @patch("scripts.ci.task_timeout_recovery.fetch_tasks_by_state")
    def test_no_recovery_within_threshold(self, mock_fetch, mock_get_updated, mock_apply, mock_transition, mock_comment):
        from scripts.ci.task_state_machine import Task, TaskPriority, TaskState, TaskType
        recent = datetime.now(UTC) - timedelta(minutes=5)
        mock_get_updated.return_value = recent
        task = Task(
            task_id="task-1",
            task_type=TaskType.FIX,
            state=TaskState.ASSIGNED,
            priority=TaskPriority.P1_HIGH,
            title="Fix bug",
            issue_number=100,
        )
        def state_filter(state):
            return [task] if task.state == state else []
        mock_fetch.side_effect = state_filter
        recovered = recover_timeout_tasks(dry_run=False)
        assert len(recovered) == 0
