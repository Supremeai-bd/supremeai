"""M09 P-G — first-fleet tool activation চুক্তি-টেস্ট।

বাংলা: ৪৪ dormant টুলের প্রথম জাগরণ (cot_verify_math) — flag-gated
(SUPREMEAI_TOOL_FLEET), নীতি-শ্রেণি R0 (deterministic, পার্শ্বপ্রতিক্রিয়া-শূন্য),
flag-off = registry হুবহু আজকের ৩-টুল।
"""

from __future__ import annotations

import pytest

from core.mcp_policy import evaluate_tool
from core.tool_loop import _resolve_call_args, execute_tool_decision, tool_registry
from tools.agent_tools import FLEET_TOOLS, SUPREME_TOOLS, governed_tools


@pytest.fixture(autouse=True)
def _fleet_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SUPREMEAI_TOOL_FLEET", raising=False)
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)


def test_flag_off_registry_unchanged():
    # বাংলা: flag-off = আজকের আচরণ — ৩টি বেস টুল, ফ্লিট নীরবে ঢোকে না।
    assert set(tool_registry()) == {fn.__name__ for fn in SUPREME_TOOLS}
    assert governed_tools() == list(SUPREME_TOOLS)


def test_flag_on_adds_fleet_tool(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPREMEAI_TOOL_FLEET", "true")
    registry = tool_registry()
    assert {fn.__name__ for fn in SUPREME_TOOLS} < set(registry)
    assert "cot_verify_math" in registry
    assert registry["cot_verify_math"] is FLEET_TOOLS[0]


def test_fleet_tool_policy_is_r0_allow():
    # বাংলা: deterministic গাণিতিক যাচাই — পার্শ্বপ্রতিক্রিয়া-শূন্য → R0/ALLOW।
    decision, risk = evaluate_tool("cot_verify_math")
    assert decision == "ALLOW"
    assert risk == "R0"


def test_multi_arg_resolution_strict():
    # বাংলা: জানা কী-ই কেবল পাস হয়; অতিরিক্ত কী নীরবে ঢোকে না।
    resolved = _resolve_call_args(
        "cot_verify_math",
        {"expression": "2+2", "claimed_result": "4", "evil_key": "x"},
    )
    assert resolved == {"expression": "2+2", "claimed_result": "4"}


@pytest.mark.asyncio
async def test_fleet_tool_end_to_end_verified(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_TOOL_FLEET", "true")
    result = await execute_tool_decision(
        {"tool": "cot_verify_math", "args": {"expression": "2+2", "claimed_result": "4"}}
    )
    assert result["executed"] is True
    assert result["status"] == "ok"
    assert "VERIFIED" in result["observation"]


@pytest.mark.asyncio
async def test_fleet_tool_end_to_end_refuted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_TOOL_FLEET", "true")
    result = await execute_tool_decision(
        {"tool": "cot_verify_math", "args": {"expression": "2+2", "claimed_result": "5"}}
    )
    assert result["executed"] is True
    # বাংলা: ভুল দাবি REFUTED — সত্য প্রতিফলন, কোনো ভান নয়; রান-চুক্তিতে
    # এটি execution-সাফল্য (টুল সত্যিই চলেছে) — status থাকে ok।
    assert "REFUTED" in result["observation"]


@pytest.mark.asyncio
async def test_fleet_tool_hidden_when_flag_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    result = await execute_tool_decision(
        {"tool": "cot_verify_math", "args": {"expression": "2+2", "claimed_result": "4"}}
    )
    assert result["executed"] is False
    assert result["status"] == "unknown_tool"
