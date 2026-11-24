"""core.services.memory_graph — UserMemoryGraph, the personal-executive memory.

বাংলা (Master Blueprint, পিলার ১ — "ইউজার সম্পর্কে জানা ও প্রো-অ্যাক্টিভ
অ্যাসিস্ট্যান্স"): সাধারণ চ্যাটবট প্রতিটি সেশনে ইউজারকে ভুলে যায়; ব্যক্তিগত
এক্সিকিউটিভ ইউজারকে প্রতিদিন আরও গভীরভাবে চেনে। এই মডিউল সেই স্মৃতির হালকা,
স্থানীয়-প্রথম (local-first) বাস্তবায়ন:

* **Passive fact extraction** — চ্যাট/ভয়েস ট্রানসক্রিপ্ট থেকে deterministic,
  শূন্য-খরচ (কোনো LLM কল নয়) নিয়মে তথ্য বের করা: ভাষা-পছন্দ, পছন্দ,
  ওয়েবসাইট, মানুষ, অভ্যাস ও কাজের ইতিহাস;
* **Per-tenant JSON store** — প্রতি টেন্যান্টের জন্য একটি ছোট, পারমাণবিক-লেখা
  (atomic write) ফাইল; করাপ্ট ফাইল = খালি গ্রাফ + জোরালো লগ (নীরব ভান নয়);
* **Morning briefing** — গ্রাফ থেকেই সকালের ব্রিফিং কার্ডের সৎ ডেটা (শুধু
  যা সত্যিই জানা, বানানো নয়)।

গভর্ন্যান্স:

* কিল-সুইচ: ``SUPREMEAI_MEMORY_GRAPH=false`` → পুরো সারফেস নিষ্ক্রিয়,
  সৎ ``enabled: false`` উত্তর (ডিফল্ট ON — এটাই প্রোডাক্টের মূল ফিচার);
* ইউজার নিয়ন্ত্রণ: প্রতিটি ফ্যাক্ট ``forget`` করা যায়, পুরো গ্রাফ মোছা যায়;
* কোনো LLM, কোনো এমবেডিং, কোনো নেটওয়ার্ক কল নেই — ফাইল I/O ছাড়া কিছুই নয়।
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.monitoring.logging_config import logger

#: কিল-সুইচ env — মান "false"/"off"/"0" হলে সারফেস বন্ধ (অজানা মান = ON + সতর্কতা)。
KILL_SWITCH_ENV = "SUPREMEAI_MEMORY_GRAPH"
#: স্টোর ডিরেক্টরি env — টেস্ট tmp_path-এ ইনজেক্ট করা যায়।
STORE_DIR_ENV = "SUPREMEAI_MEMORY_GRAPH_DIR"

#: প্রতি টেন্যান্ট গ্রাফে সর্বোচ্চ ফ্যাক্ট — মেমরি-বিস্ফোরণ কাঠামোগতভাবে অসম্ভব।
MAX_FACTS = 200
#: এক প্যাসেজে সর্বোচ্চ যত ফ্যাক্ট নেওয়া হবে।
MAX_FACTS_PER_ABSORB = 24

_GRAPH_VERSION = 1
_LOCK = threading.Lock()

FACT_KINDS = ("language", "preference", "site", "person", "habit", "task")

# ── deterministic extraction patterns (বাংলা + ইংরেজি) ───────────────────────
_BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
_URL_RE = re.compile(r"https?://[^\s)\]>'\"।]+|(?<![\w/])www\.[^\s)\]>'\"।]+", re.IGNORECASE)
_PREFERENCE_RE = re.compile(
    r"(?:i (?:prefer|like|love|hate|always|never)\s+(?:to\s+)?|"
    r"আমি\s+(?:পছন্দ\s+করি|ভালোবাসি|অপছন্দ\s+করি|সবসময়|কখনো)\s*)"
    r"([^\n।.!?]{2,120})",
    re.IGNORECASE,
)
_PERSON_RE = re.compile(
    r"(?:call|email|contact|message|text|remind)\s+([A-Z][\w'-]{1,30})|"
    r"(?:কে|কাছে)\s+(?:কল|মেইল|ইমেইল|মেসেজ|জানাও|বলো)\s*(?:করো|করুন|দাও)?\s*([\u0980-\u09FF\w'-]{2,30})",
    re.IGNORECASE,
)
_HABIT_RE = re.compile(
    r"(?:every\s+(?:day|morning|evening|night|week)|daily|"
    r"at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)|"
    r"প্রতিদিন|প্রতি\s*(?:সকাল|সন্ধ্যা|রাত|সপ্তাহ)|রাত\s*\d{1,2}ট(?:া|য়)|সকাল\s*\d{1,2}ট(?:া|য়))",
    re.IGNORECASE,
)
_TASK_RE = re.compile(
    r"(?:^|\n)\s*(?:todo|task|remind me to|need to|কাজ|মনে\s+করিয়ে\s+দিও|মনে\s+রাখো)[:\s-]+([^\n]{3,160})",
    re.IGNORECASE,
)


def memory_enabled() -> bool:
    """কিল-সুইচ — ডিফল্ট ON; স্পষ্ট ``false``-এ বন্ধ (অজানা মান = ON + সতর্কতা)।"""
    raw = os.environ.get(KILL_SWITCH_ENV, "").strip().lower()
    if raw in ("", "on", "true", "1"):
        return True
    if raw in ("false", "off", "0"):
        return False
    logger.warning(
        f"[memory_graph] {KILL_SWITCH_ENV}={raw!r} অজানা মান — ডিফল্ট ON ব্যবহৃত"
    )
    return True


def store_dir() -> Path:
    """গ্রাফ-স্টোর ডিরেক্টরি (env-এ ইনজেক্টযোগ্য; ডিফল্ট ``data/memory_graph``)।"""
    raw = os.environ.get(STORE_DIR_ENV, "").strip()
    path = Path(raw) if raw else Path("data") / "memory_graph"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tenant_slug(tenant_id: str) -> str:
    """ফাইল-নিরাপদ টেন্যান্ট নাম — অচেনা অক্ষর থাকলে ডাইজেস্ট-নাম (পাথ-ট্রাভার্সাল নিষিদ্ধ)।"""
    tenant = (tenant_id or "").strip() or "anonymous"
    slug = re.sub(r"[^A-Za-z0-9_-]", "", tenant)[:64]
    if not slug or slug != tenant:
        import hashlib

        digest = hashlib.sha256(tenant.encode("utf-8")).hexdigest()[:12]
        slug = f"t-{digest}"
    return slug


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _empty_graph(tenant_id: str) -> dict[str, Any]:
    return {
        "version": _GRAPH_VERSION,
        "tenantId": (tenant_id or "").strip() or "anonymous",
        "updatedAt": _now(),
        "facts": [],
    }


def _graph_path(tenant_id: str) -> Path:
    return store_dir() / f"{_tenant_slug(tenant_id)}.json"


def _load_graph(tenant_id: str) -> dict[str, Any]:
    """গ্রাফ লোড — করাপ্ট/অচেনা ফাইল = খালি গ্রাফ + জোরালো লগ (নীরব ভান নয়)।"""
    path = _graph_path(tenant_id)
    if not path.exists():
        return _empty_graph(tenant_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("facts"), list):
            raise ValueError("graph root must be an object with a facts list")
        data.setdefault("tenantId", tenant_id)
        data.setdefault("version", _GRAPH_VERSION)
        return data
    except Exception as exc:
        logger.error(
            f"[memory_graph] tenant={tenant_id} graph file unreadable ({type(exc).__name__}: {exc})"
            " — starting an empty graph, the corrupt file is kept as .corrupt"
        )
        try:
            path.replace(path.with_suffix(".json.corrupt"))
        except OSError:
            pass
        return _empty_graph(tenant_id)


def _save_graph(tenant_id: str, graph: dict[str, Any]) -> None:
    """পারমাণবিক লেখা — অর্ধেক-লেখা ফাইল কখনো থাকবে না (tmp + replace)।"""
    path = _graph_path(tenant_id)
    graph["updatedAt"] = _now()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def extract_facts(text: str) -> list[dict[str, str]]:
    """Deterministic, zero-cost fact extraction — কোনো LLM নেই, তাই পুরোপুরি পুনরাবৃত্তযোগ্য।

    রিটার্ন: ``[{"kind", "value"}]`` — ভাষা অনুপাত, পছন্দ, সাইট, মানুষ, অভ্যাস ও কাজ।
    """
    if not text or not text.strip():
        return []
    facts: list[dict[str, str]] = []

    # ভাষা: বাংলা অক্ষরের অনুপাত > ০.২৫ → "bn"; ডমিন্যান্ট ASCII → "en"।
    letters = [c for c in text if c.isalpha()]
    if letters:
        bengali = sum(1 for c in letters if _BENGALI_RE.match(c))
        if bengali / max(len(letters), 1) > 0.25:
            facts.append({"kind": "language", "value": "bn"})
        else:
            facts.append({"kind": "language", "value": "en"})

    for match in _PREFERENCE_RE.finditer(text):
        value = match.group(1).strip()
        if value:
            facts.append({"kind": "preference", "value": value[:120]})
    for match in _URL_RE.finditer(text):
        value = match.group(0).rstrip(".,;:")
        if value:
            facts.append({"kind": "site", "value": value[:160]})
    for match in _PERSON_RE.finditer(text):
        value = next((g for g in match.groups() if g), None)
        if value:
            facts.append({"kind": "person", "value": value.strip()[:60]})
    for match in _HABIT_RE.finditer(text):
        value = match.group(0).strip()
        if value:
            facts.append({"kind": "habit", "value": value[:80]})
    for match in _TASK_RE.finditer(text):
        value = match.group(1).strip()
        if value:
            facts.append({"kind": "task", "value": value[:160]})

    return facts[:MAX_FACTS_PER_ABSORB]


def _fact_id(kind: str, value: str) -> str:
    import hashlib

    digest = hashlib.sha256(f"{kind}:{value.strip().lower()}".encode("utf-8")).hexdigest()[:12]
    return f"f-{digest}"


def absorb_text(tenant_id: str, text: str, source: str = "chat") -> dict[str, Any]:
    """এক প্যাসেজ থেকে ফ্যাক্ট নিয়ে গ্রাফে জমান — ডিডাপ সহ (count += 1)।"""
    if not memory_enabled():
        return {"enabled": False, "absorbed": [], "totalFacts": 0, "reason": "memory graph disabled"}
    extracted = extract_facts(text)
    if not extracted:
        return {"enabled": True, "absorbed": [], "totalFacts": None, "source": source}

    with _LOCK:
        graph = _load_graph(tenant_id)
        by_key = {
            (f["kind"], f["value"].strip().lower()): f for f in graph["facts"]
        }
        absorbed: list[str] = []
        for item in extracted:
            key = (item["kind"], item["value"].strip().lower())
            existing = by_key.get(key)
            if existing:
                existing["count"] = int(existing.get("count", 1)) + 1
                existing["lastSeen"] = _now()
                absorbed.append(existing["id"])
                continue
            fact = {
                "id": _fact_id(item["kind"], item["value"]),
                "kind": item["kind"],
                "value": item["value"].strip(),
                "source": source,
                "count": 1,
                "firstSeen": _now(),
                "lastSeen": _now(),
            }
            by_key[key] = fact
            graph["facts"].append(fact)
            absorbed.append(fact["id"])

        # সর্বোচ্চ সীমা: সবচেয়ে পুরোনো দেখা ফ্যাক্ট প্রথমে বাদ (LRU)।
        if len(graph["facts"]) > MAX_FACTS:
            graph["facts"].sort(key=lambda f: f.get("lastSeen", ""), reverse=True)
            graph["facts"] = graph["facts"][:MAX_FACTS]

        _save_graph(tenant_id, graph)
    logger.info(
        f"[memory_graph] tenant={tenant_id} absorbed={len(absorbed)} source={source}"
    )
    return {
        "enabled": True,
        "absorbed": absorbed,
        "totalFacts": len(graph["facts"]),
        "source": source,
    }


def get_graph(tenant_id: str) -> dict[str, Any]:
    """সম্পূর্ণ গ্রাফ (কপি) — ইউজারের নিজের ডেটা, তাই পুরোটাই দেখানো হয়।"""
    if not memory_enabled():
        return {"enabled": False, **_empty_graph(tenant_id)}
    with _LOCK:
        graph = _load_graph(tenant_id)
    graph["facts"].sort(key=lambda f: f.get("lastSeen", ""), reverse=True)
    return {"enabled": True, **graph}


def forget_fact(tenant_id: str, fact_id: str) -> bool:
    """ইউজার-নিয়ন্ত্রণ: এক ফ্যাক্ট ভুলে যাওয়া। রিটার্ন — সত্যিই মুছেছে কি না।"""
    with _LOCK:
        graph = _load_graph(tenant_id)
        before = len(graph["facts"])
        graph["facts"] = [f for f in graph["facts"] if f.get("id") != (fact_id or "").strip()]
        removed = len(graph["facts"]) < before
        if removed:
            _save_graph(tenant_id, graph)
    return removed


def wipe_graph(tenant_id: str) -> bool:
    """ইউজার-নিয়ন্ত্রণ: পুরো গ্রাফ মুছুন (right-to-be-forgotten)।"""
    path = _graph_path(tenant_id)
    existed = path.exists()
    if existed:
        path.unlink()
    return existed


def _greeting_for(language: str, hour: int) -> str:
    """ভাষা-সচেতন শুভেচ্ছা — গ্রাফের ভাষা-ফ্যাক্ট অনুযায়ী (বানানো নয়)।"""
    if language == "bn":
        if 4 <= hour < 12:
            return "শুভ সকাল!"
        if 12 <= hour < 17:
            return "শুভ দুপুর!"
        if 17 <= hour < 20:
            return "শুভ বিকাল!"
        return "শুভ রাত্রি!"
    if 4 <= hour < 12:
        return "Good morning!"
    if 12 <= hour < 17:
        return "Good afternoon!"
    if 17 <= hour < 20:
        return "Good evening!"
    return "Working late!"


def morning_briefing(tenant_id: str, now: datetime | None = None) -> dict[str, Any]:
    """প্রো-অ্যাক্টিভ মর্নিং ব্রিফিং — কেবল গ্রাফে সত্যিই থাকা তথ্য; বানানো কিছু নেই।"""
    local_now = now or datetime.now(UTC)
    if not memory_enabled():
        return {"enabled": False, "reason": "memory graph disabled", "greeting": None, "recentTasks": [], "topFacts": []}

    graph = get_graph(tenant_id)
    facts = graph.get("facts", [])
    language = next(
        (f["value"] for f in facts if f["kind"] == "language"),
        "en",
    )
    recent_tasks = [
        {"value": f["value"], "lastSeen": f["lastSeen"], "count": f["count"]}
        for f in facts
        if f["kind"] == "task"
    ][:5]
    top_facts = [
        {"kind": f["kind"], "value": f["value"], "count": f["count"]}
        for f in facts
        if f["kind"] in ("preference", "site", "person", "habit")
    ][:6]

    return {
        "enabled": True,
        "tenantId": graph.get("tenantId", tenant_id),
        "generatedAt": _now(),
        "greeting": _greeting_for(language, local_now.hour),
        "language": language,
        "recentTasks": recent_tasks,
        "topFacts": top_facts,
        "totalFacts": len(facts),
        "hasMemory": bool(facts),
    }
