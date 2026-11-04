"""Regression test guard for telemetry fallback in EventBus.

Validates that missing Sentry or legacy `monitoring.track_exception` imports
never crash the error bus or flood logs (Zero-Recurrence Invariant).
"""

from unittest.mock import MagicMock, patch
import pytest

from core.messaging.event_bus import (
    ErrorEvent,
    IntelligentErrorBus,
    _forward_to_telemetry,
)
import core.messaging.event_bus as eb


def test_event_bus_emit_without_sentry_does_not_crash(monkeypatch):
    """EventBus emit must gracefully fallback when sentry-sdk is absent."""
    eb._telemetry_warning_emitted = False
    bus = IntelligentErrorBus()
    event = ErrorEvent(
        module="test_module",
        error_type="RUNTIME_TEST_ERROR",
        message="Simulated test error",
        severity="CRITICAL",
    )

    # Should not raise any ImportError or exception
    bus.emit(event)
    assert eb._telemetry_warning_emitted is True


def test_event_bus_emit_rate_limits_telemetry_warning(caplog):
    """EventBus must not spam telemetry warnings for every high-severity event."""
    eb._telemetry_warning_emitted = False
    bus = IntelligentErrorBus()

    event1 = ErrorEvent(
        module="test1",
        error_type="ERR1",
        message="First error",
        severity="HIGH",
    )
    event2 = ErrorEvent(
        module="test2",
        error_type="ERR2",
        message="Second error",
        severity="ERROR",
    )

    bus.emit(event1)
    bus.emit(event2)

    # Count warnings about telemetry
    telemetry_warnings = [
        rec for rec in caplog.records
        if "Telemetry unavailable" in rec.message or "Telemetry forwarding unavailable" in rec.message
    ]
    assert len(telemetry_warnings) <= 1


def test_event_bus_forwards_to_sentry_when_available():
    """EventBus forwards to sentry_sdk.capture_exception when sentry is installed."""
    mock_sentry = MagicMock()
    with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
        event = ErrorEvent(
            module="auth_service",
            error_type="AUTH_FAILURE",
            message="Token expired",
            severity="CRITICAL",
        )
        _forward_to_telemetry(event)

        assert mock_sentry.capture_exception.called
        args, kwargs = mock_sentry.capture_exception.call_args
        assert "[AUTH_FAILURE] Token expired" in str(args[0])
        assert "supremeai" in kwargs["contexts"]


@pytest.mark.asyncio
async def test_deterministic_config_errors_skip_pattern_escalation():
    """Missing secret and deterministic config errors must not escalate to SILENT_PATTERN_ESCALATED."""
    bus = IntelligentErrorBus()
    event = ErrorEvent(
        module="secret_vault",
        error_type="CRITICAL_SECRET_MISSING",
        message="Secret UPSTASH_REDIS_REST_URL is missing",
        severity="CRITICAL",
    )

    # Emit 4 times consecutively
    for _ in range(4):
        bus.emit(event)

    # Must NOT have escalated to SILENT_PATTERN_ESCALATED
    assert event.error_type == "CRITICAL_SECRET_MISSING"

    # Self healing should cleanly skip non-retryable error
    await bus.process_error_for_healing(event)
    assert event.resolved is False

