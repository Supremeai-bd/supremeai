"""Issue #1703 (CRITICAL) — systemic fail-open on Redis failure: rate limiters.

This locks the last of the three guards named by #1703 (self-evolution lock
and token budget were fixed under #1685/#1687). Redis-down must degrade to an
in-memory guard — never unlimited allow, never full deny-outage.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.rate_limit_quota import DailyQuotaLimiter
from core.security.api_key_limiter import enforce_api_key_rate_limit


def _broken_quota_limiter() -> DailyQuotaLimiter:
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")

    async def broken_redis():
        raise ConnectionError("redis down")

    limiter.get_redis = broken_redis
    return limiter


class TestDailyQuotaFallback:
    async def test_redis_down_allows_within_limit_then_denies(self):
        limiter = _broken_quota_limiter()
        results = [await limiter.check_daily_quota("u-1", "anonymous") for _ in range(51)]
        # anonymous limit = 50 → first 50 allowed, 51st denied (was: always True)
        assert results[:50] == [True] * 50
        assert results[50] is False

    async def test_redis_down_respects_tier_limit(self):
        limiter = _broken_quota_limiter()
        for _ in range(500):
            assert await limiter.check_daily_quota("u-auth", "authenticated") is True
        assert await limiter.check_daily_quota("u-auth", "authenticated") is False

    async def test_redis_down_users_isolated(self):
        limiter = _broken_quota_limiter()
        for _ in range(50):
            await limiter.check_daily_quota("u-a", "anonymous")
        assert await limiter.check_daily_quota("u-a", "anonymous") is False
        assert await limiter.check_daily_quota("u-b", "anonymous") is True

    async def test_redis_healthy_uses_redis_truth(self):
        limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
        redis = MagicMock()
        redis.incr = AsyncMock(return_value=2)
        redis.expire = AsyncMock(return_value=True)
        limiter._redis = redis
        assert await limiter.check_daily_quota("u-ok", "authenticated") is True
        redis.incr.assert_awaited_once()


class TestApiKeyLimiterFallback:
    async def test_no_redis_under_limit_passes(self):
        manager = MagicMock()
        manager.client = None
        with patch("core.cache.redis_manager.redis_manager", manager):
            await enforce_api_key_rate_limit("fresh-key-hash", max_requests=60)

    async def test_no_redis_over_limit_429(self):
        manager = MagicMock()
        manager.client = None
        with patch("core.cache.redis_manager.redis_manager", manager):
            with pytest.raises(HTTPException) as exc:
                for _ in range(61):
                    await enforce_api_key_rate_limit("flooded-key-hash", max_requests=60)
            assert exc.value.status_code == 429

    async def test_unexpected_redis_error_uses_fallback(self):
        client = MagicMock()
        client.eval = AsyncMock(return_value=1)  # redis "works"
        manager = MagicMock()
        manager.client = client
        with patch("core.cache.redis_manager.redis_manager", manager):
            # Under fallback limit → allowed (existing contract test passes too)
            await enforce_api_key_rate_limit("boom-key-hash", max_requests=10_000)

        # Now simulate redis raising mid-flight with a tiny fallback limit
        client.eval = AsyncMock(side_effect=Exception("redis boom"))
        with patch("core.cache.redis_manager.redis_manager", manager):
            # fallback window (max=2): first 2 calls pass, 3rd hits 429
            await enforce_api_key_rate_limit("boom2-key", max_requests=2)
            await enforce_api_key_rate_limit("boom2-key", max_requests=2)
            with pytest.raises(HTTPException) as exc:
                await enforce_api_key_rate_limit("boom2-key", max_requests=2)
            assert exc.value.status_code == 429
