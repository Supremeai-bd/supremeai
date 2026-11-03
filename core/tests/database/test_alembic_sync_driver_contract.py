# বাংলা মন্তব্য: Issue #2619 — Alembic sync-driver চুক্তির গার্ড টেস্ট।
"""Regression tests locking the alembic sync-driver contract (#2597 + #2619).

Deploy Train Migration Gate run 36686618685 প্রমাণ করেছে: SQLAlchemy 2.1.1
(dependabot #2462) থেকে bare `postgresql://` URL-এর ডিফল্ট dialect psycopg (v3)
— রিপোতে যে মডিউল নেই। `_normalize_sync_driver_url()` এখন সব postgres scheme
(driver-সহ বা driver-হীন) কে `postgresql+psycopg2://`-তে পিন করে। এই টেস্ট
env.py থেকে হুবহু shipped ফাংশন-বডি AST দিয়ে লোড করে চুক্তিটা লক করে রাখে —
কোনো ভারী import (core.config/models) ছাড়াই, deterministic ভাবে।
"""

from __future__ import annotations

import ast
import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

ENV_PY_PATH = Path(__file__).resolve().parents[2] / "alembic_migrations" / "env.py"


def _load_normalize_fn() -> Callable[[str], str]:
    """env.py-র সোর্স থেকে শুধু `_normalize_sync_driver_url` AST-extract করে exec।

    বাংলা মন্তব্য: env.py module-level-এ settings/model import ও URL রেজলিউশন
    চালায় — পুরো মডিউল লোড করা টেস্টের জন্য ভারী ও ইনপুট-নির্ভর। তাই shipped
    ফাংশন-বডিই হুবহু (সোর্স টেক্সট থেকে) নিয়ে বিচ্ছিন্ন namespace-এ exec করা হয় —
    ফাংশন কেউ এডিট করলে টেস্ট সেটাই যাচাই করবে; মুছে ফেললে টেস্ট fail করবে।
    """
    source = ENV_PY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_normalize_sync_driver_url"
    ]
    assert fn_defs, (
        "_normalize_sync_driver_url env.py থেকে মুছে ফেলা হয়েছে — "
        "sync-driver চুক্তি (#2597/#2619) অরক্ষিত!"
    )
    module = ast.Module(body=fn_defs, type_ignores=[])
    namespace: dict[str, Any] = {}
    exec(compile(module, str(ENV_PY_PATH), "exec"), namespace)
    return namespace["_normalize_sync_driver_url"]


def test_bare_postgresql_scheme_pinned_to_psycopg2() -> None:
    """bare `postgresql://` (writer secret-এর প্রকৃত shape) → psycopg2।

    বাংলা মন্তব্য: SQLAlchemy 2.1+ এটাকে psycopg v3 dialect-এ পাঠায় —
    রান 36686618685-এর ModuleNotFoundError-এর সরাসরি কারণ।
    """
    normalize = _load_normalize_fn()
    result = normalize("postgresql://postgres:secret@db.ref.supabase.co:5432/postgres")
    assert result == ("postgresql+psycopg2://postgres:secret@db.ref.supabase.co:5432/postgres")


def test_legacy_postgres_scheme_pinned_to_psycopg2() -> None:
    """লিগ্যাসি `postgres://` → psycopg2 (SQLAlchemy 2.x এটাকে এমনিও reject করে)।"""
    normalize = _load_normalize_fn()
    result = normalize("postgres://postgres:secret@db.ref.supabase.co:5432/postgres")
    assert result == ("postgresql+psycopg2://postgres:secret@db.ref.supabase.co:5432/postgres")


def test_explicit_psycopg_v3_scheme_still_pinned() -> None:
    """`postgresql+psycopg://` (v3) → psycopg2 — #2597-র মূল চুক্তি অক্ষুণ্ণ।"""
    normalize = _load_normalize_fn()
    result = normalize("postgresql+psycopg://postgres.ref:secret@pooler.supabase.com:5432/postgres")
    assert result == ("postgresql+psycopg2://postgres.ref:secret@pooler.supabase.com:5432/postgres")


def test_asyncpg_scheme_pinned_for_sync_engine() -> None:
    """`postgresql+asyncpg://` → psycopg2 — sync engine-এ asyncpg অবৈধ (#2597)।"""
    normalize = _load_normalize_fn()
    result = normalize("postgresql+asyncpg://postgres.ref:secret@pooler.supabase.com:5432/postgres")
    assert result == ("postgresql+psycopg2://postgres.ref:secret@pooler.supabase.com:5432/postgres")


def test_psycopg2_scheme_not_double_rewritten() -> None:
    """`postgresql+psycopg2://` ইনপুট অপরিবর্তিত থাকে — ডাবল-রিরাইট অসম্ভব।"""
    normalize = _load_normalize_fn()
    url = "postgresql+psycopg2://u:p@localhost:5432/db"
    assert normalize(url) == url


def test_non_postgres_scheme_untouched() -> None:
    """`sqlite://` জাতীয় non-postgres scheme অপরিবর্তিত — লোকাল dev পথ নিরাপদ।"""
    normalize = _load_normalize_fn()
    url = "sqlite:///./local_dev.db"
    assert normalize(url) == url


def test_pooler_rebuilt_url_shape_is_covered() -> None:
    """pooler-fallback-এ পুনর্নির্মিত URL-ও (query সহ) পিনিং চুক্তির আওতায়।

    বাংলা মন্তব্য: `_resolve_reachable_url` scheme সংরক্ষণ করে pooler host
    বসায়; query string (sslmode ইত্যাদি) হারানো যাবে না।
    """
    normalize = _load_normalize_fn()
    result = normalize(
        "postgresql://postgres.ref:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    )
    assert result == (
        "postgresql+psycopg2://postgres.ref:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    )
