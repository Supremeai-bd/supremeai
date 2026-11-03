"""Deterministic contract tests for tenant quota enforcement."""

from unittest.mock import AsyncMock

import pytest

from backend.tools.tenant_rate_limiter import TenantRateLimiter


class FakeRedis:
    def __init__(self, values=None):
        self.values = values or {}

    async def get(self, key):
        return self.values.get(key)


@pytest.mark.asyncio
async def test_free_tenant_is_allowed_under_rpm_and_rpd_limits(monkeypatch):
    limiter = TenantRateLimiter(redis_client=FakeRedis())
    monkeypatch.setattr(limiter, "get_tier", AsyncMock(return_value="free"))

    result = await limiter.check_quota("tenant-a", cost=0.0)

    assert result == {"allowed": True, "reason": "ok", "tier": "free"}


@pytest.mark.asyncio
async def test_quota_rejects_rpm_exhaustion(monkeypatch):
    limiter = TenantRateLimiter(redis_client=FakeRedis())
    monkeypatch.setattr(limiter, "get_tier", AsyncMock(return_value="free"))
    minute_key = limiter._redis_key("tenant-a", "0:rpm")
    monkeypatch.setattr("backend.tools.tenant_rate_limiter.time.time", lambda: 0)
    limiter.queue.values[minute_key] = str(limiter.billing_tiers["free"]["rpm"])

    result = await limiter.check_quota("tenant-a", cost=0.0)

    assert result["allowed"] is False
    assert result["reason"] == "rpm_exceeded"
    assert result["limit"] == 60


@pytest.mark.asyncio
async def test_admin_override_bypasses_quota_reads(monkeypatch):
    limiter = TenantRateLimiter(redis_client=FakeRedis())
    get_tier = AsyncMock(return_value="pro")
    monkeypatch.setattr(limiter, "get_tier", get_tier)

    result = await limiter.check_quota("tenant-a", cost=10.0, admin_override=True)

    assert result == {"allowed": True, "reason": "admin_override", "tier": "pro"}
    get_tier.assert_awaited_once_with("tenant-a")


@pytest.mark.asyncio
async def test_quota_fails_closed_when_redis_errors(monkeypatch):
    limiter = TenantRateLimiter(redis_client=FakeRedis())
    monkeypatch.setattr(limiter, "get_tier", AsyncMock(return_value="free"))
    limiter.queue.get = AsyncMock(side_effect=RuntimeError("redis unavailable"))

    result = await limiter.check_quota("tenant-a", cost=0.0)

    assert result == {
        "allowed": False,
        "reason": "quota_unavailable",
        "tier": "free",
    }


@pytest.mark.asyncio
async def test_invalid_billing_tier_is_rejected():
    limiter = TenantRateLimiter(redis_client=FakeRedis())

    with pytest.raises(ValueError, match="Invalid tier"):
        await limiter.set_tier("tenant-a", "unknown")
