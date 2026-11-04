"""Regression test guard for telemetry fallback in EventBus.

Validates that missing Sentry or legacy `monitoring.track_exception` imports
never crash the error bus or flood logs (Zero-Recurrence Invariant).
Also validates fail-closed SecretNotFoundError and non-retryable config errors.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from core.messaging.event_bus import (
    ErrorEvent,
    IntelligentErrorBus,
    _forward_to_telemetry,
)
import core.messaging.event_bus as eb
from core.security.secret_vault import ProductionSecretVault, SecretNotFoundError


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


@pytest.mark.asyncio
async def test_secret_not_found_error_is_non_retryable():
    """SecretNotFoundError must be classified as non-retryable in IntelligentErrorBus."""
    bus = IntelligentErrorBus()
    event = ErrorEvent(
        module="secret_vault",
        error_type="SecretNotFoundError",
        message="Secret SUPABASE_URL not found in production! Fail-closed.",
        severity="CRITICAL",
    )

    for _ in range(5):
        bus.emit(event)

    assert event.error_type == "SecretNotFoundError"
    await bus.process_error_for_healing(event)
    assert event.resolved is False


def test_vault_fail_closed_raises_secret_not_found_error(monkeypatch):
    """Production vault must raise SecretNotFoundError when required secret is absent."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setenv("PRE_COMMIT", "0")
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    vault = ProductionSecretVault()
    vault.env = "production"

    with pytest.raises(SecretNotFoundError) as exc_info:
        vault._fallback_to_env("SUPABASE_URL", None)

    assert "CRITICAL" in str(exc_info.value)
    assert issubclass(SecretNotFoundError, RuntimeError)


def test_vault_raw_rest_fetch_fallback(monkeypatch):
    """Production vault _fetch_raw_secrets must populate cache from raw REST response."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "test-project-123")
    monkeypatch.setenv("INFISICAL_TOKEN", "mock-token-raw")

    vault = ProductionSecretVault()
    vault.env = "production"
    vault.project_id = "test-project-123"
    vault.token = "mock-token-raw"

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "secrets": [
            {"secretKey": "UPSTASH_REDIS_REST_URL", "secretValue": "https://redis.upstash.io"},
            {"secretKey": "UPSTASH_REDIS_REST_TOKEN", "secretValue": "token-xyz-123"}
        ]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        secrets = vault._fetch_raw_secrets(environment="prod")

    assert secrets.get("UPSTASH_REDIS_REST_URL") == "https://redis.upstash.io"
    assert "UPSTASH_REDIS_REST_URL" in vault._cache
    assert vault._cache["UPSTASH_REDIS_REST_URL"].value == "https://redis.upstash.io"
