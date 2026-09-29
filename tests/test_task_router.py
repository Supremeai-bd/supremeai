"""Tests for task_router.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.task_router import (
    check_dependencies,
    get_active_agents,
    infer_agent_capabilities,
    match_capabilities,
    route_all_tasks,
    route_single_task,
)
from scripts.ci.task_state_machine import Task, TaskPriority, TaskState, TaskType


class TestInferAgentCapabilities:
    def test_coder_capabilities(self):
        caps = infer_agent_capabilities("coder-1")
        assert "coding" in caps
        assert "debugging" in caps

    def test_ci_capabilities(self):
        caps = infer_agent_capabilities("ci-bot")
        assert "ci" in caps
        assert "devops" in caps

    def test_unknown_agent_has_general_caps(self):
        caps = infer_agent_capabilities("unknown-agent")
        assert "coding" in caps
        assert "general" in caps


class TestMatchCapabilities:
    def test_perfect_match(self):
        task = MagicMock(capabilities_required=["coding", "debugging"])
        score = match_capabilities(task, {"coding", "debugging", "testing"})
        assert score == 1.0

    def test_partial_match(self):
        task = MagicMock(capabilities_required=["coding", "security"])
        score = match_capabilities(task, {"coding"})
        assert score == 0.5

    def test_no_requirements(self):
        task = MagicMock(capabilities_required=[])
        score = match_capabilities(task, {"coding"})
        assert score == 1.0


class TestCheckDependencies:
    def test_dependencies_met(self):
        task = MagicMock(depends_on=["task-2"], task_id="task-1")
        all_tasks = [
            MagicMock(task_id="task-1", state=MagicMock(value="ready")),
            MagicMock(task_id="task-2", state=TaskState.DONE),
        ]
        ok, blocked = check_dependencies(task, all_tasks)
        assert ok is True
        assert blocked == []

    def test_dependencies_not_met(self):
        task = MagicMock(depends_on=["task-2"], task_id="task-1")
        all_tasks = [
            MagicMock(task_id="task-1", state=MagicMock(value="ready")),
            MagicMock(task_id="task-2", state=TaskState.READY),
        ]
        ok, blocked = check_dependencies(task, all_tasks)
        assert ok is False
        assert "task-2" in blocked


class TestRouteSingleTask:
    @patch("scripts.ci.task_router.get_active_agents")
    def test_assigns_when_agent_available(self, mock_agents):
        task = Task(
            task_id="task-1",
            task_type=TaskType.FIX,
            state=TaskState.READY,
            priority=TaskPriority.P1_HIGH,
            title="Fix bug",
            capabilities_required=["coding"],
        )
        mock_agents.return_value = [{"name": "coder-1", "active_issue": None}]
        result = route_single_task(task, [task], [{"name": "coder-1", "active_issue": None}])
        assert result is not None
        assert result.get("action") == "assign"
        assert result.get("agent") == "coder-1"

    @patch("scripts.ci.task_router.get_active_agents")
    def test_waiting_when_no_agents(self, mock_agents):
        task = Task(
            task_id="task-1",
            task_type=TaskType.FIX,
            state=TaskState.READY,
            priority=TaskPriority.P1_HIGH,
            title="Fix bug",
        )
        mock_agents.return_value = []
        result = route_single_task(task, [task], [])
        assert result is not None
        assert result.get("action") == "waiting"
