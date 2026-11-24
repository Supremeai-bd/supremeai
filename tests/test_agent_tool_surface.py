"""Governed chat tool surface — manifest, per-tenant allowlist and execution.

The loop itself is covered by ``tests/test_tool_loop*.py``; this suite pins the
HTTP contract added in audit item ⑯:

* ``GET /api/agent/tools`` is honest when the flag is off (``enabled: false``,
  empty list, no error) and OpenAI-shaped when it is on;
* the per-tenant allowlist can only *narrow* what the MCP policy already allows
  (``execute_python_code`` stays unavailable even when explicitly allowed);
* ``POST /api/agent/tool-calls`` distinguishes surface errors (403/400) from
  runtime refusals (200 + ``executed: false`` + a reason the model can read);
* every governed tool has an OpenAI spec, and every spec names a real tool —
  drift in either direction fails here instead of silently vanishing.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

STUB = {"sub": "surface-test-user", "tenant_id": "tenant-a", "role": "user"}


@pytest_asyncio.fixture
async def client(monkeypatch):
    from api.deps import get_current_user_token
    from api.routes.agent_tools import router

    monkeypatch.delenv("SUPREMEAI_AGENT_TOOL_ALLOWLIST", raising=False)
    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    os.environ.pop("SUPREMEAI_AGENT_TOOLS", None)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_token] = lambda: STUB
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


# ── manifest ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_manifest_is_honest_when_flag_is_off(client):
    resp = await client.get("/api/agent/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["tools"] == []
    assert body["availableCount"] == 0
    assert body["flag"] == "SUPREMEAI_AGENT_TOOLS"


@pytest.mark.asyncio
async def test_manifest_lists_policy_allowed_tools_in_openai_shape(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    body = (await client.get("/api/agent/tools")).json()

    assert body["enabled"] is True
    assert body["allowlistSource"] == "default"
    names = [tool["function"]["name"] for tool in body["tools"]]
    assert names == sorted(names), "manifest must be deterministic"
    assert "search_database" in names
    assert "check_system_health" in names
    # R5 code execution is never auto-allowed, so the fail-closed default omits it.
    assert "execute_python_code" not in names

    entry = body["tools"][names.index("search_database")]
    assert entry["type"] == "function"
    assert entry["function"]["parameters"]["required"] == ["query"]
    assert entry["agent"]["available"] is True
    assert entry["agent"]["policy"] == "ALLOW"
    assert body["availableCount"] == len(names)


@pytest.mark.asyncio
async def test_allowlist_narrows_per_tenant_and_cannot_widen_policy(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv(
        "SUPREMEAI_AGENT_TOOL_ALLOWLIST",
        '{"tenant-a": ["search_database", "execute_python_code"]}',
    )
    body = (await client.get("/api/agent/tools")).json()

    assert body["allowlistSource"] == "tenant:tenant-a"
    by_name = {tool["function"]["name"]: tool for tool in body["tools"]}
    assert set(by_name) == {"search_database", "execute_python_code"}
    assert by_name["search_database"]["agent"]["available"] is True
    # Explicitly allowed, still not runnable: policy decides, the allowlist only narrows.
    assert by_name["execute_python_code"]["agent"]["available"] is False
    assert by_name["execute_python_code"]["agent"]["policy"] == "REQUIRE_APPROVAL"
    assert "approval" in by_name["execute_python_code"]["agent"]["reason"]
    assert body["availableCount"] == 1


@pytest.mark.asyncio
async def test_wildcard_entry_serves_tenants_without_their_own_entry(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOL_ALLOWLIST", '{"*": ["check_system_health"]}')
    body = (await client.get("/api/agent/tools")).json()

    assert body["allowlistSource"] == "wildcard"
    assert [t["function"]["name"] for t in body["tools"]] == ["check_system_health"]


@pytest.mark.asyncio
async def test_tenant_without_match_gets_no_tools(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOL_ALLOWLIST", '{"tenant-b": ["search_database"]}')
    body = (await client.get("/api/agent/tools")).json()

    assert body["tools"] == []
    assert body["allowlistSource"] == "deny:no-matching-tenant"


@pytest.mark.asyncio
async def test_malformed_allowlist_denies_everything_and_says_so(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOL_ALLOWLIST", "{not json")
    body = (await client.get("/api/agent/tools")).json()

    assert body["tools"] == []
    assert body["allowlistError"]
    assert body["allowlistSource"] == "error:deny-all"


@pytest.mark.asyncio
async def test_unknown_allowlist_entries_are_reported_not_swallowed(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv(
        "SUPREMEAI_AGENT_TOOL_ALLOWLIST",
        '{"tenant-a": ["search_database", "definitely_not_a_tool"]}',
    )
    body = (await client.get("/api/agent/tools")).json()

    assert body["ignoredAllowlistEntries"] == ["definitely_not_a_tool"]
    assert [t["function"]["name"] for t in body["tools"]] == ["search_database"]


# ── tool calls ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_is_refused_when_flag_is_off(client):
    resp = await client.post(
        "/api/agent/tool-calls", json={"tool": "search_database", "arguments": {"query": "x"}}
    )
    assert resp.status_code == 403
    assert "SUPREMEAI_AGENT_TOOLS" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_call_outside_the_allowlist_is_refused(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOL_ALLOWLIST", '{"tenant-a": ["check_system_health"]}')
    resp = await client.post(
        "/api/agent/tool-calls", json={"tool": "search_database", "arguments": {"query": "x"}}
    )
    assert resp.status_code == 403
    assert "allowlist" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_missing_required_argument_is_a_400(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    resp = await client.post("/api/agent/tool-calls", json={"tool": "search_database"})
    assert resp.status_code == 400
    assert "query" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_successful_call_returns_a_tool_message(client, monkeypatch):
    import core.tools.agent_tools as agent_tools

    async def fake_search(query: str) -> str:
        return f"Found 2 record(s) matching {query!r}"

    # The registry is keyed by fn.__name__, so keep the governed name.
    fake_search.__name__ = "search_database"

    # SUPREME_TOOLS is a list of function objects built at import time, so the
    # registry has to be replaced, not the module attribute.
    monkeypatch.setattr(
        agent_tools, "SUPREME_TOOLS", [fake_search, *agent_tools.SUPREME_TOOLS[1:]]
    )
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")

    resp = await client.post(
        "/api/agent/tool-calls",
        json={
            "tool": "search_database",
            "arguments": {"query": "invoice"},
            "tool_call_id": "call_1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "tool"
    assert body["tool_call_id"] == "call_1"
    assert body["name"] == "search_database"
    assert body["executed"] is True
    assert body["status"] == "ok"
    assert body["content"] == "Found 2 record(s) matching 'invoice'"
    assert body["tenantId"] == "tenant-a"


@pytest.mark.asyncio
async def test_policy_blocked_call_is_a_recoverable_tool_result(client, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv(
        "SUPREMEAI_AGENT_TOOL_ALLOWLIST", '{"tenant-a": ["execute_python_code"]}'
    )
    resp = await client.post(
        "/api/agent/tool-calls",
        json={"tool": "execute_python_code", "arguments": {"code": "1+1"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["executed"] is False
    assert body["status"] == "policy_blocked"
    assert body["risk"] == "R5"
    assert "approval" in body["content"]


# ── drift guard: specs <-> governed registry ────────────────────────────────


def test_every_governed_tool_has_a_spec_and_vice_versa(monkeypatch):
    from core.agent_tool_specs import SPECS_BY_NAME
    from core.tools.agent_tools import governed_tools

    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_TOOL_FLEET", "true")

    registry_names = {fn.__name__ for fn in governed_tools()}
    assert registry_names == set(SPECS_BY_NAME), (
        "governed registry and OpenAI specs drifted apart — add/remove the "
        "declaration in core/agent_tool_specs.py in the same commit"
    )
