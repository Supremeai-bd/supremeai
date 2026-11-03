"""M09 P-A — governed tool loop tests (decision → execution half).

বাংলা: ReAct সিদ্ধান্ত এখন তিনটি গেট (ফ্ল্যাগ/রেজিস্ট্রি/পলিসি) পার হয়ে
সত্যিই নির্বাহ হয় — প্রতিটি গেটের আচরণ এখানে পিন করা। SUPREME_TOOLS
মেম্বার-সংখ্যা-চুক্তি (tests/tools/test_agent_tools.py) অক্ষুণ্ণ —
রেজিস্ট্রি সেখান থেকেই আসে, এখানে monkeypatch-করা হয় শুধু নির্ধারিততার জন্য।
"""

from __future__ import annotations

from typing import Any

import pytest

import tools.agent_tools as agent_tools_module
from brain.reasoning_orchestrator import ReasoningOrchestrator
from core import tool_loop
from core.tool_loop import agent_tools_enabled, execute_tool_decision


def _install_fake_tools(monkeypatch: pytest.MonkeyPatch, fns: list[Any]) -> None:
    monkeypatch.setattr(agent_tools_module, "SUPREME_TOOLS", fns)


# ---------------------------------------------------------------------------
# Flag gate — SUPREMEAI_AGENT_TOOLS
# ---------------------------------------------------------------------------


def test_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    assert agent_tools_enabled() is False


@pytest.mark.parametrize("raw", ["false", "0", "no", "yes", "garbage", "on", "1", ""])
def test_flag_strict_true_only(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", raw)
    # অজানা/ভুল মানও OFF — fail-safe (কোনো নীরব সম্প্রসারণ নয়)।
    assert agent_tools_enabled() is False


async def test_execution_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    called = {"n": 0}

    async def fake_tool(query: str) -> str:
        called["n"] += 1
        return "found"

    _install_fake_tools(monkeypatch, [fake_tool])
    outcome = await execute_tool_decision(
        {"tool": "fake_tool", "args": {"query": "x"}, "source": "test"}
    )
    assert outcome["executed"] is False
    assert outcome["status"] == "disabled"
    assert "SUPREMEAI_AGENT_TOOLS" in outcome["reason"]
    assert called["n"] == 0  # কোনো টুলই চলেনি


# ---------------------------------------------------------------------------
# Registry gate
# ---------------------------------------------------------------------------


async def test_unknown_tool_rejected_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    _install_fake_tools(monkeypatch, [])
    outcome = await execute_tool_decision({"tool": "delete_everything", "args": {}})
    assert outcome["executed"] is False
    assert outcome["status"] == "unknown_tool"


async def test_done_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    outcome = await execute_tool_decision({"tool": "done", "args": {}})
    assert outcome == {
        "tool": "done",
        "decision_source": "unknown",
        "executed": False,
        "status": "done",
    }


# ---------------------------------------------------------------------------
# Policy gate — R0 ALLOW, R5 REQUIRE_APPROVAL (real mcp_policy mappings)
# ---------------------------------------------------------------------------


async def test_policy_blocks_guest_code_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    called = {"n": 0}

    async def fake_real_name(code: str) -> str:
        called["n"] += 1
        return "would run"

    fake_real_name.__name__ = "execute_python_code"
    _install_fake_tools(monkeypatch, [fake_real_name])
    outcome = await execute_tool_decision(
        {"tool": "execute_python_code", "args": {"code": "import os"}, "source": "test"}
    )
    assert outcome["executed"] is False
    assert outcome["status"] == "policy_blocked"
    assert outcome["risk"] == "R5"
    assert called["n"] == 0  # অনুমোদন ছাড়া কোড চলেনি


async def test_policy_allows_read_only_tool_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")

    async def fake_search(query: str) -> str:
        return f"Found 2 records for {query}"

    fake_search.__name__ = "search_database"
    _install_fake_tools(monkeypatch, [fake_search])

    outcome = await execute_tool_decision(
        {
            "tool": "search_database",
            "args": {"query": "task 402"},
            "source": "llm_react",
        }
    )
    assert outcome["executed"] is True
    assert outcome["status"] == "ok"
    assert outcome["risk"] == "R0"
    assert outcome["observation"] == "Found 2 records for task 402"


# ---------------------------------------------------------------------------
# Argument mapping — deterministic fallback {"target": ...} → টুল-সিগনেচার
# ---------------------------------------------------------------------------


async def test_fallback_target_arg_maps_to_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    captured: dict[str, Any] = {}

    def fake_health() -> str:
        return "System Status: ONLINE"

    fake_health.__name__ = "check_system_health"

    async def fake_search(query: str) -> str:
        captured["query"] = query
        return "ok"

    fake_search.__name__ = "search_database"
    _install_fake_tools(monkeypatch, [fake_health, fake_search])

    outcome = await execute_tool_decision(
        {
            "tool": "search_database",
            "args": {"target": "project records"},  # deterministic-fallback আকৃতি
            "source": "deterministic_fallback",
        }
    )
    assert outcome["executed"] is True
    assert captured["query"] == "project records"


# ---------------------------------------------------------------------------
# decide_and_execute — ReAct লুপের সম্পূর্ণ অর্ধেক (integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_and_execute_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    executed: dict[str, str] = {}

    async def fake_search(query: str) -> str:
        executed["q"] = query
        return "2 rows"

    fake_search.__name__ = "search_database"
    _install_fake_tools(monkeypatch, [fake_search])

    orchestrator = ReasoningOrchestrator(model_router=None)
    result = await orchestrator.decide_and_execute(
        task="Find query in database for task 402",
        context={"user_id": "u1"},
    )
    assert result["decision"]["tool"] == "search_database"
    assert result["outcome"]["executed"] is True
    assert result["outcome"]["observation"] == "2 rows"
    assert executed["q"]  # fallback target-ম্যাপ কাজ করেছে


@pytest.mark.asyncio
async def test_decide_and_execute_flag_off_never_executes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    orchestrator = ReasoningOrchestrator(model_router=None)
    result = await orchestrator.decide_and_execute(task="server cpu status?")
    assert result["decision"]["tool"] == "check_system_health"  # সিদ্ধান্ত হয়
    assert result["outcome"]["status"] == "disabled"  # কিন্তু নির্বাহ নয়


@pytest.mark.asyncio
async def test_tool_error_reported_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")

    async def boom(query: str) -> str:
        raise RuntimeError("supabase exploded")

    boom.__name__ = "search_database"
    _install_fake_tools(monkeypatch, [boom])

    outcome = await execute_tool_decision({"tool": "search_database", "args": {"query": "x"}})
    assert outcome["executed"] is False
    assert outcome["status"] == "error"
    assert "RuntimeError" in outcome["error"]


# ---------------------------------------------------------------------------
# mcp_policy mapping pins — agent_tools শ্রেণি
# ---------------------------------------------------------------------------


def test_agent_tools_policy_mappings() -> None:
    from core.mcp_policy import evaluate_tool

    assert evaluate_tool("search_database") == ("ALLOW", "R0")
    assert evaluate_tool("check_system_health") == ("ALLOW", "R0")
    assert evaluate_tool("execute_python_code") == ("REQUIRE_APPROVAL", "R5")
