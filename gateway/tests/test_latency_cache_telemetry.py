"""Tests for Phase 5 multi-tier response cache and Phase 8 latency telemetry."""
import pytest
from fastapi.testclient import TestClient

from gateway.service.cache import MultiTierResponseCache
from gateway.service.pool import FederationSquad
from gateway.service.app import app


def test_cache_is_cacheable_rules():
    assert MultiTierResponseCache.is_cacheable({"model": "auto", "messages": [{"role": "user", "content": "hi"}], "temperature": 0})
    assert not MultiTierResponseCache.is_cacheable({"model": "auto", "messages": [], "temperature": 0.7})
    assert not MultiTierResponseCache.is_cacheable({"model": "auto", "messages": [], "temperature": 0, "stream": True})
    assert not MultiTierResponseCache.is_cacheable(
        {"model": "auto", "messages": [], "temperature": 0},
        headers={"cache-control": "no-cache"},
    )


@pytest.mark.asyncio
async def test_cache_l1_hit_and_miss(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    cache = MultiTierResponseCache(max_l1_size=10, ttl_seconds=60)
    key = cache.build_key({"model": "auto", "messages": [{"role": "user", "content": "ping"}]})

    assert await cache.get(key) is None
    assert cache.misses == 1

    await cache.set(key, {"choices": [{"message": {"content": "pong"}}]})
    hit = await cache.get(key)
    assert hit is not None
    assert hit["choices"][0]["message"]["content"] == "pong"
    assert cache.hits == 1


def test_squad_stats_includes_avg_latency(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_valid_key_123456")
    sq = FederationSquad()
    pool = sq.pools["groq"]
    slot = pool.get_next_key()
    assert slot is not None
    sq.report_success("groq", slot, 120.0)
    stats = sq.stats()
    assert stats["providers"]["groq"]["avg_latency_ms"] == 120.0


def test_telemetry_latency_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/telemetry/latency")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "squad" in data
    assert "cache" in data
