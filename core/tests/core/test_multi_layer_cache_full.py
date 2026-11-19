"""Offline contract for exact chat response reuse, with Redis and without it."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.cache import multi_layer_cache as mlc

pytestmark = pytest.mark.asyncio


@pytest.fixture
def cache(monkeypatch):
    mlc.invalidate_session_cache(all_scopes=True)
    monkeypatch.setattr(mlc, "record_cache_access", AsyncMock())
    monkeypatch.setattr(mlc.metrics_collector, "observe_histogram", AsyncMock())
    monkeypatch.setattr(mlc.error_event_bus, "emit", Mock())
    yield mlc.MultiLayerCache()
    mlc.invalidate_session_cache(all_scopes=True)


SCOPE = {"user_id": "alice", "tenant_id": "team", "session_id": "session", "model_name": "requested-model"}


@pytest.mark.parametrize("redis_state", ["ready", "down", "unconfigured"])
async def test_both_cache_layers_isolate_the_complete_scope(cache, monkeypatch, redis_state):
    # In-process Redis contract with a simulated disconnect, not just a flush.
    rows = {}
    redis = SimpleNamespace(
        get=AsyncMock(side_effect=rows.get),
        setex=AsyncMock(side_effect=lambda key, ttl, value: rows.__setitem__(key, value)),
    )
    if redis_state == "down":
        redis.get.side_effect = redis.setex.side_effect = ConnectionError("fixture outage")
    get_redis = Mock(return_value=None if redis_state == "unconfigured" else redis)
    monkeypatch.setattr(mlc, "_get_redis_client", get_redis)
    await cache.set("complete prompt", "private reply", **SCOPE)
    for changed in (
        {"user_id": "bob"}, {"user_id": None}, {"tenant_id": "team-other"},
        {"session_id": "another"}, {"session_id": None}, {"model_name": "other-model"},
    ):
        assert await cache.get("complete prompt", **{**SCOPE, **changed}) is None
    assert await cache.get("complete", **SCOPE) is None
    assert await cache.get("complete prompt with changed context", **SCOPE) is None
    hit = await cache.get("complete prompt", **SCOPE)
    assert hit["response"] == "private reply"
    assert hit["source"] == ("L1_EXACT_CACHE" if redis_state == "ready" else "L4_SESSION_CACHE")
    stats = await cache.get_cache_statistics()
    assert stats["tokens_saved"] > 0
    if redis_state == "down":
        error_types = {call.args[0].error_type for call in mlc.error_event_bus.emit.call_args_list}
        assert error_types == {"L1_READ_FAILED", "L1_WRITE_FAILED"}


async def test_redis_roundtrip_does_not_read_unscoped_legacy_keys(cache, monkeypatch):
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    async with fakeredis.FakeRedis(decode_responses=True) as redis:
        monkeypatch.setattr(mlc, "_get_redis_client", lambda: redis)
        legacy_digest = hashlib.sha256(b"alice:fixture:requested-model").hexdigest()
        await redis.setex(f"exact:{legacy_digest}", 60, "legacy response")
        assert await cache.get("fixture", **SCOPE) is None
        await cache.set("fixture", "scoped", **SCOPE)
        mlc.invalidate_session_cache(all_scopes=True)
        assert (await cache.get("fixture", **SCOPE))["response"] == "scoped"
        # The existing admin cache:* scan covers the new exact keys.
        assert len(await redis.keys("cache:*")) == 1


async def test_unowned_or_oversized_writes_do_not_open_redis(cache, monkeypatch):
    get_redis = Mock()
    monkeypatch.setattr(mlc, "_get_redis_client", get_redis)
    await cache.set("prompt", "not shared", model_name="model", session_id="s")
    assert await cache.get("prompt", model_name="model", session_id="s") is None
    await cache.set("prompt", "x" * (50 * 1024 + 1), **SCOPE)
    get_redis.assert_not_called()
    assert len(mlc._session_cache) == 0


async def test_exact_ttl_with_operator_opt_in(cache, monkeypatch):
    redis = SimpleNamespace(setex=AsyncMock())
    monkeypatch.setattr(mlc, "_get_redis_client", lambda: redis)
    monkeypatch.setenv("ENABLE_SMART_TTL", "true")
    monkeypatch.setattr("core.learning.policies.smart_ttl", lambda *args, **kwargs: 1200)
    await cache.set("fixture", "scoped", **SCOPE)
    assert redis.setex.call_args.args[1] == 1200


async def test_invalidation_matches_tenant_not_session_substring(cache, monkeypatch):
    monkeypatch.setattr(mlc, "_get_redis_client", lambda: None)
    other = {**SCOPE, "tenant_id": "team-other", "session_id": "team"}
    await cache.set("prompt", "one", **SCOPE)
    await cache.set("prompt", "two", **other)
    mlc._cache_invalidation_listener(SimpleNamespace(error_type="LLM_DOWN", context={}))
    assert (await cache.get("prompt", **SCOPE))["response"] == "one"
    mlc._cache_invalidation_listener(SimpleNamespace(error_type="LLM_DOWN", context={"tenant_id": "team"}))
    assert await cache.get("prompt", **SCOPE) is None
    assert (await cache.get("prompt", **other))["response"] == "two"

    async def events():
        yield "broken json"
        yield json.dumps({"type": "CACHE_INVALIDATE_REQUESTED", "data": {"scope": "global"}})

    monkeypatch.setattr(mlc.swarm_streamer, "subscribe", events)
    await mlc.start_swarm_cache_invalidator()
    assert await cache.get("prompt", **other) is None
