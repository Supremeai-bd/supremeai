"""Free-tier evidence is exact, expires, and never comes from a paid inference probe."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from gateway.service import app as edge
from gateway.service import free_model_discovery as discovery
from gateway.service.free_route_policy import POLICY_ENV, approved_models
from gateway.service.pool import KeySlot, ProviderKeyPool
from gateway.service.providers import adapters

MODEL = "vendor/fixture:free"
KEY = "fixture-provider-secret"
BASE = adapters.PROVIDER_CONFIGS["openrouter"]["base_url"]
ZERO = {"prompt": "0", "completion": "0.0"}


def _approve(monkeypatch, provider="openrouter", **overrides):
    entry = {
        "provider": provider,
        "base_url": adapters.PROVIDER_CONFIGS[provider]["base_url"],
        "key_sha256": hashlib.sha256(KEY.encode()).hexdigest(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "models": [MODEL],
    }
    monkeypatch.setenv(POLICY_ENV, json.dumps([{**entry, **overrides}]))


def test_approval_binds_credential_origin_and_model(monkeypatch):
    _approve(monkeypatch)
    assert approved_models("openrouter", BASE, KEY) == (MODEL,)
    assert approved_models("openrouter", BASE, "rotated-key") == ()
    assert approved_models("openrouter", BASE + "/next", KEY) == ()
    assert approved_models("kilo", BASE, KEY) == ()


@pytest.mark.parametrize("override", [
    {"expires_at": "2000-01-01T00:00:00Z"},
    {"expires_at": "2099-01-01T00:00:00"},
    {"models": ["openrouter/free"]},
    {"models": ["kilo-auto/efficient"]},
    {"base_url": "http://example.invalid"},
    {"base_url": "https://example.invalid/api?flag=1"},
])
def test_unproven_approval_is_ineligible(monkeypatch, override):
    _approve(monkeypatch, **override)
    assert approved_models("openrouter", BASE, KEY) == ()


@pytest.mark.parametrize("item", [
    MODEL,
    {"id": MODEL},
    {"id": MODEL, "pricing": {"prompt": "0"}},
    {"id": MODEL, "pricing": {**ZERO, "completion": "0.00001"}},
    {"id": MODEL, "pricing": {**ZERO, "request": "0.0001"}},
    {"id": MODEL, "pricing": {**ZERO, "image": None}},
    {"id": "openrouter/free", "pricing": ZERO},
])
def test_price_record_must_confirm_concrete_zero_cost(item):
    assert discovery._extract_free_aggregator_model(item) is None


@pytest.mark.asyncio
async def test_catalog_refresh_uses_same_origin_and_only_approved_zero_price_models(monkeypatch):
    withdrawn = "vendor/withdrawn:free"
    _approve(monkeypatch, models=[MODEL, withdrawn])
    slot = KeySlot("fixture-slot", KEY, "openrouter")
    assert adapters.eligible_chat_models("openrouter", KEY, slot) == ()
    transport = Mock(return_value=httpx.Response(200, json={"data": [
        {"id": "vendor/other:free", "pricing": ZERO},
        {"id": withdrawn, "pricing": {**ZERO, "image": "1"}},
        {"id": MODEL, "pricing": ZERO},
    ]}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        await discovery.validate_slot(slot, client)
        transport.assert_called_once()
        request = transport.call_args.args[0]
        assert request.method == "GET" and str(request.url) == BASE + "/models"
        assert adapters.eligible_chat_models("openrouter", KEY, slot) == (MODEL,)
        monkeypatch.delenv(POLICY_ENV)
        await discovery.validate_slot(slot, client)
        assert transport.call_count == 1
        assert adapters.eligible_chat_models("openrouter", KEY, slot) == ()


@pytest.mark.asyncio
async def test_stale_or_failed_catalog_is_not_routes_evidence(monkeypatch):
    _approve(monkeypatch)
    slot = KeySlot("fixture-slot", KEY, "openrouter", discovered_models=[MODEL])
    slot.catalog_identity = (BASE, hashlib.sha256(KEY.encode()).hexdigest())
    assert adapters.eligible_chat_models("openrouter", KEY, slot) == ()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        await discovery.validate_slot(slot, client)
    assert adapters.eligible_chat_models("openrouter", KEY, slot) == ()


def test_pool_deduplicates_credential_aliases(monkeypatch):
    monkeypatch.setenv("FIXTURE_KEY", KEY)
    monkeypatch.setenv("FIXTURE_KEY_BACKUP", KEY)
    monkeypatch.setenv("FIXTURE_KEYS", f"{KEY},fixture-other-secret")
    pool = ProviderKeyPool("groq", ["FIXTURE_KEY", "FIXTURE_KEYS"])
    assert {slot.key for slot in pool.slots} == {KEY, "fixture-other-secret"}
    assert len(pool.slots) == 2


@pytest.mark.asyncio
async def test_only_one_refresh_task_runs_and_shutdown_cancels_it(monkeypatch):
    started = asyncio.Event()
    refresh = AsyncMock(side_effect=lambda: None)

    async def loop(_squad):
        await refresh()
        started.set()
        await asyncio.Future()

    monkeypatch.setattr(discovery, "discovery_loop", loop)
    monkeypatch.setattr(edge, "hydrate_vault_secrets", AsyncMock())
    monkeypatch.setattr(edge, "close_stealth_client", AsyncMock())
    await edge._on_startup()
    await asyncio.wait_for(started.wait(), timeout=1)
    task = edge.app.state.discovery_task
    await edge._close_stealth_http_client()
    refresh.assert_awaited_once()
    assert task.cancelled() and edge.app.state.discovery_task is None


@pytest.mark.asyncio
async def test_catalog_pass_cancels_a_stuck_refresh(monkeypatch):
    slot = KeySlot("fixture-slot", KEY, "openrouter")
    cancelled = asyncio.Event()

    async def stuck(*_):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    monkeypatch.setattr(discovery, "validate_slot", stuck)
    monkeypatch.setattr(discovery, "REFRESH_DEADLINE_S", 0.05)
    await discovery.run_discovery(SimpleNamespace(pools={"openrouter": SimpleNamespace(slots=[slot])}))
    assert cancelled.is_set()
