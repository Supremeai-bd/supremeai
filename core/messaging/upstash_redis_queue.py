from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from core.config import settings
from core.logging_config import logger


class QuotaExhaustedError(RuntimeError):
    """Raised when all configured Upstash Redis REST accounts are soft-capped or quota-exhausted."""


def _quota_window() -> str:
    raw = (os.getenv("UPSTASH_QUOTA_WINDOW", "monthly") or "monthly").strip().lower()
    return "daily" if raw == "daily" else "monthly"


def _next_utc_reset_epoch() -> float:
    now = datetime.now(UTC)
    tomorrow = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
    return tomorrow.timestamp() + 60.0


def _next_quota_reset_epoch() -> float:
    if _quota_window() == "daily":
        return _next_utc_reset_epoch()
    now = datetime.now(UTC)
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        nxt = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return nxt.timestamp() + 60.0


class UpstashRedisQueue:
    def __init__(
        self,
        rest_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.rest_url = (rest_url or getattr(settings, "upstash_redis_rest_url", "") or "").rstrip(
            "/"
        )
        self.token = token or getattr(settings, "upstash_redis_rest_token", "") or ""
        self.timeout = timeout
        # বাংলা মন্তব্য: Upstash Rest Queue ক্লায়েন্টে সর্বোচ্চ ১০টি কানেকশন এবং ৫টি কিপ-অলাইভ কানেকশনের সীমা যুক্ত করা হলো।
        self._client = (
            httpx.Client(
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                timeout=self.timeout,
            )
            if (self.rest_url and self.token)
            or (hasattr(settings, "upstash_redis_rest_pool") and settings.upstash_redis_rest_pool)
            else None
        )
        self._active_pool_idx = 0
        raw_cap = os.getenv("UPSTASH_QUOTA_SOFT_CAP") or os.getenv("UPSTASH_DAILY_SOFT_CAP")
        try:
            self._soft_cap_limit = int(raw_cap) if raw_cap is not None else 400_000
        except ValueError:
            self._soft_cap_limit = 400_000
        self._day_bucket_until = _next_quota_reset_epoch()
        self._window_counts: dict[str, int] = {}
        self._softcap_accounts: dict[str, str] = {}
        self._cooldown_accounts: dict[str, str] = {}
        self._stats: dict[str, int] = {"softcap_shifts": 0, "quota_cooldowns": 0}

    @property
    def configured(self) -> bool:
        return bool(self._client)

    def _rollover_if_needed(self) -> None:
        now = time.time()
        if now >= self._day_bucket_until:
            self._day_bucket_until = _next_quota_reset_epoch()
            self._window_counts.clear()
            self._softcap_accounts.clear()
            self._cooldown_accounts.clear()

    def quota_status(self) -> dict[str, Any]:
        self._rollover_if_needed()
        counts = dict(self._window_counts)
        return {
            "window": _quota_window(),
            "window_counts": counts,
            "window_soft_cap": self._soft_cap_limit,
            "daily_counts": counts,
            "daily_soft_cap": self._soft_cap_limit,
            "cooldown_accounts": dict(self._cooldown_accounts),
            "softcap_accounts": dict(self._softcap_accounts),
            "stats": dict(self._stats),
        }

    def _request(self, *args: str) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError(
                "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are not configured"
            )

        self._rollover_if_needed()

        # Issue #754 (MA-04): multi-account federation failover across all 5 Upstash instances
        pool = getattr(settings, "upstash_redis_rest_pool", [])
        endpoints = (
            pool
            if pool
            else ([(self.rest_url, self.token)] if (self.rest_url and self.token) else [])
        )
        if not endpoints:
            raise RuntimeError("No configured Upstash Redis REST endpoints available")

        last_err: Exception | None = None
        skipped_by_quota = 0
        reset_iso = datetime.fromtimestamp(self._day_bucket_until, UTC).isoformat()

        for i in range(len(endpoints)):
            idx = (self._active_pool_idx + i) % len(endpoints)
            target_url, target_token = endpoints[idx]

            if target_url in self._cooldown_accounts:
                skipped_by_quota += 1
                continue

            if self._soft_cap_limit > 0:
                used = self._window_counts.get(target_url, 0)
                if used >= self._soft_cap_limit:
                    self._softcap_accounts.setdefault(target_url, reset_iso)
                    self._stats["softcap_shifts"] = self._stats.get("softcap_shifts", 0) + 1
                    skipped_by_quota += 1
                    continue

            try:
                response = self._client.post(
                    target_url,
                    headers={"Authorization": f"Bearer {target_token}"},
                    json=list(args),
                )
                status_code = getattr(response, "status_code", 200)
                body_text = str(getattr(response, "text", "") or "").lower()
                if status_code in (400, 402, 429) and (
                    "limit exceeded" in body_text or "quota" in body_text
                ):
                    self._cooldown_accounts[target_url] = reset_iso
                    self._stats["quota_cooldowns"] = self._stats.get("quota_cooldowns", 0) + 1
                    skipped_by_quota += 1
                response.raise_for_status()
                self._window_counts[target_url] = self._window_counts.get(target_url, 0) + 1
                if self._soft_cap_limit > 0 and self._window_counts[target_url] >= self._soft_cap_limit:
                    if target_url not in self._softcap_accounts:
                        self._softcap_accounts[target_url] = reset_iso
                if idx != self._active_pool_idx:
                    self._active_pool_idx = idx
                return response.json()
            except Exception as exc:
                last_err = exc
                logger.warning(f"Upstash Redis REST instance {idx} failed ({exc}); failing over...")

        if skipped_by_quota >= len(endpoints):
            raise QuotaExhaustedError(
                "All configured Upstash Redis REST accounts have reached their quota or soft-cap"
            )
        if last_err:
            raise last_err
        return {}

    # বাংলা মন্তব্য: SET NX EX মেকানিজম ইমপ্লিমেন্ট করা হলো যা শুধুমাত্র কী না থাকলে লক সেট করবে
    def set_nx(self, key: str, value: str, ex: int | None = None) -> bool:
        if not self.configured:
            return False
        try:
            command: list[Any] = ["SET", key, value, "NX"]
            if ex:
                command.extend(["EX", str(ex)])
            response = self._request(*command)
            # Upstash REST-এর ক্ষেত্রে সেট সফল হলে {"result": "OK"} অন্যথায় {"result": null} আসে
            return response.get("result") == "OK"
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis SET NX failed: {exc}")
            return False

    # বাংলা মন্তব্য: Lua Script এক্সিকিউট করার জন্য EVAL কমান্ড সাপোর্ট যুক্ত করা হলো
    def eval(self, script: str, numkeys: int, *args: str) -> Any:
        if not self.configured:
            return None
        try:
            command: list[Any] = ["EVAL", script, str(numkeys)]
            command.extend(args)
            response = self._request(*command)
            return response.get("result")
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis EVAL failed: {exc}")
            return None

    def get(self, key: str) -> str | None:
        if not self.configured:
            return None
        try:
            return self._request("GET", key).get("result")
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis GET failed: {exc}")
            return None

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        if not self.configured:
            return False
        try:
            command: list[Any] = ["SET", key, value]
            if ex:
                command.extend(["EX", ex])
            self._request(*command)
            return True
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis SET failed: {exc}")
            return False

    def incr(self, key: str) -> int | None:
        if not self.configured:
            return None
        try:
            result = self._request("INCR", key).get("result")
            return int(result) if result is not None else None
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            RuntimeError,
            ValueError,
        ) as exc:
            logger.error(f"Upstash Redis INCR failed: {exc}")
            return None

    def decr(self, key: str) -> int | None:
        if not self.configured:
            return None
        try:
            result = self._request("DECR", key).get("result")
            return int(result) if result is not None else None
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            RuntimeError,
            ValueError,
        ) as exc:
            logger.error(f"Upstash Redis DECR failed: {exc}")
            return None

    def expire(self, key: str, ttl: int) -> bool:
        if not self.configured:
            return False
        try:
            self._request("EXPIRE", key, str(ttl))
            return True
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis EXPIRE failed: {exc}")
            return False

    def publish(self, channel: str, message: str) -> bool:
        if not self.configured:
            return False
        try:
            self._request("PUBLISH", channel, message)
            return True
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis PUBLISH failed: {exc}")
            return False

    def lpush(self, key: str, value: str) -> int | None:
        if not self.configured:
            return None
        try:
            result = self._request("LPUSH", key, value).get("result")
            return int(result) if result is not None else None
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            RuntimeError,
            ValueError,
        ) as exc:
            logger.error(f"Upstash Redis LPUSH failed: {exc}")
            return None

    def rpop(self, key: str) -> str | None:
        if not self.configured:
            return None
        try:
            return self._request("RPOP", key).get("result")
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis RPOP failed: {exc}")
            return None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
