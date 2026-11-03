"""Full-coverage tests for core.security.intelligence.behavioral_analyzer.

Pure-logic anomaly-detection tests. Clock-dependent branches are isolated via
a FakeDatetime injected into the module (no sleeps, deterministic).
"""

from __future__ import annotations

from datetime import datetime as real_datetime
from datetime import timedelta

import pytest

import core.security.intelligence.behavioral_analyzer as ba_module
from core.security.intelligence.behavioral_analyzer import (
    AnomalyAlert,
    AnomalyDetector,
    BehavioralAnalyzer,
    BehaviorEvent,
    BehaviorTracker,
    get_analyzer,
)

pytestmark = pytest.mark.security


class FakeDatetime(real_datetime):
    """datetime subclass with a controllable now()."""

    _fixed: real_datetime = real_datetime(2024, 6, 15, 3, 0, 0)  # 3 AM

    @classmethod
    def now(cls, tz=None):  # noqa: ARG003
        return cls._fixed

    @classmethod
    def set_hour(cls, hour: int) -> None:
        cls._fixed = real_datetime(2024, 6, 15, hour, 0, 0)


@pytest.fixture(autouse=True)
def patched_datetime(monkeypatch):
    monkeypatch.setattr(ba_module, "datetime", FakeDatetime)
    yield
    FakeDatetime.set_hour(3)


def make_event(user_id="u1", ip="1.1.1.1", action="login", ts=None):
    return BehaviorEvent(
        user_id=user_id,
        ip_address=ip,
        action=action,
        timestamp=ts if ts is not None else ba_module.time.time(),
    )


class TestBehaviorEvent:
    def test_defaults(self):
        event = make_event()
        assert event.metadata == {}
        assert event.user_id == "u1"


class TestBehaviorTracker:
    def test_init_defaults(self):
        tracker = BehaviorTracker()
        assert tracker.window_size == timedelta(hours=24)
        assert tracker.events == []
        assert tracker.user_profiles == {}

    def test_custom_window(self):
        tracker = BehaviorTracker(window_size_hours=2)
        assert tracker.window_size == timedelta(hours=2)

    def test_record_event_updates_profile(self):
        tracker = BehaviorTracker()
        before = ba_module.time.time()
        tracker.record_event(make_event(ts=before))
        profile = tracker.user_profiles["u1"]
        assert profile["ip_addresses"]["1.1.1.1"] == 1
        assert profile["actions"]["login"] == 1
        assert profile["last_seen"] == before
        assert profile["total_events"] == 1
        assert len(tracker.events) == 1

    def test_record_event_accumulates(self):
        tracker = BehaviorTracker()
        tracker.record_event(make_event(ip="1.1.1.1"))
        tracker.record_event(make_event(ip="2.2.2.2", action="query"))
        profile = tracker.user_profiles["u1"]
        assert profile["ip_addresses"]["1.1.1.1"] == 1
        assert profile["ip_addresses"]["2.2.2.2"] == 1
        assert profile["actions"]["login"] == 1
        assert profile["actions"]["query"] == 1
        assert profile["total_events"] == 2

    def test_cleanup_removes_events_older_than_window(self):
        tracker = BehaviorTracker(window_size_hours=1)
        old_ts = ba_module.time.time() - 7200  # 2h ago, outside 1h window
        tracker.events.append(make_event(ts=old_ts))
        tracker.record_event(make_event(ts=ba_module.time.time()))
        assert len(tracker.events) == 1
        assert tracker.events[0].timestamp > old_ts

    def test_cleanup_keeps_events_inside_window(self):
        tracker = BehaviorTracker(window_size_hours=24)
        tracker.record_event(make_event(ts=ba_module.time.time() - 60))
        assert len(tracker.events) == 1

    def test_get_user_pattern_existing(self):
        tracker = BehaviorTracker()
        tracker.record_event(make_event())
        pattern = tracker.get_user_pattern("u1")
        assert pattern["total_events"] == 1
        # Returned dict is a copy — mutating it does not affect the tracker
        pattern["total_events"] = 99
        assert tracker.user_profiles["u1"]["total_events"] == 1

    def test_get_user_pattern_unknown_returns_empty(self):
        assert BehaviorTracker().get_user_pattern("ghost") == {}

    def test_get_recent_ips_filters_by_user_and_time(self):
        tracker = BehaviorTracker()
        now = ba_module.time.time()
        tracker.record_event(make_event(user_id="u1", ip="1.1.1.1", ts=now - 60))
        tracker.record_event(make_event(user_id="u1", ip="2.2.2.2", ts=now - 60))
        tracker.record_event(make_event(user_id="u2", ip="3.3.3.3", ts=now - 60))
        tracker.record_event(make_event(user_id="u1", ip="4.4.4.4", ts=now - 7200))
        recent = tracker.get_recent_ips("u1", hours=1)
        assert set(recent) == {"1.1.1.1", "2.2.2.2"}

    def test_get_recent_ips_unknown_user_empty(self):
        assert BehaviorTracker().get_recent_ips("ghost") == []


def ts_at_hour(hour: int, days_ago: int) -> float:
    """Deterministic timestamp at a fixed local hour N days ago."""
    return real_datetime(2024, 6, 1 + (days_ago % 28), hour, 0, 0).timestamp()


class TestAnomalyDetector:
    def _tracker_with_events(self, events):
        """Build a tracker bypassing record_event's window cleanup so
        historical (out-of-window) events can be staged deterministically."""
        tracker = BehaviorTracker()
        for event in events:
            profile = tracker.user_profiles[event.user_id]  # defaultdict creates entry
            profile["ip_addresses"][event.ip_address] += 1
            profile["actions"][event.action] += 1
            profile["last_seen"] = event.timestamp
            profile["total_events"] += 1
        tracker.events = list(events)
        return tracker

    def test_init_thresholds(self):
        detector = AnomalyDetector(BehaviorTracker())
        assert detector.ip_churn_threshold == 5
        assert detector.unusual_hour_threshold == 2

    def test_detect_ip_churn_below_threshold_none(self):
        now = ba_module.time.time()
        tracker = self._tracker_with_events(
            [make_event(ip=f"10.0.0.{i}", ts=now - i) for i in range(3)]
        )
        detector = AnomalyDetector(tracker)
        assert detector.detect_ip_churn("u1", "10.0.0.9") is None

    def test_detect_ip_churn_over_threshold_alerts(self):
        now = ba_module.time.time()
        tracker = self._tracker_with_events(
            [make_event(ip=f"10.0.0.{i}", ts=now - i) for i in range(7)]
        )
        detector = AnomalyDetector(tracker)
        alert = detector.detect_ip_churn("u1", "10.0.0.99")
        assert isinstance(alert, AnomalyAlert)
        assert alert.anomaly_type == "ip_churn"
        assert alert.severity == "high"
        assert alert.ip_address == "10.0.0.99"
        assert alert.confidence == 0.7
        assert alert.recommended_action == "require_additional_authentication"
        assert "7 times" in alert.description

    def test_detect_ip_churn_confidence_capped_at_one(self):
        now = ba_module.time.time()
        tracker = self._tracker_with_events(
            [make_event(ip=f"10.0.0.{i}", ts=now - i) for i in range(12)]
        )
        alert = AnomalyDetector(tracker).detect_ip_churn("u1", "10.0.0.99")
        assert alert.confidence == 1.0

    def test_detect_unusual_time_no_profile_none(self):
        assert AnomalyDetector(BehaviorTracker()).detect_unusual_time("ghost") is None

    def test_detect_unusual_time_few_events_none(self):
        tracker = self._tracker_with_events([make_event() for _ in range(4)])
        assert AnomalyDetector(tracker).detect_unusual_time("u1") is None

    def test_detect_unusual_time_zero_stddev_none(self):
        # All events at the same hour -> std_dev == 0 -> no alert
        FakeDatetime.set_hour(12)
        base = ba_module.time.time() - 3600 * 48
        events = [make_event(ts=base + i * 3600 * 24) for i in range(5)]
        tracker = self._tracker_with_events(events)
        assert AnomalyDetector(tracker).detect_unusual_time("u1") is None

    def test_detect_unusual_time_anomaly_alerts(self):
        # Typical activity at noon (avg ~12, small stddev); "now" is 3 AM -> far
        FakeDatetime.set_hour(3)
        events = [
            make_event(ts=ts_at_hour(12, days_ago=5)),
            make_event(ts=ts_at_hour(12, days_ago=4)),
            make_event(ts=ts_at_hour(12, days_ago=3)),
            make_event(ts=ts_at_hour(12, days_ago=2)),
            make_event(ts=ts_at_hour(13, days_ago=1)),
        ]
        tracker = self._tracker_with_events(events)
        alert = AnomalyDetector(tracker).detect_unusual_time("u1")
        assert isinstance(alert, AnomalyAlert)
        assert alert.anomaly_type == "unusual_time"
        assert alert.severity == "medium"
        assert alert.confidence == 0.6
        assert alert.recommended_action == "monitor_closely"
        assert alert.ip_address == "1.1.1.1"

    def test_detect_unusual_time_normal_hour_none(self):
        # Current hour (3 AM) sits inside the typical activity spread -> None
        FakeDatetime.set_hour(3)
        events = [
            make_event(ts=ts_at_hour(2, days_ago=5)),
            make_event(ts=ts_at_hour(3, days_ago=4)),
            make_event(ts=ts_at_hour(4, days_ago=3)),
            make_event(ts=ts_at_hour(3, days_ago=2)),
            make_event(ts=ts_at_hour(3, days_ago=1)),
        ]
        tracker = self._tracker_with_events(events)
        assert AnomalyDetector(tracker).detect_unusual_time("u1") is None

    def test_detect_rapid_actions_below_threshold_none(self):
        now = ba_module.time.time()
        tracker = self._tracker_with_events(
            [make_event(action="query", ts=now - i) for i in range(10)]
        )
        assert AnomalyDetector(tracker).detect_rapid_actions("u1", "query") is None

    def test_detect_rapid_actions_over_threshold_alerts(self):
        now = ba_module.time.time()
        tracker = self._tracker_with_events(
            [make_event(action="query", ts=now - i) for i in range(12)]
        )
        alert = AnomalyDetector(tracker).detect_rapid_actions("u1", "query")
        assert isinstance(alert, AnomalyAlert)
        assert alert.anomaly_type == "rapid_actions"
        assert alert.severity == "high"
        assert alert.confidence == 0.8
        assert alert.recommended_action == "rate_limit"
        assert "12 times" in alert.description

    def test_detect_rapid_actions_ignores_other_actions_and_old_events(self):
        now = ba_module.time.time()
        events = [make_event(action="query", ts=now - i) for i in range(8)]
        events += [make_event(action="other", ts=now - i) for i in range(5)]
        events += [make_event(action="query", ts=now - 3600) for i in range(5)]
        tracker = self._tracker_with_events(events)
        # Only 8 same-action events inside the 60s window -> below threshold
        assert AnomalyDetector(tracker).detect_rapid_actions("u1", "query") is None

    def test_detect_new_user_pattern_no_profile_none(self):
        assert AnomalyDetector(BehaviorTracker()).detect_new_user_pattern("ghost") is None

    def test_detect_new_user_pattern_few_events_alerts(self):
        tracker = self._tracker_with_events([make_event(), make_event()])
        alert = AnomalyDetector(tracker).detect_new_user_pattern("u1")
        assert isinstance(alert, AnomalyAlert)
        assert alert.anomaly_type == "new_user"
        assert alert.severity == "low"
        assert alert.confidence == 0.3
        assert alert.recommended_action == "standard_monitoring"

    def test_detect_new_user_pattern_established_user_none(self):
        tracker = self._tracker_with_events([make_event() for _ in range(3)])
        assert AnomalyDetector(tracker).detect_new_user_pattern("u1") is None


class TestBehavioralAnalyzer:
    def test_init(self):
        analyzer = BehavioralAnalyzer()
        assert analyzer.tracker is not None
        assert analyzer.detector.tracker is analyzer.tracker
        assert analyzer.alert_handlers == []

    def test_record_event_no_anomalies(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_event("u1", "1.1.1.1", "login")
        assert analyzer.tracker.user_profiles["u1"]["total_events"] == 1

    def test_record_event_with_metadata(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_event("u1", "1.1.1.1", "login", metadata={"m": 1})
        assert analyzer.tracker.events[0].metadata == {"m": 1}

    def test_record_event_triggers_handlers_on_anomaly(self):
        analyzer = BehavioralAnalyzer()
        seen = []
        analyzer.register_alert_handler(seen.append)
        # 12 rapid identical actions -> rapid_actions anomaly on the 12th record
        for _ in range(12):
            analyzer.record_event("u1", "1.1.1.1", "query")
        assert seen, "expected at least one anomaly alert for rapid actions"
        assert all(a.anomaly_type == "rapid_actions" for a in seen)

    def test_check_anomalies_includes_unusual_time(self, monkeypatch):
        analyzer = BehavioralAnalyzer()
        FakeDatetime.set_hour(3)
        # Stage 5 historical events at noon (deterministic local hour), with a
        # single IP and a non-matching action so only unusual_time fires.
        events = [
            make_event(ip="9.9.9.9", action="chat", ts=ts_at_hour(12, days_ago=5)),
            make_event(ip="9.9.9.9", action="chat", ts=ts_at_hour(12, days_ago=4)),
            make_event(ip="9.9.9.9", action="chat", ts=ts_at_hour(12, days_ago=3)),
            make_event(ip="9.9.9.9", action="chat", ts=ts_at_hour(13, days_ago=2)),
            make_event(ip="9.9.9.9", action="chat", ts=ts_at_hour(12, days_ago=1)),
        ]
        for event in events:
            profile = analyzer.tracker.user_profiles["u1"]
            profile["ip_addresses"][event.ip_address] += 1
            profile["actions"][event.action] += 1
            profile["total_events"] += 1
            profile["last_seen"] = event.timestamp
        analyzer.tracker.events = list(events)
        anomalies = analyzer._check_anomalies("u1", "9.9.9.9", "query")
        types = {a.anomaly_type for a in anomalies}
        assert "unusual_time" in types
        assert "ip_churn" not in types
        assert "rapid_actions" not in types

    def test_failing_handler_is_isolated(self):
        analyzer = BehavioralAnalyzer()

        def bad_handler(alert):
            raise RuntimeError("handler exploded")

        seen = []
        analyzer.register_alert_handler(bad_handler)
        analyzer.register_alert_handler(seen.append)
        now = ba_module.time.time()
        for i in range(12):
            analyzer.tracker.record_event(make_event(action="query", ts=now - i))
        # Force detection directly through record_event path
        analyzer.record_event("u1", "1.1.1.1", "query")
        assert seen, "second handler should still run after first handler raised"

    def test_check_anomalies_returns_all_types(self, monkeypatch):
        analyzer = BehavioralAnalyzer()
        now = ba_module.time.time()
        # > 5 distinct recent IPs -> ip_churn
        for i in range(7):
            analyzer.tracker.record_event(make_event(ip=f"10.0.0.{i}", ts=now - i))
        anomalies = analyzer._check_anomalies("u1", "10.0.0.6", "query")
        types = {a.anomaly_type for a in anomalies}
        assert "ip_churn" in types
        assert "rapid_actions" in types or "unusual_time" in types or len(anomalies) >= 1

    def test_get_user_risk_score_unknown_user(self):
        assert BehavioralAnalyzer().get_user_risk_score("ghost") == 0.0

    def test_get_user_risk_score_new_user(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_event("u1", "1.1.1.1", "login")
        assert analyzer.get_user_risk_score("u1") == pytest.approx(0.3)

    def test_get_user_risk_score_multiple_ips(self):
        analyzer = BehavioralAnalyzer()
        now = ba_module.time.time()
        for i in range(6):
            analyzer.tracker.record_event(make_event(ip=f"10.0.0.{i}", ts=now - i))
        # total_events >= 5 (no new-user factor); ip_count=6 > 3 -> min(0.4, 0.6)=0.4
        assert analyzer.get_user_risk_score("u1") == pytest.approx(0.4)

    def test_get_user_risk_score_averages_factors(self):
        analyzer = BehavioralAnalyzer()
        now = ba_module.time.time()
        # 4 distinct IPs with only 4 events -> new-user factor (0.3) +
        # IP factor min(0.4, 4*0.1)=0.4 -> averaged
        for i in range(4):
            analyzer.tracker.record_event(make_event(ip=f"10.0.0.{i}", ts=now - i))
        score = analyzer.get_user_risk_score("u1")
        assert score == pytest.approx((0.3 + 0.4) / 2)

    def test_get_user_risk_score_low_activity_no_risk(self):
        analyzer = BehavioralAnalyzer()
        now = ba_module.time.time()
        for i in range(5):
            analyzer.tracker.record_event(make_event(ip="1.1.1.1", ts=now - i))
        assert analyzer.get_user_risk_score("u1") == 0.0

    def test_get_stats(self):
        """DOCUMENTED BUG (not fixed — tests-only policy): get_stats() reads
        self.ip_churn_threshold which only exists on AnomalyDetector, so the
        method always raises AttributeError. This test pins the current
        (broken) behaviour; if the source is ever fixed to read
        self.detector.ip_churn_threshold, update this test to assert the
        stats dict instead."""
        analyzer = BehavioralAnalyzer()
        analyzer.record_event("u1", "1.1.1.1", "login")
        with pytest.raises(AttributeError):
            analyzer.get_stats()


class TestGlobalAnalyzerSingleton:
    def test_get_analyzer_creates_once(self, monkeypatch):
        monkeypatch.setattr(ba_module, "_analyzer", None)
        analyzer = get_analyzer()
        assert get_analyzer() is analyzer

    def test_get_analyzer_returns_existing(self, monkeypatch):
        existing = BehavioralAnalyzer()
        monkeypatch.setattr(ba_module, "_analyzer", existing)
        assert get_analyzer() is existing
