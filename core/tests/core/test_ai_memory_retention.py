"""Tests for core/ai_memory/retention.py (issue #1109).

No live DB / REST client needed: the RPC and REST paths are exercised with
injected fakes; the get_retention_days contract is tested against env values.
"""

from __future__ import annotations

import pytest

from core.ai_memory import retention
from core.ai_memory.retention import (
    CleanupResult,
    cleanup_expired,
    delete_user_memories,
    get_retention_days,
)

# ── get_retention_days ────────────────────────────────────────────────────────


def test_retention_days_default(monkeypatch):
    monkeypatch.delenv("AI_MEMORY_RETENTION_DAYS", raising=False)
    assert get_retention_days() == retention.DEFAULT_RETENTION_DAYS == 180


def test_retention_days_env_override(monkeypatch):
    monkeypatch.setenv("AI_MEMORY_RETENTION_DAYS", "30")
    assert get_retention_days() == 30


def test_retention_days_rejects_zero_and_garbage(monkeypatch):
    # Fail-closed: a typo must raise, never silently fall back to 180.
    monkeypatch.setenv("AI_MEMORY_RETENTION_DAYS", "0")
    with pytest.raises(ValueError, match=">= 1"):
        get_retention_days()
    monkeypatch.setenv("AI_MEMORY_RETENTION_DAYS", "abc")
    with pytest.raises(ValueError, match="integer"):
        get_retention_days()


def test_cleanup_rejects_bad_explicit_days():
    import asyncio

    with pytest.raises(ValueError, match=">= 1"):
        asyncio.run(cleanup_expired(retention_days=0, supabase_client=object()))


# ── cleanup_expired: RPC path ─────────────────────────────────────────────────


def test_cleanup_rpc_path(monkeypatch):
    class FakeResult:
        data = 7

    class FakeRPC:
        def __init__(self, name, params):
            assert name == "fn_ai_memory_retention_cleanup"
            assert params == {"p_days": 90}

        def execute(self):
            return FakeResult()

    class FakeClient:
        def rpc(self, name, params):
            return FakeRPC(name, params)

    import asyncio

    result = asyncio.run(cleanup_expired(retention_days=90, supabase_client=FakeClient()))
    assert isinstance(result, CleanupResult)
    assert result.mode == "rpc"
    assert result.deleted == 7
    assert result.retention_days == 90


def test_cleanup_falls_back_to_direct_when_rpc_raises(monkeypatch):
    class BrokenClient:
        def rpc(self, name, params):
            raise RuntimeError("rpc unavailable")

    calls: list[int] = []

    async def fake_direct(days: int) -> int:
        calls.append(days)
        return 3

    monkeypatch.setattr(retention, "_table_delete_expired", fake_direct)

    import asyncio

    result = asyncio.run(cleanup_expired(retention_days=45, supabase_client=BrokenClient()))
    assert result.mode == "direct"
    assert result.deleted == 3
    assert calls == [45]  # TTL passed through to the fallback


# ── delete_user_memories (GDPR) ───────────────────────────────────────────────


def test_gdpr_erasure_rest_path():
    captured: dict = {}

    class FakeQuery:
        def __init__(self, table):
            captured["table"] = table

        def delete(self):
            return self

        def eq(self, col, val):
            captured["filter"] = (col, val)
            return self

        def execute(self):
            class R:
                data = [{"id": "a"}, {"id": "b"}]  # two rows erased

            return R()

    class FakeClient:
        def table(self, name):
            return FakeQuery(name)

    import asyncio

    result = asyncio.run(delete_user_memories("user-42", supabase_client=FakeClient()))
    assert result.mode == "rpc"
    assert result.deleted == 2
    assert captured["filter"] == ("user_id", "user-42")  # scoped to the owner


def test_gdpr_erasure_requires_user_id():
    import asyncio

    with pytest.raises(ValueError, match="user_id"):
        asyncio.run(delete_user_memories("   "))


def test_gdpr_erasure_falls_back_to_direct(monkeypatch):
    class BrokenClient:
        def table(self, name):
            raise RuntimeError("rest down")

    # The fallback resolves the session factory via `from core.db import
    # get_session_factory` at call time → patch the attribute on core.db.
    import core.db as core_db

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, stmt):
            class R:
                rowcount = 5

            return R()

        async def commit(self):
            return None

    class FakeFactory:
        def __call__(self):
            return FakeSession()

    monkeypatch.setattr(core_db, "get_session_factory", lambda: FakeFactory())

    import asyncio

    result = asyncio.run(retention.delete_user_memories("user-7", supabase_client=BrokenClient()))
    assert result.mode == "direct"
    assert result.deleted == 5
