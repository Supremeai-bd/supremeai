"""Coverage tests for core/cache.py (QueryCache + get_cache singleton)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from core.cache.query_cache import QueryCache, get_cache


@pytest.fixture
def fake_redis():
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.keys = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


def test_hash_query_deterministic_and_normalized():
    a = QueryCache.hash_query("Hello   World", model="gpt")
    b = QueryCache.hash_query("hello world", model="gpt")
    assert a == b


def test_hash_query_metadata_changes_hash():
    a = QueryCache.hash_query("x", model="gpt")
    b = QueryCache.hash_query("x", model="claude")
    assert a != b


async def test_disabled_cache_short_circuits():
    cache = QueryCache(redis_url="redis://x", enabled=False)
    assert await cache.get("any") is None
    assert await cache.set("k", 1) is False


async def test_get_redis_connection_failure_disables():
    # বাংলা (#4169): query_cache now uses redis_manager.get_managed_client_sync()
    # When it returns None, cache should be disabled.
    with patch("core.cache.redis_manager.redis_manager.get_managed_client_sync", return_value=None):
        cache = QueryCache(redis_url="redis://bad")
        r = await cache._get_redis()
        assert r is None
        assert cache.enabled is False


async def test_get_hit(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.get = AsyncMock(return_value=json.dumps({"result": 42}))
    assert await cache.get("h") == 42
    assert cache._stats["hits"] == 1


async def test_get_miss(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.get = AsyncMock(return_value=None)
    assert await cache.get("h") is None
    assert cache._stats["misses"] == 1


async def test_get_invalid_json_increments_errors(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.get = AsyncMock(return_value="not-json")
    assert await cache.get("h") is None
    assert cache._stats["errors"] == 1


# ---------------------------------------------------------------------------
# set()
# ---------------------------------------------------------------------------


async def test_set_success(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    ok = await cache.set("k", {"a": 1}, ttl=60)
    assert ok is True
    fake_redis.setex.assert_awaited_once()
    args, _kwargs = fake_redis.setex.await_args
    assert args[0] == f"{QueryCache.PREFIX_EXACT}k"


async def test_set_redis_error_returns_false(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.setex = AsyncMock(side_effect=RedisError("boom"))
    assert await cache.set("k", 1, ttl=60) is False
    assert cache._stats["errors"] == 1


async def test_set_disabled_returns_false():
    cache = QueryCache(redis_url="redis://x", enabled=False)
    assert await cache.set("k", 1, ttl=60) is False


# ---------------------------------------------------------------------------
# get_or_compute()
# ---------------------------------------------------------------------------


async def test_get_or_compute_miss_then_compute(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis

    async def compute():
        return {"computed": True}

    result, meta = await cache.get_or_compute("hello", compute, model="gpt")
    assert result == {"computed": True}
    assert meta["source"] == "computed"
    fake_redis.setex.assert_awaited_once()


async def test_get_or_compute_cache_hit_skips_compute(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.get = AsyncMock(return_value=json.dumps({"result": "hit"}))
    called = []

    async def compute():
        called.append(1)
        return "fresh"

    result, meta = await cache.get_or_compute("hello", compute, model="gpt")
    assert result == "hit"
    assert meta == {"source": "cache", "hit_type": "exact"}
    assert called == []


async def test_get_or_compute_propagates_exception(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis

    async def compute():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await cache.get_or_compute("hello", compute)


# ---------------------------------------------------------------------------
# invalidate / clear_pattern / close / stats / singleton
# ---------------------------------------------------------------------------


async def test_invalidate_success_and_failure(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.delete = AsyncMock(return_value=1)
    assert await cache.invalidate("abc") is True
    fake_redis.delete = AsyncMock(return_value=0)
    assert await cache.invalidate("abc") is False
    fake_redis.delete = AsyncMock(side_effect=RedisError("boom"))
    assert await cache.invalidate("abc", prefix=QueryCache.PREFIX_SEMANTIC) is False


async def test_clear_pattern(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.keys = AsyncMock(return_value=["k1", "k2"])
    fake_redis.delete = AsyncMock(return_value=2)
    n = await cache.clear_pattern("llm:*")
    assert n == 2
    fake_redis.keys = AsyncMock(return_value=[])
    assert await cache.clear_pattern("llm:*") == 0
    fake_redis.keys = AsyncMock(side_effect=RedisError("boom"))
    assert await cache.clear_pattern("llm:*") == 0


async def test_close_closes_redis(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    await cache.close()
    fake_redis.close.assert_awaited_once()


async def test_close_no_redis_is_noop():
    cache = QueryCache(redis_url="redis://x")
    cache._redis = None
    await cache.close()  # no raise


def test_get_stats_shape(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    s = cache.get_stats()
    assert s["enabled"] is True
    assert s["connected"] is True
    assert s["hit_rate"] == 0
    cache._stats["hits"] = 2
    cache._stats["misses"] = 2
    assert cache.get_stats()["hit_rate"] == 50.0


async def test_get_cache_singleton(monkeypatch):
    import core.cache.query_cache as cmod

    monkeypatch.setattr(cmod, "_global_cache", None)
    monkeypatch.setenv("REDIS_URL", "redis://x")
    c1 = get_cache()
    c2 = get_cache()
    assert c1 is c2
    monkeypatch.setattr(cmod, "_global_cache", None)


async def test_get_redis_error_increments_errors(fake_redis):
    cache = QueryCache(redis_url="redis://x")
    cache._redis = fake_redis
    fake_redis.get = AsyncMock(side_effect=RedisError("boom"))
    assert await cache.get("h") is None
    assert cache._stats["errors"] == 1
