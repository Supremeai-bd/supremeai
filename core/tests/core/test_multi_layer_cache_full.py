"""Full-coverage tests for core/cache/multi_layer_cache.py (Task 7-d).

All Redis traffic goes through ``fakeredis.aioredis.FakeRedis`` (patched into
``_get_redis_client``); the semantic cache layer and swarm streamer are
AsyncMock/stub generators. Covers L1/L2/L3/L4 hits, misses, error events,
writes (fixed + smart TTL), statistics, event-sourced invalidation and the
swarm invalidator loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

fakeredis = pytest.importorskip("fakeredis", reason="fakeredis not installed")
import fakeredis.aioredis

import core.cache.multi_layer_cache as mlc

# The stub classes are underscore-private; grab them explicitly.
_InMemoryRedisStub = mlc._InMemoryRedisStub
_PipelineStub = mlc._PipelineStub
MultiLayerCache = mlc.MultiLayerCache
_cache_invalidation_listener = mlc._cache_invalidation_listener
_set_session_cache = mlc._set_session_cache
_get_session_cache = mlc._get_session_cache
_session_cache = mlc._session_cache
start_swarm_cache_invalidator = mlc.start_swarm_cache_invalidator


def _exact_key(prompt: str, model: str, scope: str = "") -> str:
    return f"exact:{hashlib.sha256(f'{scope}{prompt}:{model}'.encode()).hexdigest()}"


def _prefix_key(prefix: str, model: str, scope: str = "") -> str:
    return f"prefix:{hashlib.sha256(f'{scope}{prefix}:{model}'.encode()).hexdigest()}"


@pytest.fixture()
def fake_redis(monkeypatch):
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(mlc, "_get_redis_client", lambda: client)
    yield client
    asyncio.get_event_loop_policy()


@pytest.fixture()
def cache(fake_redis, monkeypatch):
    """Fresh MultiLayerCache with mocked metrics/error-bus plumbing."""
    c = MultiLayerCache()
    c.cache_stats = {
        "exact_hits": 0,
        "semantic_hits": 0,
        "prefix_hits": 0,
        "session_hits": 0,
        "misses": 0,
        "tokens_saved": 0,
    }
    monkeypatch.setattr(mlc, "record_cache_access", AsyncMock())
    monkeypatch.setattr(mlc.metrics_collector, "observe_histogram", AsyncMock())
    monkeypatch.setattr(mlc.error_event_bus, "emit", MagicMock())
    return c


def _semantic_mock(response=None, error: Exception | None = None):
    sem = MagicMock()
    if error:
        sem.query_similar = AsyncMock(side_effect=error)
        sem.set = AsyncMock(side_effect=error)
    else:
        sem.query_similar = AsyncMock(
            return_value=SimpleNamespace(response=response) if response else None
        )
        sem.set = AsyncMock()
    return sem


class TestInMemoryStub:
    async def test_get_miss_and_hit(self):
        stub = _InMemoryRedisStub()
        assert await stub.get("nope") is None
        await stub.setex("k", 60, "v")
        assert await stub.get("k") == "v"

    async def test_get_expired_entry_evicts(self):
        stub = _InMemoryRedisStub()
        stub._store["k"] = (-1.0, "v")  # already expired
        assert await stub.get("k") is None
        assert "k" not in stub._store

    async def test_setex_rejects_oversized_value(self):
        stub = _InMemoryRedisStub()
        await stub.setex("big", 60, "x" * (50 * 1024 + 10))
        assert "big" not in stub._store

    async def test_set_bounded_evicts_oldest(self):
        stub = _InMemoryRedisStub()
        for i in range(stub._MAX_STORE_SIZE + 5):
            stub._set_bounded(f"k{i}", 60, "v")
        assert len(stub._store) == stub._MAX_STORE_SIZE
        assert "k0" not in stub._store  # oldest evicted
        assert f"k{stub._MAX_STORE_SIZE + 4}" in stub._store

    async def test_mget_batch(self):
        stub = _InMemoryRedisStub()
        await stub.setex("a", 60, "1")
        assert await stub.mget(["a", "b", "a"]) == ["1", None, "1"]

    async def test_pipeline_setex_and_execute(self):
        stub = _InMemoryRedisStub()
        pipe = await stub.pipeline()
        async with pipe:
            await pipe.setex("p1", 30, "v1")
            await pipe.setex("p2", 30, "v2")
            results = await pipe.execute()
        assert results == [None, None]
        assert await stub.get("p1") == "v1"


class TestLayerHits:
    async def test_l1_exact_hit(self, cache, fake_redis):
        await fake_redis.set(_exact_key("hello", "m1"), "cached-reply")
        out = await cache.get("hello", "m1")
        assert out["source"] == "L1_EXACT_CACHE"
        assert out["response"] == "cached-reply"
        assert cache.cache_stats["exact_hits"] == 1
        assert cache.cache_stats["tokens_saved"] > 0

    async def test_l1_user_scoping(self, cache, fake_redis):
        await fake_redis.set(_exact_key("hello", "m1", scope="bob:"), "bob-reply")
        out = await cache.get("hello", "m1", user_id="bob")
        assert out is not None and out["response"] == "bob-reply"
        # alice's scope misses → None
        assert await cache.get("hello", "m1", user_id="alice") is None

    async def test_l2_semantic_hit(self, cache, monkeypatch):
        sem = _semantic_mock(response="semantic-reply")
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        out = await cache.get("hello world", "m1")
        assert out["source"] == "L2_SEMANTIC_CACHE"
        assert cache.cache_stats["semantic_hits"] == 1

    async def test_l3_prefix_hit(self, cache, fake_redis):
        await fake_redis.set(_prefix_key("hello big", "m1"), "prefix-reply")
        out = await cache.get("hello big world", "m1")
        assert out["source"] == "L3_PREFIX_CACHE"
        assert cache.cache_stats["prefix_hits"] == 1

    async def test_l4_session_hit_and_miss(self, cache):
        _set_session_cache("sess-1", "session prompt", "session-reply")
        out = await cache.get("session prompt", "m1", session_id="sess-1")
        assert out["source"] == "L4_SESSION_CACHE"
        assert cache.cache_stats["session_hits"] == 1
        # miss on session but layers 1-3 also miss → None and miss recorded
        out2 = await cache.get("other prompt", "m1", session_id="sess-1")
        assert out2 is None
        assert cache.local_cache_misses == 1
        assert cache.cache_stats["misses"] == 1

    async def test_all_miss_returns_none(self, cache):
        out = await cache.get("unknown", "m1")
        assert out is None
        assert cache.cache_stats["misses"] == 1


class TestLayerErrors:
    async def test_l1_read_error_emits_event(self, cache, monkeypatch):
        boom = MagicMock()
        boom.get = AsyncMock(side_effect=RuntimeError("redis down"))
        monkeypatch.setattr(cache, "_get_exact_cache", lambda: boom)
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        out = await cache.get("p", "m1")
        assert out is None
        emitted = mlc.error_event_bus.emit.call_args_list
        assert any(e.args[0].error_type == "L1_READ_FAILED" for e in emitted)

    async def test_l2_error_emits_event(self, cache, monkeypatch):
        sem = _semantic_mock(error=RuntimeError("embed fail"))
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.get("p", "m1")
        emitted = mlc.error_event_bus.emit.call_args_list
        assert any(e.args[0].error_type == "L2_READ_FAILED" for e in emitted)

    async def test_l3_error_emits_event(self, cache, monkeypatch):
        boom = MagicMock()
        boom.mget = AsyncMock(side_effect=RuntimeError("mget fail"))
        monkeypatch.setattr(cache, "_get_prefix_cache", lambda: boom)
        await cache.get("p", "m1")
        emitted = mlc.error_event_bus.emit.call_args_list
        assert any(e.args[0].error_type == "L3_READ_FAILED" for e in emitted)

    async def test_record_hit_with_non_str_response(self, cache):
        cache._record_hit("exact", 12345)
        assert cache.cache_stats["tokens_saved"] >= 0


class TestSet:
    async def test_set_writes_all_layers(self, cache, fake_redis, monkeypatch):
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("the full prompt", "the reply", "m1", session_id="s1")
        assert await fake_redis.get(_exact_key("the full prompt", "m1")) == "the reply"
        # prefix keys written through the pipeline
        assert await fake_redis.get(_prefix_key("the full prompt", "m1")) == "the reply"
        assert await fake_redis.get(_prefix_key("the full", "m1")) == "the reply"
        assert _get_session_cache("s1", "the full prompt") == "the reply"
        sem.set.assert_awaited_once()

    async def test_set_smart_ttl_opt_in(self, cache, fake_redis, monkeypatch):
        monkeypatch.setenv("ENABLE_SMART_TTL", "true")
        monkeypatch.setattr(
            "core.learning.policies.smart_ttl", lambda base, *, hit_rate, reuse_count: 1200
        )
        cache.cache_stats["exact_hits"] = 10
        cache.cache_stats["misses"] = 5
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("smart prompt", "smart reply", "m1")
        ttl = await fake_redis.ttl(_exact_key("smart prompt", "m1"))
        assert 0 < ttl <= 1200

    async def test_set_smart_ttl_import_failure_falls_back(self, cache, fake_redis, monkeypatch):
        monkeypatch.setenv("ENABLE_SMART_TTL", "true")
        monkeypatch.setattr(
            "core.learning.policies.smart_ttl",
            lambda base, *, hit_rate, reuse_count: (_ for _ in ()).throw(RuntimeError("x")),
        )
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("smart2", "reply", "m1")
        ttl = await fake_redis.ttl(_exact_key("smart2", "m1"))
        assert 3500 < ttl <= 3600  # fixed 3600 fallback

    async def test_set_l1_write_error_emits_event(self, cache, monkeypatch):
        boom = MagicMock()
        boom.setex = AsyncMock(side_effect=RuntimeError("write fail"))
        monkeypatch.setattr(cache, "_get_exact_cache", lambda: boom)
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("p", "r", "m1")
        emitted = mlc.error_event_bus.emit.call_args_list
        assert any(e.args[0].error_type == "L1_WRITE_FAILED" for e in emitted)

    async def test_set_l2_write_error_emits_event(self, cache, monkeypatch):
        sem = _semantic_mock(error=RuntimeError("nope"))
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("p", "r", "m1")
        emitted = mlc.error_event_bus.emit.call_args_list
        assert any(e.args[0].error_type == "L2_WRITE_FAILED" for e in emitted)

    async def test_set_l3_write_error_emits_event(self, cache, monkeypatch):
        boom = MagicMock()
        boom.pipeline = MagicMock(side_effect=RuntimeError("pipe fail"))
        monkeypatch.setattr(cache, "_get_prefix_cache", lambda: boom)
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("p", "r", "m1")
        emitted = mlc.error_event_bus.emit.call_args_list
        assert any(e.args[0].error_type == "L3_WRITE_FAILED" for e in emitted)

    async def test_set_without_pipeline_uses_setex_loop(self, cache, fake_redis, monkeypatch):
        class NoPipeline:
            def __init__(self, client):
                self.client = client

            async def setex(self, key, ttl, value):
                await self.client.setex(key, ttl, value)

        # bypass _get_redis_client so prefix cache is the NoPipeline wrapper
        monkeypatch.setattr(cache, "_get_prefix_cache", lambda: NoPipeline(fake_redis))
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("one two", "r", "m1")
        assert await fake_redis.get(_prefix_key("one two", "m1")) == "r"


class TestStatistics:
    async def test_get_cache_statistics_empty(self, cache):
        stats = await cache.get_cache_statistics()
        assert stats["total_accesses"] == 0
        assert stats["hit_rate_percentage"] == 0
        assert stats["avg_tokens_saved_per_hit"] is None

    async def test_get_cache_statistics_with_hits(self, cache):
        cache.cache_stats.update(
            {"exact_hits": 6, "semantic_hits": 2, "prefix_hits": 1, "session_hits": 1, "misses": 10}
        )
        cache.cache_stats["tokens_saved"] = 50
        cache.local_cache_hits = 3
        cache.local_cache_misses = 7
        stats = await cache.get_cache_statistics()
        assert stats["total_accesses"] == 20
        assert stats["hit_rate_percentage"] == pytest.approx(50.0)
        assert stats["avg_tokens_saved_per_hit"] == pytest.approx(5.0)
        assert stats["local_cache_hits"] == 3


class TestEventInvalidation:
    def _event(self, error_type, tenant=None):
        structured = SimpleNamespace(env=tenant)
        return SimpleNamespace(error_type=error_type, context={}, structured_context=structured)

    def test_listener_ignores_unrelated_events(self):
        _set_session_cache("t1:sess", "p", "r")
        _cache_invalidation_listener(self._event("UNRELATED"))
        assert _get_session_cache("t1:sess", "p") == "r"

    def test_listener_clears_tenant_keys(self):
        _session_cache.clear()
        _set_session_cache("t1:sess", "p", "r1")
        _set_session_cache("t2:sess", "p", "r2")
        event = SimpleNamespace(
            error_type="CIRCUIT_OPEN", context={"tenant_id": "t1"}, structured_context=None
        )
        _cache_invalidation_listener(event)
        assert _get_session_cache("t1:sess", "p") is None
        assert _get_session_cache("t2:sess", "p") == "r2"

    def test_listener_fallback_clears_all(self):
        _set_session_cache("t1:sess", "p", "r1")
        _cache_invalidation_listener(self._event("LLM_DOWN", tenant=None))
        assert len(_session_cache) == 0


class TestSwarmInvalidator:
    async def test_swarm_invalidator_processes_events(self, monkeypatch):
        _session_cache.clear()
        events = [
            json.dumps({"type": "KNOWLEDGE_BASE_UPDATED", "data": {"tenant_id": "t9"}}),
            "not-json{",
            json.dumps({"type": "OTHER_EVENT", "data": {}}),
        ]

        async def subscribe():
            for e in events:
                yield e

        streamer = MagicMock()
        streamer.subscribe = subscribe
        monkeypatch.setattr(mlc, "swarm_streamer", streamer)

        _set_session_cache("t9:sess", "p", "r")
        task = asyncio.create_task(start_swarm_cache_invalidator())
        # let the generator finish
        for _ in range(10):
            await asyncio.sleep(0)
        assert _get_session_cache("t9:sess", "p") is None
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                assert task.cancelled()
        else:
            assert task.exception() is None

    async def test_swarm_invalidator_cancelled(self, monkeypatch):
        async def subscribe():
            yield json.dumps({"type": "CACHE_INVALIDATE_REQUESTED", "data": {}})
            await asyncio.sleep(10)  # keep the loop alive until cancelled

        streamer = MagicMock()
        streamer.subscribe = subscribe
        monkeypatch.setattr(mlc, "swarm_streamer", streamer)
        task = asyncio.create_task(start_swarm_cache_invalidator())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            assert task.cancelled()

    async def test_swarm_invalidator_crash_is_logged(self, monkeypatch):
        async def subscribe():
            raise RuntimeError("pubsub exploded")
            yield  # pragma: no cover

        streamer = MagicMock()
        streamer.subscribe = subscribe
        monkeypatch.setattr(mlc, "swarm_streamer", streamer)
        await start_swarm_cache_invalidator()  # must not raise


class TestSessionCacheHelpers:
    async def test_session_cache_ttl_and_size_limit(self):
        _set_session_cache("s", "p1", "r1")
        assert _get_session_cache("s", "p1") == "r1"
        oversized = "x" * (50 * 1024 + 1)
        _set_session_cache("s", "p2", oversized)
        assert _get_session_cache("s", "p2") is None

    async def test_roundtrip_through_set_and_get(self, cache, fake_redis, monkeypatch):
        sem = _semantic_mock()
        monkeypatch.setattr(cache, "_get_semantic_cache", lambda: sem)
        await cache.set("round prompt", "round reply", "m1")
        out = await cache.get("round prompt", "m1")
        assert out["source"] == "L1_EXACT_CACHE"
