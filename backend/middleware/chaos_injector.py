import asyncio
import os
import random

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.logging_config import logger

# বাংলা মন্তব্য: ChaosInjectorMiddleware — LOCAL_CHAOS_MODE env var দিয়ে নিয়ন্ত্রিত।
# Production-এ সম্পূর্ণ নিষ্ক্রিয়। শুধুমাত্র local dev/test-এ random delay, packet drop
# এবং (৩-স্তর টেস্টিং প্ল্যান Tier-2 থেকে) HTTP 429 rate-limit inject করে।


# ডিফল্ট থ্রেশহোল্ড — বাংলা মন্তব্য (Tier-2): মানগুলো এখন env দিয়ে override করা যায়
# (api/middleware.py-এর অব্যবহৃত ডুপ্লিকেটের env-tunable ডিজাইনের সাথে সঙ্গতি), যাতে
# টেস্ট deterministic ফল্ট force করতে পারে (chance=1.0)। ডিফল্ট মান অপরিবর্তিত।
_DEFAULT_DROP_THRESHOLD = 0.15
_DEFAULT_DELAY_THRESHOLD = 0.3
# 429 ইনজেকশন ডিফল্টে বন্ধ (0.0) — শুধু সচেতনভাবে চালু করলেই হবে।
_DEFAULT_RATE_LIMIT_THRESHOLD = 0.0
_DELAY_MIN = 0.5
_DELAY_MAX = 3.5


def _env_float(name: str, default: float) -> float:
    """Env var থেকে float থ্রেশহোল্ড — ভুল মান হলে নীরবে ডিফল্টে ফেরত (log সহ)।"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(f"[CHAOS] Invalid {name}={raw!r} — falling back to {default}")
        return default
    if value < 0.0 or value > 1.0:
        logger.warning(f"[CHAOS] Out-of-range {name}={value} — falling back to {default}")
        return default
    return value


class ChaosInjectorMiddleware(BaseHTTPMiddleware):
    """
    Chaos Engineering Middleware — LOCAL_CHAOS_MODE=true হলে random delay, packet drop
    এবং 429 rate-limit inject করে।
    Production Safety: ENV=production হলে সম্পূর্ণ bypass।

    বাংলা মন্তব্য (Tier-2): একটি roll-এর উপর cascading ব্যান্ড —
    [0, rate_limit) → 429, [rate_limit, drop) → 504, [drop, delay) → latency।
    প্রতিটি ব্যান্ডের প্রস্থ env দিয়ে নিয়ন্ত্রণযোগ্য, তাই টেস্টে
    CHAOS_RATE_LIMIT_CHANCE=1.0 দিলে নিশ্চিতভাবে 429 পাওয়া যায়।
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        # বাংলা মন্তব্য: LOCAL_CHAOS_MODE env var থেকে chaos_enabled নির্ধারণ করা হয়
        self.chaos_enabled = os.getenv("LOCAL_CHAOS_MODE", "false").lower() == "true"
        # Fault rates — init-সময়ে একবার পড়া হয়, তাই টেস্ট env সেট করে তারপর
        # middleware কনস্ট্রাক্ট করলেই deterministic আচরণ পাওয়া যায়।
        self.rate_limit_threshold = _env_float(
            "CHAOS_RATE_LIMIT_CHANCE", _DEFAULT_RATE_LIMIT_THRESHOLD
        )
        self.drop_threshold = _env_float("CHAOS_PACKET_DROP_CHANCE", _DEFAULT_DROP_THRESHOLD)
        self.delay_threshold = _env_float("CHAOS_LATENCY_CHANCE", _DEFAULT_DELAY_THRESHOLD)

    async def dispatch(self, request: Request, call_next) -> Response:
        env = os.getenv("ENV", "local").lower()
        # Production safety switch — production is completely bypassed regardless of
        # LOCAL_CHAOS_MODE. self.chaos_enabled (explicit LOCAL_CHAOS_MODE=true opt-in) is
        # the only other gate needed: nothing in .github/workflows/ or render.yaml ever sets
        # that var, so no test/CI run is affected unless it deliberately opts in (as this
        # middleware's own unit tests do, to verify the injection logic itself). An earlier
        # blanket "pytest in sys.modules" / CI/GITHUB_ACTIONS bypass here broke exactly those
        # tests, in both local pytest runs and real GitHub Actions CI (GITHUB_ACTIONS=true is
        # always set there).
        if env == "production" or not self.chaos_enabled:
            return await call_next(request)

        roll = random.random()  # — intentional non-crypto random for chaos

        # rate-limit injection — HTTP 429 + Retry-After (Tier-2: provider rate-limit storm সিমুলেশন;
        # predictive breaker + LLM gateway retry পথের যাচাইয়ের জন্য)
        if roll < self.rate_limit_threshold:
            logger.warning(f"[CHAOS] Injecting HTTP 429 rate-limit for {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Chaos: simulated provider rate limit"},
                headers={"Retry-After": "60"},
            )

        # packet drop — 504 Gateway Timeout
        if roll < self.rate_limit_threshold + self.drop_threshold:
            logger.warning(f"[CHAOS] Packet drop for {request.url.path}")
            return JSONResponse(status_code=504, content={"detail": "Chaos: packet dropped"})

        # latency injection — random sleep
        if roll < self.rate_limit_threshold + self.drop_threshold + self.delay_threshold:
            delay = _DELAY_MIN + random.random() * (_DELAY_MAX - _DELAY_MIN)
            logger.warning(f"[CHAOS] Injecting {delay:.2f}s delay for {request.url.path}")
            await asyncio.sleep(delay)
            # packet drop after delay (values[1] < threshold triggers drop)
            if random.random() < self.drop_threshold:
                return JSONResponse(
                    status_code=504, content={"detail": "Chaos: packet dropped after delay"}
                )

        return await call_next(request)
