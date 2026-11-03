"""
Unit tests for ReasoningOrchestrator ReAct decision making and consensus synthesis.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from brain.reasoning_orchestrator import ReasoningOrchestrator


@pytest.mark.asyncio
async def test_decide_with_llm_react_json():
    mock_router = MagicMock()
    mock_router.async_route_and_generate = AsyncMock(
        return_value={
            "success": True,
            "text": '{"thought": "User wants to look up past user tasks.", "tool": "search_database", "args": {"query": "task 402"}, "reasoning": "Database search required."}',
        }
    )

    orchestrator = ReasoningOrchestrator(model_router=mock_router)
    decision = await orchestrator.decide(
        task="Find records for task 402",
        context={"user_id": "u1"},
    )

    assert decision["source"] == "llm_react"
    assert decision["tool"] == "search_database"
    assert decision["args"] == {"query": "task 402"}
    assert "User wants to look up" in decision["thought"]


@pytest.mark.asyncio
async def test_decide_with_markdown_codeblock():
    mock_router = MagicMock()
    mock_router.async_route_and_generate = AsyncMock(
        return_value={
            "success": True,
            "text": '```json\n{\n  "thought": "Need to run python code.",\n  "tool": "execute_python_code",\n  "args": {"code": "print(2+2)"},\n  "reasoning": "Executes calculation"\n}\n```',
        }
    )

    orchestrator = ReasoningOrchestrator(model_router=mock_router)
    decision = await orchestrator.decide(task="Calculate 2+2 in Python")

    assert decision["source"] == "llm_react"
    assert decision["tool"] == "execute_python_code"
    assert decision["args"]["code"] == "print(2+2)"


@pytest.mark.asyncio
async def test_decide_deterministic_fallbacks():
    # Router returns failure, triggering semantic deterministic fallback
    mock_router = MagicMock()
    mock_router.async_route_and_generate = AsyncMock(
        return_value={"success": False, "error": "upstream timeout"}
    )

    orchestrator = ReasoningOrchestrator(model_router=mock_router)

    # 1. Health task
    res_health = await orchestrator.decide(task="What is the server cpu and ram status?")
    assert res_health["source"] == "deterministic_fallback"
    assert res_health["tool"] == "check_system_health"

    # 2. Database search task
    res_db = await orchestrator.decide(task="Find query in database for projects")
    assert res_db["source"] == "deterministic_fallback"
    assert res_db["tool"] == "search_database"

    # 3. Code execution task
    res_code = await orchestrator.decide(task="Execute python script to analyze logs")
    assert res_code["source"] == "deterministic_fallback"
    assert res_code["tool"] == "execute_python_code"

    # 4. General conversation -> done
    res_done = await orchestrator.decide(task="Hello there, how are you?")
    assert res_done["source"] == "deterministic_fallback"
    assert res_done["tool"] == "done"


@pytest.mark.asyncio
async def test_synthesize_findings_with_llm():
    mock_router = MagicMock()
    mock_router.async_route_and_generate = AsyncMock(
        return_value={
            "success": True,
            "text": "Consensus reached: 2 agents verified database integrity, 1 agent identified high latency.",
        }
    )

    orchestrator = ReasoningOrchestrator(model_router=mock_router)
    findings = [
        {"agent": "AgentA", "outcome": "db_ok"},
        {"agent": "AgentB", "outcome": "db_ok"},
        {"agent": "AgentC", "outcome": "high_latency"},
    ]

    result = await orchestrator.synthesize(
        task="Audit database cluster performance",
        findings=findings,
    )

    assert result["source"] == "llm_consensus"
    assert result["total_findings"] == 3
    assert "Consensus reached" in result["summary"]


@pytest.mark.asyncio
async def test_synthesize_empty_and_fallback():
    orchestrator = ReasoningOrchestrator(model_router=None)

    # Empty
    res_empty = await orchestrator.synthesize(task="Test task", findings=[])
    assert res_empty["total_findings"] == 0
    assert res_empty["source"] == "empty"

    # Deterministic fallback
    findings = [{"agent": "A", "status": "completed"}, {"agent": "B", "status": "failed"}]
    res_fallback = await orchestrator.synthesize(task="Run diagnostics", findings=findings)
    assert res_fallback["source"] == "deterministic_summary"
    assert res_fallback["total_findings"] == 2
    assert "completed" in res_fallback["summary"]
    assert "failed" in res_fallback["summary"]
