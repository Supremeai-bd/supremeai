import asyncio
import os
import random

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.logging_config import logger

# বাংলা মন্তব্য: ChaosInjectorMiddleware — LOCAL_CHAOS_MODE env var দিয়ে নিয়ন্ত্রিত।
# Production-এ সম্পূর্ণ নিষ্ক্রিয়। শুধুমাত্র local dev/test-এ random delay ও packet drop inject করে।

_DEFAULT_DROP_THRESHOLD: float = 0.15
_DEFAULT_DELAY_THRESHOLD: float = 0.3
_DEFAULT_RATE_LIMIT_THRESHOLD: float = 0.0

_DROP_THRESHOLD: float = _DEFAULT_DROP_THRESHOLD
_DELAY_THRESHOLD: float = _DEFAULT_DELAY_THRESHOLD
_DELAY_MIN: float = 0.5
_DELAY_MAX: float = 3.5


def _parse_chance(env_var: str, default: float) -> float:
    raw = os.getenv(env_var)
    if raw is None:
        return default
    try:
        val = float(raw)
        if 0.0 <= val <= 1.0:
            return val
        logger.warning(f"{env_var}={raw} out of range [0.0, 1.0], using default {default}")
        return default
    except (ValueError, TypeError):
        logger.warning(f"Invalid float for {env_var}={raw}, using default {default}")
        return default


class ChaosInjectorMiddleware(BaseHTTPMiddleware):
    """
    Chaos Engineering Middleware — LOCAL_CHAOS_MODE=true হলে random delay ও packet drop inject করে।
    Production Safety: ENV=production হলে সম্পূর্ণ bypass।
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self.chaos_enabled = os.getenv("LOCAL_CHAOS_MODE", "false").lower() == "true"
        self.rate_limit_threshold = _parse_chance(
            "CHAOS_RATE_LIMIT_CHANCE", _DEFAULT_RATE_LIMIT_THRESHOLD
        )
        self.drop_threshold = _parse_chance(
            "CHAOS_PACKET_DROP_CHANCE", _DEFAULT_DROP_THRESHOLD
        )
        self.delay_threshold = _parse_chance(
            "CHAOS_LATENCY_CHANCE", _DEFAULT_DELAY_THRESHOLD
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        env = os.getenv("ENV", "local").lower()
        if env == "production" or not self.chaos_enabled:
            return await call_next(request)

        # 1. Rate limit check (429)
        if self.rate_limit_threshold > 0 and random.random() < self.rate_limit_threshold:
            logger.warning(f"Chaos injected: Rate limit 429 for {getattr(request.url, 'path', '')}")
            return JSONResponse(
                {"detail": "Chaos: rate limit simulated. Please try again later.", "error": "rate limit"},
                status_code=429,
                headers={"retry-after": "60"},
            )

        # 2. Packet drop (504)
        if self.drop_threshold > 0 and random.random() < self.drop_threshold:
            logger.warning(f"Chaos injected: Packet drop 504 for {getattr(request.url, 'path', '')}")
            return Response(status_code=504, content="Gateway Timeout (Chaos Injection)")

        # 3. Latency injection
        if self.delay_threshold > 0 and random.random() < self.delay_threshold:
            delay = random.uniform(_DELAY_MIN, _DELAY_MAX)
            logger.info(f"Chaos injected: Delay {delay:.2f}s for {getattr(request.url, 'path', '')}")
            await asyncio.sleep(delay)

        return await call_next(request)
