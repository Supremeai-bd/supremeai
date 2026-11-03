from unittest.mock import patch

from core.resilience.predictive_circuit_breaker import PredictiveCircuitBreaker
from core.resilience.predictive_metrics import PredictiveMetricsTracker


def test_predictive_metrics_empty_and_percentile_interpolation():
    tracker = PredictiveMetricsTracker()

    assert tracker.calculate_percentile(95) == 0.0
    assert tracker.get_error_rate() == 0.0
    assert tracker.is_anomaly_detected() is False

    tracker.latencies.extend([(1.0, 10.0), (1.0, 20.0)])
    tracker.status_codes.extend([(1.0, 200), (1.0, 500)])

    assert tracker.calculate_percentile(50) == 15.0
    assert tracker.get_error_rate() == 50.0


def test_predictive_metrics_tracks_ewma_and_resets_consecutive_errors():
    tracker = PredictiveMetricsTracker(alpha=0.2)

    tracker.record_request(100.0, 500)
    tracker.record_request(200.0, 500)
    assert tracker.ewma_latency == 120.0
    assert tracker.consecutive_errors == 2

    tracker.record_request(300.0, 200)
    assert tracker.ewma_latency == 156.0
    assert tracker.consecutive_errors == 0


def test_predictive_metrics_detects_consecutive_5xx_anomaly():
    tracker = PredictiveMetricsTracker()

    for _ in range(5):
        tracker.record_request(100.0, 500)

    assert tracker.is_anomaly_detected() is True


def test_predictive_metrics_detects_high_error_rate_with_ten_samples():
    tracker = PredictiveMetricsTracker()

    for _ in range(9):
        tracker.record_request(100.0, 200)
    tracker.record_request(100.0, 500)

    assert tracker.get_error_rate() == 10.0
    assert tracker.is_anomaly_detected() is False

    tracker.record_request(100.0, 500)
    assert tracker.get_error_rate() == 18.181818181818183
    assert tracker.is_anomaly_detected() is True


def test_predictive_metrics_removes_expired_samples():
    tracker = PredictiveMetricsTracker(window_size_seconds=10)
    tracker.latencies.extend([(0.0, 10.0), (95.0, 20.0)])
    tracker.status_codes.extend([(0.0, 500), (95.0, 200)])

    tracker._clean_old_metrics(100.0)

    assert list(tracker.latencies) == [(95.0, 20.0)]
    assert list(tracker.status_codes) == [(95.0, 200)]


def test_predictive_circuit_breaker_starts_on_primary():
    breaker = PredictiveCircuitBreaker("test")

    assert breaker.state == "CLOSED"
    assert breaker.get_active_provider() == "gemini"


def test_predictive_circuit_breaker_opens_on_anomaly_and_uses_fallback():
    breaker = PredictiveCircuitBreaker("test", fallback_provider="openrouter")
    breaker.tracker.is_anomaly_detected = lambda: True

    with patch("core.resilience.predictive_circuit_breaker.time.time", return_value=100.0):
        breaker.record_request_outcome(100.0, 500)
        assert breaker.state == "OPEN"
        assert breaker.get_active_provider() == "openrouter"


def test_predictive_circuit_breaker_uses_groq_when_fallback_is_none():
    breaker = PredictiveCircuitBreaker("test", fallback_provider=None)
    breaker.state = "OPEN"

    assert breaker.get_active_provider() == "groq"


def test_predictive_circuit_breaker_moves_to_half_open_after_cooldown():
    breaker = PredictiveCircuitBreaker("test", cooldown_seconds=60)
    breaker.state = "OPEN"
    breaker.last_state_change = 100.0

    with patch("core.resilience.predictive_circuit_breaker.time.time", return_value=161.0):
        assert breaker.get_active_provider() == "gemini"

    assert breaker.state == "HALF_OPEN"


def test_predictive_circuit_breaker_recovery_returns_to_closed():
    breaker = PredictiveCircuitBreaker("test")
    breaker.state = "HALF_OPEN"

    with patch("core.resilience.predictive_circuit_breaker.time.time", return_value=200.0):
        breaker.mark_recovery_success()

    assert breaker.state == "CLOSED"
    assert breaker.last_state_change == 200.0


def test_predictive_circuit_breaker_does_not_recover_from_closed():
    breaker = PredictiveCircuitBreaker("test")
    breaker.last_state_change = 123.0

    breaker.mark_recovery_success()

    assert breaker.state == "CLOSED"
    assert breaker.last_state_change == 123.0
