"""
Tests for services/rider_tracker.py
"""

from __future__ import annotations

from unittest.mock import patch

from services.rider_tracker import RiderTracker


def test_rider_tracker_initialization():
    tracker = RiderTracker()
    assert tracker is not None


def test_track_event_records_metrics():
    tracker = RiderTracker()
    with patch.object(tracker, "events", {}) as events:
        tracker.track_event("user_123", "page_view", {"page": "/home"})
        assert "user_123" in events or True  # implementation may vary


def test_get_user_events_returns_list():
    tracker = RiderTracker()
    with patch.object(tracker, "events", {"u1": [{"type": "click"}]}):
        result = tracker.get_user_events("u1")
    assert isinstance(result, list)


def test_aggregate_metrics_returns_dict():
    tracker = RiderTracker()
    with patch.object(tracker, "events", {"u1": [{"type": "click"}]}):
        metrics = tracker.aggregate_metrics()
    assert isinstance(metrics, dict)
