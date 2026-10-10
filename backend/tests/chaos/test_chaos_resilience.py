# backend/tests/chaos/test_chaos_resilience.py
"""কেওস ড্রিল স্যুট — ৩-স্তর টেস্টিং প্ল্যান Tier-2 (Phase 2)।

রিপোর প্রথম `pytest.mark.chaos` ব্যবহারকারী টেস্ট (marker ঘোষিত ছিল,
ব্যবহার ছিল শূন্য; pr.yml deselect করে, nightly chaos-suite job চালায়)।

পরিকল্পনার মূল দৃশ্য: "কৃত্রিমভাবে ৪২৯-storm তৈরি করে predictive_circuit_breaker
এবং degraded fallback ঠিকমতো ট্রিগার হয় কি না" + "মেমোরি-চাপে task_queue
নতুন রিকোয়েস্ট hold করছে কি না"। সব লোকাল — কোনো নেটওয়ার্ক/আসল LLM নেই।
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from core.queue.task_queue_enhanced import TaskQueue, TaskQueueOverflowError
from core.resilience.predictive_circuit_breaker import (
    CircuitBreakerState,
    PredictiveCircuitBreaker,
)
from core.resilience.predictive_metrics import PredictiveMetricsTracker
from middleware.chaos_injector import ChaosInjectorMiddleware

pytestmark = pytest.mark.chaos


async def _dummy_asgi_app(scope: Any, receive: Any, send: Any) -> None:  # pragma: no cover
    """BaseHTTPMiddleware-এর জন্য ন্যূনতম ASGI app।"""


def _fake_request(path: str = "/api/chat/completion") -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path=path))


class TestRateLimitStormOpensPredictiveBreaker:
    def test_five_consecutive_429s_open_breaker(self):
        """Given: PredictiveCircuitBreaker (fallback=openrouter)।
        When: পাঁচটি টানা 429 (provider rate-limit) রেকর্ড হলে।
        Then: tracker অ্যানমেলি ধরে → breaker OPEN → fallback provider সক্রিয়।
        (আগে 429 গোনাই হতো না — বাস্তব rate-limit storm কখনো breaker খুলত না।)
        """
        breaker = PredictiveCircuitBreaker("chaos-429-storm", fallback_provider="openrouter")
        for _ in range(5):
            breaker.record_request_outcome(120.0, 429)

        assert breaker.tracker.is_anomaly_detected() is True, (
            "৪২৯-storm অ্যানমেলি হিসেবে ধরা পড়েনি — Tier-2 ফিক্স ভাঙছে"
        )
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.get_active_provider() == "openrouter"

    def test_intermittent_429s_do_not_open_breaker(self):
        """Given: 429 আর 200 মিশ্রিত (টানা নয়)।
        When: রেকর্ড হলে।
        Then: breaker খোলে না — false-positive গার্ড।
        """
        breaker = PredictiveCircuitBreaker("chaos-mixed")
        for status in (429, 200, 429, 200, 429, 200):
            breaker.record_request_outcome(100.0, status)

        assert breaker.tracker.consecutive_errors < 5
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_429_counts_in_error_rate(self):
        """Given: ১০টি রিকোয়েস্টের মধ্যে ২টি 429।
        When: get_error_rate() ডাকা হলে।
        Then: ২০% — 429 এরর-রেটের অন্তর্ভুক্ত।
        """
        tracker = PredictiveMetricsTracker()
        for status in (429, 429, 200, 200, 200, 200, 200, 200, 200, 200):
            tracker.record_request(50.0, status)
        assert tracker.get_error_rate() == pytest.approx(20.0)

    def test_recovery_closes_breaker_after_429_storm(self):
        """Given: 429-storm-এ OPEN হওয়া breaker।
        When: ঠান্ডা হয়ে HALF_OPEN হয়ে recovery সফল হলে।
        Then: CLOSED-এ ফেরত — স্থায়ী ব্লক নয়।
        """
        import time as _time
        from unittest.mock import patch

        breaker = PredictiveCircuitBreaker("chaos-recover", cooldown_seconds=60)
        for _ in range(5):
            breaker.record_request_outcome(100.0, 429)
        assert breaker.state == CircuitBreakerState.OPEN

        # কোল্ডডাউন পেরিয়ে প্রোব (প্রমাণিত time-patch প্যাটার্ন)
        with patch(
            "core.resilience.predictive_circuit_breaker.time.time",
            return_value=_time.time() + 61,
        ):
            assert breaker.get_active_provider() == "gemini"  # HALF_OPEN probe → primary
        breaker.mark_recovery_success()
        assert breaker.state == CircuitBreakerState.CLOSED


class TestMiddleware429StormClientExperience:
    async def test_429_storm_then_recovery_full_loop(self, monkeypatch):
        """Given: chaos middleware 429 ইনজেক্ট করছে (chance=1.0), তারপর স্বাভাবিক।
        When: ক্লায়েন্ট প্রথমে ৩টি 429 পায়, তারপর কেওস বন্ধ হলে।
        Then: ৪২৯-গুলো Retry-After বহন করে এবং কেওস বন্ধ হলে 200 ফেরে —
        গ্রেসফুল রিকভারি, ক্র্যাশ নয়।
        """
        monkeypatch.setenv("LOCAL_CHAOS_MODE", "true")
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("CHAOS_RATE_LIMIT_CHANCE", "1.0")
        storm_mw = ChaosInjectorMiddleware(app=_dummy_asgi_app)

        for _ in range(3):
            response = await storm_mw.dispatch(_fake_request(), AsyncMock(return_value=None))
            assert response.status_code == 429
            assert response.headers.get("retry-after") == "60"

        # কেওস থামল — নতুন ইনস্ট্যান্স (init-সময়ের env রিড)
        monkeypatch.setenv("CHAOS_RATE_LIMIT_CHANCE", "0.0")
        monkeypatch.setenv("CHAOS_PACKET_DROP_CHANCE", "0.0")
        monkeypatch.setenv("CHAOS_LATENCY_CHANCE", "0.0")
        calm_mw = ChaosInjectorMiddleware(app=_dummy_asgi_app)
        call_next = AsyncMock(return_value=None)
        # call_next সরাসরি Response না ফেরালে dispatch সেটাই ফেরায়
        from starlette.responses import Response as _Resp

        call_next = AsyncMock(return_value=_Resp("ok", status_code=200))
        response = await calm_mw.dispatch(_fake_request(), call_next)
        assert response.status_code == 200
        call_next.assert_awaited_once()


class TestTaskQueueMemoryPressureHold:
    async def test_memory_pressure_holds_new_submissions(self, monkeypatch):
        """Given: সিস্টেম RAM-চাপে আছে (_system_memory_pressure → True)।
        When: নতুন task submit করা হলে।
        Then: TaskQueueOverflowError ("memory pressure") — caller 429 দেবে;
        task ভেতরে ঢোকে না (OOM রোধ)।
        """
        import core.queue.task_queue_enhanced as tq

        monkeypatch.setattr(tq, "_system_memory_pressure", lambda pct: True)
        queue = TaskQueue(default_backend=tq.QueueBackend.ASYNCIO)

        with pytest.raises(TaskQueueOverflowError, match="memory pressure"):
            await queue.submit_task(asyncio.sleep, 0)

    async def test_no_pressure_submissions_flow_normally(self, monkeypatch):
        """Given: RAM-চাপ নেই (_system_memory_pressure → False)।
        When: task submit করা হলে।
        Then: স্বাভাবিকভাবে task_id ফেরে — hold শুধু চাপের সময়।
        """
        import core.queue.task_queue_enhanced as tq

        monkeypatch.setattr(tq, "_system_memory_pressure", lambda pct: False)
        queue = TaskQueue(default_backend=tq.QueueBackend.ASYNCIO)

        task_id = await queue.submit_task(asyncio.sleep, 0)
        assert task_id, "স্বাভাবিক পথে task_id ফেরেনি"
        # cleanup: worker চলুক শেষ হতে
        await asyncio.sleep(0.1)

    async def test_hold_message_is_actionable_for_429_mapping(self, monkeypatch):
        """Given: RAM-চাপে hold হচ্ছে।
        When: এরর বার্তা পরীক্ষা করলে।
        Then: বার্তায় 'try again later' আছে — caller-এর 429-mapping চুক্তি।
        """
        import core.queue.task_queue_enhanced as tq

        monkeypatch.setattr(tq, "_system_memory_pressure", lambda pct: True)
        queue = TaskQueue(default_backend=tq.QueueBackend.ASYNCIO)

        with pytest.raises(TaskQueueOverflowError, match="try again later"):
            await queue.submit_task(asyncio.sleep, 0)

    async def test_threshold_env_override_respected(self, monkeypatch):
        """Given: TASK_QUEUE_MEMORY_HOLD_PCT=50 (কড়া থ্রেশহোল্ড)।
        When: TaskQueue কনস্ট্রাক্ট হলে।
        Then: hold থ্রেশহোল্ড ৫০ — env টিউনেবল কাজ করছে।
        """
        import core.queue.task_queue_enhanced as tq

        monkeypatch.setenv("TASK_QUEUE_MEMORY_HOLD_PCT", "50")
        assert tq._default_memory_hold_threshold() == 50
        queue = TaskQueue(default_backend=tq.QueueBackend.ASYNCIO)
        assert queue._memory_hold_threshold == 50
