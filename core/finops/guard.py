"""FinOps guard — real per-user / global chat limits (admin Step 4).

বাংলা মন্তব্য: আগে `TokenBudgetManager.check_user_budget()` ছিল কিন্তু কেউ ডাকত না, আর
cost-caps একটা JSON ফাইলে (Render-এর ক্ষণস্থায়ী ডিস্ক) — কিছুই বলবৎ হতো না। এখন:

* সেটিংস: Supabase `public.finops_settings` (id=1) — অ্যাডমিন UI edge → core দিয়ে লেখে,
  core ৬০ সেকেন্ড ক্যাশ করে। টেবিল/নেটওয়ার্ক না পেলে নিরাপদ ডিফল্ট।
* বলবৎ: প্রতিটি চ্যাট স্ট্রিমের আগে `check()` —
  ১) ইউজার/মিনিট রিকোয়েস্ট (AsyncRateLimiter sliding window)
  ২) ইউজারের দৈনিক টোকেন (বিদ্যমান TokenBudgetManager)
  ৩) পুরো প্ল্যাটফর্মের দৈনিক টোকেন (0 = বন্ধ)
  অ্যাডমিন/সার্ভিস-টোকেন ছাড়।
* গণনা: স্ট্রিম শেষে `record()` — ইউজার কাউন্টার + গ্লোবাল কাউন্টার + আজকের টপ-ইউজার zset।
  টোকেন অনুমানভিত্তিক (estimate_tokens), তাই UI-তে "আনুমানিক" লেখা।
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from core.monitoring.logging_config import logger

SETTINGS_TABLE = "finops_settings"
CACHE_TTL_S = 60.0
DEFAULTS: dict[str, Any] = {
    "enforce": True,
    "user_daily_tokens": 200_000,
    "user_rpm": 20,
    "global_daily_tokens": 0,
}
LIMITS = {
    "user_daily_tokens": (0, 50_000_000),
    "user_rpm": (0, 10_000),
    "global_daily_tokens": (0, 5_000_000_000),
}
KEY_TTL_S = 2 * 86400

_cache: dict[str, Any] = {"at": 0.0, "value": dict(DEFAULTS), "source": "default"}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""
    retry_after: int = 0
    limit: int = 0


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _seconds_to_midnight_utc() -> int:
    now = time.time()
    return max(60, int(86400 - (now % 86400)))


def validate_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a clean settings dict or raise ValueError with a safe message."""
    out: dict[str, Any] = {}
    if "enforce" in payload:
        if not isinstance(payload["enforce"], bool):
            raise ValueError("enforce must be true/false")
        out["enforce"] = payload["enforce"]
    for key, (lo, hi) in LIMITS.items():
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(f"{key} must be an integer {lo}–{hi} (0 = off)")
        out[key] = value
    if not out:
        raise ValueError("no settings to update")
    return out


def _rest_config() -> tuple[str, str] | None:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    return (url, key) if url and key else None


def _merge(row: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULTS)
    for k in DEFAULTS:
        if row and row.get(k) is not None:
            merged[k] = row[k]
    if row:
        merged["updated_by"] = row.get("updated_by")
        merged["updated_at"] = row.get("updated_at")
    return merged


async def load_settings(force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    if not force and now - _cache["at"] < CACHE_TTL_S:
        return _cache["value"]
    cfg = _rest_config()
    if cfg:
        try:
            import httpx

            url, key = cfg
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(
                    f"{url}/rest/v1/{SETTINGS_TABLE}",
                    params={"id": "eq.1", "select": "*"},
                    headers={"apikey": key, "Authorization": f"Bearer {key}"},
                )
            if res.status_code == 200:
                rows = res.json()
                _cache.update(value=_merge(rows[0] if rows else None), source="supabase")
            else:
                logger.warning(f"[FinOps] settings read HTTP {res.status_code}; keeping last known")
        except Exception as exc:  # noqa: BLE001 — settings read must never break chat
            logger.warning(f"[FinOps] settings read failed ({type(exc).__name__}); keeping last known")
    _cache["at"] = now
    return _cache["value"]


async def save_settings(changes: dict[str, Any], updated_by: str) -> dict[str, Any]:
    cfg = _rest_config()
    if not cfg:
        raise RuntimeError("Supabase is not configured on core")
    import httpx

    url, key = cfg
    current = await load_settings(force=True)
    row = {k: current.get(k, DEFAULTS[k]) for k in DEFAULTS}
    row.update(changes)
    row.update(id=1, updated_by=updated_by[:200])
    async with httpx.AsyncClient(timeout=6.0) as client:
        res = await client.post(
            f"{url}/rest/v1/{SETTINGS_TABLE}",
            params={"on_conflict": "id"},
            json=row,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Supabase write failed (HTTP {res.status_code})")
    data = res.json()
    _cache.update(value=_merge(data[0] if data else row), source="supabase", at=time.monotonic())
    return _cache["value"]


async def _redis():
    try:
        from core.cache.redis_manager import redis_manager

        return await redis_manager.get_client_async()
    except Exception:  # noqa: BLE001
        return None


def _is_exempt(payload: dict[str, Any] | None) -> bool:
    role = str((payload or {}).get("role") or "").lower()
    return role in {"admin", "owner", "service"}


async def check(user_id: str, payload: dict[str, Any] | None = None) -> Decision:
    """Pre-flight gate for one chat request. Never raises."""
    try:
        settings = await load_settings()
        if not settings.get("enforce") or _is_exempt(payload) or not user_id:
            return Decision(True)
        rpm = int(settings.get("user_rpm") or 0)
        if rpm > 0:
            from core.middleware.rate_limiter import AsyncRateLimiter

            if not await AsyncRateLimiter().acquire(f"finops_rpm:{user_id}", limit=rpm, window=60):
                return Decision(False, "rate_limited", 60, rpm)
        daily = int(settings.get("user_daily_tokens") or 0)
        if daily > 0:
            from core.llm.token_budget import get_budget_manager

            if not await get_budget_manager().check_user_budget(user_id, daily_limit=daily):
                return Decision(False, "user_daily_tokens", _seconds_to_midnight_utc(), daily)
        global_cap = int(settings.get("global_daily_tokens") or 0)
        if global_cap > 0:
            client = await _redis()
            if client is not None:
                used = int(await client.get(f"finops_global:{_today()}") or 0)
                if used >= global_cap:
                    return Decision(False, "global_daily_tokens", _seconds_to_midnight_utc(), global_cap)
        return Decision(True)
    except Exception as exc:  # noqa: BLE001 — guard failure must not take chat down
        logger.warning(f"[FinOps] check failed open ({type(exc).__name__}: {exc})")
        return Decision(True)


async def record(user_id: str, tokens: int) -> None:
    """Post-flight usage accounting. Never raises."""
    if not user_id or tokens <= 0:
        return
    try:
        from core.llm.token_budget import get_budget_manager

        await get_budget_manager().record_user_usage(user_id, tokens)
        client = await _redis()
        if client is None:
            return
        today = _today()
        pipe = client.pipeline()
        pipe.incrby(f"finops_global:{today}", tokens)
        pipe.expire(f"finops_global:{today}", KEY_TTL_S)
        pipe.zincrby(f"finops_top:{today}", tokens, user_id)
        pipe.expire(f"finops_top:{today}", KEY_TTL_S)
        await pipe.execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[FinOps] record failed ({type(exc).__name__}: {exc})")


async def usage_snapshot(top: int = 10) -> dict[str, Any]:
    today = _today()
    client = await _redis()
    if client is None:
        return {"date": today, "available": False, "globalTokens": 0, "topUsers": []}
    used = int(await client.get(f"finops_global:{today}") or 0)
    rows = await client.zrevrange(f"finops_top:{today}", 0, max(0, top - 1), withscores=True)
    return {
        "date": today,
        "available": True,
        "globalTokens": used,
        "topUsers": [{"userId": str(uid), "tokens": int(score)} for uid, score in rows],
    }


def limit_message(decision: Decision) -> str:
    return {
        "rate_limited": "Too many messages per minute — please wait a moment.",
        "user_daily_tokens": "Today's usage limit is reached — it resets at midnight UTC.",
        "global_daily_tokens": "The platform's daily capacity is reached — it resets at midnight UTC.",
    }.get(decision.reason, "Usage limit reached.")
