"""Autonomous ReAct chat loop — unit + HTTP contract tests (offline).

The loop (``core.agent_chat_loop.AgentChatLoop``) is the M09 P-C piece that
turns chat into governed action. This suite pins:

* flag-off = plain chat mode — no decision theater, honest meta;
* direct answers (decider → ``done``) never touch tools;
* one governed round-trip: tool_call → three-gate execution → observation
  fed back into the next decision context → streamed synthesis;
* the tenant allowlist holds at the loop level too (``tenant_blocked``,
  never executed);
* policy-blocked tools stay honest (R5 refusal, no execution);
* ``max_steps`` bounds the loop (``boundedStop``) — infinite ReAct is
  structurally impossible;
* synthesis failure is honest (an ``error`` event, never a fabricated answer);
* ``POST /api/agent/chat`` JSON and ``POST /api/agent/stream`` SSE contracts,
  including the terminal ``[DONE]`` frame and payload validation.

Everything runs offline: the decider and the LLM gateway are injected fakes.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

STUB = {"sub": "loop-test-user", "tenant_id": "tenant-a", "role": "user"}


@pytest.fixture(autouse=True)
def _hermetic_memory_store(tmp_path, monkeypatch):
    """Keep the passive UserMemoryGraph absorb (M10) out of the repo tree.

    The loop now absorbs chat text best-effort into the per-tenant memory
    graph; pointing the store dir at tmp_path keeps every test here hermetic
    without touching the feature's default-on production behaviour.
    """
    monkeypatch.setenv("SUPREMEAI_MEMORY_GRAPH_DIR", str(tmp_path / "memory_graph"))
    yield


class FakeDecider:
    """Scripted stand-in for ``ReasoningOrchestrator.decide``."""

    def __init__(self, script: list[dict[str, Any]] | None = None):
        self.script = list(script or [])
        self.calls: list[dict[str, Any]] = []

    async def decide(self, task, context=None, tools=None):
        self.calls.append({"task": task, "tools": list(tools or []), "context": context})
        if self.script:
            return self.script.pop(0)
        return {"tool": "done", "args": {}, "thought": "script exhausted", "source": "fake"}


class EndlessToolDecider:
    """Always wants a tool — proves the step budget is structural, not polite."""

    async def decide(self, task, context=None, tools=None):
        return {
            "tool": "check_system_health",
            "args": {},
            "thought": "always another tool",
            "source": "fake",
        }


class FakeLLM:
    """Stand-in for ``LLMGateway.acompletion`` (stream + non-stream)."""

    def __init__(self, chunks: tuple[str, ...] = ("সুপ্রিম", " উত্তর"), fail: bool = False):
        self.chunks = list(chunks)
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def acompletion(self, prompt=None, context=None, stream=False, model=None, **kwargs):
        self.calls.append(
            {"prompt": prompt, "stream": stream, "context": context, "model": model}
        )
        if self.fail:
            raise RuntimeError("provider down")

        if stream:
            async def _gen():
                for chunk in self.chunks:
                    yield chunk

            return _gen()

        return {"success": True, "text": "".join(self.chunks), "model": "fake"}


def make_loop(decider, llm):
    from core.agent_chat_loop import AgentChatLoop

    return AgentChatLoop(decider=decider, llm=llm)


async def collect(loop, **kwargs):
    return [event async for event in loop.run_stream(**kwargs)]


def _conversation():
    return [{"role": "user", "content": "আজকের সিস্টেম হেলথ দেখো"}]


# ── loop units ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plain_chat_mode_when_flag_off(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    decider = FakeDecider()  # must never be consulted
    llm = FakeLLM()
    events = await collect(
        make_loop(decider, llm), messages=_conversation(), tenant_id="tenant-a"
    )

    meta = events[0]
    assert meta["type"] == "meta"
    assert meta["toolsEnabled"] is False
    assert meta["availableTools"] == []
    assert decider.calls == [], "flag-off must skip the decision phase entirely"
    assert not any(e["type"] in {"tool_call", "tool_result"} for e in events)

    deltas = "".join(e["delta"] for e in events if e["type"] == "content_delta")
    assert deltas == "সুপ্রিম উত্তর"
    final = events[-1]
    assert final["type"] == "final"
    assert final["answer"] == deltas
    assert final["stepsUsed"] == 0
    assert final["boundedStop"] is False


@pytest.mark.asyncio
async def test_direct_answer_without_tool(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    decider = FakeDecider(
        [{"tool": "done", "args": {}, "thought": "no tool needed", "source": "fake"}]
    )
    events = await collect(
        make_loop(decider, FakeLLM()), messages=_conversation(), tenant_id="tenant-a"
    )

    meta = events[0]
    assert meta["toolsEnabled"] is True
    assert "check_system_health" in meta["availableTools"]
    thoughts = [e for e in events if e["type"] == "thought"]
    assert len(thoughts) == 1 and thoughts[0]["source"] == "fake"
    assert not any(e["type"] in {"tool_call", "tool_result"} for e in events)
    # The decider only ever sees tenant-allowlisted tools.
    assert decider.calls[0]["tools"] == meta["availableTools"]


@pytest.mark.asyncio
async def test_one_governed_tool_round_trip(monkeypatch):
    import core.tools.agent_tools as agent_tools

    async def fake_search(query: str) -> str:
        return f"Found 1 record matching {query!r}"

    fake_search.__name__ = "search_database"
    monkeypatch.setattr(
        agent_tools, "SUPREME_TOOLS", [fake_search, *agent_tools.SUPREME_TOOLS[1:]]
    )
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")

    decider = FakeDecider(
        [
            {
                "tool": "search_database",
                "args": {"query": "invoice"},
                "thought": "need data",
                "source": "fake",
            },
            {"tool": "done", "args": {}, "thought": "have data", "source": "fake"},
        ]
    )
    llm = FakeLLM()
    events = await collect(
        make_loop(decider, llm),
        messages=[{"role": "user", "content": "find invoices"}],
        tenant_id="tenant-a",
    )

    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e for e in events if e["type"] == "tool_result"]
    assert calls[0]["tool"] == "search_database"
    assert calls[0]["args"] == {"query": "invoice"}
    assert results[0]["executed"] is True
    assert results[0]["status"] == "ok"
    assert "invoice" in results[0]["observation"]

    # ReAct memory: the observation reached the next decision context.
    assert "Found 1 record matching 'invoice'" in json.dumps(decider.calls[-1]["context"])
    # And the synthesis prompt is grounded in the same observation.
    assert "Found 1 record matching 'invoice'" in llm.calls[0]["prompt"]

    final = events[-1]
    assert final["type"] == "final"
    assert final["stepsUsed"] == 1
    assert final["toolCalls"][0]["status"] == "ok"


@pytest.mark.asyncio
async def test_tool_outside_tenant_allowlist_never_executes(monkeypatch):
    import core.tools.agent_tools as agent_tools

    executed = {"count": 0}

    async def forbidden_search(query: str) -> str:
        executed["count"] += 1
        return "should never run"

    forbidden_search.__name__ = "search_database"
    monkeypatch.setattr(
        agent_tools, "SUPREME_TOOLS", [forbidden_search, *agent_tools.SUPREME_TOOLS[1:]]
    )
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOL_ALLOWLIST", '{"tenant-a": ["check_system_health"]}')

    decider = FakeDecider(
        [
            {"tool": "search_database", "args": {"query": "x"}, "thought": "", "source": "fake"},
            {"tool": "done", "args": {}, "thought": "", "source": "fake"},
        ]
    )
    events = await collect(
        make_loop(decider, FakeLLM()), messages=_conversation(), tenant_id="tenant-a"
    )

    blocked = [e for e in events if e["type"] == "tool_result"]
    assert blocked[0]["status"] == "tenant_blocked"
    assert blocked[0]["executed"] is False
    assert "allowlist" in blocked[0]["reason"]
    assert executed["count"] == 0, "the governed registry function must never run"


@pytest.mark.asyncio
async def test_policy_blocked_tool_stays_honest(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv(
        "SUPREMEAI_AGENT_TOOL_ALLOWLIST",
        '{"tenant-a": ["check_system_health", "execute_python_code"]}',
    )
    decider = FakeDecider(
        [
            {
                "tool": "execute_python_code",
                "args": {"code": "1+1"},
                "thought": "",
                "source": "fake",
            },
            {"tool": "done", "args": {}, "thought": "", "source": "fake"},
        ]
    )
    events = await collect(
        make_loop(decider, FakeLLM()), messages=_conversation(), tenant_id="tenant-a"
    )

    result = [e for e in events if e["type"] == "tool_result"][0]
    assert result["executed"] is False
    assert result["status"] == "policy_blocked"
    assert result["risk"] == "R5"
    assert "approval" in result["reason"]


@pytest.mark.asyncio
async def test_max_steps_bounds_the_loop(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    llm = FakeLLM()
    events = await collect(
        make_loop(EndlessToolDecider(), llm),
        messages=_conversation(),
        tenant_id="tenant-a",
        max_steps=3,
    )

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) == 3, "each budgeted step may execute exactly one tool"
    final = events[-1]
    assert final["boundedStop"] is True
    assert final["stepsUsed"] == 3
    # The synthesis prompt must tell the model the budget ran out — no pretending.
    assert "budget was exhausted" in llm.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_hard_max_steps_cap_cannot_be_exceeded(monkeypatch):
    from core.agent_chat_loop import HARD_MAX_STEPS

    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    events = await collect(
        make_loop(EndlessToolDecider(), FakeLLM()),
        messages=_conversation(),
        tenant_id="tenant-a",
        max_steps=50,  # beyond the hard cap
    )
    assert len([e for e in events if e["type"] == "tool_call"]) == HARD_MAX_STEPS


@pytest.mark.asyncio
async def test_synthesis_failure_is_honest(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    events = await collect(
        make_loop(FakeDecider(), FakeLLM(fail=True)),
        messages=_conversation(),
        tenant_id="tenant-a",
    )

    errors = [e for e in events if e["type"] == "error"]
    assert errors, "a broken synthesis must surface an error event"
    final = events[-1]
    assert final["type"] == "final"
    assert final["answer"] == "", "no fabricated answer may appear when synthesis failed"


@pytest.mark.asyncio
async def test_run_collects_the_full_turn(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    decider = FakeDecider(
        [{"tool": "done", "args": {}, "thought": "", "source": "fake"}]
    )
    result = await make_loop(decider, FakeLLM()).run(
        messages=_conversation(), tenant_id="tenant-a", max_steps=2
    )

    assert result["answer"] == "সুপ্রিম উত্তর"
    assert result["meta"]["tenantId"] == "tenant-a"
    assert result["stepsUsed"] == 0
    assert result["toolCalls"] == []
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_empty_messages_fail_fast_and_honestly(monkeypatch):
    events = await collect(make_loop(FakeDecider(), FakeLLM()), messages=[], tenant_id="*")
    assert events[0]["type"] == "error"
    assert events[-1]["type"] == "final"
    assert events[-1]["answer"] == ""


# ── HTTP contracts ───────────────────────────────────────────────────────────


class StubLoop:
    """Route-level stub — the HTTP contract must not need real collaborators."""

    def __init__(self, events: list[dict[str, Any]]):
        self.events = list(events)
        self.kwargs: dict[str, Any] | None = None

    async def run(self, **kwargs):
        self.kwargs = kwargs
        answer = "".join(
            e.get("delta", "") for e in self.events if e["type"] == "content_delta"
        )
        final = next((e for e in self.events if e["type"] == "final"), {})
        return {
            "answer": answer,
            "toolCalls": [],
            "meta": {"tenantId": "tenant-a"},
            "stepsUsed": final.get("stepsUsed", 0),
            "boundedStop": False,
            "errors": [],
        }

    async def run_stream(self, **kwargs):
        self.kwargs = kwargs
        for event in self.events:
            yield event


@pytest_asyncio.fixture
async def client(monkeypatch):
    from api.deps import get_current_user_token
    from api.routes import agent_tools as routes

    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user_token] = lambda: STUB
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, routes
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stream_route_sse_contract(client, monkeypatch):
    http, routes = client
    events = [
        {"type": "meta", "tenantId": "tenant-a", "toolsEnabled": False, "availableTools": []},
        {"type": "content_delta", "delta": "হ্যালো"},
        {"type": "final", "answer": "হ্যালো", "stepsUsed": 0, "toolCalls": [], "boundedStop": False},
    ]
    stub = StubLoop(events)
    monkeypatch.setattr(routes, "_new_agent_chat_loop", lambda: stub)

    resp = await http.post(
        "/api/agent/stream", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["x-accel-buffering"] == "no"

    frames = [line[6:] for line in resp.text.splitlines() if line.startswith("data: ")]
    assert frames[-1] == "[DONE]", "the stream must end with the terminal DONE frame"
    parsed = [json.loads(frame) for frame in frames[:-1]]
    assert [p["type"] for p in parsed] == ["meta", "content_delta", "final"]
    # Tenant attribution flows from the auth token into the loop.
    assert stub.kwargs["tenant_id"] == "tenant-a"
    assert stub.kwargs["model"] == "auto"
    assert stub.kwargs["max_steps"] == 5


@pytest.mark.asyncio
async def test_chat_route_json_contract(client, monkeypatch):
    http, routes = client
    stub = StubLoop(
        [
            {"type": "content_delta", "delta": "সব ঠিক আছে"},
            {"type": "final", "answer": "সব ঠিক আছে", "stepsUsed": 0},
        ]
    )
    monkeypatch.setattr(routes, "_new_agent_chat_loop", lambda: stub)

    resp = await http.post(
        "/api/agent/chat",
        json={
            "messages": [{"role": "user", "content": "স্ট্যাটাস দাও"}],
            "max_steps": 2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "সব ঠিক আছে"
    assert body["stepsUsed"] == 0
    assert body["meta"]["tenantId"] == "tenant-a"
    assert stub.kwargs["max_steps"] == 2


@pytest.mark.asyncio
async def test_route_payload_validation_is_tight(client):
    http, _routes = client

    resp = await http.post("/api/agent/chat", json={"messages": []})
    assert resp.status_code == 422

    resp = await http.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "x"}], "max_steps": 99},
    )
    assert resp.status_code == 422, "the hard max-steps cap is structural"

    resp = await http.post(
        "/api/agent/stream",
        json={"messages": [{"role": "hacker", "content": "x"}]},
    )
    assert resp.status_code == 422
