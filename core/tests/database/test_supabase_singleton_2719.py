"""#2719 slice-2 — SupabaseDB lazy-singleton contract tests.

Locked contract (issue #2719, founder directive: per-request client churn ×25+):
- `get_db()` returns ONE process-wide shared `SupabaseDB` instance (lazy: first
  call constructs, later calls reuse — zero per-request client creation).
- `reset_db_singleton()` clears the shared instance (test hook).
- Runtime call-sites (routes + capability_adapters) must NOT instantiate
  `SupabaseDB()` directly — source-scan regression guard.
"""

import re
from pathlib import Path

import database.supabase_client as supabase_client_module
from database.supabase_client import get_db, reset_db_singleton

RUNTIME_SITES = [
    "api/routes/artifacts.py",
    "api/routes/share.py",
    "api/routes/chat_upload.py",
    "api/routes/slash_commands.py",
    "api/routes/keys.py",
    "api/routes/conversations.py",
    "api/routes/chat_search.py",
    "core/orchestration/capability_adapters.py",
]


def teardown_function():
    """বাংলা মন্তব্য: প্রতিটি টেস্টের পরে singleton রিসেট — ক্রস-টেস্ট দূষণ শূন্য।"""
    reset_db_singleton()


def test_get_db_returns_same_instance():
    """একই প্রসেসে N বার কল → একই instance (identity চুক্তি)।"""
    first = get_db()
    second = get_db()
    third = get_db()
    assert first is second
    assert second is third


def test_get_db_constructs_exactly_once(monkeypatch):
    """get_db() N বার কলেও SupabaseDB কনস্ট্রাক্টর ঠিক ১ বার চলে — churn বিলুপ্ত।"""
    constructions: list[object] = []

    class _CountingDB:
        def __init__(self):
            constructions.append(self)

    monkeypatch.setattr(supabase_client_module, "SupabaseDB", _CountingDB)
    try:
        a = get_db()
        b = get_db()
        c = get_db()
        assert len(constructions) == 1, (
            f"SupabaseDB constructed {len(constructions)}× — must be lazy-once"
        )
        assert a is b is c is constructions[0]
    finally:
        # monkeypatch টেস্ট-শেষে নিজেই undo করে; এখানে singleton পরিষ্কার করা হচ্ছে
        reset_db_singleton()


def test_reset_db_singleton_forces_fresh_instance():
    """reset_db_singleton()-এর পরে get_db() নতুন instance দেয় — আবার identity স্থির।"""
    first = get_db()
    reset_db_singleton()
    second = get_db()
    assert first is not second
    assert get_db() is second


def test_runtime_sites_no_direct_instantiation():
    """রিগ্রেশন-গার্ড: runtime ফাইলে `SupabaseDB(` ইনস্ট্যানশিয়েশন নিষিদ্ধ।

    আগে ২৪টি per-request সাইট ছিল (artifacts ৬, share ৫, chat_upload ৪,
    slash_commands ৩, keys ২, conversations ২, chat_search ১, adapters ১) —
    সবগুলো `get_db()` হতে হবে। ক্লাস-ইমপোর্টও অবশিষ্ট থাকবে না (অব্যবহৃত)।
    """
    backend_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for rel in RUNTIME_SITES:
        text = (backend_root / rel).read_text(encoding="utf-8")
        if re.search(r"SupabaseDB\s*\(", text):
            offenders.append(rel)
        if re.search(r"import\s+SupabaseDB\b", text):
            offenders.append(f"{rel} (stale class import)")
    assert offenders == [], f"per-request SupabaseDB() churn remains: {offenders}"
