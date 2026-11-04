# backend/tests/middleware/test_chaos_injector.py
"""ChaosInjectorMiddleware ইউনিট টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-2।

এই ফাইলের টেস্টগুলো `chaos` marker বহন করে না — মিডলওয়্যারের নিজস্ব
লজিক (429/504/latency ইনজেকশন, off-switch, production bypass) PR-CI-তেই
দ্রুত যাচাই হবে। আসল কেওস ড্রিল (breaker ট্রিগার ইত্যাদি) পাবেন
tests/chaos/test_chaos_resilience.py-তে (রাতের chaos job)।

আগে এই মিডলওয়্যারের কোনো টেস্টই ছিল না (কোড কমেন্ট দাবি করলেও)।
CI-safe: আসল HTTP নেই — dispatch() সরাসরি, ফেক request।
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from starlette.responses import JSONResponse, Response

from core.middleware.chaos_injector import (
    _DEFAULT_DELAY_THRESHOLD,
    _DEFAULT_DROP_THRESHOLD,
    _DEFAULT_RATE_LIMIT_THRESHOLD,
    ChaosInjectorMiddleware,
)

pytestmark = pytest.mark.important


def _fake_request(path: str = "/api/test") -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path=path))


def _make_middleware(monkeypatch, **env: str) -> ChaosInjectorMiddleware:
    """env সেট করে middleware কনস্ট্রাক্ট — init-সময়ের env রিডের জন্য।"""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return ChaosInjectorMiddleware(app=_dummy_asgi_app)


async def _dummy_asgi_app(scope: Any, receive: Any, send: Any) -> None:  # pragma: no cover
    """BaseHTTPMiddleware-এর জন্য ন্যূনতম ASGI app — ব্যবহৃত হয় না (dispatch সরাসরি)।"""


def _ok_call_next() -> AsyncMock:
    mock = AsyncMock(return_value=Response("ok", status_code=200))
    return mock


class TestOffSwitches:
    async def test_disabled_by_default_bypasses(self, monkeypatch):
        """Given: LOCAL_CHAOS_MODE সেট করা নেই।
        When: dispatch চালালে।
        Then: chaos নেই — call_next সরাসরি ডাকা হয়।
        """
        monkeypatch.delenv("LOCAL_CHAOS_MODE", raising=False)
        monkeypatch.setenv("ENV", "local")
        mw = _make_middleware(monkeypatch)
        call_next = _ok_call_next()

        response = await mw.dispatch(_fake_request(), call_next)

        assert response.status_code == 200
        call_next.assert_awaited_once()

    async def test_production_bypasses_even_when_enabled(self, monkeypatch):
        """Given: LOCAL_CHAOS_MODE=true কিন্তু ENV=production।
        When: dispatch চালালে।
        Then: সম্পূর্ণ bypass — production-এ কখনোই কেওস নয়।
        """
        mw = _make_middleware(monkeypatch, LOCAL_CHAOS_MODE="true", ENV="production")
        call_next = _ok_call_next()

        response = await mw.dispatch(_fake_request(), call_next)

        assert response.status_code == 200
        call_next.assert_awaited_once()

    async def test_zero_chances_never_inject(self, monkeypatch):
        """Given: chaos চালু কিন্তু সব chance=0।
        When: ২০ বার dispatch চালালে।
        Then: একবারও fault ইনজেক্ট হয় না।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_RATE_LIMIT_CHANCE="0",
            CHAOS_PACKET_DROP_CHANCE="0",
            CHAOS_LATENCY_CHANCE="0",
        )
        for _ in range(20):
            call_next = _ok_call_next()
            response = await mw.dispatch(_fake_request(), call_next)
            assert response.status_code == 200
            call_next.assert_awaited_once()


class TestRateLimitInjection:
    async def test_full_chance_returns_429_with_retry_after(self, monkeypatch):
        """Given: CHAOS_RATE_LIMIT_CHANCE=1.0 (নিশ্চিত ইনজেকশন)।
        When: dispatch চালালে।
        Then: HTTP 429 + Retry-After হেডার + স্পষ্ট fallback বার্তা।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_RATE_LIMIT_CHANCE="1.0",
        )
        call_next = _ok_call_next()

        response = await mw.dispatch(_fake_request("/api/chat/completion"), call_next)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 429
        assert response.headers.get("retry-after") == "60", "Retry-After হেডার চাই"
        body = response.body.decode() if isinstance(response.body, bytes) else str(response.body)
        assert "rate limit" in body.lower(), f"ইউজার-বোধগম্য বার্তা নেই: {body}"
        call_next.assert_not_awaited()

    async def test_default_rate_limit_chance_is_off(self, monkeypatch):
        """Given: কোনো override নেই।
        When: middleware কনস্ট্রাক্ট হলে।
        Then: 429-চ্যান্স ডিফল্টে 0 — অজান্তে কেওস নয়।
        """
        monkeypatch.delenv("CHAOS_RATE_LIMIT_CHANCE", raising=False)
        mw = _make_middleware(monkeypatch, LOCAL_CHAOS_MODE="true", ENV="local")
        assert mw.rate_limit_threshold == _DEFAULT_RATE_LIMIT_THRESHOLD == 0.0


class TestPacketDropAndLatency:
    async def test_full_drop_chance_returns_504(self, monkeypatch):
        """Given: CHAOS_PACKET_DROP_CHANCE=1.0, rate-limit বন্ধ।
        When: dispatch চালালে।
        Then: HTTP 504 packet-drop।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_RATE_LIMIT_CHANCE="0",
            CHAOS_PACKET_DROP_CHANCE="1.0",
        )
        response = await mw.dispatch(_fake_request(), _ok_call_next())
        assert response.status_code == 504

    async def test_full_latency_chance_still_reaches_backend(self, monkeypatch):
        """Given: CHAOS_LATENCY_CHANCE=1.0, drop বন্ধ।
        When: dispatch চালালে।
        Then: বিলম্বের পরেও backend পৌঁছায় (200) — latency ইনজেকশন
        রেসপন্স হারায় না।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_RATE_LIMIT_CHANCE="0",
            CHAOS_PACKET_DROP_CHANCE="0",
            CHAOS_LATENCY_CHANCE="1.0",
        )
        call_next = _ok_call_next()
        response = await mw.dispatch(_fake_request(), call_next)
        assert response.status_code == 200
        call_next.assert_awaited_once()


class TestEnvParsing:
    async def test_invalid_env_value_falls_back_to_default(self, monkeypatch):
        """Given: CHAOS_RATE_LIMIT_CHANCE='banana'।
        When: middleware কনস্ট্রাক্ট হলে।
        Then: ডিফল্ট 0.0-এ ফলব্যাক — ক্র্যাশ নয়, নীরব নয় (warning log)।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_RATE_LIMIT_CHANCE="banana",
        )
        assert mw.rate_limit_threshold == 0.0

    async def test_out_of_range_env_value_falls_back(self, monkeypatch):
        """Given: CHAOS_PACKET_DROP_CHANCE='5.0' (>1.0)।
        When: middleware কনস্ট্রাক্ট হলে।
        Then: ডিফল্ট 0.15-এ ফলব্যাক।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_PACKET_DROP_CHANCE="5.0",
        )
        assert mw.drop_threshold == _DEFAULT_DROP_THRESHOLD

    async def test_defaults_preserved_when_no_env(self, monkeypatch):
        """Given: কোনো chance env নেই।
        When: middleware কনস্ট্রাক্ট হলে।
        Then: পুরনো ডিফল্ট আচরণ অপরিবর্তিত (drop 0.15, delay 0.30)।
        """
        for var in ("CHAOS_RATE_LIMIT_CHANCE", "CHAOS_PACKET_DROP_CHANCE", "CHAOS_LATENCY_CHANCE"):
            monkeypatch.delenv(var, raising=False)
        mw = _make_middleware(monkeypatch, LOCAL_CHAOS_MODE="true", ENV="local")
        assert mw.drop_threshold == _DEFAULT_DROP_THRESHOLD
        assert mw.delay_threshold == _DEFAULT_DELAY_THRESHOLD

    async def test_latency_band_respects_rate_limit_offset(self, monkeypatch):
        """Given: rate_limit=0.5, drop=0.3 (cascade ব্যান্ড)।
        When: থ্রেশহোল্ড যাচাই করলে।
        Then: ব্যান্ডগুলো যোগফাল-ভিত্তিক — ডকুমেন্টেড cascade চুক্তি।
        """
        mw = _make_middleware(
            monkeypatch,
            LOCAL_CHAOS_MODE="true",
            ENV="local",
            CHAOS_RATE_LIMIT_CHANCE="0.5",
            CHAOS_PACKET_DROP_CHANCE="0.3",
        )
        assert mw.rate_limit_threshold == pytest.approx(0.5)
        assert mw.drop_threshold == pytest.approx(0.3)


class TestChaosEngineFaultTypes:
    async def test_rate_limit_fault_raises_connection_error(self, monkeypatch):
        """Given: ENABLE_CHAOS_MODE=true ইঞ্জিন।
        When: inject_fault('rate_limit_429') ডাকা হলে।
        Then: ConnectionError — health-probe-এর try/except degraded-পথে যাবে।
        """
        from core.resilience.chaos_engine import ChaosEngine

        engine = ChaosEngine()
        monkeypatch.setattr(engine, "enabled", True)
        with pytest.raises(ConnectionError, match="429"):
            await engine.inject_fault("rate_limit_429")

    async def test_memory_pressure_fault_raises_memory_error(self, monkeypatch):
        """Given: চালু ইঞ্জিন।
        When: inject_fault('memory_pressure')।
        Then: MemoryError — OOM-adjacent সিমুলেশন।
        """
        from core.resilience.chaos_engine import ChaosEngine

        engine = ChaosEngine()
        monkeypatch.setattr(engine, "enabled", True)
        with pytest.raises(MemoryError):
            await engine.inject_fault("memory_pressure")

    async def test_unknown_fault_type_raises_value_error(self, monkeypatch):
        """Given: চালু ইঞ্জিন।
        When: অজানা fault_type দিলে।
        Then: স্পষ্ট ValueError — নীরব উপেক্ষা নয়।
        """
        from core.resilience.chaos_engine import ChaosEngine

        engine = ChaosEngine()
        monkeypatch.setattr(engine, "enabled", True)
        with pytest.raises(ValueError, match="Unknown chaos fault type"):
            await engine.inject_fault("definitely_not_a_fault")

    async def test_disabled_engine_is_silent_noop(self):
        """Given: বন্ধ ইঞ্জিন (ডিফল্ট)।
        When: inject_fault('memory_pressure') ডাকা হলে।
        Then: কিছুই হয় না — ডিফল্টে কেওস নয়।
        """
        from core.resilience.chaos_engine import ChaosEngine

        engine = ChaosEngine()  # ENABLE_CHAOS_MODE unset
        assert engine.enabled is False
        await engine.inject_fault("memory_pressure")  # কোনো exception নয়

    async def test_fault_types_registry_contains_new_faults(self):
        """Given: CHAOS_FAULT_TYPES রেজিস্ট্রি।
        When: পরীক্ষা করলে।
        Then: rate_limit_429 ও memory_pressure উভয়ই তালিকাভুক্ত।
        """
        from core.resilience.chaos_engine import CHAOS_FAULT_TYPES

        assert "rate_limit_429" in CHAOS_FAULT_TYPES
        assert "memory_pressure" in CHAOS_FAULT_TYPES
