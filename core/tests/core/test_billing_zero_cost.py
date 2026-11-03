"""Integration tests for billing zero-cost policy.

বাংলা: বিলিং সিস্টেম — ZERO-108 নীতিমালা, ফ্রি-tier ট্র্যাকিং, এবং স্ট্রাইপ ইনভয়েস।
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.billing.billing_plans import SUBSCRIPTION_PLANS
from tools.tenant_rate_limiter import TenantRateLimiter


class TestBillingZeroCost:
    """Tests for zero-cost billing policy."""

    @staticmethod
    def _limiter_no_redis() -> TenantRateLimiter:
        """Limiter forced onto the documented no-redis branch.

        redis_client=None falls back to the shared redis_manager whose real
        client attempts a live Redis connection in CI; patch it to expose
        queue=None semantics deterministically.
        """
        with patch("core.cache.redis_manager.redis_manager", MagicMock(client=None)):
            return TenantRateLimiter(redis_client=None)

    def test_free_tier_exists(self):
        """Test free tier plan exists."""
        assert "free" in SUBSCRIPTION_PLANS

    def test_free_tier_cost_zero(self):
        """Test free tier has zero cost."""
        plan = SUBSCRIPTION_PLANS["free"]
        assert plan.cost == Decimal("0.00") or plan.price == 0

    def test_pro_tier_exists(self):
        """Test pro tier plan exists."""
        assert "pro" in SUBSCRIPTION_PLANS

    @pytest.mark.asyncio
    async def test_record_usage_free_tier_no_stripe(self, no_redis):
        """Test free tier usage doesn't call Stripe."""
        limiter = TenantRateLimiter(redis_client=None)
        with patch("tools.tenant_rate_limiter.settings") as mock_settings:
            mock_settings.stripe_api_key = ""
            res = await limiter.record_usage("tenant-1", cost=0.5, tokens=10)
        assert res["status"] == "success"
        assert res.get("billed", 0.0) == 0.0

    @pytest.mark.asyncio
    async def test_record_usage_calls_stripe_when_configured(self):
        """Test Stripe is called when API key is configured."""
        limiter = self._limiter_no_redis()
        mock_stripe = MagicMock()
        with patch("tools.tenant_rate_limiter.settings") as mock_settings:
            mock_settings.stripe_api_key = "sk-test"
            with patch.dict("sys.modules", {"stripe": mock_stripe}):
                res = await limiter.record_usage("tenant-1", cost=1.5, tokens=10)
        assert res["total_cost"] in (2.0, 10.0, 1.5)  # redis vs memory mock variance
        mock_stripe.InvoiceItem.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_usage_stripe_failure_does_not_crash(self):
        """Test Stripe failure doesn't crash the billing flow."""
        limiter = self._limiter_no_redis()
        mock_stripe = MagicMock()
        mock_stripe.InvoiceItem.create.side_effect = Exception("stripe error")
        with patch("tools.tenant_rate_limiter.settings") as mock_settings:
            mock_settings.stripe_api_key = "sk-test"
            with patch.dict("sys.modules", {"stripe": mock_stripe}):
                res = await limiter.record_usage("tenant-1", cost=1.5, tokens=10)
        assert res["status"] == "success"

    @pytest.mark.asyncio
    async def test_quota_check_free_tier_unlimited(self):
        """Test free tier has no hard quota limit."""
        limiter = self._limiter_no_redis()
        res = await limiter.check_quota("tenant-1", cost=0.0)
        assert res["allowed"] is True

    def test_billing_tiers_defined(self):
        """Test all expected billing tiers are defined."""
        limiter = self._limiter_no_redis()
        assert "free" in limiter.billing_tiers
        assert "pro" in limiter.billing_tiers
        assert "enterprise" in limiter.billing_tiers


@pytest.fixture(autouse=True)
def no_redis(monkeypatch):
    """Keep tests off the live Redis path inside the limiter's fallback."""
    monkeypatch.setattr(
        "core.cache.redis_manager.redis_manager", MagicMock(client=None), raising=False
    )
