"""Tests for task_detector.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.task_detector import (
    detect_tasks_from_failed_ci,
    detect_tasks_from_issues,
    detect_tasks_from_prs,
)


class TestDetectTasksFromIssues:
    @patch("scripts.ci.task_detector.get_open_issues")
    def test_detects_security_task(self, mock_get_issues):
        mock_get_issues.return_value = [
            {
                "number": 10,
                "title": "Fix security vulnerability",
                "body": "Security issue found",
                "labels": [{"name": "P0-critical"}],
                "createdAt": "2026-09-01T00:00:00Z",
            }
        ]
        tasks = detect_tasks_from_issues(mock_get_issues.return_value)
        assert len(tasks) == 1
        assert tasks[0].task_type.value == "security"
        assert tasks[0].priority.value == "P0-critical"

    @patch("scripts.ci.task_detector.get_open_issues")
    def test_skips_existing_tasks(self, mock_get_issues):
        mock_get_issues.return_value = [
            {
                "number": 10,
                "title": "Existing task",
                "body": "",
                "labels": [{"name": "task:ready"}, {"name": "P0-critical"}],
                "createdAt": "2026-09-01T00:00:00Z",
            }
        ]
        tasks = detect_tasks_from_issues(mock_get_issues.return_value)
        assert len(tasks) == 0


class TestDetectTasksFromFailedCI:
    @patch("scripts.ci.task_detector.get_recent_workflow_runs")
    def test_detects_failed_ci(self, mock_get_runs):
        mock_get_runs.return_value = [
            {
                "conclusion": "failure",
                "workflowName": "CI",
                "headBranch": "main",
                "createdAt": "2026-09-01T00:00:00Z",
            }
        ]
        tasks = detect_tasks_from_failed_ci()
        assert len(tasks) == 1
        assert tasks[0].task_type.value == "ci-fix"
        assert tasks[0].priority.value == "P1-high"

    @patch("scripts.ci.task_detector.get_recent_workflow_runs")
    def test_skips_successful_runs(self, mock_get_runs):
        mock_get_runs.return_value = [
            {
                "conclusion": "success",
                "workflowName": "CI",
                "headBranch": "main",
                "createdAt": "2026-09-01T00:00:00Z",
            }
        ]
        tasks = detect_tasks_from_failed_ci()
        assert len(tasks) == 0


class TestDetectTasksFromPRs:
    @patch("scripts.ci.task_detector.get_open_prs")
    def test_detects_conflicting_pr(self, mock_get_prs):
        mock_get_prs.return_value = [
            {
                "number": 50,
                "title": "Fix bug",
                "labels": [],
                "mergeable": "CONFLICTING",
                "mergeStateStatus": "dirty",
            }
        ]
        tasks = detect_tasks_from_prs(mock_get_prs.return_value)
        assert len(tasks) == 1
        assert tasks[0].task_type.value == "ci-fix"
