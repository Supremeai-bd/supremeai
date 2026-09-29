"""Tests for task_state_machine.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.task_state_machine import (
    Task,
    TaskPriority,
    TaskState,
    TaskType,
    apply_task_to_issue,
    create_task,
    fetch_task_by_issue,
    fetch_tasks_by_state,
    parse_task_labels,
    transition_task,
)


class TestParseTaskLabels:
    def test_parse_all_labels(self):
        labels = ["task:ready", "task-type:fix", "P0-critical", "group:step-1"]
        state, task_type, priority = parse_task_labels(labels)
        assert state == TaskState.READY
        assert task_type == TaskType.FIX
        assert priority == TaskPriority.P0_CRITICAL

    def test_parse_partial_labels(self):
        labels = ["task:executing", "P1-high"]
        state, task_type, priority = parse_task_labels(labels)
        assert state == TaskState.EXECUTING
        assert task_type is None
        assert priority == TaskPriority.P1_HIGH

    def test_parse_no_task_labels(self):
        labels = ["group:step-1", "P2-medium"]
        state, task_type, priority = parse_task_labels(labels)
        assert state is None
        assert task_type is None
        assert priority == TaskPriority.P2_MEDIUM


class TestCreateTask:
    def test_creates_task_with_defaults(self):
        task = create_task(
            task_id="task-1",
            task_type=TaskType.FIX,
            priority=TaskPriority.P1_HIGH,
            title="Fix bug",
        )
        assert task.task_id == "task-1"
        assert task.state == TaskState.READY
        assert task.priority == TaskPriority.P1_HIGH
        assert task.title == "Fix bug"
        assert task.assigned_agent == ""
        assert task.issue_number is None


class TestTransitionTask:
    def test_valid_transition_ready_to_waiting(self):
        task = create_task("task-1", TaskType.FIX, TaskPriority.P1_HIGH, "Fix")
        transitioned = transition_task(task, TaskState.WAITING_FOR_AGENT)
        assert transitioned.state == TaskState.WAITING_FOR_AGENT

    def test_valid_transition_waiting_to_assigned(self):
        task = create_task("task-1", TaskType.FIX, TaskPriority.P1_HIGH, "Fix")
        task = transition_task(task, TaskState.WAITING_FOR_AGENT)
        transitioned = transition_task(task, TaskState.ASSIGNED, agent_name="agent-1")
        assert transitioned.state == TaskState.ASSIGNED
        assert transitioned.assigned_agent == "agent-1"

    def test_invalid_transition_raises(self):
        task = create_task("task-1", TaskType.FIX, TaskPriority.P1_HIGH, "Fix")
        with pytest.raises(ValueError):
            transition_task(task, TaskState.DONE)


class TestApplyTaskToIssue:
    @patch("scripts.ci.task_state_machine.run")
    def test_applies_labels(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"labels": []}))
        task = create_task("task-1", TaskType.FIX, TaskPriority.P1_HIGH, "Fix")
        apply_task_to_issue(task, 100)
        assert mock_run.call_count >= 3

    @patch("scripts.ci.task_state_machine.run")
    def test_removes_old_labels(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"labels": [{"name": "task:ready"}, {"name": "task-type:fix"}, {"name": "P1-high"}]}))
        task = create_task("task-1", TaskType.FIX, TaskPriority.P1_HIGH, "Fix")
        task.state = TaskState.ASSIGNED
        apply_task_to_issue(task, 100)
        add_calls = [c for c in mock_run.call_args_list if "--add-label" in str(c)]
        remove_calls = [c for c in mock_run.call_args_list if "--remove-label" in str(c)]
        assert len(add_calls) >= 1
        assert len(remove_calls) >= 1
