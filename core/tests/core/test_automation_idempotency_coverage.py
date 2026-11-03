"""Coverage tests for core/automation/idempotency.py."""

import json
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.automation.idempotency import (
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
    create_idempotency_store,
)
from core.automation.models import AutomationResult, AutomationStatus


def _result(**kw):
    base = dict(status=AutomationStatus.DELIVERED, provider="t", message="m")
    base.update(kw)
    return AutomationResult(**base)


# ------------------------------------------------------------------ InMemory


async def test_inmemory_get_missing_returns_none():
    store = InMemoryIdempotencyStore()
    assert await store.get("missing") is None


async def test_inmemory_set_and_get_roundtrip():
    store = InMemoryIdempotencyStore()
    r = _result(execution_id="e1")
    await store.set("k", r)
    assert await store.get("k") == r


async def test_inmemory_expires_after_ttl():
    store = InMemoryIdempotencyStore(max_size=10, ttl=100)
    r = _result()
    await store.set("k", r)
    # Directly backdate the stored timestamp to simulate TTL expiry
    stored_result, _ = store._cache["k"]
    store._cache["k"] = (stored_result, 0.0)  # set ts to epoch 0 — always expired
    assert await store.get("k") is None
    assert await store.size() == 0


async def test_inmemory_lru_eviction():
    store = InMemoryIdempotencyStore(max_size=2)
    r = _result()
    await store.set("a", r)
    await store.set("b", r)
    await store.get("a")  # mark 'a' recently used
    await store.set("c", r)  # exceeds max_size -> evict least recently used (b)
    assert await store.get("b") is None
    assert await store.get("a") == r


async def test_inmemory_clear():
    store = InMemoryIdempotencyStore()
    await store.set("x", _result())
    await store.clear()
    assert await store.size() == 0


async def test_inmemory_size():
    store = InMemoryIdempotencyStore()
    await store.set("a", _result())
    await store.set("b", _result())
    assert await store.size() == 2


# ------------------------------------------------------------------ Redis


async def test_redis_get_hit():
    r = _result(execution_id="e1")
    client = AsyncMock()
    client.get = AsyncMock(return_value=r.model_dump_json())
    store = RedisIdempotencyStore(client)
    got = await store.get("k")
    assert got == r


async def test_redis_get_miss_returns_none():
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    store = RedisIdempotencyStore(client)
    assert await store.get("k") is None


async def test_redis_get_invalid_json_returns_none():
    client = AsyncMock()
    client.get = AsyncMock(return_value="not-json")
    store = RedisIdempotencyStore(client)
    assert await store.get("k") is None


async def test_redis_get_error_returns_none():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=ConnectionError("boom"))
    store = RedisIdempotencyStore(client)
    assert await store.get("k") is None


async def test_redis_set_and_clear():
    client = AsyncMock()
    client.scan_iter = MagicMock(return_value=_agen([]))
    store = RedisIdempotencyStore(client)
    await store.set("k", _result())
    args = client.set.await_args
    assert args.args[0] == "idemp:k"
    assert args.kwargs["ex"] == 3600
    await store.clear()  # no keys -> delete not called


async def test_redis_clear_iterates_keys():
    client = AsyncMock()
    client.scan_iter = MagicMock(return_value=_agen(["idemp:a", "idemp:b"]))
    client.delete = AsyncMock()
    store = RedisIdempotencyStore(client)
    await store.clear()
    client.delete.assert_awaited_once_with("idemp:a", "idemp:b")


async def test_redis_clear_error_swallowed():
    client = AsyncMock()
    client.scan_iter = MagicMock(side_effect=ConnectionError("boom"))
    store = RedisIdempotencyStore(client)
    await store.clear()  # must not raise


async def test_redis_size_counts_keys():
    client = AsyncMock()
    client.scan_iter = MagicMock(return_value=_agen(["idemp:a", "idemp:b"]))
    store = RedisIdempotencyStore(client)
    assert await store.size() == 2


async def test_redis_size_error_returns_zero():
    client = AsyncMock()
    client.scan_iter = MagicMock(side_effect=ConnectionError("boom"))
    store = RedisIdempotencyStore(client)
    assert await store.size() == 0


async def test_redis_set_error_swallowed():
    client = AsyncMock()
    client.set = AsyncMock(side_effect=ConnectionError("boom"))
    store = RedisIdempotencyStore(client)
    await store.set("k", _result())  # no raise


# ------------------------------------------------------------------ factory


def _agen(items):
    async def _gen():
        for i in items:
            yield i

    return _gen()


async def test_create_store_inmemory_when_no_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)
    store = create_idempotency_store()
    assert isinstance(store, InMemoryIdempotencyStore)


async def test_create_store_redis_when_configured(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")  # is_local()
    client = AsyncMock()
    with patch("redis.asyncio.from_url", return_value=client):
        store = create_idempotency_store()
    assert isinstance(store, RedisIdempotencyStore)


async def test_create_store_falls_back_on_redis_error(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")  # is_local()
    with patch("redis.asyncio.from_url", side_effect=ConnectionError("down")):
        store = create_idempotency_store()
    assert isinstance(store, InMemoryIdempotencyStore)
