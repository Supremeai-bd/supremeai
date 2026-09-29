"""Tests for scripts/ci/auto_escalate_priority.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci.auto_escalate_priority import (
    count_by_priority,
    escalate,
    get_open_issues,
    parse_priority,
    promote_issues,
)


class TestParsePriority:
    def test_returns_priority_label(self):
        assert parse_priority(["P0-critical", "group:step-1"]) == "P0-critical"
        assert parse_priority(["P1-high"]) == "P1-high"
        assert parse_priority([]) is None


class TestCountByPriority:
    def test_counts_correctly(self):
        issues = [
            {"labels": ["P0-critical"]},
            {"labels": ["P1-high"]},
            {"labels": ["P0-critical", "group:x"]},
            {"labels": ["P2-medium"]},
        ]
        counts = count_by_priority(issues)
        assert counts["P0-critical"] == 2
        assert counts["P1-high"] == 1
        assert counts["P2-medium"] == 1
        assert counts["P3-low"] == 0


class TestPromoteIssues:
    def test_promotes_oldest_first(self):
        issues = [
            {"number": 1, "createdAt": "2026-09-01T00:00:00Z", "labels": ["P1-high"]},
            {"number": 2, "createdAt": "2026-08-01T00:00:00Z", "labels": ["P1-high"]},
            {"number": 3, "createdAt": "2026-10-01T00:00:00Z", "labels": ["P1-high"]},
        ]
        promoted = promote_issues(issues, "P0-critical", 2)
        assert [p["number"] for p in promoted] == [2, 1]

    def test_respects_batch_size(self):
        issues = [
            {"number": i, "createdAt": "2026-09-01T00:00:00Z", "labels": ["P1-high"]}
            for i in range(5)
        ]
        promoted = promote_issues(issues, "P0-critical", 2)
        assert len(promoted) == 2


class TestEscalate:
    @patch("scripts.ci.auto_escalate_priority.run")
    def test_escalates_when_p0_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([
            {"number": 10, "title": "P1 issue", "labels": ["P1-high"], "createdAt": "2026-09-01T00:00:00Z"},
            {"number": 11, "title": "P1 issue 2", "labels": ["P1-high"], "createdAt": "2026-08-01T00:00:00Z"},
        ]))
        
        report = escalate()
        assert len(report) > 0
        assert any(item["to"] == "P0-critical" for item in report)

    @patch("scripts.ci.auto_escalate_priority.run")
    def test_no_escalation_when_p0_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([
            {"number": 1, "title": "P0 issue", "labels": ["P0-critical"], "createdAt": "2026-09-01T00:00:00Z"},
            {"number": 2, "title": "P1 issue", "labels": ["P1-high"], "createdAt": "2026-08-01T00:00:00Z"},
        ]))
        
        report = escalate()
        assert len(report) == 0
