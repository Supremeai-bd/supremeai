"""Free-tier evidence is exact, expires, and never comes from a paid inference probe."""

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from gateway.service import app as edge
from gateway.service import free_model_discovery as discovery
from gateway.service.free_route_policy import HMAC_KEY_ENV, POLICY_ENV, approved_route, credential_identity
from gateway.service.pool import KeySlot, ProviderKeyPool
from gateway.service.providers import adapters

MODEL = "vendor/fixture:free"
KEY = "fixture-provider-secret"
BINDING_KEY = bytes(range(32)).hex()
BASE = adapters.PROVIDER_CONFIGS["openrouter"]["base_url"]
ZERO = {"prompt": "0", "completion": "0.0"}


def _approve(monkeypatch, provider="openrouter", *, binding_key=BINDING_KEY, **overrides):
    monkeypatch.setenv(HMAC_KEY_ENV, binding_key)
    base_url = adapters.PROVIDER_CONFIGS[provider]["base_url"]
    identity = credential_identity(provider, base_url, KEY)
    assert identity is not None
    entry = {
        "provider": provider,
        "base_url": base_url,
        "key_hmac_sha256": identity[2],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "models": [MODEL],
    }
    monkeypatch.setenv(POLICY_ENV, json.dumps([{**entry, **overrides}]))


def test_approval_binds_credential_origin_and_model(monkeypatch):
    _approve(monkeypatch)
    route = approved_route("openrouter", BASE, KEY)
    assert route is not None and route.models == (MODEL,)
    assert approved_route("openrouter", BASE, "rotated-key") is None
    assert approved_route("openrouter", BASE + "/next", KEY) is None
    assert approved_route("kilo", BASE, KEY) is None

    payload = json.dumps(["openrouter", BASE, KEY], separators=(",", ":")).encode()
    expected = hmac.new(bytes.fromhex(BINDING_KEY), b"supremeai:free-route:v1\x00" + payload, "sha256").hexdigest()
    assert credential_identity("openrouter", BASE + "/", KEY) == ("openrouter", BASE, expected)


def test_legacy_sha_only_approval_never_authorizes(monkeypatch):
    monkeypatch.setenv(HMAC_KEY_ENV, BINDING_KEY)
    monkeypatch.setenv(POLICY_ENV, json.dumps([{
        "provider": "openrouter", "base_url": BASE, "models": [MODEL],
        "key_sha256": hashlib.sha256(KEY.encode()).hexdigest(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }]))
    assert approved_route("openrouter", BASE, KEY) is None


@pytest.mark.parametrize("binding_key", [None, "invalid-hex", "ab" * 31, "cd" * 32])
def test_missing_invalid_or_rotated_binding_key_disables_approval(monkeypatch, binding_key):
    _approve(monkeypatch)
    if binding_key is None:
        monkeypatch.delenv(HMAC_KEY_ENV)
    else:
        monkeypatch.setenv(HMAC_KEY_ENV, binding_key)
    assert approved_route("openrouter", BASE, KEY) is None


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
    assert approved_route("openrouter", BASE, KEY) is None


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
        assert request.headers["authorization"] == f"Bearer {KEY}"
        assert adapters.eligible_chat_models("openrouter", KEY, slot) == (MODEL,)
        monkeypatch.delenv(POLICY_ENV)
        await discovery.validate_slot(slot, client)
        assert transport.call_count == 1
        assert adapters.eligible_chat_models("openrouter", KEY, slot) == ()


@pytest.mark.asyncio
async def test_inflight_catalog_cannot_prove_a_rotated_approval(monkeypatch):
    _approve(monkeypatch)
    slot = KeySlot("fixture-slot", KEY, "openrouter")
    rotated = False

    def respond(request):
        nonlocal rotated
        assert request.headers["authorization"] == f"Bearer {KEY}"
        if not rotated:
            rotated = True
            _approve(monkeypatch, binding_key="ab" * 32)
        return httpx.Response(200, json={"data": [{"id": MODEL, "pricing": ZERO}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await discovery.validate_slot(slot, client)
        assert approved_route("openrouter", BASE, KEY) is not None
        assert adapters.eligible_chat_models("openrouter", KEY, slot) == ()
        await discovery.validate_slot(slot, client)
        assert adapters.eligible_chat_models("openrouter", KEY, slot) == (MODEL,)


@pytest.mark.asyncio
async def test_stale_or_failed_catalog_is_not_routes_evidence(monkeypatch):
    _approve(monkeypatch)
    slot = KeySlot("fixture-slot", KEY, "openrouter", discovered_models=[MODEL])
    slot.catalog_identity = credential_identity("openrouter", BASE, KEY)
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
