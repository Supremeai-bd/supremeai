"""Tests for Multi-Agent Cross-PR & Branch Collision Detector."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from scripts.git.cross_pr_collision_detector import (
    CollisionItem,
    CollisionReport,
    detect_collisions,
    format_markdown_report,
    format_text_report,
)



def test_collision_report_clean():
    report = CollisionReport(target_branch="agent-5-ci-action", target_pr=100)
    assert not report.has_direct_collision
    text = format_text_report(report)
    assert "[OK] No file collisions detected" in text
    md = format_markdown_report(report)
    assert "Cross-PR Collision Check: Clean" in md


def test_collision_report_with_overlap():
    report = CollisionReport(
        target_branch="agent-3-coder-1",
        target_pr=1617,
        target_files=["backend/api/routes/healing_stats.py"],
        direct_collisions=[
            CollisionItem(
                file_path="backend/api/routes/healing_stats.py",
                target_pr=1617,
                target_branch="agent-3-coder-1",
                colliding_pr=1622,
                colliding_branch="agent-6-coder-2",
                colliding_author="agent-6",
            )
        ],
    )
    assert report.has_direct_collision
    text = format_text_report(report)
    assert "CROSS-AGENT COLLISION DETECTED" in text
    assert "healing_stats.py" in text
    assert "PR #1622" in text

    md = format_markdown_report(report)
    assert "Multi-Agent Cross-PR Collision Warning" in md
    assert "`backend/api/routes/healing_stats.py`" in md
    assert "[#1622]" in md
    assert "@agent-6" in md


@patch("scripts.git.cross_pr_collision_detector.fetch_open_prs")
def test_detect_collisions_disjoint(mock_fetch_prs):
    mock_fetch_prs.return_value = [
        {
            "number": 200,
            "headRefName": "agent-6-coder-2",
            "author": {"login": "agent-6"},
            "files": [{"path": "backend/core/kernel/dispatcher.py"}],
            "isDraft": False,
        }
    ]

    report = detect_collisions(
        target_branch="agent-3-coder-1",
        target_pr_num=100,
        target_files=["backend/api/routes/healing_stats.py"],
    )
    assert not report.has_direct_collision
    assert len(report.direct_collisions) == 0


@patch("scripts.git.cross_pr_collision_detector.fetch_open_prs")
def test_detect_collisions_direct_overlap(mock_fetch_prs):
    mock_fetch_prs.return_value = [
        {
            "number": 200,
            "headRefName": "agent-6-coder-2",
            "author": {"login": "agent-6"},
            "files": [
                {"path": "backend/api/routes/healing_stats.py"},
                {"path": "backend/services/auto_healer.py"},
            ],
            "isDraft": False,
        }
    ]

    report = detect_collisions(
        target_branch="agent-3-coder-1",
        target_pr_num=100,
        target_files=["backend/api/routes/healing_stats.py", "backend/config.py"],
    )
    assert report.has_direct_collision
    assert len(report.direct_collisions) == 1
    assert report.direct_collisions[0].file_path == "backend/api/routes/healing_stats.py"
    assert report.direct_collisions[0].colliding_pr == 200
    assert report.direct_collisions[0].colliding_branch == "agent-6-coder-2"
