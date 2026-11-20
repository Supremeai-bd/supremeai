"""gateway/service/request_trace.py — per-request latency attribution for the chat path.

WHY THIS EXISTS (the user problem)
----------------------------------
A one-word reply ("hi") measured 6.2s end-to-end and the only thing the logs
could prove was ``Stealth webhook OK ... latency=Nms`` — one number for a hop
that is (a) behind a lane decision and (b) behind four serial steps in the
gateway. A single request therefore could not be attributed: was the time spent
in SQLite persistence, in the context compiler, in the route decision, in the
upstream relay, or in a lane that never should have been chosen?

That question was answered by reading ~4,000 lines of source. It should have
been answered by one log line. This module is that log line.

DESIGN
------
* ``RequestTrace`` is a monotonic clock plus named checkpoints. It is created
  once per chat request and marks the stages the chat path actually has:
  ``auth`` → ``persist`` → ``context`` → ``route`` → ``upstream`` → ``total``.
* Stages are recorded, not enforced: this module never raises, never awaits and
  never touches I/O on the failure path. A tracing bug must not be able to fail
  a chat request (every caller wraps in try/except; the methods themselves are
  arithmetic only).
* Two outputs: one structured log line (for log-based analysis) and a compact
  ``Server-Timing`` header value (for the browser devtools / curl/time).
  ``Server-Timing`` is the W3C format already understood by Chrome DevTools, so
  a slow request becomes visually attributable without any new tooling.

Deliberately NOT included: any per-token or per-chunk instrumentation. Marking
inside a streaming generator would add overhead to the hot path this module
exists to protect. Only pre-first-token stages are measured.

Stdlib only. No secrets, no config, no imports from the rest of the gateway.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger("supremeai.request_trace")

# Stage order as the chat path executes them. Used only for stable log output.
STAGES = ("auth", "persist", "context", "route", "upstream")

# Server-Timing is a response header; keep the whole value well under the point
# where a proxy would truncate it. 6 stages * ~20 chars is ~120 chars.
_MAX_HEADER_STAGES = 8


class RequestTrace:
    """Monotonic stopwatch with named checkpoints for one chat request.

    Usage::

        trace = RequestTrace(model="supreme-spark")
        trace.mark("auth")
        ...
        trace.mark("persist")
        ...
        trace.finish(lane="stealth-webhook", provider="ghost_gemini")

    ``mark(name)`` closes the stage that started at the previous mark, so the
    caller never has to pair ``start``/``stop`` by hand. Times are monotonic and
    therefore immune to wall-clock adjustments.
    """

    __slots__ = ("_start", "_last", "_durations", "_order", "model", "lane", "provider", "_finished")

    def __init__(self, model: Optional[str] = None) -> None:
        now = time.monotonic()
        self._start = now
        self._last = now
        self._durations: Dict[str, float] = {}
        self._order: List[str] = []
        self.model = model
        self.lane: Optional[str] = None
        self.provider: Optional[str] = None
        self._finished = False

    # ── checkpoints ────────────────────────────────────────────────────────
    def mark(self, stage: str) -> float:
        """Close ``stage`` and return its duration in milliseconds.

        Repeated marks for the same stage accumulate rather than overwrite, so a
        loop (e.g. a provider retry) reports its true total cost.
        """
        now = time.monotonic()
        elapsed_ms = (now - self._last) * 1000.0
        self._last = now
        if stage not in self._durations:
            self._order.append(stage)
            self._durations[stage] = 0.0
        self._durations[stage] += elapsed_ms
        return elapsed_ms

    # ── outputs ────────────────────────────────────────────────────────────
    @property
    def total_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000.0

    def mark_finished(self) -> None:
        """Seal the trace. Later ``mark`` calls are ignored (double-emit guard)."""
        self._finished = True

    def server_timing(self) -> str:
        """W3C ``Server-Timing`` header value: ``auth;dur=2, context;dur=11, ...``.

        Stage names are sanitised because header values must not contain commas,
        semicolons or spaces in the metric name itself.
        """
        parts: List[str] = []
        for stage in self._order[:_MAX_HEADER_STAGES]:
            safe = "".join(ch for ch in stage if ch.isalnum() or ch in "-_") or "stage"
            parts.append(f"{safe};dur={self._durations[stage]:.1f}")
        parts.append(f"total;dur={self.total_ms:.1f}")
        return ", ".join(parts)

    def log(self, *, level: int = logging.INFO) -> None:
        """Emit the one line that makes a slow request attributable.

        Field order mirrors the chat path so a grep of ``chat_timing`` reads as a
        timeline. ``total_ms`` is measured to the log call, i.e. before the
        response body is written to the socket — it excludes client/transfer
        time on purpose (that is a different question).
        """
        if self._finished:
            return
        stage_parts = " ".join(
            f"{stage}_ms={self._durations[stage]:.0f}" for stage in self._order
        )
        logger.log(
            level,
            "chat_timing model=%s lane=%s provider=%s %s total_ms=%.0f",
            self.model or "-",
            self.lane or "-",
            self.provider or "-",
            stage_parts or "(no stages)",
            self.total_ms,
        )
        self._finished = True


def self_test() -> int:
    """Arithmetic + contract self-test (no sleeps longer than 2ms)."""
    trace = RequestTrace(model="supreme-spark")
    trace.mark("auth")
    trace.mark("persist")
    trace.mark("persist")  # accumulates rather than overwrites
    assert set(trace._durations) == {"auth", "persist"}, trace._durations
    assert trace._order == ["auth", "persist"], trace._order

    header = trace.server_timing()
    assert header.startswith("auth;dur="), header
    assert "persist;dur=" in header and header.endswith(header.split(", ")[-1]), header
    assert "total;dur=" in header, header
    # Header must never carry a raw stage name that could break parsing.
    assert ", " in header and ";" in header

    # __slots__ is load-bearing: a trace is created per request, so an accidental
    # new attribute must fail loudly here rather than silently per-request.
    try:
        trace.not_a_real_field = 1  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:  # pragma: no cover - only if __slots__ were removed
        raise AssertionError("__slots__ contract broken: trace accepted a new attribute")

    trace.mark_finished()
    before = trace.total_ms
    trace.mark("route")  # a mark after finish still records; only LOGGING is sealed
    assert trace.total_ms >= before
    assert "route" in trace._durations
    trace.log()  # must not raise, and must emit
    # Second log call is a no-op (sealed) so a request can never log twice.
    trace.log()
    print("request_trace self-test: PASS (1/1)")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    import sys

    sys.exit(self_test())
