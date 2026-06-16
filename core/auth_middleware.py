from __future__ import annotations

import os
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from loguru import logger


def _get_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.enabled = bool(os.getenv("SUPREMEAI_API_TOKEN"))

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        path = request.url.path
        public_paths = {
            "/health",
            "/actuator/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        if path in public_paths or path.startswith("/static"):
            return await call_next(request)

        token = _get_bearer_token(request)
        expected = os.getenv("SUPREMEAI_API_TOKEN")
        if not token or token != expected:
            logger.warning(f"Unauthorized access attempt to {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API token."},
            )
        return await call_next(request)
