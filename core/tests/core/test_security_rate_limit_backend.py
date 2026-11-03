"""P1 — Redis-authoritative security rate limiter tests.

বাংলা: RequestValidationMiddleware._check_rate_limit এখন Redis-authoritative;
Redis না থাকলে per-instance in-memory EMERGENCY fallback (WARNING লগসহ)।
Issue #460 update: Redis path এখন একক atomic EVAL (১ billable op) — পুরনো
দুই-ফেজ ৪-কমান্ড pipeline নয়।
"""

import time
from importlib import import_module
from unittest.mock import patch

import pytest

from core.middleware.security import RequestValidationMiddleware

# বাংলা: core.cache.__init__ নিজেই 'redis_manager' নামে ইনস্ট্যান্স রি-এক্সপোর্ট
# করে, তাই 'import core.cache.redis_manager as m' মডিউল নয় ইনস্ট্যান্স দেয়।
# মডিউল অবজেক্ট সরাসরি নিতে হয়।
#
# FIX (#2088 fallout): resolve the module LAZILY (per call), never once at
# module/collection time. Other suite members (test_redis_budget_guard)
# legitimately swap the core.cache.redis_manager module object in sys.modules
# mid-session; a collection-time import_module() captures a STALE object whose
# monkeypatches then silently no-op against the live module the middleware
# imports — exactly the CI-only "Event loop is closed" failures (the REAL
# singleton was reached instead of the FakeRedis) that pass in isolation.


def _redis_manager_module():
    """The LIVE core.cache.redis_manager module object (never a stale copy)."""
    return import_module("core.cache.redis_manager")


class _FakeRedis:
    """Minimal redis client stub exposing the atomic EVAL contract (#460).

    `eval` returns the window count that the rate-limit Lua script would
    produce; `window_counts` maps counter key -> reported count.
    """

    def __init__(self, window_counts: dict[str, int] | None = None):
        self.window_counts = window_counts or {}
        self.eval_calls: list[tuple] = []

    async def eval(self, script, numkeys, key, window, *args):  # noqa: ARG002
        self.eval_calls.append((key, window))
        return self.window_counts.get(key, 0)

    def _prime(self, counter_key: str, count: int):
        self.window_counts[counter_key] = count


@pytest.fixture
def mw():
    """Build a middleware instance without a real app."""
    return RequestValidationMiddleware(app=None)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()

    class _Manager:
        async def get_client_async(self):
            return fake

    # বাংলা: core.cache.redis_manager হলো মডিউল — সেখানেই module-level
    # redis_manager ভেরিয়েবল প্যাচ করতে হয় (core.cache থেকে ইমপোর্ট করলে
    # ইনস্ট্যান্স পাওয়া যায়, মডিউল নয়)।
    monkeypatch.setattr(_redis_manager_module(), "redis_manager", _Manager())
    return fake


@pytest.mark.asyncio
async def test_redis_authoritative_allows_under_limit(mw, fake_redis):
    allowed = await mw._check_rate_limit("1.2.3.4", "/api/v1/anything")
    assert allowed is True
    # Exactly ONE billable op per evaluation (issue #460)
    assert len(fake_redis.eval_calls) == 1
    key, window = fake_redis.eval_calls[0]
    assert key == "security_rate_limit:1.2.3.4"
    assert window == 60


@pytest.mark.asyncio
async def test_redis_authoritative_rejects_over_limit(mw, fake_redis):
    # default limit is 100/min → count 101 breaches
    fake_redis._prime("security_rate_limit:1.2.3.4", 101)
    allowed = await mw._check_rate_limit("1.2.3.4", "/api/v1/anything")
    assert allowed is False


@pytest.mark.asyncio
async def test_critical_path_limit_override(mw, fake_redis):
    """Login path uses 5/600 limit, not the default 100/60."""

    allowed = await mw._check_rate_limit("9.9.9.9", "/api/v1/auth/login")
    assert allowed is True  # count 0 → allowed
    key, window = fake_redis.eval_calls[0]
    assert key == "security_rate_limit:9.9.9.9:/api/v1/auth/login"
    assert window == 600

    fake_redis._prime("security_rate_limit:9.9.9.9:/api/v1/auth/login", 6)
    assert await mw._check_rate_limit("9.9.9.9", "/api/v1/auth/login") is False


@pytest.mark.asyncio
async def test_fallback_when_redis_unavailable(mw, monkeypatch):
    class _NoneManager:
        async def get_client_async(self):
            return None

    monkeypatch.setattr(_redis_manager_module(), "redis_manager", _NoneManager())

    results = []
    for _ in range(3):
        results.append(await mw._check_rate_limit("7.7.7.7", "/api/v1/anything"))
    assert results == [True, True, True]
    for _ in range(97):
        assert await mw._check_rate_limit("7.7.7.7", "/api/v1/anything") is True
    # next one breaches the default 100/min limit
    assert await mw._check_rate_limit("7.7.7.7", "/api/v1/anything") is False


@pytest.mark.asyncio
async def test_fallback_memory_is_per_instance():
    class _NoneManager:
        async def get_client_async(self):
            return None

    with patch.object(_redis_manager_module(), "redis_manager", _NoneManager()):
        a = RequestValidationMiddleware(app=None)
        b = RequestValidationMiddleware(app=None)
        # both allow the first request; state is independent per instance
        assert await a._check_rate_limit("5.5.5.5", "/api/v1/anything") is True
        assert await b._check_rate_limit("5.5.5.5", "/api/v1/anything") is True
        assert "5.5.5.5" in a._request_log
        assert "5.5.5.5" in b._request_log


@pytest.mark.asyncio
async def test_old_entries_ignored_in_fallback(mw, monkeypatch):
    class _NoneManager:
        async def get_client_async(self):
            return None

    monkeypatch.setattr(_redis_manager_module(), "redis_manager", _NoneManager())
    # seed stale timestamps far outside the window
    mw._request_log["6.6.6.6"] = [time.time() - 10_000] * 500
    assert await mw._check_rate_limit("6.6.6.6", "/api/v1/anything") is True
