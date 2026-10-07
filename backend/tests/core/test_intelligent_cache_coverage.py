"""Coverage tests for core/intelligent_cache.py (IntelligentCache)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.intelligent_cache as ic
from core.intelligent_cache import (
    CacheConfig,
    CacheStats,
    CacheTier,
    IntelligentCache,
    cached_get,
    cached_set,
    get_cache,
)


@pytest.fixture(autouse=True)
def _stub_predictive(monkeypatch):
    """Avoid importing heavy predictive_cache_engine inside get()."""
    import sys
    import types
    from unittest.mock import AsyncMock as _AsyncMock

    engine = _AsyncMock()
    engine.cache_client = None
    engine.initialize = _AsyncMock(return_value=None)
    engine.record_access = _AsyncMock(return_value=None)
    fake = types.ModuleType("core.cache.predictive_cache_engine")
    fake.get_predictive_engine = lambda: engine
    monkeypatch.setitem(sys.modules, "core.cache.predictive_cache_engine", fake)
    yield engine


@pytest.fixture
def cache():
    ic._cache_instance = None
    ic.IntelligentCache._instance = None
    return IntelligentCache(config=CacheConfig(enabled=True))


@pytest.fixture
def redis_client():
    c = MagicMock()
    c.ping = MagicMock(return_value=True)
    c.get = MagicMock(return_value=None)
    c.setex = MagicMock(return_value=True)
    c.keys = MagicMock(return_value=[])
    c.delete = MagicMock(return_value=0)
    c.info = MagicMock(return_value={"used_memory": 100, "db0": {"keys": 2}})
    return c


def test_cache_stats_to_dict_and_hit_rate():
    s = CacheStats(hits=3, misses=1)
    d = s.to_dict()
    assert d["hit_rate"] == "75.00%"
    s0 = CacheStats()
    assert s0.to_dict()["hit_rate"] == "0.00%"


def test_disabled_config_skips_redis():
    cache = IntelligentCache(config=CacheConfig(enabled=False))
    assert cache._redis_client is None


def test_initialize_redis_no_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    cache = IntelligentCache(config=CacheConfig(enabled=True))
    assert cache._redis_client is None


def test_initialize_redis_success(monkeypatch, redis_client):
    # বাংলা (#4169): intelligent_cache now uses redis_manager.get_managed_client_sync()
    # instead of redis.from_url(). Mock redis_manager instead.
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    with patch("core.cache.redis_manager.redis_manager.get_managed_client_sync", return_value=redis_client):
        cache = IntelligentCache(config=CacheConfig(enabled=True))
        assert cache._redis_client is redis_client


def test_initialize_redis_failure(monkeypatch):
    # বাংলা (#4169): when redis_manager returns None, cache falls back to None
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    with patch("core.cache.redis_manager.redis_manager.get_managed_client_sync", return_value=None):
        cache = IntelligentCache(config=CacheConfig(enabled=True))
    assert cache._redis_client is None


def test_circuit_breaker_open_then_expires(cache, monkeypatch):
    import time

    monkeypatch.setattr("core.intelligent_cache.time.time", lambda: 1000.0)
    cache._circuit_breaker_open = True
    cache._circuit_breaker_until = 999.0  # expired
    assert cache._check_circuit_breaker() is True
    assert cache._circuit_breaker_open is False


def test_circuit_breaker_still_open(cache, monkeypatch):
    import time

    monkeypatch.setattr("core.intelligent_cache.time.time", lambda: 1000.0)
    cache._circuit_breaker_open = True
    cache._circuit_breaker_until = 2000.0
    assert cache._check_circuit_breaker() is False


def test_open_circuit_breaker_sets_deadline(cache, monkeypatch):
    monkeypatch.setattr("core.intelligent_cache.time.time", lambda: 1000.0)
    cache._open_circuit_breaker()
    assert cache._circuit_breaker_open is True
    assert cache._circuit_breaker_until == 1030


def test_generate_key_deterministic(cache):
    k1 = cache._generate_key("prefix", user="u", model="m")
    k2 = cache._generate_key("prefix", user="u", model="m")
    assert k1 == k2
    assert k1.startswith("supremeai:prefix:")


# ---------------------------------------------------------------------------
# get() / set()
# ---------------------------------------------------------------------------


async def test_get_disabled_returns_local(cache, monkeypatch):
    cache.config.enabled = False
    cache._local_cache["k"] = {"value": "v"}
    assert await cache.get("k") == "v"
    assert await cache.get("missing", "default") == "default"


async def test_set_stores_local_and_redis(cache, redis_client):
    cache._redis_client = redis_client
    ok = await cache.set("k", {"v": 1})
    assert ok is True
    assert "k" in cache._local_cache
    redis_client.setex.assert_called_once()


async def test_set_disabled_returns_false(cache):
    cache.config.enabled = False
    assert await cache.set("k", 1) is False


async def test_set_evicts_when_over_limit(cache):
    cache._local_cache_max = 2
    for i in range(3):
        await cache.set(f"k{i}", i)
    assert "k0" not in cache._local_cache
    assert len(cache._local_cache) == 2


async def test_get_hit_from_redis(cache, redis_client):
    cache._redis_client = redis_client
    import json

    redis_client.get = MagicMock(return_value=json.dumps({"value": "hit"}))
    val = await cache.get("k")
    assert val == "hit"
    assert cache.stats.hits == 1


async def test_get_redis_error_opens_circuit(cache, redis_client, monkeypatch):
    cache._redis_client = redis_client
    redis_client.get = MagicMock(side_effect=ConnectionError("boom"))
    await cache.get("k")
    assert cache._circuit_breaker_open is True


async def test_get_or_compute_cache_hit_counts_savings(cache, monkeypatch):
    cache._local_cache_max = 1000
    # seed a cached value
    cache._local_cache["k"] = {"value": "cached"}
    monkeypatch.setattr(cache.stats, "total_savings_usd", 0.0)

    called = []

    async def compute():
        called.append(1)
        return "fresh"

    val = await cache.get_or_compute("k", compute, force_refresh=False, estimated_cost_usd=0.5)
    assert val == "cached"
    assert called == []
    assert cache.stats.total_savings_usd == 0.5
    assert cache.stats.total_api_calls_avoided == 1


async def test_get_or_compute_force_refresh_bypasses_cache(cache):
    cache._local_cache["k"] = {"value": "cached"}
    called = []

    async def compute():
        called.append(1)
        return "fresh"

    val = await cache.get_or_compute("k", compute, force_refresh=True)
    assert val == "fresh"
    assert called == [1]


# ---------------------------------------------------------------------------
# invalidate / stats / health / decorator / singletons
# ---------------------------------------------------------------------------


def test_invalidate_all_clears_local(cache):
    cache._local_cache["a"] = 1
    cache._local_cache["b"] = 2
    assert cache.invalidate("*") == 2
    assert len(cache._local_cache) == 0


def test_invalidate_pattern_subset(cache):
    cache._local_cache["user:1"] = 1
    cache._local_cache["user:2"] = 2
    cache._local_cache["other:1"] = 3
    assert cache.invalidate("user") == 2
    assert "other:1" in cache._local_cache


def test_invalidate_with_redis(cache, redis_client):
    cache._redis_client = redis_client
    redis_client.keys = MagicMock(return_value=["supremeai:foo", "supremeai:bar"])
    count = cache.invalidate("*")
    assert count == 2


def test_get_stats_with_redis_info(cache, redis_client):
    cache._redis_client = redis_client
    stats = cache.get_stats()
    assert "redis_memory_used_bytes" in stats
    assert stats["redis_total_keys"] == 2
    assert stats["enabled"] is True


def test_get_stats_redis_info_error(cache, redis_client):
    cache._redis_client = redis_client
    redis_client.info = MagicMock(side_effect=RuntimeError("nope"))
    stats = cache.get_stats()
    assert "redis_memory_used_bytes" not in stats


def test_clear_stats(cache):
    cache.stats.hits = 5
    cache.stats.misses = 3
    cache.clear_stats()
    assert cache.stats.hits == 0
    assert cache.stats.misses == 0


def test_health_check_no_backend(cache):
    cache._redis_client = None
    cache._local_cache.clear()
    health = cache.health_check()
    assert health["status"] == "no_cache"
    assert health["redis_connected"] is False


def test_health_check_healthy(cache, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    cache._redis_client = None  # ensure no Redis client regardless of env
    cache._local_cache["k"] = {"value": 1}
    health = cache.health_check()
    assert health["redis_connected"] is False
    assert health["local_cache_active"] is True
    assert health["status"] == "healthy"


def test_health_check_redis_unreachable(cache, redis_client):
    cache._redis_client = redis_client
    cache._local_cache["k"] = {"value": 1}
    redis_client.ping = MagicMock(side_effect=ConnectionError("down"))
    health = cache.health_check()
    assert health["status"] == "degraded"
    assert health["redis_connected"] is False


def test_get_instance_singleton():
    ic.IntelligentCache._instance = None
    e1 = IntelligentCache.get_instance()
    e2 = IntelligentCache.get_instance()
    assert e1 is e2
    ic.IntelligentCache._instance = None


async def test_cached_decr_returns_from_cache(cache, monkeypatch):
    calls = []

    @cache.cached(ttl=60)
    async def f(x):
        calls.append(x)
        return x * 2

    r1 = await f(3)
    r2 = await f(3)
    assert r1 == 6 and r2 == 6
    assert calls == [3]  # compute only once


async def test_cached_get_set_helpers(monkeypatch):
    monkeypatch.setattr(ic, "_cache_instance", None)
    monkeypatch.setenv("LLM_CACHE_ENABLED", "true")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    await cached_set("k", {"v": 1})
    assert await cached_get("k") == {"v": 1}
    monkeypatch.setattr(ic, "_cache_instance", None)


async def test_get_or_compute_computes_and_stores(cache, redis_client):
    cache._redis_client = redis_client

    async def compute(a=1):
        return {"ok": a}

    val = await cache.get_or_compute("k", compute, a=2)
    assert val == {"ok": 2}
    # stored in local cache
    assert "k" in cache._local_cache


async def test_get_or_compute_compute_raises(cache):
    async def compute():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await cache.get_or_compute("k", compute, force_refresh=True)


async def test_get_or_compute_kwno_kwargs_branch(cache):
    # compute with empty kwargs -> calls compute() with no args
    async def compute():
        return "v"

    val = await cache.get_or_compute("k", compute, force_refresh=True)
    assert val == "v"


def test_match_pattern():
    assert (
        ic.IntelligentCache.__new__(ic.IntelligentCache)._match_pattern("abc_user_123", "user")
        is True
    )
    inst = ic.IntelligentCache.__new__(ic.IntelligentCache)
    assert inst._match_pattern("abc", "xyz") is False
