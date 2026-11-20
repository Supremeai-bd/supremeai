"""gateway/middleware/server_timing.py — Server-Timing on *every* response.

WHY THIS EXISTS (the gap it closes)
-----------------------------------
``gateway/service/request_trace.py`` gives the chat path a rich, stage-by-stage
``Server-Timing`` header (auth → persist → context → route → upstream). That
header is attached at the four *successful* return sites in ``app.py``.

The failure paths are the ones people actually ask about. Of the ~16 exits in
the chat handler, ~12 are ``raise HTTPException(...)`` — 400/401/502/503. Not one
of those carried ``Server-Timing``, so a request that failed was also a request
that could not be timed. Measured before this module existed::

    'hi'      -> 200, timing=auth;dur=0.0, upstream;dur=0.1, total;dur=0.4
    'France…' -> 503, timing=None      <-- invisible

That is the wrong way round: the slow/failing request is the one you need to
attribute.

DESIGN
------
* Pure-ASGI middleware, outermost, on ``http.response.start`` only. It never
  reads, buffers or re-chunks the body, so streaming (SSE) is untouched.
* **Additive, never destructive.** If the route already set ``Server-Timing``
  (the chat success path's detailed value), that value is preserved verbatim.
  This middleware only fills the gap when the header is absent — which is
  exactly the error paths, plus every non-chat endpoint.
* **Self-identifying.** The fallback value ends in ``;desc=gw`` so a reader can
  tell a coarse middleware-only measurement from a full route trace. A coarse
  number that looks like a detailed one is worse than no number.
* **Total is measured at header-send time**, i.e. it includes everything the
  server did up to response start. It excludes body transfer, which is a
  different question (and is what the browser's own timing already answers).
* Non-HTTP scopes (lifespan, websocket) pass through untouched.
* Standard library + starlette only; no new dependencies.

Mount (must be added AFTER the security-headers middleware so it is OUTERMOST —
Starlette ``add_middleware`` prepends)::

    from gateway.middleware.server_timing import ServerTimingMiddleware
    app.add_middleware(ServerTimingMiddleware)

Local test:
    pytest gateway/tests/test_server_timing_middleware.py
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from starlette.datastructures import MutableHeaders
from starlette.types import Message, Scope

from gateway.middleware.http_header_middleware import HttpHeaderMiddleware

#: Header name (W3C Server-Timing, https://www.w3.org/TR/server-timing/).
HEADER = b"server-timing"

#: Marker appended to the fallback value. Route-level traces carry stage names
#: and never this token, so the two origins are distinguishable at a glance.
FALLBACK_DESC = "gw"

#: Scope key carrying the monotonic start time, so an exception handler can
#: measure the request even though it sits outside the outer server-error layer.
SCOPE_KEY = "supremeai.timing_start"


class ServerTimingMiddleware(HttpHeaderMiddleware):
    """Stamp a coarse ``Server-Timing`` on any response that lacks one."""

    def before_http(self, scope: Scope) -> float:
        started = time.monotonic()
        # Stash on the scope so a global exception handler — which runs inside
        # the stack, unlike Starlette's outermost ServerErrorMiddleware — can
        # still measure the request it is about to turn into a 500.
        scope[SCOPE_KEY] = started
        return started

    def stamp(self, message: Message, state: Any = None) -> None:
        # Preserve a richer, route-level trace if the handler produced one;
        # only fill the gap when nothing is there.
        existing = _find_header(message.get("headers") or [], HEADER)
        if existing is not None:
            return
        started = state if state is not None else time.monotonic()
        total_ms = (time.monotonic() - started) * 1000.0
        headers = MutableHeaders(scope=message)
        headers.append(
            "Server-Timing",
            f"total;dur={total_ms:.1f};desc={FALLBACK_DESC}",
        )


def _find_header(headers: List[Tuple[bytes, bytes]], name: bytes):
    """Return the value of ``name`` (case-insensitive) or ``None``."""
    for key, value in headers:
        if key.lower() == name:
            return value
    return None


def timing_header_for_scope(scope: dict) -> Dict[str, str]:
    """Return a ``Server-Timing`` header for a scope this middleware has seen.

    For exception handlers only. Starlette builds the 500 response for an
    unhandled exception in ``ServerErrorMiddleware``, which sits *outside* every
    user middleware — so no middleware can stamp that response. A global
    ``Exception`` handler, by contrast, runs inside the stack, but by then the
    body is being built by code that never saw the clock. This hands it back.

    Returns ``{}`` when this middleware never ran for the request (so a caller
    can splat it into ``headers=`` unconditionally).
    """
    started = scope.get(SCOPE_KEY) if isinstance(scope, dict) else None
    if started is None:
        return {}
    total_ms = (time.monotonic() - started) * 1000.0
    return {"Server-Timing": f"total;dur={total_ms:.1f};desc={FALLBACK_DESC}"}


def self_test() -> int:
    """Offline self-check: header lookup is case-insensitive and total-ordered.

    Returns 0 on success, 1 on failure. Used by the guard roster; the real
    behaviour is covered by ``gateway/tests/test_server_timing_middleware.py``.
    """
    failures: List[str] = []

    if _find_header([(b"Server-Timing", b"total;dur=1.0")], HEADER) != b"total;dur=1.0":
        failures.append("exact-case lookup failed")
    if _find_header([(b"server-timing", b"x")], HEADER) != b"x":
        failures.append("lower-case lookup failed")
    if _find_header([(b"content-type", b"text/plain")], HEADER) is not None:
        failures.append("absent header was reported present")
    if _find_header([], HEADER) is not None:
        failures.append("empty header list was reported present")

    # Exception-handler helper: no clock -> no header (must be splat-safe).
    if timing_header_for_scope({}) != {}:
        failures.append("handler helper invented a header without a clock")
    timed = timing_header_for_scope({SCOPE_KEY: time.monotonic()})
    if "Server-Timing" not in timed:
        failures.append("handler helper produced no header for a timed scope")
    elif not timed["Server-Timing"].startswith("total;dur="):
        failures.append("handler helper header malformed")

    for item in failures:
        print(f"  [FAIL] {item}")
    if failures:
        print(f"server_timing self-test: FAIL ({len(failures)} cases)")
        return 1
    print("server_timing self-test: PASS (6 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
