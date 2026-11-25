"""Hermetic security & runtime regression suite for Waves 2–6 root-cause fixes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_browser_tools_enforce_owner_isolation_and_fail_closed():
    """Browser tools must NEVER fall back to a shared global owner_id."""
    from core.tools.agent_tools import CURRENT_TOOL_OWNER, _require_browser_owner

    # Default / wildcard must fail closed
    with pytest.raises(PermissionError):
        _require_browser_owner()

    tok_star = CURRENT_TOOL_OWNER.set("*")
    try:
        with pytest.raises(PermissionError):
            _require_browser_owner()
    finally:
        CURRENT_TOOL_OWNER.reset(tok_star)

    # Distinct tenants receive strictly distinct owner namespaces
    tok_a = CURRENT_TOOL_OWNER.set("tenant-alpha")
    try:
        owner_a = _require_browser_owner()
    finally:
        CURRENT_TOOL_OWNER.reset(tok_a)

    tok_b = CURRENT_TOOL_OWNER.set("tenant-bravo")
    try:
        owner_b = _require_browser_owner()
    finally:
        CURRENT_TOOL_OWNER.reset(tok_b)

    assert owner_a == "agent_exec:tenant-alpha"
    assert owner_b == "agent_exec:tenant-bravo"
    assert owner_a != owner_b


@pytest.mark.asyncio
async def test_agent_chat_loop_emits_approval_required_on_r2_browser_write(monkeypatch):
    """State-changing browser tools (R2) must emit explicit approval_required events."""
    from core.agent_chat_loop import AgentChatLoop

    monkeypatch.setenv("SUPREMEAI_AGENT_TOOLS", "true")
    monkeypatch.setenv("SUPREMEAI_TOOL_FLEET", "true")
    monkeypatch.setenv(
        "SUPREMEAI_AGENT_TOOL_ALLOWLIST",
        '{"tenant-a": ["browser_open", "browser_click"]}',
    )

    calls = 0

    class FakeDecider:
        async def decide(self, task, context=None, tools=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {
                    "tool": "browser_click",
                    "args": {"selector": "#submit-btn"},
                    "thought": "Need to submit form",
                    "source": "test",
                }
            return {"tool": "done", "thought": "Stopping for approval", "source": "test"}

    class FakeGateway:
        async def acompletion(self, *args, **kwargs):
            return {"text": "Awaiting your approval before clicking submit."}

    loop = AgentChatLoop(decider=FakeDecider(), llm=FakeGateway())
    events = []
    async for ev in loop.run_stream(
        messages=[{"role": "user", "content": "Click submit"}],
        tenant_id="tenant-a",
    ):
        events.append(ev)

    approval_events = [e for e in events if e.get("type") == "approval_required"]
    assert len(approval_events) == 1
    assert approval_events[0]["tool"] == "browser_click"
    assert approval_events[0]["risk"] == "R2"


def test_gateway_config_layers_require_operator_auth_and_allowlist(monkeypatch):
    """/api/v1/config/layers must reject unauthenticated callers and non-allowlisted keys."""
    from gateway.service import app as gw_mod
    from gateway.service import auth_verification as auth_mod

    monkeypatch.setattr(auth_mod, "OPERATOR_KEYS", frozenset({"test-super-secret-admin-key"}))
    monkeypatch.setattr(gw_mod, "OPERATOR_KEYS", frozenset({"test-super-secret-admin-key"}))
    client = TestClient(gw_mod.app)

    # Unauthenticated GET & POST must fail closed
    assert client.get("/api/v1/config/layers").status_code in (401, 403)
    assert (
        client.post("/api/v1/config/layers", json={"key": "default_model", "value": "gpt-4o"})
        .status_code
        in (401, 403)
    )

    headers = {"X-Admin-Key": "test-super-secret-admin-key"}
    # Arbitrary unknown key rejected
    bad = client.post(
        "/api/v1/config/layers",
        headers=headers,
        json={"key": "INJECTED_SECRET", "value": "evil"},
    )
    assert bad.status_code == 400

    # Valid operator override + read + rollback
    ok = client.post(
        "/api/v1/config/layers",
        headers=headers,
        json={"key": "rate_limit_per_minute", "value": 240},
    )
    assert ok.status_code == 200
    layers = client.get("/api/v1/config/layers", headers=headers).json()["layers"]
    assert layers["L3_dynamic_overrides"]["rate_limit_per_minute"] == 240
    assert layers["L4_effective"]["rate_limit_per_minute"] == 240

    rb = client.delete("/api/v1/config/layers/rate_limit_per_minute", headers=headers)
    assert rb.status_code == 200
    assert rb.json()["rolled_back"] is True


def test_dynamic_translation_validates_input_and_never_poisons_cache_on_fallback(monkeypatch):
    """/api/v1/localization/ai-translate rejects multiline dumps and avoids caching fallbacks."""
    from gateway.service import app as gw_mod

    monkeypatch.setattr(gw_mod.squad, "get_candidate_slots", lambda *a, **kw: [])
    client = TestClient(gw_mod.app)

    # Seeded Bengali UI key resolves from memory in 0ms
    seeded = client.post(
        "/api/v1/localization/ai-translate",
        json={"key": "settings", "target_lang": "bn"},
    )
    assert seeded.status_code == 200
    assert seeded.json()["translation"] == "সেটিংস"
    assert seeded.json()["cached"] is True

    # Multiline chat text rejected (400)
    multiline = client.post(
        "/api/v1/localization/ai-translate",
        json={"key": "line1\nprivate user chat message", "target_lang": "bn"},
    )
    assert multiline.status_code == 400

    # Uncached phrase with 0 provider keys returns honest fallback without poisoning cache
    probe_key = "Unique Uncached Button Label"
    miss = client.post(
        "/api/v1/localization/ai-translate",
        json={"key": probe_key, "target_lang": "es"},
    )
    assert miss.status_code == 200
    assert miss.json()["fallback"] is True
    assert ("es", probe_key) not in gw_mod._LOCAL_TRANSLATION_CACHE


def test_memory_briefing_gateway_proxy_requires_auth():
    """Gateway /api/memory/briefing proxy must reject unauthenticated callers."""
    from gateway.service.app import app

    client = TestClient(app)
    resp = client.get("/api/memory/briefing")
    assert resp.status_code == 401
