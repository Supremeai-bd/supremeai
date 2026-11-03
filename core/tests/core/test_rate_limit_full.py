"""Full-coverage tests for core/rate_limit.py (Task 7-d).

Covers RateLimiter tiers/limits, sliding-window fallback, atomic Redis path,
client-id extraction, RateLimitMiddleware dispatch branches and the
per-endpoint ``rate_limit`` decorator. All I/O is mocked (no real Redis).
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.cache.redis_manager import redis_manager as _redis_manager
from core.config import settings
from core.rate_limit import RateLimiter, RateLimitMiddleware, rate_limit


def _fake_request(
    path: str = "/api/chat",
    user: dict | object | None = None,
    headers: dict | None = None,
    client_host: str = "10.0.0.1",
):
    req = MagicMock()
    req.url.path = path
    req.method = "POST"
    req.state = SimpleNamespace(user=user, db=None)
    req.headers = headers or {"user-agent": "pytest-agent"}
    req.client = SimpleNamespace(host=client_host)
    return req


@pytest.fixture(autouse=True)
def _restore_simplified_flag():
    """RATE_LIMIT_USE_SIMPLIFIED is True in the test env — remember & restore."""
    original = getattr(settings, "RATE_LIMIT_USE_SIMPLIFIED", True)
    yield
    settings.RATE_LIMIT_USE_SIMPLIFIED = original


class TestRateLimiterTiers:
    async def test_get_redis_simplified_returns_none(self):
        settings.RATE_LIMIT_USE_SIMPLIFIED = True
        rl = RateLimiter()
        assert await rl._get_redis() is None

    async def test_get_redis_success(self):
        settings.RATE_LIMIT_USE_SIMPLIFIED = False
        rl = RateLimiter()
        fake = object()
        with patch.object(_redis_manager, "get_client_async", new=AsyncMock(return_value=fake)):
            assert await rl._get_redis() is fake

    async def test_get_redis_failure_sets_none(self):
        settings.RATE_LIMIT_USE_SIMPLIFIED = False
        rl = RateLimiter()
        rl._redis = None
        with patch.object(
            _redis_manager,
            "get_client_async",
            new=AsyncMock(side_effect=RuntimeError("down")),
        ):
            assert await rl._get_redis() is None

    async def test_get_redis_caches_client(self):
        settings.RATE_LIMIT_USE_SIMPLIFIED = False
        rl = RateLimiter()
        fake = object()
        with patch.object(_redis_manager, "get_client_async", new=AsyncMock(return_value=fake)):
            assert await rl._get_redis() is fake
            assert await rl._get_redis() is fake  # second call uses cached attr

    def test_get_tier_anonymous(self):
        assert RateLimiter()._get_tier(_fake_request(user=None)) == "anonymous"

    def test_get_tier_dict_shapes(self):
        rl = RateLimiter()
        assert rl._get_tier(_fake_request(user={"role": "admin"})) == "admin"
        assert rl._get_tier(_fake_request(user={"is_premium": True})) == "premium"
        assert rl._get_tier(_fake_request(user={"role": "user"})) == "authenticated"

    def test_get_tier_object_shapes(self):
        rl = RateLimiter()
        admin = SimpleNamespace(role="admin", is_premium=False)
        premium = SimpleNamespace(role=None, is_premium=True)
        plain = SimpleNamespace(role=None, is_premium=False)
        assert rl._get_tier(_fake_request(user=admin)) == "admin"
        assert rl._get_tier(_fake_request(user=premium)) == "premium"
        assert rl._get_tier(_fake_request(user=plain)) == "authenticated"


class TestRateLimits:
    async def test_get_limits_endpoint_override_list(self):
        req = _fake_request(path="/api/chat/stream")
        with patch(
            "core.rate_limit.ConfigService.get_config",
            new=AsyncMock(return_value={"/api/chat/stream": [7, 30]}),
        ):
            limit, window = await RateLimiter()._get_limits(req, "/api/chat/stream", "anonymous")
        assert (limit, window) == (7, 30)

    async def test_get_limits_endpoint_override_dict(self):
        req = _fake_request(path="/api/ai/generate")
        with patch(
            "core.rate_limit.ConfigService.get_config",
            new=AsyncMock(return_value={"/api/ai/generate": {"limit": 11, "window": 22}}),
        ):
            limit, window = await RateLimiter()._get_limits(req, "/api/ai/generate", "anonymous")
        assert (limit, window) == (11, 22)

    async def test_get_limits_tier_defaults(self):
        req = _fake_request(path="/api/other")
        with patch(
            "core.rate_limit.ConfigService.get_config",
            new=AsyncMock(return_value={"premium": [300, 60]}),
        ):
            limit, window = await RateLimiter()._get_limits(req, "/api/other", "premium")
        assert (limit, window) == (300, 60)

    async def test_get_limits_tier_dict(self):
        req = _fake_request(path="/api/other")
        with patch(
            "core.rate_limit.ConfigService.get_config",
            new=AsyncMock(return_value={"premium": {"limit": 5, "window": 6}}),
        ):
            limit, window = await RateLimiter()._get_limits(req, "/api/other", "premium")
        assert (limit, window) == (5, 6)

    async def test_get_limits_falls_back_to_anonymous(self):
        req = _fake_request(path="/api/other")
        with patch(
            "core.rate_limit.ConfigService.get_config",
            new=AsyncMock(return_value={"anonymous": {"limit": 3, "window": 9}}),
        ):
            limit, window = await RateLimiter()._get_limits(req, "/api/other", "unknown_tier")
        assert (limit, window) == (3, 9)

    async def test_get_limits_class_default_when_anon_missing(self):
        req = _fake_request(path="/api/other")
        with patch(
            "core.rate_limit.ConfigService.get_config",
            new=AsyncMock(return_value={}),
        ):
            limit, window = await RateLimiter()._get_limits(req, "/api/other", "ghost")
        assert (limit, window) == RateLimiter.TIERS["anonymous"]

    def test_static_limits_endpoint_override(self):
        assert RateLimiter()._static_limits("/api/browser/scrape", "admin") == (5, 60)

    def test_static_limits_tier(self):
        assert RateLimiter()._static_limits("/api/none", "premium") == (300, 60)

    def test_static_limits_unknown_shapes(self):
        rl = RateLimiter()
        with (
            patch.object(RateLimiter, "ENDPOINT_OVERRIDES", {"/x": "not-a-tuple"}, create=True),
            patch.object(RateLimiter, "TIERS", {"/x": "bad", "anonymous": "bad2"}, create=True),
        ):
            assert rl._static_limits("/x", "missing") == RateLimiter.TIERS["anonymous"]


class TestFallbackWindow:
    def test_fallback_allows_then_denies(self):
        rl = RateLimiter()
        key = f"fb:{time.time_ns()}"
        allowed, meta = rl._fallback_is_allowed(key, limit=2, window=60)
        assert allowed and meta["remaining"] == 1
        allowed2, meta2 = rl._fallback_is_allowed(key, limit=2, window=60)
        assert allowed2 and meta2["current"] == 2
        allowed3, meta3 = rl._fallback_is_allowed(key, limit=2, window=60)
        assert not allowed3
        assert meta3["remaining"] == 0

    def test_fallback_window_expiry(self):
        rl = RateLimiter()
        key = f"fbexp:{time.time_ns()}"
        rl._fallback_is_allowed(key, limit=1, window=60)
        # Simulate an old timestamp inside the cache window
        from core import rate_limit as rl_mod

        rl_mod.fallback_cache[key] = [time.time() - 999]
        allowed, meta = rl._fallback_is_allowed(key, limit=1, window=60)
        assert allowed  # old entry pruned
        assert meta["current"] == 1

    def test_fallback_exception_fail_open(self):
        rl = RateLimiter()
        with patch.object(RateLimiter, "_fallback_is_allowed", side_effect=None) as _:
            pass
        # Force an exception inside by replacing fallback_cache with a poisoned mapping
        from core import rate_limit as rl_mod

        class Boom(dict):
            def get(self, *a, **kw):
                raise RuntimeError("boom")

        original = rl_mod.fallback_cache
        rl_mod.fallback_cache = Boom()
        try:
            allowed, meta = rl._fallback_is_allowed("k", 5, 60)
            assert allowed and meta["limit"] == 5
        finally:
            rl_mod.fallback_cache = original


class TestIsAllowed:
    async def test_disabled_short_circuits(self):
        rl = RateLimiter(enabled=False)
        allowed, meta = await rl.is_allowed("k", 10, 60)
        assert allowed and meta["remaining"] == 10

    async def test_no_redis_uses_fallback(self):
        rl = RateLimiter()
        with patch.object(rl, "_get_redis", new=AsyncMock(return_value=None)):
            allowed, meta = await rl.is_allowed("fbk", 100, 60)
        assert allowed

    async def test_atomic_redis_path(self):
        rl = RateLimiter()
        redis = MagicMock()
        with (
            patch.object(rl, "_get_redis", new=AsyncMock(return_value=redis)),
            patch("core.cache.rate_limit_atomic.atomic_window_incr", new=AsyncMock(return_value=3)),
        ):
            allowed, meta = await rl.is_allowed("k1", 10, 60)
        assert allowed and meta["current"] == 3 and meta["remaining"] == 7

    async def test_atomic_redis_over_limit(self):
        rl = RateLimiter()
        redis = MagicMock()
        with (
            patch.object(rl, "_get_redis", new=AsyncMock(return_value=redis)),
            patch(
                "core.cache.rate_limit_atomic.atomic_window_incr", new=AsyncMock(return_value=11)
            ),
        ):
            allowed, meta = await rl.is_allowed("k2", 10, 60)
        assert not allowed and meta["remaining"] == 0

    async def test_atomic_error_falls_back(self):
        rl = RateLimiter()
        redis = MagicMock()
        with (
            patch.object(rl, "_get_redis", new=AsyncMock(return_value=redis)),
            patch(
                "core.cache.rate_limit_atomic.atomic_window_incr",
                new=AsyncMock(side_effect=RuntimeError("eval failed")),
            ),
        ):
            allowed, meta = await rl.is_allowed("fbk2", 100, 60)
        assert allowed  # fail-open fallback


class TestCheckRateLimit:
    async def test_headers_when_redis_unavailable(self):
        rl = RateLimiter()
        req = _fake_request(path="/api/chat/stream", user={"role": "admin", "sub": "u-1"})
        with patch.object(rl, "_get_redis", new=AsyncMock(return_value=None)):
            allowed, headers = await rl.check_rate_limit(req)
        assert allowed
        assert headers["X-RateLimit-Limit"] == "30"  # endpoint override for stream
        assert headers["X-RateLimit-Tier"] == "admin"
        assert int(headers["Retry-After"]) >= 1
        assert "ip:10.0.0.1" not in headers["X-RateLimit-Reset"]

    async def test_headers_with_redis_db_limits(self):
        rl = RateLimiter()
        req = _fake_request(path="/api/other", user={"uid": "u-9"})

        async def _cfg(_db, key, default):
            return {"authenticated": (60, 60)} if key == "rate_limit_tiers" else default

        with (
            patch.object(rl, "_get_redis", new=AsyncMock(return_value=MagicMock())),
            patch("core.rate_limit.ConfigService.get_config", new=AsyncMock(side_effect=_cfg)),
            patch("core.cache.rate_limit_atomic.atomic_window_incr", new=AsyncMock(return_value=1)),
        ):
            allowed, headers = await rl.check_rate_limit(req)
        assert allowed
        assert headers["X-RateLimit-Limit"] == "60"  # authenticated tier
        # client id derived from uid
        key = rl._get_client_id(req)
        assert key == "user:u-9"

    async def test_retry_after_bad_reset_uses_default(self):
        rl = RateLimiter()
        req = _fake_request(path="/api/other")

        class _Reset:
            """int()-able but not float()-able → forces the Retry-After fallback."""

            def __int__(self):
                return 120

            def __float__(self):
                raise TypeError("no float")

        meta = {"reset": _Reset(), "remaining": 1}
        with patch.object(rl, "_get_redis", new=AsyncMock(return_value=None)):
            with patch.object(rl, "is_allowed", new=AsyncMock(return_value=(True, meta))):
                allowed, headers = await rl.check_rate_limit(req)
        assert headers["Retry-After"] == "60"
        assert headers["X-RateLimit-Reset"] == "120"


class TestClientID:
    def test_user_dict_prefers_sub_then_uid_then_id(self):
        rl = RateLimiter()
        assert rl._get_client_id(_fake_request(user={"sub": "s"})) == "user:s"
        assert rl._get_client_id(_fake_request(user={"uid": "u"})) == "user:u"
        assert rl._get_client_id(_fake_request(user={"id": "i"})) == "user:i"

    def test_user_object_id(self):
        rl = RateLimiter()
        obj = SimpleNamespace(id="obj-1")
        assert rl._get_client_id(_fake_request(user=obj)) == "user:obj-1"

    def test_ip_fallback(self):
        rl = RateLimiter()
        req = _fake_request(user=None)
        with patch("utils.client_ip.get_client_ip", return_value="8.8.8.8"):
            assert rl._get_client_id(req) == "ip:8.8.8.8"

    def test_unknown_ip_uses_session_hash(self):
        rl = RateLimiter()
        req = _fake_request(user=None, headers={"user-agent": "UA"})
        with patch("utils.client_ip.get_client_ip", return_value="unknown"):
            cid = rl._get_client_id(req)
        assert cid.startswith("ip:unknown:")


class TestMiddleware:
    def _mw(self, limiter=None):
        app = MagicMock()
        return RateLimitMiddleware(app, limiter or RateLimiter())

    async def test_health_paths_bypass(self):
        mw = self._mw()
        call_next = AsyncMock(return_value="response")
        for path in ("/health", "/ready", "/metrics", "/api/v1/health", "/api/health-check"):
            result = await mw.dispatch(_fake_request(path=path), call_next)
            assert result == "response"

    async def test_testing_bypass(self, monkeypatch):
        mw = self._mw()
        monkeypatch.setenv("TESTING", "true")
        call_next = AsyncMock(return_value="ok")
        assert await mw.dispatch(_fake_request(path="/api/chat"), call_next) == "ok"
        call_next.assert_awaited_once()

    async def test_rate_limited_returns_429(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        # dispatch checks PYTEST_CURRENT_TEST — need to temporarily clear it.
        # Since it is set while running tests, emulate via patched os.getenv.
        mw = self._mw(limiter=MagicMock())
        mw.limiter.check_rate_limit = AsyncMock(
            return_value=(False, {"Retry-After": "12", "X-RateLimit-Limit": "1"})
        )
        call_next = AsyncMock()
        with patch("core.rate_limit.os.getenv", side_effect=lambda k, d=None: None):
            resp = await mw.dispatch(_fake_request(path="/api/chat"), call_next)
        assert resp.status_code == 429
        call_next.assert_not_awaited()

    async def test_allowed_sets_headers(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        mw = self._mw(limiter=MagicMock())
        headers = {"X-RateLimit-Limit": "10", "Retry-After": "30"}
        mw.limiter.check_rate_limit = AsyncMock(return_value=(True, headers))
        resp = MagicMock()
        resp.headers = {}
        call_next = AsyncMock(return_value=resp)
        with patch("core.rate_limit.os.getenv", side_effect=lambda k, d=None: None):
            out = await mw.dispatch(_fake_request(path="/api/chat"), call_next)
        assert out is resp
        assert resp.headers["X-RateLimit-Limit"] == "10"


class TestDecorator:
    async def test_decorator_allows(self):
        @rate_limit(limit=5, window=60)
        async def endpoint(request):
            return {"ok": True}

        req = _fake_request()
        with patch.object(
            RateLimiter,
            "is_allowed",
            new=AsyncMock(return_value=(True, {"reset": time.time() + 60})),
        ):
            out = await endpoint(req)
        assert out == {"ok": True}

    async def test_decorator_blocks_with_429(self):
        @rate_limit(limit=1, window=60)
        async def endpoint(request):
            return {"ok": True}

        req = _fake_request()
        with patch.object(
            RateLimiter,
            "is_allowed",
            new=AsyncMock(return_value=(False, {"reset": time.time() + 12})),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(req)
        assert exc_info.value.status_code == 429
