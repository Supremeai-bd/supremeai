# backend/tests/services/test_provider_rate_limiter.py
"""Tests for IntelligentRateLimiter and CloudDBTester."""

import pytest

from core.provider_rate_limiter import get_provider_rate_limiter
from tests.cloud_db_load_test import CloudDBTester


@pytest.mark.asyncio
async def test_intelligent_rate_limiter_request():
    limiter = get_provider_rate_limiter()
    res = await limiter.make_request("Explain quicksort in Python")
    assert res["success"] is True
    assert res["provider_used"] in [
        "Gemini",
        "Groq",
        "OpenRouter",
        "Ollama Local",
        "gemini",
        "groq",
        "openrouter",
        "ollama_local",
    ]


@pytest.mark.asyncio
async def test_cloud_db_tester_quick_test():
    """CloudDBTester-এর সৎ চুক্তি (#4217 Phase 1)।

    বাংলা নোট: পুরনো সংস্করণ মক টার্গেটেও sleep-বানানো মান দিয়ে
    connection_ok=True / successful_ops>0 ফেরাত — এই টেস্টের পুরনো পাসটি
    সেই ভুয়া-সবুজের উপর দাঁড়িয়ে ছিল। এখন দুই-শাখা সৎ যাচাই: আসল
    টার্গেট থাকলে আসল মাপের সফলতা; না থাকলে সৎ not-ok/শূন্য-অপ।
    """
    tester = CloudDBTester()
    init_ok = await tester.initialize()
    assert init_ok is True  # client-object তৈরি (supabase ইনস্টলড) — নেটওয়ার্ক নয়

    health = await tester.health_check()
    res = await tester.run_quick_test()

    if tester.has_real_target():
        # আসল Supabase টার্গেট — আসল প্রোব ও আসল মাপ
        assert health.connection_ok is True
        assert res.successful_ops > 0
        assert res.error_rate == 0.0
    else:
        # মক/অনুপস্থিত টার্গেট — সৎ ব্যর্থতা-রিপোর্ট, ভুয়া সবুজ নয়
        assert health.connection_ok is False
        assert res.successful_ops == 0
        assert res.total_operations == 0

    # generate_report: পুরনো dict-শেপ, কিন্তু হার্ডকোডেড "EXCELLENT ✅" নয়
    report = tester.generate_report()
    assert isinstance(report, dict)
    assert "summary" in report
    assert report["summary"]["overall_health"] in (
        "HEALTHY",
        "DEGRADED",
        "UNHEALTHY",
        "NO TARGET",
        "NO DATA",
    )
