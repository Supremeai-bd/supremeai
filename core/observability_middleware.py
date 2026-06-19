from __future__ import annotations

import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.routes.metrics import record_error, record_request, record_request_duration
from core.telemetry import setup_tracing, trace_span


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        setup_tracing()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)

        method = request.method
        started = time.perf_counter()
        status_code = 500
        error_type = None

        try:
            with trace_span(
                f"{method} {path}",
                attributes={
                    "http.method": method,
                    "http.route": path,
                    "http.url": str(request.url),
                },
                kind="server",
            ):
                response = await call_next(request)
                status_code = response.status_code
                return response
        except Exception as exc:  # pylint: disable=broad-except
            error_type = type(exc).__name__
            record_error(error_type, path)
            raise
        finally:
            duration = time.perf_counter() - started
            record_request(method, path, status_code)
            record_request_duration(method, path, duration)
