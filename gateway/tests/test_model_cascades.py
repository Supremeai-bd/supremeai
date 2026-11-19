"""An approved model cascade is bounded to the selected credential and lane."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from gateway.service.free_route_policy import ApprovedRoute
from gateway.service.pool import FederationSquad, KeySlot
from gateway.service.providers import adapters
from gateway.service.route_arbiter import DynamicRouteArbiter


@pytest.fixture(autouse=True)
def _approval(monkeypatch):
    monkeypatch.setattr(adapters, "approved_route", lambda provider, url, _key, **_kw: ApprovedRoute((provider, url, "fixture-tag"), ("first-approved", "second-approved")))
    monkeypatch.setattr(adapters, "_PAID_MODELS", set())


@pytest.mark.parametrize("status", [400, 402, 404, 429, 503])
@pytest.mark.asyncio
async def test_cascade_only_to_approved_alternate(monkeypatch, status):
    posted = Mock(side_effect=[
        httpx.Response(status),
        httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
    ])
    @asynccontextmanager
    async def client(_timeout):
        async with httpx.AsyncClient(transport=httpx.MockTransport(posted)) as client:
            yield client

    monkeypatch.setattr(adapters, "_pooled_http_client", client)
    status_code, body = await adapters.forward_chat_completion(
        provider="groq", api_key="fixture-key",
        payload={"model": "not-approved", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert status_code == 200 and body["model"] == "second-approved"
    assert [json.loads(call.args[0].content)["model"] for call in posted.call_args_list] == ["first-approved", "second-approved"]


@pytest.mark.asyncio
async def test_model_exhaustion_does_not_reset_unsupported_set(monkeypatch):
    slot = KeySlot("fixture-slot", "fixture-key", "groq", unsupported_models={"first-approved", "second-approved"})
    transport = AsyncMock()
    monkeypatch.setattr(adapters, "_pooled_http_client", transport)
    payload = {"model": "first-approved", "messages": [{"role": "user", "content": "hi"}]}
    status, _ = await adapters.forward_chat_completion("groq", slot.key, payload, slot=slot)
    events = [item async for item in adapters.stream_chat_completion_events("groq", slot.key, payload, slot=slot)]
    assert status == 503 and events[0][0] == "error" and events[0][1]["status"] == 503
    assert slot.unsupported_models == {"first-approved", "second-approved"}
    transport.assert_not_called()


def test_jules_key_discovery_does_not_confer_approval(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-gemini-a")
    monkeypatch.setenv("JULES_API_KEY", "fixture-gemini-b")
    monkeypatch.setattr(adapters, "approved_route", lambda *_, **_kw: None)
    squad = FederationSquad()
    assert {s.name for s in squad.pools["gemini"].slots} == {"GEMINI_API_KEY", "JULES_API_KEY"}
    assert squad.get_candidate_slots("gemini") == []


def test_route_arbiter_prioritizes_preferred_approved_provider(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fixture-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-gemini")
    squad = FederationSquad()
    squad.pools["groq"].slots[0].ewma_latency_ms = 50
    squad.pools["gemini"].slots[0].ewma_latency_ms = 5
    decision = DynamicRouteArbiter(squad=squad).choose_best_route(
        requested_model="supreme-core", preferred_provider="groq", adaptive_routes={}, stealth_available=False,
    )
    assert [provider for provider, _ in decision.candidate_slots] == ["groq", "gemini"]
