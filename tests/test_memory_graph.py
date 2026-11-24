"""UserMemoryGraph — deterministic extraction, store, briefing + HTTP contract.

The memory graph (``core.services.memory_graph``) is the personal-executive
memory (blueprint pillar 1): passive fact extraction from chat/voice, a
per-tenant local JSON store, and honest morning-briefing data. This suite pins:

* extraction is deterministic and zero-cost (no LLM): language ratio, sites,
  preferences, people, habits and tasks — বাংলা ও ইংরেজি দুটোই;
* absorb de-duplicates (count += 1) and honours the structural facts cap;
* corrupt store files degrade to an empty graph loudly, never silently lie;
* the kill-switch (``SUPREMEAI_MEMORY_GRAPH=false``) disables the surface
  honestly (``enabled: false`` answers, not 403s);
* user control: ``forget`` one fact, ``wipe`` the whole graph;
* briefing mirrors the user's language and only reports really-known facts;
* the agent chat loop's passive absorb hook never breaks the loop and is
  hermetic under the ``SUPREMEAI_MEMORY_GRAPH_DIR`` override.

Everything runs offline: no network, no Supabase, no model calls.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

STUB = {"sub": "memory-test-user", "tenant_id": "tenant-m", "role": "user"}


@pytest.fixture(autouse=True)
def _store_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEMORY_GRAPH_DIR", str(tmp_path / "memory_graph"))
    monkeypatch.delenv("SUPREMEAI_MEMORY_GRAPH", raising=False)
    yield


def _graph():
    from core.services import memory_graph

    return memory_graph


# ── deterministic extraction ─────────────────────────────────────────────────


def test_extraction_detects_bengali_language():
    facts = _graph().extract_facts("আমি প্রতিদিন সকালে ট্রেনের টিকিট চেক করি")
    kinds = {f["kind"] for f in facts}
    assert "language" in kinds
    assert next(f for f in facts if f["kind"] == "language")["value"] == "bn"
    assert any(f["kind"] == "habit" for f in facts)


def test_extraction_detects_english_language():
    facts = _graph().extract_facts("Please check the ticket site every morning at 9am")
    lang = next(f for f in facts if f["kind"] == "language")
    assert lang["value"] == "en"
    assert any(f["kind"] == "habit" for f in facts)


def test_extraction_pulls_sites_preferences_and_tasks():
    text = (
        "I prefer short answers. Check https://example.com/notice for updates.\n"
        "TODO: book the train ticket\n"
        "remind me to email Rahim"
    )
    facts = _graph().extract_facts(text)
    by_kind: dict[str, list[str]] = {}
    for f in facts:
        by_kind.setdefault(f["kind"], []).append(f["value"])
    assert any("example.com" in v for v in by_kind.get("site", []))
    assert by_kind["preference"], "English preference pattern must match"
    assert by_kind["task"], "TODO task must be captured"
    assert any("Rahim" in v for v in by_kind.get("person", []))


def test_extraction_is_deterministic_and_empty_safe():
    once = _graph().extract_facts("I prefer short answers")
    twice = _graph().extract_facts("I prefer short answers")
    assert once == twice
    assert _graph().extract_facts("") == []
    assert _graph().extract_facts("   ") == []


# ── store behaviour ──────────────────────────────────────────────────────────


def test_absorb_dedupes_and_counts():
    g = _graph()
    first = g.absorb_text("tenant-m", "I prefer dark mode", source="chat")
    assert first["enabled"] is True
    second = g.absorb_text("tenant-m", "I prefer dark mode", source="chat")

    graph = g.get_graph("tenant-m")
    prefs = [f for f in graph["facts"] if f["kind"] == "preference"]
    assert len(prefs) == 1, "the same fact must merge, not duplicate"
    assert prefs[0]["count"] == 2
    assert second["totalFacts"] == len(graph["facts"])
    assert second["absorbed"]


def test_absorb_respects_the_kill_switch(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEMORY_GRAPH", "false")
    result = _graph().absorb_text("tenant-m", "I prefer dark mode")
    assert result["enabled"] is False
    assert result["absorbed"] == []


def test_corrupt_store_degrades_loudly_to_empty_graph():
    from core.services.memory_graph import store_dir

    path = store_dir() / "tenant-m.json"
    path.write_text("{ this is not json", encoding="utf-8")

    graph = _graph().get_graph("tenant-m")
    assert graph["facts"] == []
    assert path.with_suffix(".json.corrupt").exists(), "the corrupt file must be preserved"


def test_forget_and_wipe_give_the_user_control():
    g = _graph()
    g.absorb_text("tenant-m", "I prefer dark mode")
    graph = g.get_graph("tenant-m")
    target = graph["facts"][0]["id"]

    assert g.forget_fact("tenant-m", target) is True
    assert g.forget_fact("tenant-m", target) is False, "second forget must be honest"

    g.absorb_text("tenant-m", "check https://example.com daily")
    assert g.wipe_graph("tenant-m") is True
    assert g.get_graph("tenant-m")["facts"] == []
    assert g.wipe_graph("tenant-m") is False


def test_tenant_slug_blocks_path_traversal():
    g = _graph()
    slug = g._tenant_slug("../../etc/passwd")
    assert "/" not in slug and ".." not in slug
    assert slug.startswith("t-")


def test_facts_cap_is_structural():
    g = _graph()
    for i in range(260):
        g.absorb_text("tenant-m", f"I prefer unique colour number {i}")
    graph = g.get_graph("tenant-m")
    assert len(graph["facts"]) <= g.MAX_FACTS


# ── morning briefing ─────────────────────────────────────────────────────────


def test_briefing_mirrors_known_language_and_only_known_facts():
    g = _graph()
    empty = g.morning_briefing("tenant-m", now=datetime(2026, 11, 25, 8, 0, 0))
    assert empty["enabled"] is True
    assert empty["hasMemory"] is False
    assert empty["greeting"].startswith("Good morning")  # no facts → English default

    g.absorb_text("tenant-m", "আমি প্রতিদিন সকালে ট্রেনের টিকিট চেক করি")
    g.absorb_text("tenant-m", "মনে করিয়ে দিও: ভাড়া জমা দিতে হবে")
    briefing = g.morning_briefing("tenant-m", now=datetime(2026, 11, 25, 8, 0, 0))

    assert briefing["greeting"].startswith("শুভ সকাল"), "Bengali facts → Bengali greeting"
    assert briefing["language"] == "bn"
    assert briefing["recentTasks"], "absorbed tasks must surface in the briefing"
    assert briefing["hasMemory"] is True


def test_briefing_honours_the_kill_switch(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEMORY_GRAPH", "false")
    briefing = _graph().morning_briefing("tenant-m")
    assert briefing["enabled"] is False
    assert briefing["recentTasks"] == []


# ── HTTP contract ────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    from api.deps import get_current_user_token
    from api.routes import memory_graph as routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user_token] = lambda: STUB
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_graph_routes_round_trip(client):
    resp = await client.post(
        "/api/memory/graph/absorb",
        json={"text": "I prefer concise answers about billing", "source": "manual"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True and body["absorbed"]

    resp = await client.get("/api/memory/graph")
    assert resp.status_code == 200
    graph = resp.json()
    assert graph["tenantId"] == "tenant-m"
    assert graph["facts"], "absorbed facts must be visible to their owner"

    fact_id = graph["facts"][0]["id"]
    resp = await client.post("/api/memory/graph/forget", json={"factId": fact_id})
    assert resp.status_code == 200 and resp.json()["removed"] is True

    resp = await client.delete("/api/memory/graph")
    assert resp.status_code == 200 and resp.json()["wiped"] is True


@pytest.mark.asyncio
async def test_briefing_route_contract(client):
    resp = await client.get("/api/memory/briefing")
    assert resp.status_code == 200
    body = resp.json()
    assert {"enabled", "greeting", "recentTasks", "topFacts", "hasMemory"} <= set(body)


@pytest.mark.asyncio
async def test_kill_switch_is_honest_on_every_route(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEMORY_GRAPH", "false")

    resp = await client.get("/api/memory/graph")
    assert resp.status_code == 200 and resp.json()["enabled"] is False

    resp = await client.post(
        "/api/memory/graph/absorb", json={"text": "anything", "source": "manual"}
    )
    assert resp.status_code == 200 and resp.json()["enabled"] is False

    resp = await client.get("/api/memory/briefing")
    assert resp.status_code == 200 and resp.json()["enabled"] is False


# ── agent chat loop hook ─────────────────────────────────────────────────────


class _FakeLLM:
    async def acompletion(self, prompt=None, context=None, stream=False, model=None, **kw):
        if stream:
            async def _gen():
                yield "ok"

            return _gen()
        return {"success": True, "text": "ok", "model": "fake"}


@pytest.mark.asyncio
async def test_agent_loop_absorbs_passively_and_never_breaks(monkeypatch):
    from core.agent_chat_loop import AgentChatLoop

    class _DoneDecider:
        async def decide(self, task, context=None, tools=None):
            return {"tool": "done", "args": {}, "thought": "", "source": "fake"}

    events = [
        event
        async for event in AgentChatLoop(decider=_DoneDecider(), llm=_FakeLLM()).run_stream(
            messages=[{"role": "user", "content": "I prefer short answers"}],
            tenant_id="tenant-m",
        )
    ]
    assert events[-1]["type"] == "final"
    graph = _graph().get_graph("tenant-m")
    assert graph["facts"], "the loop must feed the memory graph passively"


@pytest.mark.asyncio
async def test_agent_loop_survives_a_broken_memory_store(monkeypatch):
    from core.agent_chat_loop import AgentChatLoop

    class _DoneDecider:
        async def decide(self, task, context=None, tools=None):
            return {"tool": "done", "args": {}, "thought": "", "source": "fake"}

    def _boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("core.services.memory_graph.absorb_text", _boom)
    events = [
        event
        async for event in AgentChatLoop(decider=_DoneDecider(), llm=_FakeLLM()).run_stream(
            messages=[{"role": "user", "content": "hello"}],
            tenant_id="tenant-m",
        )
    ]
    assert events[-1]["type"] == "final", "memory failure must never break the chat turn"
    assert events[-1]["answer"] == "ok"


@pytest.mark.asyncio
async def test_agent_loop_skips_memory_for_wildcard_tenant(monkeypatch):
    from core.agent_chat_loop import AgentChatLoop

    class _DoneDecider:
        async def decide(self, task, context=None, tools=None):
            return {"tool": "done", "args": {}, "thought": "", "source": "fake"}

    calls: list[str] = []

    def _spy(tenant, text, source="chat"):
        calls.append(tenant)

    monkeypatch.setattr("core.services.memory_graph.absorb_text", _spy)
    async for _ in AgentChatLoop(decider=_DoneDecider(), llm=_FakeLLM()).run_stream(
        messages=[{"role": "user", "content": "hi"}], tenant_id="*"
    ):
        pass
    assert calls == [], "wildcard tenants must not write memory"
