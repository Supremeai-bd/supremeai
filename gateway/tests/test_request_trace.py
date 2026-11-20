"""Per-request latency attribution on the chat path (gateway/service/request_trace.py).

WHY THIS EXISTS
---------------
A one-word reply ("hi") measured 6.2s end-to-end and could not be attributed from
logs: the only latency signal was ``Stealth webhook OK ... latency=Nms``, which
covers ONE hop behind a lane decision that itself sits behind four serial gateway
steps. These tests pin the three properties that make the trace trustworthy:

1. The stage arithmetic is right and accumulating (a retry loop reports its total
   cost, not just the last attempt).
2. Both output channels exist — one structured ``chat_timing`` log line and a
   W3C ``Server-Timing`` header a browser/curl can read.
3. Tracing can never break a chat request: a broken/absent trace must not raise,
   and a single request can never emit two log lines.

Contracts asserted here are the ones the chat path relies on, so a future edit
that removes instrumentation fails loudly instead of silently going dark again.
"""

from __future__ import annotations

import logging

import pytest

from gateway.service.request_trace import STAGES, RequestTrace


def test_stage_arithmetic_accumulates_across_repeats() -> None:
    """A repeated stage (e.g. provider retry) sums, and order is kept stable."""
    trace = RequestTrace(model="supreme-spark")
    trace.mark("auth")
    trace.mark("persist")
    first_persist = trace._durations["persist"]
    trace.mark("persist")  # simulated retry
    assert trace._durations["persist"] >= first_persist
    assert trace._order == ["auth", "persist"], trace._order
    assert trace._order.count("persist") == 1


def test_total_is_monotonic_and_non_negative() -> None:
    trace = RequestTrace()
    before = trace.total_ms
    trace.mark("auth")
    after = trace.total_ms
    assert after >= before >= 0.0


def test_server_timing_header_is_w3c_shaped() -> None:
    """Header format must stay parseable: ``name;dur=<float>`` entries, comma-joined."""
    trace = RequestTrace(model="supreme-spark")
    for stage in STAGES:
        trace.mark(stage)
    header = trace.server_timing()

    assert header, "Server-Timing must never be empty"
    assert "total;dur=" in header
    for entry in header.split(", "):
        name, _, dur = entry.partition(";dur=")
        assert name and name.replace("-", "").replace("_", "").isalnum(), entry
        float(dur)  # raises if not numeric
    # Every declared stage that was marked is present.
    for stage in STAGES:
        assert f"{stage};dur=" in header


def test_server_timing_name_is_sanitised() -> None:
    """A stage name with header-hostile characters must not corrupt the value."""
    trace = RequestTrace()
    trace.mark('weird, "name";\n')
    header = trace.server_timing()
    assert "\n" not in header
    assert header.count(";dur=") == 2  # the stage + total


def test_log_emits_one_attributable_line(caplog: pytest.LogCaptureFixture) -> None:
    """The log line carries model, lane, provider and each stage — this is the
    artefact that turns 'it felt slow' into 'context_ms=720 upstream_ms=5100'."""
    trace = RequestTrace(model="supreme-spark")
    trace.mark("auth")
    trace.mark("persist")
    trace.mark("context")
    trace.mark("route")
    trace.mark("upstream")
    trace.lane = "stealth-webhook"
    trace.provider = "ghost_gemini"

    with caplog.at_level(logging.INFO, logger="supremeai.request_trace"):
        trace.log()

    text = caplog.text
    assert "chat_timing" in text
    assert "model=supreme-spark" in text
    assert "lane=stealth-webhook" in text
    assert "provider=ghost_gemini" in text
    for stage in STAGES:
        assert f"{stage}_ms=" in text
    assert "total_ms=" in text


def test_log_is_idempotent_per_request(caplog: pytest.LogCaptureFixture) -> None:
    """Double-emit guard: one request must never produce two chat_timing lines."""
    trace = RequestTrace(model="supreme-spark")
    trace.mark("auth")
    with caplog.at_level(logging.INFO, logger="supremeai.request_trace"):
        trace.log()
        trace.log()
    assert caplog.text.count("chat_timing") == 1


def test_trace_never_raises_on_hostile_input() -> None:
    """Tracing is on the hot path: it must degrade, never fail the request."""
    trace = RequestTrace(model=None)
    trace.mark("")  # empty stage name
    trace.mark("x" * 10_000)  # absurdly long stage name
    header = trace.server_timing()
    assert header  # still produces a usable header
    trace.log()  # must not raise with no model and no lane


def test_slots_contract_prevents_head_growth() -> None:
    """One trace per request: an accidental new attribute must fail loudly."""
    trace = RequestTrace()
    with pytest.raises(AttributeError):
        trace.accidental_attribute = 1  # type: ignore[attr-defined]
