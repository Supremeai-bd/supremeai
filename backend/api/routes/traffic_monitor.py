import json
import time
from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import get_current_admin
from core.cache.redis_manager import redis_manager
from core.logging_config import logger

# ── Upstash daily-quota fix (#fleet-redis-quota) ─────────────────────────────
# বাংলা: পুরনো read-path প্রতি dashboard poll-এ ৩০টি আলাদা LRANGE পাঠাত —
# 5s polling এ দিনে ~518,000 Redis command পুড়ে যেত (5-account federation
# পুরোটাই নিঃশেষ হওয়ার মূল কারণ — traffic:live:* keys সেকেন্ডারি account-এ
# জমে থাকার SCAN evidence)। এখন একই ডেটা একটিমাত্র EVAL দিয়ে পড়া হয়:
# 30 commands → 1 command per poll (~98% read-side reduction)। Upstash-এ
# EVAL একটি মাত্র command হিসেবে গোনা হয়। EVAL ব্যর্থ হলে (যেমন FakeRedis
# ছাড়া টেস্ট ক্লায়েন্ট, বা script unsupported) পুরনো per-key fallback চলে —
# fail-honest, রেসপন্স শেপ অপরিবর্তিত।
_WINDOW_READ_SCRIPT = """
-- Args: 30 per-minute list keys. Returns one array of raw item arrays.
local out = {}
for i = 1, #KEYS do
  out[i] = redis.call('LRANGE', KEYS[i], 0, 999)
end
return out
"""

router = APIRouter(
    prefix="/api/admin/traffic",
    tags=["Traffic Control"],
    dependencies=[Depends(get_current_admin)],
)


def _decode_window_rows(result: Any) -> list[list[str]] | None:
    """Normalize an EVAL window result into rows of str (None = unusable).

    বাংলা: FakeRedis/redis-py কখনো bytes কখনো str দেয় — উভয়ই সামলাই;
    শেপ ভাঙলে None ফেরত দিই যাতে caller per-key fallback-এ নামে।
    """
    if not isinstance(result, list) or len(result) == 0:
        return None
    rows: list[list[str]] = []
    for row in result:
        if not isinstance(row, (list, tuple)):
            return None
        decoded: list[str] = []
        for item in row:
            if isinstance(item, bytes):
                decoded.append(item.decode("utf-8", "replace"))
            elif isinstance(item, str):
                decoded.append(item)
            else:
                return None
        rows.append(decoded)
    return rows


@router.get("/live")
async def get_live_traffic(admin: dict = Depends(get_current_admin)) -> dict[str, Any]:
    """বাংলা মন্তব্য: রিয়েল-টাইম ট্রাফিক, p95 ল্যাটেন্সি এবং অ্যারর রেট।
    এটি স্টুডিও ক্লায়েন্ট বা ফ্লাটার ড্যাশবোর্ডে লাইভ স্ট্রিমিং এর জন্য ব্যবহার হবে।

    রেস্পন্স শেপ: TrafficData = { current_rps, window_30min, distribution }
    (frontend flat shape অনুযায়ী — wrapper নয়)।"""

    # বাংলা মন্তব্য: রেডিস মিসকনফিগ (যেমন 'mock_redis_url') বা কানেকশন এররে
    # ৫০০ না দিয়ে শূন্য মেট্রিক্স রিটার্ন করি — ট্যাব crash না করে "NO DATA" দেখায়।
    def _empty() -> dict[str, Any]:
        return {
            "current_rps": 0.0,
            "window_30min": [0] * 30,
            "distribution": {},
        }

    if not redis_manager.client:
        logger.warning("traffic/live: redis not connected — returning empty metrics")
        return _empty()

    now = int(time.time())
    current_minute = now // 60
    # Fetch data for the last 30 minutes to build a rolling window
    keys_to_fetch = [f"traffic:live:{current_minute - i}" for i in range(30)]

    window_30min = [0] * 30
    total_requests = 0
    errors = 0
    durations = []

    try:
        # Quota fix: ONE EVAL fetches all 30 minute-windows in a single
        # command (was: 30 sequential LRANGE per poll → ~518k commands/day
        # at 5s dashboard polling). Fallback below keeps the old path only
        # when EVAL itself is unavailable.
        raw_rows: list[list[str]] | None = None
        try:
            eval_result = await redis_manager.client.eval(
                _WINDOW_READ_SCRIPT, len(keys_to_fetch), *keys_to_fetch
            )
            raw_rows = _decode_window_rows(eval_result)
        except Exception as eval_err:  # noqa: BLE001 — fail-honest fallback
            logger.warning(
                f"traffic/live: single-command window read unavailable "
                f"({eval_err}) — falling back to per-key reads"
            )
        if raw_rows is None:
            raw_rows = []
            for key in keys_to_fetch:
                try:
                    raw = await redis_manager.client.lrange(key, 0, 999)
                except Exception:  # noqa: BLE001 — missing key / transient
                    raw = []
                raw_rows.append(list(raw) if raw else [])

        for offset, raw_data in enumerate(raw_rows):
            minute_count = 0
            for item_str in raw_data:
                try:
                    item = json.loads(item_str)
                    total_requests += 1
                    minute_count += 1
                    if item.get("status", 200) >= 400 or item.get("error"):
                        errors += 1
                    durations.append(item.get("duration", 0.0))
                except json.JSONDecodeError:
                    continue
            window_30min[29 - offset] = minute_count

        error_rate = (errors / total_requests) * 100 if total_requests > 0 else 0.0

        p95_latency = 0.0
        if durations:
            durations.sort()
            p95_idx = int(len(durations) * 0.95)
            p95_latency = durations[p95_idx] * 1000  # convert to ms

        # requests in the most recent minute → current rps (approx)
        current_rps = round(window_30min[-1] / 60.0, 2) if window_30min[-1] else 0.0

        return {
            "current_rps": current_rps,
            "window_30min": window_30min,
            "distribution": {},
            "error_rate_percent": round(error_rate, 2),
            "p95_latency_ms": round(p95_latency, 2),
        }
    except Exception as e:
        logger.warning(f"traffic/live degraded (redis unavailable): {e}")
        return _empty()
