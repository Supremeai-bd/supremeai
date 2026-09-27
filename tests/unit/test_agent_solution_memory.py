"""Unit tests for SupremeAI Collective Agent Memory CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.agents.agent_solution_memory import (
    record_solution,
    record_solution_gap,
    search_local_lessons,
    verify_mcp,
)


def test_verify_mcp_success(tmp_path: Path):
    mock_mcp_config = tmp_path / "mcp.json"
    mock_mcp_config.write_text(
        json.dumps({
            "mcpServers": {
                "supremeai-control-tower": {
                    "command": "npx",
                    "args": ["tsx", "infrastructure/mcp-control-plane/src/index.ts"],
                }
            }
        }),
        encoding="utf-8",
    )

    with patch("scripts.agents.agent_solution_memory.MCP_CONFIG_FILE", mock_mcp_config):
        assert verify_mcp() is True


def test_verify_mcp_missing_server(tmp_path: Path):
    mock_mcp_config = tmp_path / "mcp.json"
    mock_mcp_config.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    with patch("scripts.agents.agent_solution_memory.MCP_CONFIG_FILE", mock_mcp_config):
        with patch.dict("os.environ", {}, clear=True):
            assert verify_mcp() is False


def test_search_local_lessons_finds_match(tmp_path: Path):
    mock_lessons = tmp_path / "LESSONS_LEARNED.md"
    mock_lessons.write_text(
        """# Lessons Learned

| Date | Issue | Description | Fix | Lesson |
| :--- | :--- | :--- | :--- | :--- |
| 2026-09-28 | #2201 | Windows PowerShell cp1252 stdout fails on UTF-8 emojis | Prefix command with PYTHONIOENCODING=utf-8 | Always set PYTHONIOENCODING in windows terminal subprocesses |
""",
        encoding="utf-8",
    )

    with patch("scripts.agents.agent_solution_memory.LESSONS_FILE", mock_lessons):
        results = search_local_lessons("PowerShell emojis encoding")
        assert len(results) == 1
        assert "#2201" in results[0]["text"]
        assert "PYTHONIOENCODING" in results[0]["text"]


def test_search_local_lessons_no_match(tmp_path: Path):
    mock_lessons = tmp_path / "LESSONS_LEARNED.md"
    mock_lessons.write_text(
        """# Lessons Learned
| Date | Issue | Description | Fix | Lesson |
| :--- | :--- | :--- | :--- | :--- |
""",
        encoding="utf-8",
    )

    with patch("scripts.agents.agent_solution_memory.LESSONS_FILE", mock_lessons):
        results = search_local_lessons("completely unrelated topic")
        assert len(results) == 0


def test_record_solution_appends_to_lessons(tmp_path: Path):
    mock_lessons = tmp_path / "LESSONS_LEARNED.md"
    mock_lessons.write_text(
        """# Lessons Learned

| Date | Issue | Description | Fix | Lesson |
| :--- | :--- | :--- | :--- | :--- |
| 2026-09-20 | #100 | Old issue | Old fix | Old lesson |
""",
        encoding="utf-8",
    )

    with patch("scripts.agents.agent_solution_memory.LESSONS_FILE", mock_lessons):
        with patch("scripts.agents.agent_solution_memory.SQLITE_DB_PATH", tmp_path / "test.db"):
            success = record_solution(
                task_id="9999",
                problem="Redis connection dropped",
                solution="Implement exponential backoff retry",
                lesson="Never fail on transient network errors",
                status="VERIFIED",
                tags=["redis", "network"],
            )
            assert success is True

            content = mock_lessons.read_text(encoding="utf-8")
            assert "#9999" in content
            assert "Redis connection dropped" in content
            assert "Implement exponential backoff retry" in content


def test_record_solution_gap(tmp_path: Path):
    with patch("scripts.agents.agent_solution_memory.SQLITE_DB_PATH", tmp_path / "test.db"):
        success = record_solution_gap(
            task_id="1042",
            problem="OAuth token refresh failed in container",
            failed_attempts="Direct refresh blocked by network policy",
            missing_capability="credential.refresh.scoped",
            future_path="Implement scoped broker proxy",
        )
        assert success is True
