from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx

from core.config import settings
from core.logging_config import logger

# ── কোটা-উইন্ডো সনাক্তকরণ (#26 / #2613 — R2/R3) ───────────────────────────
# বাংলা মন্তব্য: Upstash free tier-এ কোটা শেষ হলে REST API HTTP 400 + সুনির্দিষ্ট
# এই মার্কার-সহ body দেয়। এই মার্কার দেখলেই ওই account-কে পরবর্তী উইন্ডোর রিসেট
# পর্যন্ত cooldown-এ ফেলা হয় — ফলে প্রতি command-এ exhausted account-এ একটি
# নিশ্চিত-ব্যর্থ request যাওয়া বন্ধ হয় এবং পরের মুহূর্তেই secondary-তে read-shift
# হয়ে যায় (issue #2452-র free-tier permanent solution)।
#
# ⚠️ #26 সংশোধন: Upstash free-tier-এর `ERR max requests limit exceeded`
# ("Limit: 500000") একটি **মাসিক** ক্যাপ — দৈনিক নয়। প্রমাণ (2026-10-13):
# 2026-10-07-এ usage=500002 রিপোর্টের ৬ দিন পরেও (2026-10-13) হুবহু 500002 —
# দৈনিক উইন্ডো হলে মধ্যরাতে রিসেট হয়ে গণনা বদলাত।
# https://upstash.com/docs/redis/troubleshooting/max_requests_limit
# ("exceeds the max monthly request count limit")। তাই ডিফল্ট উইন্ডো এখন
# `monthly` (মাসের ১ তারিখ 00:00 UTC রিসেট); পুরনো দৈনিক-ধর্মাযজ behavior
# UPSTASH_QUOTA_WINDOW=daily দিয়ে ফেরানো যায় (legacy opt-out)।
_QUOTA_EXCEEDED_MARKER = "max requests limit"

# ডিফল্ট মাসিক সফট-ক্যাপ — মুক্ত-স্তরের 500k মাসিক হার্ড-লিমিটের ৮০%।
_DEFAULT_QUOTA_SOFT_CAP = 400_000


def _quota_window() -> str:
    """সক্রিয় কোটা-উইন্ডো — "monthly" (ডিফল্ট) বা "daily" (legacy opt-out)।"""
    raw = (os.getenv("UPSTASH_QUOTA_WINDOW", "monthly") or "").strip().lower()
    if raw in ("daily", "day", "utc-day"):
        return "daily"
    return "monthly"


class QuotaExhaustedError(RuntimeError):
    """চেইনের সব Upstash account-ই কোটা cooldown-এ আছে (R3)।

    RuntimeError-এর subclass হওয়া ইচ্ছাকৃত — বিদ্যমান callers ইতিমধ্যে
    ``(httpx.RequestError, httpx.HTTPStatusError, RuntimeError)`` ধরে থাকে,
    তাই API signature/behavior অপরিবর্তিত থাকে (graceful degradation)।
    #26: cooldown মাসিক (ডিফল্ট) উইন্ডোতে — Upstash 500k মাসিক ক্যাপ।
    """


def _next_utc_reset_epoch() -> float:
    """পরবর্তী UTC মধ্যরাত + ৬০s grace — দৈনিক উইন্ডোর রিসেট সময় (legacy)।"""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.timestamp() + 60.0


def _next_quota_reset_epoch() -> float:
    """সক্রিয় উইন্ডোর রিসেট সময় — monthly (ডিফল্ট): মাসের ১ তারিখ 00:00 UTC + 60s।

    #26: Upstash-এর 500k লিমিট মাসিক, তাই cooldown মাসের শেষে শেষ হয়ে ওঠে;
    দৈনিক রিসেট-ধরে নেওয়া মানে exhausted account-টিকে প্রতি মধ্যরাতে আবার
    নিশ্চিত-ব্যর্থ HTTP 400-এ পাঠাত (পুরনো বাগ)। daily উইন্ডোতে `_next_utc_reset_epoch`
    ফেরত দেয় (backwards compatibility)।
    """
    if _quota_window() == "daily":
        return _next_utc_reset_epoch()
    now = datetime.now(UTC)
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    next_month = datetime(year, month, 1, tzinfo=UTC)
    return next_month.timestamp() + 60.0


class _LocalTTLCache:
    """Bounded LRU + TTL লোকাল ক্যাশ (#2613 — R1 command-reduction)।

    বাংলা মন্তব্য: read-heavy caller (parallel_cloud_router ইত্যাদি) একই key
    বারবার GET করে — প্রতিটি GET একটি Upstash command খরচ করে। এই ক্যাশ ছোট
    TTL-এ (default 10s) repeated read স্থানীয়ভাবে শোষণ করে; দৈনিক command
    বাজেটে উল্লেখযোগ্য সাশ্রয় হয়। Thread-safe (নিজস্ব lock)।
    """

    _MISS = object()  # sentinel — None আসল value হতে পারে (negative cache)

    def __init__(self, max_entries: int = 512) -> None:
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max(1, max_entries)

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return self._MISS
            expires_at, value = entry
            if time.time() >= expires_at:
                del self._data[key]
                return self._MISS
            self._data.move_to_end(key)
            return value

    def put(self, key: str, value: Any, ttl: float) -> None:
        if ttl <= 0:
            return
        with self._lock:
            self._data[key] = (time.time() + ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max_entries:
                self._data.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


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
        # ── #2613: quota-aware cooldown + local read cache + command stats ──
        # বাংলা মন্তব্য: cooldown registry key হলো account-এর REST URL —
        # pool-এর order/index যেকোনো সময় বদলালেও সঠিক থাকে।
        self._cooldown_until: dict[str, float] = {}
        self._cooldown_lock = threading.Lock()
        self._stats: dict[str, int] = {
            "commands_sent": 0,
            "cache_hits": 0,
            "quota_cooldowns": 0,
            "quota_refusals": 0,
            "softcap_shifts": 0,
            "failovers": 0,
        }
        # ── #26: সক্রিয় কোটা-উইন্ডো (monthly ডিফল্ট — Upstash 500k মাসিক ক্যাপ) ──
        self._quota_window = _quota_window()
        # ── #2710 (R2.5): প্রতি-উইন্ডোর সক্রিয় soft-cap বাজেট ──
        # বাংলা মন্তব্য: R2-এর cooldown প্রতিক্রিয়াশীল — HTTP 400 আসার পরেই কাজ করে,
        # ফলে primary প্রতিদিন ১০০% পর্যন্ত ভরে যেত। এখানে প্রতি account-এর
        # উইন্ডোর command গণনা রাখা হয়; soft-cap (ডিফল্ট 400k = 500k-এর ৮০%)
        # ছুঁলে সেই account-কে রিসেট পর্যন্ত সক্রিয়ভাবে skip করা হয় —
        # ফলে কোনো account কখনোই 500k স্পর্শ করে না এবং HTTP 400-নয়েজ বন্ধ হয়।
        # #26 সংশোধন: soft-cap এখন মাসিক ক্যাপের বিপূর্ণে গণনা করে (দৈনিক নয়);
        # UPSTASH_QUOTA_SOFT_CAP অগ্রাধীন, পুরনো UPSTASH_DAILY_SOFT_CAP fallback।
        try:
            self._soft_cap_limit = max(
                0,
                int(
                    os.getenv("UPSTASH_QUOTA_SOFT_CAP")
                    or os.getenv("UPSTASH_DAILY_SOFT_CAP")
                    or _DEFAULT_QUOTA_SOFT_CAP
                ),
            )
        except ValueError:
            self._soft_cap_limit = _DEFAULT_QUOTA_SOFT_CAP
        self._window_counts: dict[str, int] = {}
        self._softcap_until: dict[str, float] = {}
        self._day_bucket_until: float = _next_quota_reset_epoch()
        try:
            self._read_cache_ttl = max(0.0, float(os.getenv("UPSTASH_READ_CACHE_TTL", "10")))
            self._negative_cache_ttl = max(0.0, float(os.getenv("UPSTASH_NEGATIVE_CACHE_TTL", "3")))
            cache_size = max(1, int(os.getenv("UPSTASH_READ_CACHE_SIZE", "512")))
        except ValueError:
            self._read_cache_ttl, self._negative_cache_ttl, cache_size = 10.0, 3.0, 512
        self._read_cache = _LocalTTLCache(max_entries=cache_size)

    @property
    def configured(self) -> bool:
        return bool(self._client)

    # ── #2613: cooldown helpers ──────────────────────────────────────────────
    def _mark_quota_cooldown(self, url: str) -> float:
        """ওই account-কে পরবর্তী উইন্ডো-রিসেট পর্যন্ত cooldown-এ ফেলে (R2)।

        #26: reset সময় সক্রিয় উইন্ডো অনুযায়ী — monthly হলে মাসের ১ তারিখ,
        daily হলে UTC মধ্যরাত।
        """
        until = _next_quota_reset_epoch()
        with self._cooldown_lock:
            self._cooldown_until[url] = until
            self._stats["quota_cooldowns"] += 1
        logger.warning(
            f"Upstash REST [{url}] কোটা শেষ ({self._quota_window} window) — রিসেট "
            f"({datetime.fromtimestamp(until, UTC).isoformat()}) পর্যন্ত cooldown, "
            f"চেইনের পরের account-এ shift করা হলো।"
        )
        return until

    def _in_cooldown(self, url: str) -> bool:
        with self._cooldown_lock:
            until = self._cooldown_until.get(url, 0.0)
            return time.time() < until

    # ── #2710 (R2.5): উইন্ডো soft-cap helpers ────────────────────────────────
    def _rollover_day_bucket_locked(self, now: float) -> None:
        """বাংলা মন্তব্য: উইন্ডো বদলালে গণনা শূন্য করা হয় — lock ধরা অবস্থায় ডাকতে হয়।

        #26: daily-এ (legacy) UTC দিন, monthly-এ মাস — _next_quota_reset_epoch()
        সক্রিয় উইন্ডো অনুসারে।
        """
        if now >= self._day_bucket_until:
            self._window_counts.clear()
            self._softcap_until.clear()
            self._day_bucket_until = _next_quota_reset_epoch()

    def _soft_capped(self, url: str) -> bool:
        # বাংলা মন্তব্য: soft-cap সক্রিয় হলে ওই account-এ আর একটিও command না গিয়ে
        # চেইনের পরের account ব্যবহৃত হয় — 500k-স্পর্শ নিশ্চিতভাবে অসম্ভব।
        with self._cooldown_lock:
            self._rollover_day_bucket_locked(time.time())
            until = self._softcap_until.get(url, 0.0)
            return time.time() < until

    def _bump_window(self, url: str) -> None:
        """সফল command-এর পরে উইন্ডো গণনা বাড়াই; soft-cap ছুঁলে সক্রিয় skip।"""
        with self._cooldown_lock:
            now = time.time()
            self._rollover_day_bucket_locked(now)
            self._window_counts[url] = self._window_counts.get(url, 0) + 1
            if (
                self._soft_cap_limit > 0
                and url not in self._softcap_until
                and self._window_counts[url] >= self._soft_cap_limit
            ):
                self._softcap_until[url] = self._day_bucket_until
                self._stats["softcap_shifts"] += 1
                logger.warning(
                    f"Upstash REST [{url}] {self._quota_window} soft-cap "
                    f"({self._soft_cap_limit}) ছুঁয়েছে — রিসেট পর্যন্ত সক্রিয়ভাবে skip "
                    f"(#2710 R2.5 · #26 window-fix); চেইনের পরের account দায়িত্ব নেবে।"
                )

    def quota_status(self) -> dict[str, Any]:
        """কোন account কতক্ষণ cooldown-এ — পর্যবেক্ষণযোগ্য প্রমাণ (invariant #5)।"""
        with self._cooldown_lock:
            now = time.time()
            return {
                "cooldown_accounts": {
                    url: datetime.fromtimestamp(until, UTC).isoformat()
                    for url, until in self._cooldown_until.items()
                    if now < until
                },
                # বাংলা মন্তব্য (#2710 R2.5): প্রতি-account উইন্ডো বাজেট-দৃশ্যমালা —
                # কোন consumer বেশি খাচ্ছে তা অডিটে শনাক্ত করা সহজ হয়।
                # #26: উইন্ডো monthly (ডিফল্ট) — Upstash 500k মাসিক ক্যাপ।
                "window": self._quota_window,
                "window_counts": dict(self._window_counts),
                "window_soft_cap": self._soft_cap_limit,
                "daily_counts": dict(self._window_counts),  # legacy alias (observability compat)
                "daily_soft_cap": self._soft_cap_limit,  # legacy alias
                "softcap_accounts": {
                    url: datetime.fromtimestamp(until, UTC).isoformat()
                    for url, until in self._softcap_until.items()
                    if now < until
                },
                "stats": dict(self._stats),
                "read_cache_ttl_s": self._read_cache_ttl,
            }

    def _request(self, *args: str) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError(
                "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are not configured"
            )

        # Issue #754 (MA-04): multi-account federation failover across all 5 Upstash instances
        pool = getattr(settings, "upstash_redis_rest_pool", [])
        endpoints = (
            pool
            if pool
            else ([(self.rest_url, self.token)] if (self.rest_url and self.token) else [])
        )
        if not endpoints:
            raise RuntimeError("No configured Upstash Redis REST endpoints available")

        # বাংলা মন্তব্য (#2613 R2 + #2710 R2.5): কোটা-exhausted বা soft-capped
        # account-গুলো আগেই বাদ দিই — একটিও wasted request যাবে না; বাকিদের
        # মধ্যে sticky-start (শেষ সফল account থেকে শুরু) থেকে failover চালাই।
        active: list[tuple[int, str, str]] = [
            (i, url, token)
            for i, (url, token) in enumerate(endpoints)
            if not (self._in_cooldown(url) or self._soft_capped(url))
        ]
        if not active:
            # R3: সব account কোটা cooldown/soft-cap-এ — সৎ, স্পষ্ট ত্রুটি (মিথ্যা "Redis down" নয়)।
            with self._cooldown_lock:
                self._stats["quota_refusals"] += 1
            raise QuotaExhaustedError(
                f"all Upstash REST accounts are in quota cooldown or soft-cap "
                f"({self._quota_window} window) until the next window reset "
                f"(free-tier federation fully consumed)"
            )

        last_err: Exception | None = None
        for offset, (idx, target_url, target_token) in enumerate(active):
            try:
                response = self._client.post(
                    target_url,
                    headers={"Authorization": f"Bearer {target_token}"},
                    json=list(args),
                )
                # বাংলা মন্তব্য (#2613 R2): HTTP 400-ও Upstash কোটা-ত্রুটি হতে পারে —
                # raise_for_status-এর আগেই body পরীক্ষা করে সঠিক কারণ আলাদা করি।
                if response.status_code == 400 and _QUOTA_EXCEEDED_MARKER in response.text:
                    self._mark_quota_cooldown(target_url)
                    last_err = QuotaExhaustedError(
                        f"upstash[{target_url}] quota exceeded ({self._quota_window} window) — "
                        f"cooldown until window reset"
                    )
                    continue
                response.raise_for_status()
                if idx != self._active_pool_idx:
                    self._active_pool_idx = idx
                    with self._cooldown_lock:
                        self._stats["failovers"] += 1
                with self._cooldown_lock:
                    self._stats["commands_sent"] += 1
                self._bump_window(target_url)  # #2710 (R2.5) · #26: উইন্ডো বাজেট ট্র্যাকিং
                return response.json()
            except QuotaExhaustedError:
                continue  # উপরে ইতিমধ্যে cooldown চিহ্নিত — পরের account
            except Exception as exc:
                last_err = exc
                logger.warning(f"Upstash Redis REST instance {idx} failed ({exc}); failing over...")

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
            # Upstash REST-এর ক্ষেত্রে সেট সফল হলে {"result": "OK"} অন্যথায় {"result": null} আসে
            ok = response.get("result") == "OK"
            if ok:
                self._read_cache.invalidate(key)
            return ok
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
            # বাংলা মন্তব্য: EVAL যেসব key ছুঁয়ে যেতে পারে তার লোকাল ক্যাশ-কপি
            # অবিশ্বস্ত হয়ে যায় — সব string-arg invalidate করে দিই (সস্তা ও নিরাপদ)।
            for maybe_key in args:
                if isinstance(maybe_key, str):
                    self._read_cache.invalidate(maybe_key)
            return response.get("result")
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis EVAL failed: {exc}")
            return None

    def get(self, key: str, ttl: float | None = None) -> str | None:
        """GET — local TTL ক্যাশ সহ (#2613 R1)।

        Args:
            key: যে key পড়তে হবে।
            ttl: এই read-এর জন্য লোকাল ক্যাশের TTL (সেকেন্ড)। None হলে
                 ক্লাস-ডিফল্ট (UPSTASH_READ_CACHE_TTL, default 10s)। 0 দিলে
                 ক্যাশ বাইপাস হয়ে সরাসরি REST-এ যাবে।
        """
        if not self.configured:
            return None
        # R1: লোকাল ক্যাশে থাকলে একটিও REST command খরচ হয় না।
        if ttl is None or ttl > 0:
            cached = self._read_cache.get(key)
            if cached is not _LocalTTLCache._MISS:
                with self._cooldown_lock:
                    self._stats["cache_hits"] += 1
                return cached
        try:
            result = self._request("GET", key).get("result")
            # বাংলা মন্তব্য: negative result (None) সংক্ষিপ্ত TTL-এ ক্যাশ করি —
            # একই missing-key বারবার REST-এ গিয়ে কোটা পোড়ানো ঠেকাতে।
            cache_ttl = (
                self._negative_cache_ttl
                if result is None
                else (self._read_cache_ttl if ttl is None else ttl)
            )
            self._read_cache.put(key, result, cache_ttl)
            return result
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
            # বাংলা মন্তব্য: write-এর পর লোকাল ক্যাশের সেই key-কপি বাতিল — stale read ঠেকাই।
            self._read_cache.invalidate(key)
            return True
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            logger.error(f"Upstash Redis SET failed: {exc}")
            return False

    def incr(self, key: str) -> int | None:
        if not self.configured:
            return None
        try:
            result = self._request("INCR", key).get("result")
            self._read_cache.invalidate(key)
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
            self._read_cache.invalidate(key)
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
            self._read_cache.invalidate(key)
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
        self._read_cache.clear()
