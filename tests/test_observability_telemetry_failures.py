"""Tracing errors must be observable without exposing payloads or breaking work."""
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.observability import telemetry


@pytest.fixture(autouse=True)
def clear_telemetry_warning_cache():
    telemetry._warn_telemetry_failure.cache_clear()
    yield
    telemetry._warn_telemetry_failure.cache_clear()


@pytest.mark.parametrize("method", ["record_exception", "set_status", "set_attribute"])
def test_span_operation_failures_are_warned_once_without_secret(caplog, method):
    span = MagicMock()
    getattr(span, method).side_effect = RuntimeError("sensitive payload")
    wrapper = telemetry._RealSpan(span)
    with caplog.at_level(logging.WARNING, logger=telemetry.__name__):
        getattr(wrapper, method)("sensitive input")
        getattr(wrapper, method)("sensitive input")
    assert len(caplog.records) == 1
    assert f"Telemetry {method} failed (RuntimeError)" in caplog.text
    assert "sensitive" not in caplog.text


def test_setup_failure_is_observable_and_non_fatal(monkeypatch, caplog):
    def fail():
        raise RuntimeError("private data")
    monkeypatch.setattr(telemetry, "init_telemetry", fail)
    assert telemetry.setup_tracing() is None
    assert "Telemetry setup failed (RuntimeError)" in caplog.text
    assert "private data" not in caplog.text


def test_failed_span_enter_does_not_exit_unentered_context(monkeypatch, caplog):
    context = MagicMock()
    context.__enter__.side_effect = RuntimeError("private data")
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = context
    monkeypatch.setattr(telemetry, "OTEL_AVAILABLE", True)
    monkeypatch.setattr(telemetry, "get_tracer", lambda: tracer)
    with telemetry.trace_span("test") as span:
        span.set_attribute("some", "value")
    context.__exit__.assert_not_called()
    assert "Telemetry span entry failed (RuntimeError)" in caplog.text
    assert "private data" not in caplog.text


def test_span_exit_error_never_masks_application_exception(monkeypatch, caplog):
    context = MagicMock()
    context.__enter__.return_value = MagicMock()
    context.__exit__.side_effect = RuntimeError("private data")
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = context
    monkeypatch.setattr(telemetry, "OTEL_AVAILABLE", True)
    monkeypatch.setattr(telemetry, "get_tracer", lambda: tracer)
    with pytest.raises(ValueError, match="application failure"):
        with telemetry.trace_span("test"):
            raise ValueError("application failure")
    assert "Telemetry span exit failed (RuntimeError)" in caplog.text
    assert "private data" not in caplog.text


def test_tracer_lookup_failure_does_not_break_application(monkeypatch, caplog):
    def fail():
        raise RuntimeError("private data")
    monkeypatch.setattr(telemetry, "get_tracer", fail)
    with telemetry.trace_span("test"):
        pass
    assert "Telemetry span entry failed (RuntimeError)" in caplog.text


def test_agent_step_keeps_application_exception_when_span_reporting_fails(monkeypatch, caplog):
    context = MagicMock()
    span = context.__enter__.return_value
    span.record_exception.side_effect = RuntimeError("private record")
    span.set_status.side_effect = RuntimeError("private status")
    context.__exit__.return_value = False
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = context
    monkeypatch.setattr(telemetry, "get_tracer", lambda: tracer)
    monkeypatch.setattr(telemetry, "trace", SimpleNamespace(StatusCode=SimpleNamespace(ERROR="ERROR")), raising=False)
    with pytest.raises(ValueError, match="application failure"):
        with telemetry.trace_agent_step("test"):
            raise ValueError("application failure")
    assert "Telemetry record_exception failed" in caplog.text
    assert "Telemetry set_status failed" in caplog.text
    assert "private" not in caplog.text


def test_agent_step_without_tracer_preserves_application_exception(monkeypatch):
    monkeypatch.setattr(telemetry, "get_tracer", lambda: None)
    with pytest.raises(ValueError, match="application failure"):
        with telemetry.trace_agent_step("test") as span:
            assert span is None
            raise ValueError("application failure")


def test_agent_step_exit_failure_never_masks_application_exception(monkeypatch, caplog):
    context = MagicMock()
    context.__exit__.side_effect = RuntimeError("private exit detail")
    tracer = MagicMock()
    tracer.start_as_current_span.return_value = context
    monkeypatch.setattr(telemetry, "get_tracer", lambda: tracer)
    monkeypatch.setattr(telemetry, "trace", SimpleNamespace(StatusCode=SimpleNamespace(ERROR="ERROR")), raising=False)
    with pytest.raises(ValueError, match="application failure"):
        with telemetry.trace_agent_step("test"):
            raise ValueError("application failure")
    assert "Telemetry agent span exit failed (RuntimeError)" in caplog.text
    assert "private exit detail" not in caplog.text
