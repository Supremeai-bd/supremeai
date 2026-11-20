"""Tests for ``gateway/middleware/server_timing.py``.

The regression these lock down is not "the header exists" — it is **"the header
exists on the failure path"**. Before this middleware the 503/502/4xx exits in
the chat handler carried no ``Server-Timing`` at all, so the requests most worth
attributing were the only ones with no timing::

    'hi'      -> 200  timing=auth;dur=0.0, upstream;dur=0.1, total;dur=0.4
    'France…' -> 503  timing=None

Every test here drives the middleware through real ASGI messages rather than
calling helpers, so a change in message shape cannot pass vacuously.
"""

from __future__ import annotations

import asyncio

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from gateway.middleware.server_timing import (
    FALLBACK_DESC,
    ServerTimingMiddleware,
    self_test,
)


# ── helpers ────────────────────────────────────────────────────────────────
class _Rig:
    """Run the middleware around a single synthetic ASGI response."""

    def __init__(self, start_headers: list[tuple[bytes, bytes]] | None = None):
        self.seen: list[dict] = []
        self.start_headers = start_headers or []

    async def run(self, scope_type: str = "http") -> list[dict]:
        async def app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 503,
                    "headers": list(self.start_headers),
                }
            )
            await send({"type": "http.response.body", "body": b"nope"})

        async def send(message):
            self.seen.append(message)

        async def receive():
            return {"type": "http.request"}

        mw = ServerTimingMiddleware(app)
        await mw({"type": scope_type}, receive, send)
        return self.seen

    def header_value(self) -> str | None:
        for msg in self.seen:
            if msg["type"] == "http.response.start":
                for key, value in msg["headers"]:
                    if key.lower() == b"server-timing":
                        return value.decode()
        return None


def _headers_of(start_message: dict) -> list[tuple[bytes, bytes]]:
    return start_message["headers"]


# ── the core gap ───────────────────────────────────────────────────────────
def test_error_response_without_timing_gets_a_timing_header():
    """THE regression: a bare error response used to carry no timing at all."""
    rig = _Rig()
    asyncio.run(rig.run())
    value = rig.header_value()
    assert value is not None, "error path must not be invisible to Server-Timing"
    assert "total;dur=" in value


def test_fallback_value_is_marked_as_middleware_coarse():
    """A coarse number must not masquerade as a route-level stage trace."""
    rig = _Rig()
    asyncio.run(rig.run())
    value = rig.header_value()
    assert value.endswith(f";desc={FALLBACK_DESC}"), value
    # Must not look like a route trace
    for stage in ("auth", "persist", "context", "route", "upstream"):
        assert f"{stage};dur=" not in value


def test_route_level_trace_is_preserved_verbatim():
    """The chat success path's detailed trace must never be overwritten."""
    detailed = b"auth;dur=0.0, upstream;dur=0.2, total;dur=5.0"
    rig = _Rig(start_headers=[(b"server-timing", detailed)])
    asyncio.run(rig.run())
    assert rig.header_value() == detailed.decode()
    # and no duplicate header was appended
    start = next(m for m in rig.seen if m["type"] == "http.response.start")
    names = [k.lower() for k, _ in _headers_of(start)]
    assert names.count(b"server-timing") == 1


def test_preserved_trace_is_not_marked_as_fallback():
    detailed = b"auth;dur=1.0, total;dur=1.0"
    rig = _Rig(start_headers=[(b"Server-Timing", detailed)])
    asyncio.run(rig.run())
    assert FALLBACK_DESC not in (rig.header_value() or "")


def test_duration_is_numeric_and_non_negative():
    rig = _Rig()
    asyncio.run(rig.run())
    value = rig.header_value()
    dur = float(value.split("dur=")[1].split(";")[0])
    assert dur >= 0.0


def test_non_http_scope_passes_through_untouched():
    """lifespan/websocket must not be given an HTTP header."""
    rig = _Rig()
    asyncio.run(rig.run(scope_type="lifespan"))
    assert rig.header_value() is None


def test_body_is_never_modified():
    rig = _Rig()
    seen = asyncio.run(rig.run())
    body = next(m for m in seen if m["type"] == "http.response.body")
    assert body["body"] == b"nope"


# ── through a real app: the failure path end to end ────────────────────────
@pytest.fixture()
def client() -> TestClient:
    async def boom(_request):
        raise RuntimeError("kaboom")

    def not_found(_request):
        return PlainTextResponse("nope", status_code=503)

    app = Starlette(
        routes=[
            Route("/503", not_found),
            Route("/boom", boom),
            Route("/ok", lambda _r: PlainTextResponse("ok")),
        ]
    )
    app.add_middleware(ServerTimingMiddleware)
    # raise_server_exceptions=False so the 500 travels as a real response
    return TestClient(app, raise_server_exceptions=False)


def test_real_503_has_timing(client: TestClient):
    r = client.get("/503")
    assert r.status_code == 503
    assert "total;dur=" in r.headers.get("server-timing", "")


def test_real_unhandled_exception_500_has_timing():
    """A crash must not be the one case with no timing.

    Starlette builds the 500 for an unhandled exception in
    ``ServerErrorMiddleware``, which is OUTSIDE every user middleware — so the
    middleware alone cannot reach it. The gateway therefore also registers a
    global ``Exception`` handler, which runs inside the stack and can read the
    start time this middleware stashed on the scope.
    """
    from gateway.middleware.server_timing import timing_header_for_scope

    async def boom(_request):
        raise RuntimeError("kaboom")

    async def handle(_request, _exc):
        return JSONResponse(
            {"detail": "Internal Server Error"},
            status_code=500,
            headers=timing_header_for_scope(_request.scope),
        )

    app = Starlette(
        routes=[Route("/boom", boom)],
        exception_handlers={Exception: handle},
    )
    app.add_middleware(ServerTimingMiddleware)
    r = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert r.status_code == 500
    assert "total;dur=" in r.headers.get("server-timing", "")


def test_unhandled_exception_is_attributable_in_the_real_gateway():
    """The gateway registers the crash handler (not just the middleware)."""
    from gateway.service.app import app as gateway_app

    handlers = getattr(gateway_app, "exception_handlers", {}) or {}
    assert Exception in handlers, (
        "gateway must register a global Exception handler so a crash is timed; "
        "Starlette's own 500 is built outside every middleware"
    )
    # and the helper is splat-safe for a scope the middleware never saw
    from gateway.middleware.server_timing import timing_header_for_scope

    assert timing_header_for_scope({}) == {}


def test_real_success_also_gets_timing(client: TestClient):
    r = client.get("/ok")
    assert r.status_code == 200
    assert "total;dur=" in r.headers.get("server-timing", "")


def test_404_has_timing(client: TestClient):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert "total;dur=" in r.headers.get("server-timing", "")


# ── CORS exposure (the second half of the gap) ─────────────────────────────
def test_server_timing_is_exposed_by_cors():
    """Browser JS cannot read a non-simple header unless CORS exposes it.

    DevTools shows Server-Timing regardless, so this is easy to miss — but a
    dashboard reading it via fetch() would silently get ``null``.
    """
    from gateway.service.app import app as gateway_app

    cors = [
        m
        for m in gateway_app.user_middleware
        if m.cls.__name__ == "CORSMiddleware"
    ]
    assert cors, "gateway must mount CORSMiddleware"
    exposed = cors[0].kwargs.get("expose_headers") or []
    assert "Server-Timing" in exposed


def test_self_test_passes():
    assert self_test() == 0
