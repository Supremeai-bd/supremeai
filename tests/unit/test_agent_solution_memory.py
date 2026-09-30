"""Unit tests for SupremeAI Collective Agent Memory CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts.agents.agent_solution_memory import (
    format_strategic_block,
    record_solution,
    record_solution_gap,
    record_strategic_decision,
    search_local_lessons,
    search_strategic_memory,
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

    with (
        patch("scripts.agents.agent_solution_memory.MCP_CONFIG_FILE", mock_mcp_config),
        patch.dict("os.environ", {}, clear=True),
    ):
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

    with (
        patch("scripts.agents.agent_solution_memory.LESSONS_FILE", mock_lessons),
        patch("scripts.agents.agent_solution_memory.SQLITE_DB_PATH", tmp_path / "test.db"),
    ):
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


# ─── #2691: Strategic Decision Harvest — record/search/inject tests ─────────


def _write_strategic_jsonl(path: Path, entries: list[dict]) -> None:
    import json as _json

    path.parent.mkdir(parents=True, exist_ok=True)
    # বাংলা মন্তব্য: এক লুপে একাধিক write এড়িয়ে একবারে জয়েন করে লেখা (FURB122)।
    payload = "".join(_json.dumps(e, ensure_ascii=False) + "\n" for e in entries)
    with open(path, "a", encoding="utf-8") as f:
        f.write(payload)


def test_record_strategic_decision_persists_jsonl(tmp_path: Path):
    """#2691: record-strategic — JSONL-এ first-class ফিল্ডসহ পারসিস্টেন্স।"""
    mock_store = tmp_path / "strategic_decisions.jsonl"
    with (
        patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", mock_store),
        patch("scripts.agents.agent_solution_memory.SQLITE_DB_PATH", tmp_path / "test.db"),
    ):
        success = record_strategic_decision(
            task_id="#2691",
            decision="Raw fetch() নিষিদ্ধ — সব API কল apiClient দিয়ে",
            what_not_to_do="UI কম্পোনেন্টে কখনো bare fetch() লিখবে না",
            why_not="bare fetch-এ timeout/queue/auth/retry কিছুই থাকে না",
            source_legitimacy="internal pattern, no external source",
            agent="auditor",
            tags=["frontend", "api"],
        )
        assert success is True

        import json as _json

        lines = mock_store.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = _json.loads(lines[0])
        # বাংলা মন্তব্য: ফার্স্ট-ক্লাস ফিল্ড যাচাই — task_id '#' ছাড়া, লাল দাগ ও why-not অটুট।
        assert entry["task_id"] == "2691"
        assert entry["what_not_to_do"] == "UI কম্পোনেন্টে কখনো bare fetch() লিখবে না"
        assert entry["why_not"] == "bare fetch-এ timeout/queue/auth/retry কিছুই থাকে না"
        assert entry["source_legitimacy_audit"] == "internal pattern, no external source"
        assert entry["agent"] == "auditor"
        assert entry["tags"] == ["frontend", "api"]


def test_record_strategic_decision_rejects_empty_fields(tmp_path: Path):
    """#2691: ভ্যালিডেশন — কোনো মূল ফিল্ড ফাঁকা হলে রেকর্ড হবে না।"""
    mock_store = tmp_path / "strategic_decisions.jsonl"
    with patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", mock_store):
        assert record_strategic_decision(
            task_id="2691", decision="x", what_not_to_do="  ", why_not="y"
        ) is False
        assert record_strategic_decision(
            task_id="2691", decision="x", what_not_to_do="y", why_not=""
        ) is False
        assert not mock_store.exists()


def test_search_strategic_memory_scores_and_limits(tmp_path: Path):
    """#2691: কীওয়ার্ড স্কোর + লিমিট + সর্টিং (বেশি স্কোর আগে)।"""
    mock_store = tmp_path / "strategic_decisions.jsonl"
    _write_strategic_jsonl(mock_store, [
        {"task_id": "1", "decision": "frontend apiClient pattern", "what_not_to_do": "no raw network calls",
         "why_not": "missing central retry", "agent": "auditor", "tags": ["frontend"]},
        {"task_id": "2", "decision": "frontend fetch timeout rule", "what_not_to_do": "red line two",
         "why_not": "reason two", "agent": "auditor", "tags": ["frontend", "api"]},
        {"task_id": "3", "decision": "database migration policy", "what_not_to_do": "no drop table",
         "why_not": "data loss", "agent": "ecosystem-scout", "tags": ["backend"]},
    ])
    with patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", mock_store):
        results = search_strategic_memory("frontend fetch timeout", limit=2)
        assert 1 <= len(results) <= 2
        # বাংলা মন্তব্য: task #2 তিনটি টার্মই ম্যাচ করে (৩) — #1 শুধু frontend (১) — #2 আগে।
        assert results[0]["task_id"] == "2"
        assert results[0]["score"] == 3
        assert results[-1]["score"] >= 1
        # database entry কখনোই আসবে না
        assert all(r["task_id"] != "3" for r in results)


def test_search_strategic_memory_missing_file_and_empty_query(tmp_path: Path):
    """#2691: ফাইল না থাকলে / কুয়েরি ফাঁকা হলে — নীরব খালি ফেরত, কোনো crash নয়।"""
    with patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", tmp_path / "nope.jsonl"):
        assert search_strategic_memory("frontend") == []
    mock_store = tmp_path / "strategic_decisions.jsonl"
    _write_strategic_jsonl(mock_store, [
        {"task_id": "1", "decision": "d", "what_not_to_do": "w", "why_not": "y", "agent": "a", "tags": []},
    ])
    with patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", mock_store):
        assert search_strategic_memory("   ") == []
        assert search_strategic_memory("frontend", limit=0) == []


def test_search_strategic_memory_skips_corrupt_lines(tmp_path: Path):
    """#2691: দূষিত JSON লাইন স্কিপ — একটি খারাপ লাইন সার্চ ভাঙবে না।"""
    mock_store = tmp_path / "strategic_decisions.jsonl"
    mock_store.parent.mkdir(parents=True, exist_ok=True)
    good = '{"task_id": "9", "decision": "frontend guard", "what_not_to_do": "w", "why_not": "y", "agent": "a", "tags": ["frontend"]}'
    mock_store.write_text("NOT-JSON-{{{\n" + good + "\n\n", encoding="utf-8")
    with patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", mock_store):
        results = search_strategic_memory("frontend guard")
        assert len(results) == 1
        assert results[0]["task_id"] == "9"


def test_format_strategic_block_renders_red_lines():
    """#2691: ইনজেকশন ব্লকে লাল দাগ + কেন-না + সোর্স প্রামাণ্যতা থাকে।"""
    block = format_strategic_block([
        {
            "task_id": "42",
            "decision": "Use apiClient everywhere",
            "what_not_to_do": "never write bare fetch()",
            "why_not": "no timeout/queue/auth",
            "source_legitimacy_audit": "internal",
            "agent": "auditor",
            "tags": ["frontend"],
        }
    ])
    assert "Strategic Red Lines" in block
    assert "never write bare fetch()" in block
    assert "no timeout/queue/auth" in block
    assert "internal" in block
    assert "#42" in block
    assert format_strategic_block([]) == ""


def test_inject_strategic_memory_posts_comment(tmp_path: Path):
    """#2691: লুপ-ইনজেকশন — ম্যাচ থাকলে ইস্যুতে লাল-দাগ কমেন্ট যায়।"""
    from scripts.agents import continuous_agent_loop as loop

    mock_store = tmp_path / "strategic_decisions.jsonl"
    _write_strategic_jsonl(mock_store, [
        {"task_id": "7", "decision": "frontend apiClient guard", "what_not_to_do": "no bare fetch",
         "why_not": "no timeout", "agent": "auditor", "tags": ["frontend"]},
    ])
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    with (
        patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", mock_store),
        patch.object(loop, "run", side_effect=fake_run),
    ):
        loop.inject_strategic_memory(1234, {"title": "frontend fetch sweep"})
        # বাংলা মন্তব্য: শিরোনাম টাস্ক-ডেটায় থাকায় gh issue view লাগবে না — শুধু কমেন্ট কল।
        assert len(calls) == 1
        assert calls[0][0:2] == ["gh", "issue"]
        assert calls[0][2] == "comment"
        assert "1234" in calls[0]
        body = calls[0][calls[0].index("--body") + 1]
        assert "no bare fetch" in body
        assert "Strategic Memory Injection" in body


def test_inject_strategic_memory_no_hits_no_comment(tmp_path: Path):
    """#2691: ম্যাচ না থাকলে কোনো কমেন্ট হবে না — এজেন্ট স্বাধীনভাবে এগোবে।"""
    from scripts.agents import continuous_agent_loop as loop

    def fake_run(cmd, **kwargs):
        raise AssertionError("gh must not be called when no strategic entries match")

    with (
        patch("scripts.agents.agent_solution_memory.STRATEGIC_FILE", tmp_path / "nope.jsonl"),
        patch.object(loop, "run", side_effect=fake_run),
    ):
        loop.inject_strategic_memory(1234, {"title": "unrelated database work"})


def test_inject_strategic_memory_never_raises(tmp_path: Path):
    """#2691: fail-safe — মেমরি সার্চ ব্যর্থ হলেও ইনজেকশন লুপ ভাঙবে না।"""
    from scripts.agents import agent_solution_memory as mem
    from scripts.agents import continuous_agent_loop as loop

    def boom(query, limit=5):
        raise RuntimeError("memory store corrupted")

    with (
        patch.object(mem, "search_strategic_memory", boom),
        patch.object(loop, "run", return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")),
    ):
        # বাংলা মন্তব্য: exception গিলে ফেলা হয় — কোনো raise নয়।
        loop.inject_strategic_memory(1234, {"title": "anything"})
