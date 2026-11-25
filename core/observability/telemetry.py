"""
core/observability/telemetry.py — SupremeAI OpenTelemetry Observability Hub.

Provides standardized distributed tracing, agent cycle spans, tool execution latency,
and GenAI semantic conventions (tokens/cost) without vendor lock-in.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

_logger = logging.getLogger(__name__)

_tracer: Any | None = None


def resolve_otlp_traces_endpoint(
    endpoint: str | None, traces_endpoint: str | None = None
) -> str | None:
    """Resolve the exact OTLP/HTTP traces endpoint from the standard env vars.

    Per the OpenTelemetry spec, ``OTEL_EXPORTER_OTLP_ENDPOINT`` is a BASE
    endpoint — the SDK appends the signal path (``/v1/traces``). But
    ``OTLPSpanExporter(endpoint=...)`` uses its value VERBATIM, so passing the
    base URL through unchanged makes every span POST hit the wrong path
    (Grafana Cloud's OTLP gateway answers 404/405 and BatchSpanProcessor then
    silently drops the batch). ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`` is the
    signal-specific variable and is always used verbatim.

    Mirrors gateway/metrics_exporter.py, which already appends ``/v1/metrics``
    to the same base variable (pinned by tests/test_gateway_metrics_otlp.py).
    """
    if traces_endpoint and traces_endpoint.strip():
        return traces_endpoint.strip()
    if not endpoint or not endpoint.strip():
        return None
    base = endpoint.strip().rstrip("/")
    if not base:
        return None
    if base.endswith("/v1/traces"):
        return base
    return f"{base}/v1/traces"


def init_telemetry(service_name: str = "supremeai-agent-engine"):
    """Initialize OpenTelemetry tracer provider with OTLP or fallback console exporter."""
    global _tracer
    if _tracer is not None:
        return _tracer

    if not OTEL_AVAILABLE:
        return None

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "environment": os.getenv("SUPREMEAI_ENV", "production"),
    })
    provider = TracerProvider(resource=resource)

    # Use OTLP exporter if an endpoint is configured, else fallback to null / console
    otlp_endpoint = resolve_otlp_traces_endpoint(
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
    )
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as exc:
            # A silently-dead exporter makes every trace vanish downstream while
            # the service looks healthy; keep the app alive but say why.
            # (Previously a bare `except Exception: pass` swallowed this.)
            _logger.warning("OTLP trace exporter init failed for %s: %s", otlp_endpoint, exc)

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    return _tracer


def get_tracer(service_name: str = "supremeai-agent-engine"):
    """Get initialized tracer instance or initialize lazily."""
    global _tracer
    if _tracer is None:
        return init_telemetry(service_name)
    return _tracer


@contextlib.contextmanager
def trace_agent_step(step_name: str, attributes: dict[str, Any] | None = None):
    """Context manager for tracing agent execution steps with GenAI conventions."""
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    attrs = attributes or {}
    with tracer.start_as_current_span(step_name, attributes=attrs) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise




class _NoOpSpan:
    """No-op span used when OpenTelemetry is unavailable."""

    def record_exception(self, exc):
        return None

    def set_status(self, *args, **kwargs):
        return None

    def set_attribute(self, *args, **kwargs):
        return None

    def end(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _RealSpan:
    def __init__(self, span):
        self._span = span

    def record_exception(self, exc):
        try:
            self._span.record_exception(exc)
        except Exception:
            pass

    def set_status(self, *args, **kwargs):
        try:
            self._span.set_status(*args, **kwargs)
        except Exception:
            pass

    def set_attribute(self, *args, **kwargs):
        try:
            self._span.set_attribute(*args, **kwargs)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def setup_tracing(*args, **kwargs):
    """Initialize OpenTelemetry tracing; alias for init_telemetry."""
    try:
        return init_telemetry()
    except Exception:
        return None


import functools


def trace_span(name, attributes=None, kind=None, **kwargs):
    """Flexible tracing helper usable as context manager or decorator."""

    class _SpanCM:
        def __init__(self):
            self._span = None

        def __enter__(self):
            tracer = get_tracer()
            if tracer is None or not OTEL_AVAILABLE:
                self._span = _NoOpSpan()
                return self._span
            try:
                self._otel_span = tracer.start_as_current_span(name, attributes=attributes or {})
                self._span = self._otel_span.__enter__()
                return _RealSpan(self._span)
            except Exception:
                self._span = _NoOpSpan()
                return self._span

        def __exit__(self, exc_type, exc, tb):
            if exc is not None and hasattr(self._span, "record_exception"):
                try:
                    self._span.record_exception(exc)
                except Exception:
                    pass
            if hasattr(self, "_otel_span"):
                try:
                    self._otel_span.__exit__(exc_type, exc, tb)
                except Exception:
                    pass
            return False

        def __call__(self, func):
            @functools.wraps(func)
            def wrapper(*a, **k):
                with trace_span(name, attributes):
                    return func(*a, **k)
            return wrapper

    return _SpanCM()
