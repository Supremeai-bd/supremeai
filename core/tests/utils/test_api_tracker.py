import time

from utils.api_tracker import APICallRecord, APITracker, get_tracker


class TestAPITracker:
    def test_record_and_get_recent(self):
        tracker = APITracker()
        record = APICallRecord(
            provider="openai",
            model="gpt-4",
            tokens=100,
            cost=0.01,
            latency_ms=120.5,
            timestamp=time.time(),
            success=True,
        )
        tracker.record(record)
        recent = tracker.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].provider == "openai"

    def test_get_recent_empty(self):
        tracker = APITracker()
        recent = tracker.get_recent(limit=5)
        assert recent == []

    def test_get_recent_limit(self):
        tracker = APITracker()
        for i in range(10):
            tracker.record(
                APICallRecord(
                    provider=f"p{i}",
                    model=f"m{i}",
                    tokens=i,
                    cost=i * 0.01,
                    latency_ms=100.0,
                    timestamp=time.time(),
                    success=True,
                )
            )
        recent = tracker.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_tracker_singleton(self):
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2

    def test_record_with_error(self):
        tracker = APITracker()
        record = APICallRecord(
            provider="openai",
            model="gpt-4",
            tokens=0,
            cost=0.0,
            latency_ms=0.0,
            timestamp=time.time(),
            success=False,
            error="rate limit",
        )
        tracker.record(record)
        recent = tracker.get_recent()
        assert recent[0].error == "rate limit"
        assert recent[0].success is False
