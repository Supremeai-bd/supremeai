"""core/observability/correlation_bridge.py — OTel span processor bridging correlation ids (Way 28).

বাংলা: প্রতিটি span-এ `supremeai.correlation_id` অ্যাট্রিবিউট বসিয়ে দেয় —
লগ আর ট্রেস এক correlation id-তে জোড়া লাগে।

This module is only imported lazily by otel_facade when the OTel SDK is active,
so `opentelemetry` imports here are guaranteed safe at runtime.
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Any

# বাংলা মন্তব্য: _correlation_id contextvar-এর একক SSOT এখন core লেয়ারে রাখা হয়েছে,
# যেন core কখনো বাইরের gateway লেয়ারকে import না করে (Graphify layer-violation fix)।
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")


def current_correlation_id() -> str:
    """Return the correlation id bound to the current async context ('' outside requests)."""
    return _correlation_id.get()


def mint_correlation_id() -> str:
    """Mint a fresh UUID4 hex correlation identifier."""
    return uuid.uuid4().hex


class CorrelationBridge:
    """ReadableProcessingSpanProcessor-compatible bridge (on_start stamping)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # accept SDK signature variants
        super().__init__(*args, **kwargs)

    def on_start(self, span: Any, parent_context: Any = None) -> None:  # noqa: D102
        try:
            cid = current_correlation_id()
            if cid:
                span.set_attribute("supremeai.correlation_id", cid)
        except Exception:  # never break tracing for a missing id
            pass

    def on_end(self, span: Any) -> None:  # noqa: D102
        return None

    def shutdown(self) -> None:  # noqa: D102
        return None

    def force_flush(self, timeout_millis: int | None = None) -> bool:  # noqa: D102
        return True
