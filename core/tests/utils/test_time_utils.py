from datetime import UTC, datetime, timedelta

from core.utils.time_utils import ensure_aware, utc_expiry, utc_now


class TestUtcNow:
    def test_returns_datetime(self):
        assert isinstance(utc_now(), datetime)

    def test_is_utc_aware(self):
        now = utc_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == datetime.now(UTC).utcoffset()

    def test_recent(self):
        before = datetime.now(UTC)
        now = utc_now()
        after = datetime.now(UTC)
        assert before <= now <= after


class TestUtcExpiry:
    def test_default_now(self):
        exp = utc_expiry()
        assert abs((exp - utc_now()).total_seconds()) < 1

    def test_minutes_offset(self):
        exp = utc_expiry(minutes=10)
        delta = exp - utc_now()
        assert 599 <= delta.total_seconds() <= 601

    def test_hours_and_seconds(self):
        exp = utc_expiry(hours=1, seconds=30)
        delta = exp - utc_now()
        assert 3629 <= delta.total_seconds() <= 3631

    def test_is_utc_aware(self):
        assert utc_expiry(minutes=5).tzinfo is not None


class TestEnsureAware:
    def test_naive_becomes_utc(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        aware = ensure_aware(naive)
        assert aware.tzinfo is not None
        assert aware.utcoffset() == timedelta(0)

    def test_aware_passthrough(self):
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert ensure_aware(aware) is aware

    def test_round_trip_comparison(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        aware = ensure_aware(naive)
        assert aware == naive.replace(tzinfo=UTC)
