"""Regression tests for the health-probe Redis fix + TTL cache (quota guard).

Covers the 2026-11-16 quota audit:
  * ``_check_redis()`` used to call ``get_cache()._redis`` on a SimpleCacheProxy
    that has no such attribute -> AttributeError -> always "unhealthy" (false
    503 on /health). It must now go through the failover-aware redis_manager.
  * Frequent Render/uptime probes must share ONE Redis command via the TTL
    cache instead of one command per probe (free-tier quota protection).
"""

from __future__ import annotations

import asyncio

import pytest

ROUTE = "core.api.routes.health"


class _FakeClient:
    def __init__(self, fail: bool = False):
        self.calls = 0
        self.fail = fail

    async def ping(self):
        self.calls += 1
        if self.fail:
            raise ConnectionError("boom")


class _FakeManager:
    """Stand-in for SecureRedisManager with a settable client + url."""

    def __init__(self, client, url: str = "rediss://default:x@host:6379"):
        self._client = client
        self.url = url
        self.is_connected = client is not None

    async def get_client_async(self):
        return self._client


@pytest.fixture(autouse=True)
def _reset_caches():
    import importlib

    mod = importlib.import_module(ROUTE)
    mod._REDIS_PROBE_CACHE = None
    mod._DB_PROBE_CACHE = None
    yield
    mod._REDIS_PROBE_CACHE = None
    mod._DB_PROBE_CACHE = None


def _load():
    import importlib

    return importlib.import_module(ROUTE)


def test_check_redis_no_client_no_url_is_not_configured(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(None, url=""))
    status = asyncio.run(mod._check_redis())
    assert status == "not_configured"


def test_check_redis_healthy_when_ping_ok(monkeypatch):
    mod = _load()
    client = _FakeClient()
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(client))
    status = asyncio.run(mod._check_redis())
    assert status == "healthy"
    assert client.calls == 1


def test_check_redis_degraded_when_breaker_open(monkeypatch):
    """Configured but client unavailable (quota/budget breaker) -> degraded, not unhealthy."""
    mod = _load()
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(None, url="rediss://x"))
    status = asyncio.run(mod._check_redis())
    assert status == "degraded"


def test_check_redis_unhealthy_on_ping_error(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(_FakeClient(fail=True)))
    status = asyncio.run(mod._check_redis())
    assert status == "unhealthy"


def test_check_redis_ttl_cache_avoids_repeat_ping(monkeypatch):
    """Two probes within the TTL window share ONE ping (quota guard)."""
    mod = _load()
    client = _FakeClient()
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(client))
    monkeypatch.setenv("HEALTH_REDIS_CACHE_TTL", "60")

    s1 = asyncio.run(mod._check_redis())
    s2 = asyncio.run(mod._check_redis())
    s3 = asyncio.run(mod._check_redis())

    assert s1 == s2 == s3 == "healthy"
    assert client.calls == 1, f"expected 1 ping (cached), got {client.calls}"


def test_check_redis_cache_expires(monkeypatch):
    """After the TTL expires, a fresh ping is issued."""
    mod = _load()
    client = _FakeClient()
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(client))
    monkeypatch.setenv("HEALTH_REDIS_CACHE_TTL", "10")

    asyncio.run(mod._check_redis())
    # Force expiry by rewinding the cache timestamp.
    mod._REDIS_PROBE_CACHE = (0.0, mod._REDIS_PROBE_CACHE[1])
    asyncio.run(mod._check_redis())
    assert client.calls == 2


def test_check_redis_never_raises_attribute_error(monkeypatch):
    """The original bug: SimpleCacheProxy has no _redis -> AttributeError."""
    mod = _load()

    class _Proxy:
        async def get(self, key):
            return None

        async def set(self, key, value, ttl=3600):
            return None

    # Even if something hands back a proxy-like object, _check_redis must not
    # touch a non-existent attribute — it only uses redis_manager.
    monkeypatch.setattr(mod, "redis_manager", _FakeManager(_FakeClient()))
    status = asyncio.run(mod._check_redis())
    assert status == "healthy"
