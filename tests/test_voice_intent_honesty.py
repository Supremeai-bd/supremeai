"""Voice channel honesty contract — REAL-ROUTER revision (audit items ⑤ / ⑱).

The voice WebSocket now has a **real** intent step: ``handle_intent`` routes
every transcript through the governed autonomous ReAct loop
(``core.agent_chat_loop.AgentChatLoop``) — the same loop behind
``POST /api/agent/chat`` — and streams its truth back over the socket. The
previous simulated echo (``HANDLE_INTENT_SIMULATED = True`` + canned strings)
is retired; the old guard that pinned the simulation has been replaced, as
that file itself instructed, by tests that drive the actual routing.

This suite pins the new honesty contract:

* ``HANDLE_INTENT_SIMULATED`` is ``False`` — no echo surface remains;
* every frame ``handle_intent`` emits carries the literal ``simulated: False``
  plus ``surface`` so a client can audit the answer path frame-by-frame;
* the terminal ``response_complete`` frame reports ``executed`` truthfully
  (``True`` only when the loop streamed a grounded reply) together with
  ``stepsUsed`` / ``toolCalls`` / ``boundedStop``;
* a failing loop produces an honest "could not complete" sentence — never a
  fabricated result, never a canned claim of work;
* the handler still contains no execution primitive (no subprocess /
  os.system / eval / exec / shell=True) — the ReAct loop's governance gates
  (flag → registry → MCP policy) remain the ONLY path to real work.

Functional tests run offline: a fake loop is injected through the
``_voice_agent_loop`` factory seam. If the module cannot be imported in a
bare environment (Supabase/ORM/security layers), the functional tests skip
and the structural (AST) checks still hold — they never need the import.
"""

from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "api" / "routes" / "websocket_voice.py"

#: Calls that would mean the handler itself runs something outside the loop.
EXECUTION_PRIMITIVES = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "os.system",
    "os.popen",
    "eval",
    "exec",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {MODULE_PATH.name}")


# ── structural checks (import-free) ──────────────────────────────────────────


def test_module_declares_real_routing():
    tree = _tree()
    flags = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        for target in [node.targets[0]]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)
    }
    flag = flags.get("HANDLE_INTENT_SIMULATED")
    assert getattr(flag, "value", None) is False, (
        "HANDLE_INTENT_SIMULATED must be False — the real governed ReAct router "
        "is wired; the simulated echo must not come back."
    )


def test_every_frame_is_real_and_labelled():
    """Every ``send_json`` frame carries literal ``simulated=False`` + ``surface``."""
    handler = _find_function(_tree(), "handle_intent")
    # Frames are emitted via the ``_send_frame`` seam, which adds the flags.
    seam = _find_function(_tree(), "_send_frame")
    seam_simulated = seam_surface = None
    for node in ast.walk(seam):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "send_json"
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            for key, value in zip(node.args[0].keys, node.args[0].values, strict=False):
                # ``**payload`` shows up as a None key — an allowed spread.
                if not isinstance(key, ast.Constant):
                    continue
                if key.value == "simulated":
                    seam_simulated = value
                if key.value == "surface":
                    seam_surface = value
    assert seam_simulated is not None, "the seam must set simulated"
    assert isinstance(seam_simulated, ast.Constant) and seam_simulated.value is False, (
        "simulated must be the literal False — real routing"
    )
    assert isinstance(seam_surface, ast.Constant) and seam_surface.value == "voice_agent", (
        "surface must be the literal voice_agent"
    )

    # No direct ``websocket.send_json`` escapes the seam inside handle_intent.
    for node in ast.walk(handler):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "send_json":
                pytest.fail(
                    "handle_intent must send frames through _send_frame so the "
                    "simulated/surface flags stay auditable"
                )


def test_terminal_frame_reports_execution_truthfully():
    handler = _find_function(_tree(), "handle_intent")
    terminal_frames: list[dict[str, ast.expr]] = []
    for node in ast.walk(handler):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_send_frame"
            and node.args
            and isinstance(node.args[-1], ast.Dict)
        ):
            keys = {
                k.value: v
                for k, v in zip(node.args[-1].keys, node.args[-1].values, strict=False)
                if isinstance(k, ast.Constant)
            }
            type_val = keys.get("type")
            if isinstance(type_val, ast.Constant) and type_val.value == "response_complete":
                terminal_frames.append(keys)
    assert terminal_frames, "handle_intent must send a response_complete frame"

    computed_frames = 0
    for keys in terminal_frames:
        executed = keys.get("executed")
        assert executed is not None, "terminal frame must carry executed"
        assert not (
            isinstance(executed, ast.Constant) and executed.value is True
        ), "executed must never be a hardcoded True claim"
        if isinstance(executed, ast.Name) and executed.id == "executed":
            computed_frames += 1
            for required in ("stepsUsed", "toolCalls", "boundedStop"):
                assert required in keys, f"computed terminal frame must carry {required}"
    assert computed_frames >= 1, (
        "the main-path terminal frame must report the computed honest flag"
    )


def test_handler_has_no_execution_primitive():
    handler = _find_function(_tree(), "handle_intent")
    called: list[str] = []
    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.append(func.id)
            elif isinstance(func, ast.Attribute):
                prefix = ""
                if isinstance(func.value, ast.Name):
                    prefix = f"{func.value.id}."
                elif isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
                    prefix = f"{func.value.value.id}.{func.value.attr}."
                called.append(f"{prefix}{func.attr}")
    offenders = sorted(set(called) & EXECUTION_PRIMITIVES)
    assert not offenders, f"handle_intent must not execute anything itself, found {offenders}"


def test_routing_goes_through_the_governed_loop():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "run_stream" in source, "the handler must consume the ReAct event stream"
    assert "_voice_agent_loop" in source, "the loop must come from the injectable seam"
    assert "agent_chat_loop" in source, "the loop is core.agent_chat_loop.AgentChatLoop"


# ── functional checks (offline, fake loop) ───────────────────────────────────

_CORE = Path(__file__).resolve().parents[1] / "core"


def _import_voice_module():
    import importlib

    core_str = str(_CORE)
    if core_str not in sys.path:
        sys.path.insert(0, core_str)
    try:
        return importlib.import_module("core.api.routes.websocket_voice")
    except Exception:
        pytest.skip("websocket_voice module deps unavailable in this environment")


class FakeWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.frames.append(payload)


class ScriptedLoop:
    """Stands in for ``AgentChatLoop.run_stream`` — scripted honest events."""

    def __init__(self, events: list[dict[str, Any]], raises: Exception | None = None):
        self.events = list(events)
        self.raises = raises
        self.kwargs: dict[str, Any] | None = None

    async def run_stream(self, **kwargs):
        self.kwargs = kwargs
        for event in self.events:
            yield event
        if self.raises is not None:
            raise self.raises


@pytest.mark.asyncio
async def test_real_answer_streams_with_honest_flags(monkeypatch):
    mod = _import_voice_module()
    loop = ScriptedLoop(
        [
            {"type": "meta", "toolsEnabled": True, "availableTools": ["check_system_health"]},
            {"type": "content_delta", "delta": "সিস্টেম ঠিক আছে"},
            {"type": "final", "answer": "সিস্টেম ঠিক আছে", "stepsUsed": 0, "boundedStop": False},
        ]
    )
    monkeypatch.setattr(mod, "_voice_agent_loop", lambda: loop)
    ws = FakeWebSocket()

    await mod.handle_intent("সিস্টেম হেলথ দেখো", ws, start_time=0.0, user_id="voice-user")

    assert loop.kwargs is not None
    assert loop.kwargs["tenant_id"] == "voice-user"
    chunks = [f for f in ws.frames if f["type"] == "response_chunk"]
    terminal = [f for f in ws.frames if f["type"] == "response_complete"]
    assert chunks and "".join(c["text"] for c in chunks) == "সিস্টেম ঠিক আছে"
    assert terminal, "the turn must end with a response_complete frame"
    for frame in ws.frames:
        assert frame["simulated"] is False, "real routing — never flagged simulated"
        assert frame["surface"] == "voice_agent"
    assert terminal[0]["executed"] is True
    assert terminal[0]["stepsUsed"] == 0


@pytest.mark.asyncio
async def test_tool_progress_is_forwarded_as_agent_events(monkeypatch):
    mod = _import_voice_module()
    loop = ScriptedLoop(
        [
            {"type": "tool_call", "step": 1, "tool": "check_system_health", "args": {}},
            {"type": "tool_result", "step": 1, "tool": "check_system_health", "executed": True, "status": "ok", "observation": "all green"},
            {"type": "content_delta", "delta": "All green."},
            {"type": "final", "answer": "All green.", "stepsUsed": 1, "boundedStop": False},
        ]
    )
    monkeypatch.setattr(mod, "_voice_agent_loop", lambda: loop)
    ws = FakeWebSocket()

    await mod.handle_intent("how is the system?", ws, start_time=0.0, user_id="u1")

    agent_events = [f for f in ws.frames if f["type"] == "agent_event"]
    assert [e["event"]["type"] for e in agent_events] == ["tool_call", "tool_result"]
    terminal = [f for f in ws.frames if f["type"] == "response_complete"][0]
    assert terminal["stepsUsed"] == 1
    assert terminal["toolCalls"] == [{"step": 1, "tool": "check_system_health"}]
    assert terminal["executed"] is True


@pytest.mark.asyncio
async def test_broken_loop_answers_honestly_never_fabricates(monkeypatch):
    mod = _import_voice_module()
    loop = ScriptedLoop([], raises=RuntimeError("provider down"))
    monkeypatch.setattr(mod, "_voice_agent_loop", lambda: loop)
    ws = FakeWebSocket()

    await mod.handle_intent("book the ticket", ws, start_time=0.0, user_id="u1")

    terminal = [f for f in ws.frames if f["type"] == "response_complete"][0]
    assert terminal["executed"] is False, "a broken loop must never claim execution"
    assert terminal.get("error"), "the failure must be named honestly"
    text = "".join(f["text"] for f in ws.frames if f["type"] == "response_chunk")
    assert "could not complete" in text
    assert "booked" not in text.lower()


@pytest.mark.asyncio
async def test_empty_transcript_is_honest_and_skips_the_loop(monkeypatch):
    mod = _import_voice_module()
    loop = ScriptedLoop([])
    monkeypatch.setattr(mod, "_voice_agent_loop", lambda: loop)
    ws = FakeWebSocket()

    await mod.handle_intent("   ", ws, start_time=0.0, user_id="u1")

    assert loop.kwargs is None, "an empty transcript must not reach the agent loop"
    terminal = [f for f in ws.frames if f["type"] == "response_complete"][0]
    assert terminal["executed"] is False
    assert terminal["intent"] == "empty_audio"


@pytest.mark.asyncio
async def test_missing_answer_from_loop_is_honest(monkeypatch):
    mod = _import_voice_module()
    # The loop "finished" but streamed nothing — the handler must not pretend.
    loop = ScriptedLoop([{"type": "final", "answer": "", "stepsUsed": 2, "boundedStop": True}])
    monkeypatch.setattr(mod, "_voice_agent_loop", lambda: loop)
    ws = FakeWebSocket()

    await mod.handle_intent("check the notice", ws, start_time=0.0, user_id="u1")

    terminal = [f for f in ws.frames if f["type"] == "response_complete"][0]
    assert terminal["executed"] is False
    assert terminal["boundedStop"] is True
    text = "".join(f["text"] for f in ws.frames if f["type"] == "response_chunk")
    assert "could not complete" in text


@pytest.mark.asyncio
async def test_voice_system_note_is_prepended(monkeypatch):
    mod = _import_voice_module()
    loop = ScriptedLoop(
        [{"type": "final", "answer": "ok", "stepsUsed": 0, "boundedStop": False}]
    )
    monkeypatch.setattr(mod, "_voice_agent_loop", lambda: loop)
    ws = FakeWebSocket()

    await mod.handle_intent("hello", ws, start_time=0.0, user_id="u1")

    messages = loop.kwargs["messages"]
    assert messages[0]["role"] == "system" and "SPEAKING" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "hello"}
