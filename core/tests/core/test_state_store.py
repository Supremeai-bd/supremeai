"""Tests for core/state_store.py (issue #451 — durable state facade).

Hermetic: no real Redis. `_redis_client` is monkeypatched to return either
None (mirror-only degradation) or a tiny fake async client (durable path).
"""

from __future__ import annotations

import asyncio

import pytest

from core import state_store
from core.state_store import DurableRing, DurableStateStore


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch):
    monkeypatch.setattr(state_store, "_registry", {})
    monkeypatch.setattr(state_store, "INVENTORY", {})
    yield


@pytest.fixture
def no_redis(monkeypatch):
    async def _none():
        return None

    monkeypatch.setattr(state_store, "_redis_client", _none)


@pytest.fixture
def fake_redis(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.data: dict[str, str] = {}
            self.calls: list[str] = []

        async def set(self, key, value, ex=None):
            self.calls.append("set")
            self.data[key] = value

        async def get(self, key):
            self.calls.append("get")
            return self.data.get(key)

        async def delete(self, key):
            self.calls.append("delete")
            self.data.pop(key, None)

        async def scan(self, match="*", count=100):
            self.calls.append("scan")
            keys = [k for k in self.data if k.startswith(match.replace("*", ""))]
            return (0, keys)

        async def mget(self, *keys):
            self.calls.append("mget")
            return [self.data.get(k) for k in keys]

    client = FakeClient()

    async def _client():
        return client

    monkeypatch.setattr(state_store, "_redis_client", _client)
    return client


# ── mirror-only degradation (no redis) ────────────────────────────────────────


def test_set_get_mirror_only(no_redis):
    store = DurableStateStore("t1")
    store.set("a", {"x": 1})
    assert store.get("a") == {"x": 1}
    assert store.last_mutation_durable is False


def test_delete_mirror_only(no_redis):
    store = DurableStateStore("t2")
    store.set("a", 1)
    store.delete("a")
    assert store.get("a") is None


def test_get_missing_returns_none(no_redis):
    store = DurableStateStore("t3")
    assert store.get("ghost") is None


# ── durable path (fake redis) ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_set_async_reaches_redis(fake_redis):
    store = DurableStateStore("t4")
    await store.set_async("k", {"v": 42})
    assert store.last_mutation_durable is True
    assert any("t4:k" in k for k in fake_redis.data)


@pytest.mark.anyio
async def test_hydrate_roundtrip(fake_redis):
    store = DurableStateStore("t5")
    await store.set_async("k1", {"n": 1})
    await store.set_async("k2", {"n": 2})
    fresh = DurableStateStore("t5")
    loaded = await fresh.hydrate_async()
    assert loaded == 2
    assert fresh.get("k1") == {"n": 1}
    assert fresh.get("k2") == {"n": 2}


@pytest.mark.anyio
async def test_hydrate_is_idempotent(fake_redis):
    store = DurableStateStore("t6")
    first = await store.hydrate_async()
    second = await store.hydrate_async()
    assert first == second == 0


@pytest.mark.anyio
async def test_delete_async_removes_from_redis(fake_redis):
    store = DurableStateStore("t7")
    await store.set_async("k", 1)
    await store.delete_async("k")
    assert "t7:k" not in fake_redis.data


# ── DurableRing ───────────────────────────────────────────────────────────────


def test_durable_ring_order(no_redis):
    ring = DurableRing("ring1", maxlen=3)
    ring.append("a", {"i": "a"})
    ring.append("b", {"i": "b"})
    ring.append("c", {"i": "c"})
    ring.evict("b")
    assert [r["i"] for r in ring.ordered_snapshot()] == ["a", "c"]


def test_durable_ring_upsert_no_duplicate(no_redis):
    ring = DurableRing("ring2", maxlen=10)
    ring.append("x", {"v": 1})
    ring.append("x", {"v": 2})
    assert len(ring.ordered_snapshot()) == 1
    assert ring.ordered_snapshot()[0]["v"] == 2


def test_durable_ring_maxlen(no_redis):
    ring = DurableRing("ring3", maxlen=2)
    ring.append("a", 1)
    ring.append("b", 2)
    ring.append("c", 3)
    assert len(ring.ordered_snapshot()) == 2


# ── registry + banner ────────────────────────────────────────────────────────


def test_durable_state_registry_is_singleton():
    s1 = state_store.durable_state("ns_a")
    s2 = state_store.durable_state("ns_a")
    assert s1 is s2


def test_banner_lists_inventory():
    state_store.durable_state("banner_ns")
    text = state_store.banner()
    assert "banner_ns" in text
    assert "redis+mirror" in text
