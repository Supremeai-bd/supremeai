"""gateway/service/user_memory_engine.py — Smart Durable User Memory & Collective AI Briefing Engine.

বাংলা মন্তব্য:
১) ইউজারের চ্যাট বার্তা (বাংলা, বাংলিশ ও ইংরেজি) থেকে স্বয়ংক্রিয়ভাবে মূল পরিচয়, ভাষা, স্ট্যাক ও পছন্দ শনাক্ত করে (`ADD / UPDATE / FORGET`)।
২) কোনো API কী, টোকেন, `.onion` লিংক বা প্রম্পট-ইনজেকশন পেলোড যেন মেমোরিতে ঢুকতে না পারে তার জন্য কঠোর স্যানিটাইজার প্রয়োগ করে।
৩) লোকাল SQLite-এর পাশাপাশি ক্লাউড Supabase (`user_preferences` এবং UUID হলে `memories` টেবিল)-এ সিঙ্ক করে ও ৫ মিনিটের ইন-মেমরি ক্যাশ রাখে।
৪) গিটহাব পাইপলাইনে অন্য AI এজেন্টদের শেয়ার করা ভেরিফায়েড নলেজ (`knowledge_base`) প্রাসঙ্গিক টেকনিক্যাল প্রশ্নে সংক্ষেপে যুক্ত করে।
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("supremeai.user_memory_engine")

_CACHE_TTL_SECONDS = 300.0
_COLLECTIVE_TTL_SECONDS = 600.0
_MAX_FACT_VALUE_CHARS = 280
_MAX_DURABLE_KEYS_PER_USER = 32

_LOCK = threading.RLock()
_USER_CLOUD_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_COLLECTIVE_CACHE: tuple[float, list[dict[str, Any]]] | None = None

# বাংলা মন্তব্য: মেমোরি পয়জনিং, ক্রেডেনশিয়াল লিক ও `.onion` OAST ব্লক করার নিরাপত্তা প্যাটার্ন।
_FORBIDDEN_MEMORY_RE = re.compile(
    r"(?:"
    r"sk-[A-Za-z0-9_\-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sb_secret_[A-Za-z0-9_\-]{12,}"
    r"|eyJ[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{15,}"
    r"|AIza[0-9A-Za-z_\-]{25,}"
    r"|xox[baprs]-[A-Za-z0-9\-]{15,}"
    r"|\b(?:password|passwd|api_key|secret_key|access_token|private_key)\s*[:=]"
    r"|\.onion(?:/|:|\b)"
    r"|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions"
    r"|disregard\s+system\s+prompt"
    r"|<script\b"
    r")",
    re.IGNORECASE,
)

# বাংলা মন্তব্য: চ্যাট থেকে মূল কী-ইনফরমেশন ধরার বহুভাষিক (বাংলা + বাংলিশ + ইংরেজি) প্যাটার্ন।
_NAME_PATTERNS = (
    re.compile(r"\b(?:my name is|call me)\s+([A-Za-z][A-Za-z .'\-]{1,48})", re.IGNORECASE),
    re.compile(r"(?:আমার নাম|আমি হচ্ছি)\s+([^\n,.;!?।]{2,48})"),
    re.compile(r"\b(?:amar nam|ami hocchi)\s+([A-Za-z][A-Za-z .'\-]{1,48})", re.IGNORECASE),
)

_LANG_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:always\s+(?:explain|reply|answer|respond)\s+in\s+(?:bangla|bengali)"
            r"|সবসময়\s*বাংলায়|বাংলায়\s*(?:বলবে|উত্তর দেবে|বুঝিয়ে বলবে)"
            r"|all\s*time\s*bangla|sob\s*somoy\s*bangla|banglay\s*(?:bolo|uttor))",
            re.IGNORECASE,
        ),
        "bn (সর্বদা বাংলায় উত্তর ও ব্যাখ্যা দিতে হবে)",
    ),
    (
        re.compile(
            r"(?:always\s+(?:explain|reply|answer|respond)\s+in\s+english"
            r"|সবসময়\s*ইংরেজিতে|reply\s+only\s+in\s+english)",
            re.IGNORECASE,
        ),
        "en (Always respond in English)",
    ),
    (
        re.compile(
            r"(?:explain\s+in\s+banglish|বাংলিশে\s*(?:বলো|বলবে))",
            re.IGNORECASE,
        ),
        "banglish (রোমান হরফে বাংলা/বাংলিশ)",
    ),
)

_ROLE_PATTERNS = (
    re.compile(
        r"\b(?:i work as(?: an?| the)?|i am(?: an?)?|my role is)\s+"
        r"([A-Za-z0-9 /&+\-]{3,70}?(?:engineer|developer|architect|founder|researcher|designer|lead|manager|student|admin|devops))(?=[,.;!?\n]|$)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:আমি একজন|পেশায় আমি)\s+([^\n,.;!?।]{3,60})"),
)

_LOCATION_PATTERNS = (
    re.compile(r"\b(?:i live in|i am based in|i'm from)\s+([A-Za-z ,\-]{2,55})(?=[,.;!?\n]|$)", re.IGNORECASE),
    re.compile(r"(?:আমি)\s+([^\n,.;!?।]{2,40})\s*(?:তে থাকি|এ থাকি|থেকে বলছি)"),
)

_STACK_PATTERNS = (
    re.compile(
        r"\b(?:our (?:tech )?stack is|we use|my primary stack is|amader stack)\s*[:\-]?\s*([^\n.;!?]{4,140})",
        re.IGNORECASE,
    ),
    re.compile(r"(?:আমাদের স্ট্যাক|আমরা ব্যবহার করি)\s*[:\-]?\s*([^\n।!?]{4,140})"),
)

_STYLE_PATTERNS = (
    re.compile(
        r"\b(?:always keep (?:answers|responses)|i prefer responses to be|response style should be)\s+([^\n.;!?]{3,90})",
        re.IGNORECASE,
    ),
    re.compile(r"(?:উত্তর সবসময়|রেসপন্স সবসময়)\s+([^\n।!?]{3,90})\s*(?:রাখবে|দেবে)?"),
)

_EXPLICIT_REMEMBER_PATTERNS = (
    re.compile(
        r"(?:please\s+)?(?:remember\s+that|keep\s+in\s+mind\s+that|note\s+that|save\s+to\s+memory\s*:?)\s+([^\n!?]{4,220})",
        re.IGNORECASE,
    ),
    re.compile(r"(?:মনে রেখো|মনে রাখবে|নোট করে রাখো)\s*[:,\-]?\s*([^\n।!?]{4,220})"),
    re.compile(r"\b(?:mone rekho|mone rakhbe)\s*[:,\-]?\s*([^\n!?]{4,220})", re.IGNORECASE),
)

_FORGET_PATTERNS = (
    re.compile(
        r"\b(?:forget\s+(?:my|about|that)|delete\s+memory\s+(?:of|about))\s+([A-Za-z0-9_ \-]{2,60})",
        re.IGNORECASE,
    ),
    re.compile(r"(?:ভুলে যাও|মেমোরি থেকে মুছে ফেলো)\s*[:,\-]?\s*([^\n।!?]{2,60})"),
    re.compile(r"\b(?:vule jao|bhule jao)\s+([A-Za-z0-9_ \-]{2,60})", re.IGNORECASE),
)

_FORGET_ALIAS_MAP: dict[str, str] = {
    "name": "user_name",
    "নাম": "user_name",
    "nam": "user_name",
    "language": "preferred_language",
    "ভাষা": "preferred_language",
    "bhasha": "preferred_language",
    "role": "user_role",
    "পেশা": "user_role",
    "location": "user_location",
    "ঠিকানা": "user_location",
    "stack": "tech_stack",
    "tech stack": "tech_stack",
    "স্ট্যাক": "tech_stack",
    "style": "response_style_pref",
}


@dataclass(frozen=True)
class MemoryOperation:
    op: str  # "upsert" | "forget"
    key: str
    value: str = ""
    kind: str = "preference"
    confidence: float = 0.95
    source_quote: str = ""


def is_safe_memory_text(text: str) -> bool:
    """বাংলা মন্তব্য: মেমোরি টেক্সটে কোনো সিক্রেট, `.onion` বা প্রম্পট ইনজেকশন আছে কি না যাচাই।"""
    cleaned = (text or "").strip()
    if not cleaned or len(cleaned) > 1000:
        return False
    return _FORBIDDEN_MEMORY_RE.search(cleaned) is None


def _clean_value(raw: str) -> str:
    val = re.sub(r"\s+", " ", (raw or "")).strip(" \t\r\n,.;:!?।\"'`")
    return val[:_MAX_FACT_VALUE_CHARS]


def _slug_key_for_note(note: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", note.lower())[:4]
    if tokens:
        return "note_" + "_".join(tokens)[:40]
    digest = uuid.uuid5(uuid.NAMESPACE_OID, note).hex[:8]
    return f"note_{digest}"


def extract_durable_user_memories(messages: list[Any]) -> list[MemoryOperation]:
    """বাংলা মন্তব্য: সাম্প্রতিক ইউজার মেসেজগুলো থেকে স্থায়ী কী-ইনফরমেশন ও ভুলে যাওয়ার নির্দেশ বের করে।"""
    ops_by_key: dict[str, MemoryOperation] = {}
    user_texts: list[str] = []
    for msg in messages[-4:]:
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = str(msg.get("content") or "").strip()
            if content:
                user_texts.append(content)

    for text in user_texts:
        if not is_safe_memory_text(text):
            continue

        # ১) Forget / মুছে ফেলার নির্দেশ সবার আগে চেক করা হয়
        forget_matched = False
        for pat in _FORGET_PATTERNS:
            m = pat.search(text)
            if m:
                target_raw = _clean_value(m.group(1)).lower()
                mapped_key = _FORGET_ALIAS_MAP.get(target_raw)
                if not mapped_key:
                    for alias, canonical in _FORGET_ALIAS_MAP.items():
                        if alias in target_raw:
                            mapped_key = canonical
                            break
                target_key = mapped_key or _slug_key_for_note(target_raw)
                ops_by_key[target_key] = MemoryOperation(
                    op="forget",
                    key=target_key,
                    value=target_raw,
                    kind="forget",
                    confidence=1.0,
                    source_quote=text[:200],
                )
                forget_matched = True
        if forget_matched:
            continue

        # ২) নাম / পরিচয়
        for pat in _NAME_PATTERNS:
            m = pat.search(text)
            if m:
                val = _clean_value(m.group(1))
                if 2 <= len(val) <= 48 and is_safe_memory_text(val):
                    ops_by_key["user_name"] = MemoryOperation(
                        op="upsert",
                        key="user_name",
                        value=val,
                        kind="profile",
                        confidence=0.97,
                        source_quote=text[:200],
                    )
                break

        # ৩) ভাষা পছন্দ
        for pat, normalized_lang in _LANG_RULES:
            if pat.search(text):
                ops_by_key["preferred_language"] = MemoryOperation(
                    op="upsert",
                    key="preferred_language",
                    value=normalized_lang,
                    kind="preference",
                    confidence=0.99,
                    source_quote=text[:200],
                )
                break

        # ৪) পেশা / রোল
        for pat in _ROLE_PATTERNS:
            m = pat.search(text)
            if m:
                val = _clean_value(m.group(1))
                if 3 <= len(val) <= 70 and is_safe_memory_text(val):
                    ops_by_key["user_role"] = MemoryOperation(
                        op="upsert",
                        key="user_role",
                        value=val,
                        kind="profile",
                        confidence=0.93,
                        source_quote=text[:200],
                    )
                break

        # ৫) অবস্থান / লোকেশন
        for pat in _LOCATION_PATTERNS:
            m = pat.search(text)
            if m:
                val = _clean_value(m.group(1))
                if 2 <= len(val) <= 55 and is_safe_memory_text(val):
                    ops_by_key["user_location"] = MemoryOperation(
                        op="upsert",
                        key="user_location",
                        value=val,
                        kind="profile",
                        confidence=0.92,
                        source_quote=text[:200],
                    )
                break

        # ৬) টেক স্ট্যাক
        for pat in _STACK_PATTERNS:
            m = pat.search(text)
            if m:
                val = _clean_value(m.group(1))
                if 3 <= len(val) <= 140 and is_safe_memory_text(val):
                    ops_by_key["tech_stack"] = MemoryOperation(
                        op="upsert",
                        key="tech_stack",
                        value=val,
                        kind="project",
                        confidence=0.94,
                        source_quote=text[:200],
                    )
                break

        # ৭) উত্তর দেওয়ার স্টাইল পছন্দ
        for pat in _STYLE_PATTERNS:
            m = pat.search(text)
            if m:
                val = _clean_value(m.group(1))
                if 3 <= len(val) <= 90 and is_safe_memory_text(val):
                    ops_by_key["response_style_pref"] = MemoryOperation(
                        op="upsert",
                        key="response_style_pref",
                        value=val,
                        kind="preference",
                        confidence=0.92,
                        source_quote=text[:200],
                    )
                break

        # ৮) সুস্পষ্ট "মনে রেখো / remember that" নির্দেশ
        for pat in _EXPLICIT_REMEMBER_PATTERNS:
            m = pat.search(text)
            if m:
                val = _clean_value(m.group(1))
                if 4 <= len(val) <= 220 and is_safe_memory_text(val):
                    nkey = _slug_key_for_note(val)
                    ops_by_key[nkey] = MemoryOperation(
                        op="upsert",
                        key=nkey,
                        value=val,
                        kind="explicit_note",
                        confidence=0.99,
                        source_quote=text[:200],
                    )
                break

    return list(ops_by_key.values())


def _supabase_creds() -> tuple[str, str] | None:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key or not url.startswith("https://"):
        return None
    return url, key


def _sb_rest(
    method: str,
    path_and_query: str,
    payload: Any = None,
    prefer: str = "return=representation",
) -> Any:
    """বাংলা মন্তব্য: একক কেন্দ্রীয় Supabase PostgREST কল হেল্পার (ফেইল-সফট, চ্যাট কখনো থামায় না)।"""
    creds = _supabase_creds()
    if creds is None:
        return None
    base_url, api_key = creds
    full_url = f"{base_url}/rest/v1/{path_and_query.lstrip('/')}"
    body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Prefer": prefer,
    }
    if body_bytes is not None:
        headers["Content-Type"] = "application/json"
    request_obj = urllib.request.Request(full_url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request_obj, timeout=4.5) as http_resp:
            text_data = http_resp.read().decode("utf-8", errors="replace")
        return json.loads(text_data) if text_data.strip() else None
    except urllib.error.HTTPError as http_exc:
        logger.debug("Supabase memory REST HTTP %s on %s", http_exc.code, path_and_query)
        return None
    except Exception as net_exc:
        logger.debug("Supabase memory REST unavailable (%s)", net_exc)
        return None


def _as_valid_uuid(raw_id: str) -> str | None:
    try:
        return str(uuid.UUID(str(raw_id).strip()))
    except (ValueError, TypeError, AttributeError):
        return None


def fetch_cloud_user_memories(user_id: str) -> list[dict[str, Any]]:
    """বাংলা মন্তব্য: Supabase `user_preferences.preferences.durable_memories` থেকে ইউজারের ক্লাউড মেমোরি লোড করে।"""
    uid = (user_id or "").strip()
    if not uid or not is_safe_memory_text(uid):
        return []
    now = time.time()
    with _LOCK:
        cached = _USER_CLOUD_CACHE.get(uid)
        if cached is not None and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return [dict(item) for item in cached[1]]

    if _supabase_creds() is None:
        return []

    encoded_uid = urllib.parse.quote(uid, safe="")
    rows = _sb_rest(
        "GET",
        f"user_preferences?user_id=eq.{encoded_uid}&select=preferences&limit=1",
    )
    items: list[dict[str, Any]] = []
    if isinstance(rows, list) and rows:
        prefs = rows[0].get("preferences") if isinstance(rows[0], dict) else None
        durable_map = prefs.get("durable_memories") if isinstance(prefs, dict) else None
        if isinstance(durable_map, dict):
            for mem_key, entry in durable_map.items():
                if isinstance(entry, dict) and entry.get("memory_value"):
                    items.append(
                        {
                            "id": str(entry.get("id") or f"cloud-{mem_key}"),
                            "user_id": uid,
                            "memory_key": str(mem_key),
                            "memory_value": str(entry["memory_value"]),
                            "confidence": float(entry.get("confidence", 0.95)),
                            "source_conv_id": entry.get("source_conv_id"),
                            "updated_at": float(entry.get("updated_at") or now),
                        }
                    )
    items.sort(key=lambda r: float(r.get("updated_at") or 0.0), reverse=True)
    with _LOCK:
        _USER_CLOUD_CACHE[uid] = (now, items)
    return [dict(item) for item in items]


def sync_cloud_user_memory_upsert(
    user_id: str,
    memory_key: str,
    memory_value: str,
    confidence: float = 0.95,
    source_conv_id: str | None = None,
    kind: str = "preference",
    source_quote: str = "",
) -> bool:
    """বাংলা মন্তব্য: Supabase `user_preferences` (সকল user_id) ও `memories` (UUID owner_id হলে `supersedes` সহ)-এ সিঙ্ক করে।"""
    uid = (user_id or "").strip()
    mkey = (memory_key or "").strip()
    mval = _clean_value(memory_value)
    if not uid or not mkey or not is_safe_memory_text(uid) or not is_safe_memory_text(mval):
        return False
    if _supabase_creds() is None:
        return False

    now = time.time()
    encoded_uid = urllib.parse.quote(uid, safe="")
    existing_rows = _sb_rest(
        "GET",
        f"user_preferences?user_id=eq.{encoded_uid}&select=preferences,sync_state&limit=1",
    )
    prefs: dict[str, Any] = {}
    sync_state: dict[str, Any] = {}
    if isinstance(existing_rows, list) and existing_rows and isinstance(existing_rows[0], dict):
        if isinstance(existing_rows[0].get("preferences"), dict):
            prefs = dict(existing_rows[0]["preferences"])
        if isinstance(existing_rows[0].get("sync_state"), dict):
            sync_state = dict(existing_rows[0]["sync_state"])

    durable_map = dict(prefs.get("durable_memories") or {}) if isinstance(prefs.get("durable_memories"), dict) else {}
    previous_entry = durable_map.get(mkey) if isinstance(durable_map.get(mkey), dict) else None
    previous_mem_uuid = previous_entry.get("memories_row_id") if isinstance(previous_entry, dict) else None

    new_mem_uuid: str | None = None
    owner_uuid = _as_valid_uuid(uid)
    if owner_uuid:
        new_mem_uuid = str(uuid.uuid4())
        mem_payload: dict[str, Any] = {
            "id": new_mem_uuid,
            "owner_id": owner_uuid,
            "kind": kind or "preference",
            "content": f"{mkey}: {mval}",
            "source_type": "chat_auto",
            "source_ref": source_conv_id or f"key:{mkey}",
            "source_quote": (source_quote or mval)[:240],
            "created_by": "supremeai-memory-engine",
            "status": "confirmed",
            "confidence": round(float(confidence), 3),
        }
        if previous_mem_uuid and _as_valid_uuid(str(previous_mem_uuid)):
            mem_payload["supersedes"] = str(previous_mem_uuid)
            _sb_rest(
                "PATCH",
                f"memories?id=eq.{urllib.parse.quote(str(previous_mem_uuid), safe='')}",
                {"status": "superseded"},
            )
        _sb_rest("POST", "memories", mem_payload)

    durable_map[mkey] = {
        "id": new_mem_uuid or f"mem-{uuid.uuid5(uuid.NAMESPACE_OID, f'{uid}:{mkey}').hex[:12]}",
        "memory_key": mkey,
        "memory_value": mval,
        "kind": kind,
        "confidence": round(float(confidence), 3),
        "source_conv_id": source_conv_id,
        "memories_row_id": new_mem_uuid,
        "updated_at": now,
    }
    if len(durable_map) > _MAX_DURABLE_KEYS_PER_USER:
        sorted_keys = sorted(
            durable_map.keys(),
            key=lambda k: float((durable_map[k] or {}).get("updated_at") or 0.0),
            reverse=True,
        )[:_MAX_DURABLE_KEYS_PER_USER]
        durable_map = {k: durable_map[k] for k in sorted_keys}

    prefs["durable_memories"] = durable_map
    sync_state["last_memory_sync_epoch"] = now
    upsert_res = _sb_rest(
        "POST",
        "user_preferences?on_conflict=user_id",
        {"user_id": uid, "preferences": prefs, "sync_state": sync_state},
        prefer="resolution=merge-duplicates,return=representation",
    )
    with _LOCK:
        _USER_CLOUD_CACHE.pop(uid, None)
    return upsert_res is not None


def sync_cloud_user_memory_forget(user_id: str, memory_key: str) -> bool:
    """বাংলা মন্তব্য: ইউজার কোনো তথ্য ভুলে যেতে বললে Supabase থেকেও সেটি মুছে দেয়।"""
    uid = (user_id or "").strip()
    mkey = (memory_key or "").strip()
    if not uid or not mkey or _supabase_creds() is None:
        return False
    encoded_uid = urllib.parse.quote(uid, safe="")
    existing_rows = _sb_rest(
        "GET",
        f"user_preferences?user_id=eq.{encoded_uid}&select=preferences,sync_state&limit=1",
    )
    if not (isinstance(existing_rows, list) and existing_rows and isinstance(existing_rows[0], dict)):
        return False
    prefs = dict(existing_rows[0].get("preferences") or {})
    sync_state = dict(existing_rows[0].get("sync_state") or {})
    durable_map = dict(prefs.get("durable_memories") or {})
    removed = durable_map.pop(mkey, None)
    if removed is None:
        return False
    if isinstance(removed, dict) and removed.get("memories_row_id"):
        rid = str(removed["memories_row_id"])
        if _as_valid_uuid(rid):
            _sb_rest("DELETE", f"memories?id=eq.{urllib.parse.quote(rid, safe='')}")
    prefs["durable_memories"] = durable_map
    sync_state["last_memory_sync_epoch"] = time.time()
    _sb_rest(
        "POST",
        "user_preferences?on_conflict=user_id",
        {"user_id": uid, "preferences": prefs, "sync_state": sync_state},
        prefer="resolution=merge-duplicates,return=representation",
    )
    with _LOCK:
        _USER_CLOUD_CACHE.pop(uid, None)
    return True


def get_collective_ai_briefing(query_text: str = "", limit: int = 4) -> list[str]:
    """বাংলা মন্তব্য: গিটহাব পাইপলাইনে বিভিন্ন AI এজেন্টদের শেয়ার করা শীর্ষ ভেরিফায়েড নলেজ (`knowledge_base`) রিটার্ন করে।"""
    if not query_text:
        return []
    now = time.time()
    global _COLLECTIVE_CACHE
    rows: list[dict[str, Any]] | None = None
    with _LOCK:
        if _COLLECTIVE_CACHE is not None and (now - _COLLECTIVE_CACHE[0]) < _COLLECTIVE_TTL_SECONDS:
            rows = _COLLECTIVE_CACHE[1]

    if rows is None:
        if _supabase_creds() is None:
            return []
        fetched = _sb_rest(
            "GET",
            "knowledge_base?status=eq.active&select=title,domain,content,source,metadata&order=updated_at.desc&limit=20",
        )
        rows = fetched if isinstance(fetched, list) else []
        with _LOCK:
            _COLLECTIVE_CACHE = (now, rows)

    if not rows:
        return []

    q_words = set(re.findall(r"[a-z0-9_]{3,}", query_text.lower()))
    if not q_words:
        return []

    scored: list[tuple[int, str]] = []
    for rec in rows:
        if not isinstance(rec, dict):
            continue
        title = str(rec.get("title") or "").strip()
        raw_content = str(rec.get("content") or "").strip()
        haystack = f"{title} {rec.get('domain', '')} {raw_content}".lower()
        overlap = sum(1 for w in q_words if w in haystack)
        if overlap <= 0:
            continue
        snippet = raw_content
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, dict):
                snippet = str(
                    parsed.get("insight")
                    or parsed.get("why_this_way")
                    or parsed.get("fix_mechanism")
                    or parsed.get("root_cause_analysis")
                    or raw_content
                )
        except Exception as parse_exc:
            logger.debug("Collective KB JSON parse fallback: %s", parse_exc)
        clean_line = _clean_value(f"[{rec.get('source', 'AI-Shared')}] {title}: {snippet}")
        if is_safe_memory_text(clean_line):
            scored.append((overlap, clean_line))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [line for _, line in scored[: max(1, min(limit, 6))]]


def clear_memory_engine_caches() -> None:
    """বাংলা মন্তব্য: ইউনিট টেস্টের আইসোলেশনের জন্য ইন-মেমরি ক্যাশ পরিষ্কার করে।"""
    global _COLLECTIVE_CACHE
    with _LOCK:
        _USER_CLOUD_CACHE.clear()
        _COLLECTIVE_CACHE = None
