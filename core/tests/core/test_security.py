from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.config import settings


@pytest.mark.asyncio
async def test_jwt_secret_persistence():
    """Test JWT secret persistence across restarts."""
    original_env = settings.env
    settings.env = "development"
    try:
        # Clear cached property if exists
        if hasattr(settings, "_jwt_secret"):
            delattr(settings, "_jwt_secret")

        secret1 = settings.jwt_secret

        # Clear cached property to simulate reload/restart
        if hasattr(settings, "_jwt_secret"):
            delattr(settings, "_jwt_secret")

        secret2 = settings.jwt_secret
        assert secret1 == secret2
    finally:
        settings.env = original_env


@pytest.mark.asyncio
async def test_cors_origin_validation():
    """Test CORS origin validation in production/staging.

    বাংলা মন্তব্য: নতুন scheme-only validation — operator-configured যেকোনো https:// domain গ্রহণযোগ্য।
    পুরনো hardcoded supremeai.com allowlist সরানো হয়েছে।
    """
    original_env = settings.env
    try:
        # বাংলা মন্তব্য: production-এ non-https origin reject হবে → RuntimeError
        settings.env = "production"
        os.environ["STRICT_CORS_TEST"] = "1"
        os.environ["CORS_ORIGINS"] = "http://insecure-origin.com"
        with pytest.raises(RuntimeError):
            _ = settings.cors_origins

        # বাংলা মন্তব্য: যেকোনো https:// origin এখন গ্রহণযোগ্য (onrender.com, vercel.app, web.app)
        os.environ["CORS_ORIGINS"] = (
            "https://supremeai-studio-client.onrender.com,https://supremeai-lac.vercel.app"
        )
        origins = settings.cors_origins
        assert "https://supremeai-studio-client.onrender.com" in origins
        assert "https://supremeai-lac.vercel.app" in origins
    finally:
        settings.env = original_env
        os.environ.pop("CORS_ORIGINS", None)
        os.environ.pop("STRICT_CORS_TEST", None)


@pytest.mark.asyncio
async def test_rate_limiting_failure_mode():
    """Test rate limiter behavior when Redis is unavailable."""
    from middleware.rate_limiter import AsyncRateLimiter

    limiter = AsyncRateLimiter()
    # বাংলা মন্তব্য (ROOT-CAUSE FIX): tests/conftest.py গোটা টেস্ট স্যুটের জন্য
    # os.environ.setdefault("RATE_LIMIT_ENABLED", "false") সেট করে, যা
    # AsyncRateLimiter.__init__()-এ পড়ে self._rate_limit_enabled = False
    # ফিক্সড হয়ে যায় (constructor সময়ে, os.getenv প্যাচের আগেই)। ফলে
    # acquire()-এর "if not self._rate_limit_enabled: return True" শর্তে
    # সবসময় early-return হতো, নিচের আসল fail-closed/fail-open লজিক কখনো
    # এক্সিকিউটই হতো না। এই টেস্ট যেহেতু নির্দিষ্টভাবে সেই লজিক যাচাই করতে চায়,
    # তাই instance-level flag সরাসরি enable করা হলো।
    limiter._rate_limit_enabled = True

    # Mock redis_manager to return None (simulating down/unavailable)
    with patch("middleware.rate_limiter.redis_manager.get_client_async", return_value=None):
        original_env = settings.env

        # Override os.getenv directly for the CI check inside acquire
        def mock_getenv(key, default=None):
            # বাংলা মন্তব্য (ROOT-CAUSE FIX): AsyncRateLimiter.acquire() শুরুতেই
            # `os.getenv("TESTING") == "true"` চেক করে True রিটার্ন করে দিত (CI-তে
            # TESTING=true সেট থাকে), ফলে নিচের production fail-closed লজিক আদৌ
            # এক্সিকিউট হতো না এবং `assert not True` ব্যর্থ হতো। TESTING-ও এখানে
            # মক করে "false" করা হলো যাতে আসল Redis-down আচরণ যাচাই করা যায়।
            if key in ("CI", "TESTING"):
                return "false"
            return os.environ.get(key, default)

        # বাংলা মন্তব্য (ROOT-CAUSE FIX): আগে এখানে `settings.test_mode = False`
        # সেট করার চেষ্টা হতো, কিন্তু `Settings` মডেলে `test_mode` নামে কোনো ফিল্ড
        # কখনোই ছিল না (repo-wide grep-এ কনফার্ম করা), আর pydantic v2 BaseSettings
        # ডিফল্টভাবে অজানা attribute সেট করতে দেয় না -- তাই `ValueError: "Settings"
        # object has no field "test_mode"` রেইজ হতো। middleware/rate_limiter.py
        # কোথাও `settings.test_mode` পড়েও না, তাই এই লাইনগুলো টেস্টের কোনো আসল
        # আচরণ নিয়ন্ত্রণ করছিল না -- অপ্রয়োজনীয় dead assignment হিসেবে সরানো হলো।
        try:
            with patch("os.getenv", side_effect=mock_getenv):
                # When Redis is unavailable, rate limiter gracefully falls back to in-memory
                # sliding window to prevent complete service outages (zero-downtime resiliency)
                settings.env = "production"
                # First request within limit must succeed via fallback limiter
                assert await limiter.acquire("test_key_resilient", limit=5)
                # Repeated requests exceeding limit must be blocked by fallback limiter
                for _ in range(5):
                    await limiter.acquire("test_key_resilient", limit=5)
                assert not await limiter.acquire("test_key_resilient", limit=5)

                # In development, it also operates cleanly via fallback
                settings.env = "development"
                assert await limiter.acquire("dev_test_key", limit=10)
        finally:
            settings.env = original_env
