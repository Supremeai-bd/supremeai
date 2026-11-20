"""gateway/middleware/http_header_middleware.py — shared base for header stampers.

WHY THIS EXISTS
---------------
``SecurityHeadersMiddleware`` and ``ServerTimingMiddleware`` are both "pure-ASGI,
HTTP-only, stamp headers on ``http.response.start``" middlewares. Written
independently they duplicated the same nine-line scaffold::

    class _X:
        def __init__(self, app): self.app = app
        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            async def send_with_x(message): ...

``detect_new_duplicates.py`` flagged that scaffold as a clone (9 lines / 62
tokens) when the second instance landed, and the guard's ``--max-new 0`` policy
is right: a third middleware written by copy-paste is how a codebase ends up with
five subtly different non-HTTP bypass rules.

The base is deliberately tiny. It owns exactly two things — the HTTP-only guard
and the delegation of ``send`` — and nothing about *which* headers are set. That
keeps every subclass free to decide its own semantics (SET vs APPEND, preserve vs
overwrite) without the base encoding a policy one of them would have to fight.

Subclasses implement ``stamp(message)``, which is called only for
``http.response.start``. It must be synchronous and must not raise: it runs after
the response has begun and a failure there would corrupt the response.

Stdlib + starlette only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class HttpHeaderMiddleware(ABC):
    """HTTP-only ASGI middleware that stamps headers as the response starts."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @abstractmethod
    def stamp(self, message: Message, state: Any) -> None:  # pragma: no cover
        """Mutate ``message``'s headers. Called only on ``http.response.start``.

        ``state`` is whatever :meth:`before_http` returned for this request.
        Implementations must be synchronous and must not raise.
        """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # lifespan / websocket have no response headers to stamp
            await self.app(scope, receive, send)
            return

        state: Any = self.before_http(scope)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.stamp(message, state)
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def before_http(self, scope: Scope) -> Any:
        """Hook run once per request, before the app is called.

        Returns an opaque per-request value passed back to ``stamp``. Default is
        ``None``; ``ServerTimingMiddleware`` uses it to start its clock.
        """
        return None
