"""
SupremeAI 2.0 — Redis-Based Rate Limiter for API Keys
Sliding window algorithm with dual limits (RPM + RPD).
"""
import time
from typing import Optional, Tuple
from dataclasses import dataclass

import redis.asyncio as redis
from loguru import logger

from core.config import settings


@dataclass
class RateLimitStatus:
    """Current rate limit status for a key."""
    allowed: bool
    current_rpm: int
    current_rpd: int
    rpm_limit: int
    rpd_limit: int
    retry_after_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "current_rpm": self.current_rpm,
            "current_rpd": self.current_rpd,
            "rpm_limit": self.rpm_limit,
            "rpd_limit": self.rpd_limit,
            "rpm_remaining": max(0, self.rpm_limit - self.current_rpm),
            "rpd_remaining": max(0, self.rpd_limit - self.current_rpd),
            "retry_after_ms": self.retry_after_ms,
        }


class APIKeyRateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.

    Keys:
        rate:<key_id>:rpm  → ZSET of request timestamps (last 60s)
        rate:<key_id>:rpd  → ZSET of request timestamps (last 86400s)
        quota:<key_id>:month → current month token usage (counter)
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client
        self._rpm_window = 60  # seconds
        self._rpd_window = 86400  # seconds (24 hours)

    async def _get_redis(self) -> redis.Redis:
        """Lazy Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._redis

    async def check_rate_limit(
        self,
        key_id: str,
        rpm_limit: int,
        rpd_limit: int,
        tokens: int = 0,
        monthly_quota: int = 0,
    ) -> RateLimitStatus:
        """
        Check if a request is within rate limits.

        Args:
            key_id: The API key ID
            rpm_limit: Max requests per minute
            rpd_limit: Max requests per day
            tokens: Number of tokens in this request (for quota check)
            monthly_quota: Monthly token quota

        Returns:
            RateLimitStatus with allow/deny decision
        """
        r = await self._get_redis()
        now = time.time()
        now_ms = int(now * 1000)

        rpm_key = f"rate:{key_id}:rpm"
        rpd_key = f"rate:{key_id}:rpd"
        quota_key = f"quota:{key_id}:month"

        pipe = r.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(rpm_key, 0, now_ms - (self._rpm_window * 1000))
        pipe.zremrangebyscore(rpd_key, 0, now_ms - (self._rpd_window * 1000))

        # Count current entries
        pipe.zcard(rpm_key)
        pipe.zcard(rpd_key)

        # Get current quota usage
        pipe.get(quota_key)

        results = await pipe.execute()

        current_rpm = results[2]
        current_rpd = results[3]
        current_quota = int(results[4] or 0)

        # Check quota first
        if monthly_quota > 0 and (current_quota + tokens) > monthly_quota:
            logger.warning(
                f"API key {key_id} exceeded monthly quota: "
                f"{current_quota + tokens} > {monthly_quota}"
            )
            return RateLimitStatus(
                allowed=False,
                current_rpm=current_rpm,
                current_rpd=current_rpd,
                rpm_limit=rpm_limit,
                rpd_limit=rpd_limit,
                retry_after_ms=self._get_quota_retry_after(),
            )

        # Check rate limits
        if current_rpm >= rpm_limit:
            retry_after = self._get_retry_after(rpm_key, self._rpm_window)
            logger.warning(
                f"API key {key_id} RPM limit exceeded: "
                f"{current_rpm}/{rpm_limit}"
            )
            return RateLimitStatus(
                allowed=False,
                current_rpm=current_rpm,
                current_rpd=current_rpd,
                rpm_limit=rpm_limit,
                rpd_limit=rpd_limit,
                retry_after_ms=retry_after,
            )

        if current_rpd >= rpd_limit:
            retry_after = self._get_retry_after(rpd_key, self._rpd_window)
            logger.warning(
                f"API key {key_id} RPD limit exceeded: "
                f"{current_rpd}/{rpd_limit}"
            )
            return RateLimitStatus(
                allowed=False,
                current_rpm=current_rpm,
                current_rpd=current_rpd,
                rpm_limit=rpm_limit,
                rpd_limit=rpd_limit,
                retry_after_ms=retry_after,
            )

        # Request is allowed — record it
        pipe = r.pipeline()
        pipe.zadd(rpm_key, {str(now_ms): now_ms})
        pipe.zadd(rpd_key, {str(now_ms): now_ms})
        pipe.expire(rpm_key, self._rpm_window + 10)
        pipe.expire(rpd_key, self._rpd_window + 10)

        if tokens > 0 and monthly_quota > 0:
            pipe.incrby(quota_key, tokens)
            # Set expiry to end of month
            pipe.expireat(quota_key, self._get_month_end_timestamp())

        await pipe.execute()

        return RateLimitStatus(
            allowed=True,
            current_rpm=current_rpm + 1,
            current_rpd=current_rpd + 1,
            rpm_limit=rpm_limit,
            rpd_limit=rpd_limit,
        )

    async def get_current_usage(self, key_id: str) -> Tuple[int, int, int]:
        """
        Get current RPM, RPD, and quota usage without incrementing.

        Returns:
            Tuple of (current_rpm, current_rpd, current_quota)
        """
        r = await self._get_redis()
        now = time.time()
        now_ms = int(now * 1000)

        rpm_key = f"rate:{key_id}:rpm"
        rpd_key = f"rate:{key_id}:rpd"
        quota_key = f"quota:{key_id}:month"

        pipe = r.pipeline()
        pipe.zremrangebyscore(rpm_key, 0, now_ms - (self._rpm_window * 1000))
        pipe.zremrangebyscore(rpd_key, 0, now_ms - (self._rpd_window * 1000))
        pipe.zcard(rpm_key)
        pipe.zcard(rpd_key)
        pipe.get(quota_key)

        results = await pipe.execute()

        return (
            results[2],  # current_rpm
            results[3],  # current_rpd
            int(results[4] or 0),  # current_quota
        )

    async def reset_quota(self, key_id: str) -> None:
        """Reset monthly quota counter (called on 1st of month)."""
        r = await self._get_redis()
        quota_key = f"quota:{key_id}:month"
        await r.delete(quota_key)
        logger.info(f"Reset quota for key {key_id}")

    async def reset_rate_limits(self, key_id: str) -> None:
        """Reset all rate limit counters (e.g., after key rotation)."""
        r = await self._get_redis()
        rpm_key = f"rate:{key_id}:rpm"
        rpd_key = f"rate:{key_id}:rpd"
        await r.delete(rpm_key, rpd_key)
        logger.info(f"Reset rate limits for key {key_id}")

    def _get_retry_after(self, key: str, window: int) -> int:
        """Calculate retry-after time in ms based on oldest entry."""
        # Conservative: wait full window
        return window * 1000

    def _get_quota_retry_after(self) -> int:
        """Calculate time until quota resets (end of month)."""
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        next_month = now.replace(day=28) + timedelta(days=4)
        next_month = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return int((next_month - now).total_seconds() * 1000)

    def _get_month_end_timestamp(self) -> int:
        """Get Unix timestamp for end of current month."""
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        next_month = now.replace(day=28) + timedelta(days=4)
        next_month = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(next_month.timestamp())

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Singleton instance
_rate_limiter: Optional[APIKeyRateLimiter] = None


def get_rate_limiter() -> APIKeyRateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = APIKeyRateLimiter()
    return _rate_limiter
