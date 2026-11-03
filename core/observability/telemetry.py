"""
core/observability/telemetry.py — SupremeAI OpenTelemetry Observability Hub.

Provides standardized distributed tracing, agent cycle spans, tool execution latency,
and GenAI semantic conventions (tokens/cost) without vendor lock-in.
"""
from __future__ import annotations

import os
import contextlib
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


_tracer: Optional[Any] = None


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

    # Use OTLP exporter if endpoint is configured, else fallback to null / console
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception:
            pass

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
def trace_agent_step(step_name: str, attributes: Optional[Dict[str, Any]] = None):
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

