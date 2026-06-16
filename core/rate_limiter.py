from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from loguru import logger


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60, burst: int = 10) -> None:
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self._hits: Dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float) -> None:
        window = 60.0
        self._hits[key] = [t for t in self._hits[key] if now - t < window]

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self._cleanup(key, now)
        hits = self._hits[key]
        if len(hits) >= self.burst:
            return False
        hits.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        self._cleanup(key, now)
        return max(0, self.burst - len(self._hits[key]))


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60, burst: int = 10) -> None:
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute=requests_per_minute, burst=burst)

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        if not self.limiter.is_allowed(client):
            logger.warning(f"Rate limit exceeded for {client}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )
        response = await call_next(request)
        return response
