"""Daily zero-burn health sweep for user-contributed API keys.

Runs under .github/workflows/ops-maintenance.yml (0 3 * * * UTC). For every
contributed key we send a non-billing metadata ping (/v1/models or /models),
flip status to 'valid'/'invalid', and recompute the per-user roll-up cache
in user_bonus_quotas (Kilo = 150000 tokens/day, others = 100000, cap 10 keys).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
import sys
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    httpx = None

import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# বাংলা মন্তব্য: ক্যানোনিকাল core.database.supabase_client থেকে get_db ইমপোর্ট — ফেইল-সেফ ফলব্যাকসহ
try:
    from core.database.supabase_client import get_db
    _db_import_error = None
except Exception as exc:  # বাংলা মন্তব্য: error-এর কেবল ধরন; secret বা URL লগ নয়।
    get_db = None
    _db_import_error = type(exc).__name__

BONUS_WEIGHTS = {
    "kilo": 150000,
}
DEFAULT_BONUS = 100000
MAX_ACTIVE_KEYS = 10
MAX_SUBMISSIONS_PER_DAY = 5


def _status_result(status: int | None) -> bool | None:
    # বাংলা মন্তব্য: শুধু স্পষ্ট authentication failure invalid; rate limit/outage অজানা।
    if status == 200:
        return True
    if status in (401, 403):
        return False
    return None


async def _ping(provider: str, api_key: str) -> bool | None:
    p = provider.lower().strip()
    urls = {
        "gemini": f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        "groq": "https://api.groq.com/openai/v1/models",
        "openrouter": "https://openrouter.ai/api/v1/auth/key",
        "cerebras": "https://api.cerebras.ai/v1/models",
        "sambanova": "https://api.sambanova.ai/v1/models",
        "mistral": "https://api.mistral.ai/v1/models",
        "cohere": "https://api.cohere.com/v1/models",
        "github": "https://models.github.ai/catalog/models",
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    if p == "gemini":
        headers = {}
    # বাংলা মন্তব্য: মেটাডেটা পিং দিয়ে ভ্যালিডেশন — কঠোরভাবে 200 OK রিকোয়ার্ড (Fail-Closed)
    url = urls.get(p)
    if not url:
        # বাংলা মন্তব্য: অচেনা provider-এর জন্য অনুমান নয়, পূর্বের status অক্ষত।
        return None
    try:
        if httpx is not None:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                return _status_result(resp.status_code)
        # বাংলা মন্তব্য: httpx ইনস্টল না থাকলে স্ট্যান্ডার্ড লাইব্রেরি urllib দিয়ে কলব্যাক
        def _urllib_ping() -> bool | None:
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    return _status_result(getattr(resp, "status", None) or getattr(resp, "code", None))
            except urllib.error.HTTPError as he:
                return _status_result(he.code)
            except (urllib.error.URLError, OSError):
                return None

        return await asyncio.to_thread(_urllib_ping)
    except Exception as exc:
        # বাংলা মন্তব্য: request exception-এ URL/credential থাকতে পারে, তাই শুধু ধরন দেখাই।
        print(f"probe warning for {p} ({type(exc).__name__})", file=sys.stderr)
        return None


async def sweep() -> bool:
    if get_db is None:
        print(f"supabase client unavailable ({_db_import_error or 'import failed'}); aborting", file=sys.stderr)
        return False
    try:
        db = get_db()
    except Exception as exc:
        print(f"supabase initialization failed ({type(exc).__name__}); aborting", file=sys.stderr)
        return False
    if not db or not db.client:
        print("supabase client unavailable (check URL and service-role configuration); aborting", file=sys.stderr)
        return False
    now = datetime.now(timezone.utc).isoformat()
    success = True

    try:
        rows = (await asyncio.to_thread(
            lambda: db.client.table("user_contributed_api_keys").select("*").execute()
        )).data or []
    except Exception as exc:
        print(f"fetch failed ({type(exc).__name__})", file=sys.stderr)
        return False

    by_user: dict[str, list[dict]] = {}
    for row in rows:
        by_user.setdefault(row["user_id"], []).append(row)

    for row in rows:
        provider = row["provider"]
        raw = ""
        try:
            from core.security.secure_credential_store import RotatingFernet
            enc = os.getenv("ENCRYPTION_KEYS") or os.getenv("SUPREMEAI_CREDENTIAL_ENC_KEY") or os.getenv("ENCRYPTION_KEY") or ""
            keys = [key.strip() for key in enc.split(",") if key.strip()]
            if keys:
                rf = RotatingFernet(keys)
                # বাংলা মন্তব্য: দীর্ঘমেয়াদি API key-তে সেশন token-এর ২৪ ঘণ্টার TTL নয়।
                raw = rf.decrypt(row.get("encrypted_key", "").encode(), ttl=None).decode()
        except Exception as exc:
            print(f"decrypt failed ({type(exc).__name__})", file=sys.stderr)
            raw = ""
        if not raw:
            # cannot decrypt -> skip (do not falsely invalidate)
            print(f"skip (no decrypt) {row['id']}")
            success = False
            continue
        is_valid = await _ping(provider, raw)
        if is_valid is None:
            print(f"probe inconclusive for {provider}; status unchanged", file=sys.stderr)
            success = False
            continue
        new_status = "valid" if is_valid else "invalid"
        # বাংলা মন্তব্য: প্রোভাইডার রেট-লিমিট ও WAF এড়াতে জিটার ডিলে
        await asyncio.sleep(random.uniform(0.2, 0.4))
        try:
            await asyncio.to_thread(
                lambda ns=new_status, rid=row["id"]: (
                    db.client.table("user_contributed_api_keys")
                    .update({"status": ns, "last_verified_at": now})
                    .eq("id", rid)
                    .execute()
                )
            )
        except Exception as exc:
            print(f"update failed for {row['id']} ({type(exc).__name__})", file=sys.stderr)
            success = False

    # Recompute roll-up cache per user
    for user_id, user_rows in by_user.items():
        valid_count = 0
        bonus = 0
        # Re-fetch fresh statuses
        try:
            fresh = (await asyncio.to_thread(
                lambda uid=user_id: (
                    db.client.table("user_contributed_api_keys")
                    .select("provider,status")
                    .eq("user_id", uid)
                    .execute()
                )
            )).data or []
        except Exception as exc:
            # বাংলা মন্তব্য: DB read ব্যর্থ হলে quota শূন্য দিয়ে overwrite নয়।
            print(f"quota refresh failed for {user_id} ({type(exc).__name__})", file=sys.stderr)
            success = False
            continue
        for r in fresh:
            if r.get("status") != "valid":
                continue
            if valid_count >= MAX_ACTIVE_KEYS:
                break
            valid_count += 1
            bonus += BONUS_WEIGHTS.get(r["provider"], DEFAULT_BONUS)
        try:
            await asyncio.to_thread(
                lambda uid=user_id, vc=valid_count, bt=bonus: (
                    db.client.table("user_bonus_quotas")
                    .upsert({"user_id": uid, "valid_keys_count": vc, "daily_bonus_tokens": bt, "updated_at": now}, on_conflict="user_id")
                    .execute()
                )
            )
        except Exception as exc:
            print(f"quota upsert failed for {user_id} ({type(exc).__name__})", file=sys.stderr)
            success = False

    print(f"sweep {'complete' if success else 'incomplete'}: {len(rows)} keys, {len(by_user)} users")
    return success


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(sweep()) else 1)
