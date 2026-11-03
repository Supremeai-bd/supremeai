from unittest.mock import AsyncMock

import pytest

from core.rate_limit_quota import DailyQuotaLimiter


@pytest.mark.asyncio
async def test_check_daily_quota_under_limit_allowed():
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock()
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
    limiter.get_redis = AsyncMock(return_value=fake_redis)

    assert await limiter.check_daily_quota("user-1", "authenticated") is True
    fake_redis.incr.assert_awaited()
    fake_redis.expire.assert_awaited()


@pytest.mark.asyncio
async def test_check_daily_quota_exceeded_denied():
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=501)
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
    limiter.get_redis = AsyncMock(return_value=fake_redis)

    assert await limiter.check_daily_quota("user-2", "authenticated") is False


@pytest.mark.asyncio
async def test_check_daily_quota_unknown_tier_defaults_to_anonymous():
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=51)
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
    limiter.get_redis = AsyncMock(return_value=fake_redis)

    assert await limiter.check_daily_quota("user-3", "unknown-tier") is False


@pytest.mark.asyncio
async def test_check_daily_quota_admin_never_exceeds():
    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=999999)
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
    limiter.get_redis = AsyncMock(return_value=fake_redis)

    assert await limiter.check_daily_quota("admin-1", "admin") is True


@pytest.mark.asyncio
async def test_check_daily_quota_fails_open_on_redis_error():
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
    limiter.get_redis = AsyncMock(side_effect=Exception("redis down"))

    assert await limiter.check_daily_quota("user-4", "premium") is True


def test_daily_limits_are_ordered():
    limiter = DailyQuotaLimiter(redis_url="redis://localhost:6379/0")
    assert limiter.DAILY_LIMITS["anonymous"] < limiter.DAILY_LIMITS["authenticated"]
    assert limiter.DAILY_LIMITS["authenticated"] < limiter.DAILY_LIMITS["premium"]
    assert limiter.DAILY_LIMITS["premium"] < limiter.DAILY_LIMITS["admin"]
