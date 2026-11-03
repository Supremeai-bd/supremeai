from datetime import UTC, datetime

from utils.timestamps import utc_now, utc_now_iso, utc_timestamp


class TestUtcNowIso:
    def test_returns_string(self):
        assert isinstance(utc_now_iso(), str)

    def test_is_parseable_iso(self):
        value = utc_now_iso()
        parsed = datetime.fromisoformat(value)
        assert parsed.tzinfo is not None

    def test_is_utc_aware(self):
        parsed = datetime.fromisoformat(utc_now_iso())
        assert parsed.utcoffset() == datetime.now(UTC).utcoffset()

    def test_recent_timestamp(self):
        before = datetime.now(UTC)
        value = utc_now_iso()
        after = datetime.now(UTC)
        parsed = datetime.fromisoformat(value)
        assert before <= parsed <= after


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


class TestUtcTimestamp:
    def test_returns_int(self):
        assert isinstance(utc_timestamp(), int)

    def test_positive_and_recent(self):
        ts = utc_timestamp()
        now = int(datetime.now(UTC).timestamp())
        assert abs(ts - now) <= 2
        assert ts > 1_700_000_000
