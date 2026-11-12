# বাংলা মন্তব্য: core.telemetry মডিউল — observability.telemetry থেকে সব symbol re-export করা হয়েছে
# যাতে tests `core.telemetry.BatchSpanProcessor`, `core.telemetry.otel_trace` ইত্যাদি patch করতে পারে।
# FIX (full audit 2026-11-13 F-003): opentelemetry-sdk was NOT declared in core/requirements.txt.
# Unguarded imports caused the entire background-services chain (lifespan -> startup.agents)
# to silently die with ImportError in any env built from requirements.txt.
# Guarded now: symbols fall back to None; observability.telemetry already has OTEL_AVAILABLE
# flag and NoOp spans for the offline case.
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # opentelemetry-sdk not installed — NoOp mode
    otel_trace = None
    TracerProvider = None
    BatchSpanProcessor = None

from core.observability.telemetry import (
    _NoOpSpan,
    _RealSpan,
    get_tracer,
    setup_tracing,
    trace_span,
)

__all__ = [
    "BatchSpanProcessor",
    "TracerProvider",
    "_NoOpSpan",
    "_RealSpan",
    "get_tracer",
    "otel_trace",
    "setup_tracing",
    "trace_span",
]
