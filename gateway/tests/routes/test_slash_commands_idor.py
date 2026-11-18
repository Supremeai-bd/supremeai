"""Regression tests for cross-tenant conversation IDOR in slash_commands.

Security context:
    ``database.supabase_client.get_db().client`` uses the Supabase service-role
    key, which BYPASSES row-level security. Any handler that accepts a
    caller-supplied ``conversation_id`` MUST verify ownership before reading or
    mutating that conversation's messages. These tests prove that a user cannot
    summarize, export, or clear another user's conversation by passing its id.

Unlike ``test_slash_commands_full.py`` (whose fake ignores ``.eq`` filters),
the fake here honours ``.eq("id", ...)`` / ``.eq("user_id", ...)`` so ownership
is actually enforced and observable.
"""

from __future__ import annotations

from typing import Any

import api.routes.slash_commands as sc
import pytest
import pytest_asyncio
from api.deps import get_current_user_token
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

SUB = "user-1"
OTHER_USER_CONV = "conv-owned-by-user-2"
OWN_USER_CONV = "conv-owned-by-user-1"


class _Result:
    def __init__(self, rows: list[dict[str, Any]]):
        self.data = rows


class _FilteringTable:
    """Minimal Supabase table stub that honours chained .eq() filters."""

    def __init__(self, rows: list[dict[str, Any]], ops: list[tuple], fail: bool = False):
        self._rows = rows
        self._ops = ops
        self._fail = fail
        self._filters: dict[str, Any] = {}

    def _clone(self) -> _FilteringTable:
        t = _FilteringTable(self._rows, self._ops, self._fail)
        t._filters = dict(self._filters)
        return t

    def select(self, *a, **k):
        self._ops.append(("select", a, k))
        return self._clone()

    def eq(self, col, val):
        self._ops.append(("eq", (col, val), {}))
        t = self._clone()
        t._filters[col] = val
        return t

    def order(self, *a, **k):
        self._ops.append(("order", a, k))
        return self._clone()

    def limit(self, *a, **k):
        self._ops.append(("limit", a, k))
        return self._clone()

    def delete(self, *a, **k):
        self._ops.append(("delete", a, k))
        return self._clone()

    def execute(self) -> _Result:
        self._ops.append(("execute", (), {}))
        if self._fail:
            raise RuntimeError("delete failed")
        rows = self._rows
        for col, val in self._filters.items():
            rows = [r for r in rows if r.get(col) == val]
        return _Result(list(rows))


class _FilteringDB:
    def __init__(self, tables: dict[str, list[dict[str, Any]]], fail_on: set[str] | None = None):
        self.tables = tables
        self.fail_on = fail_on or set()
        self.ops: list[tuple] = []
        _FilteringDB.last = self

    @property
    def client(self):
        holder = self

        class _Client:
            def table(self, name):
                return _FilteringTable(
                    holder.tables.get(name, []), holder.ops, name in holder.fail_on
                )

        return _Client()


@pytest_asyncio.fixture
async def idor_env(monkeypatch):
    app = FastAPI()
    app.include_router(sc.router)

    async def fake_user():
        return {"sub": SUB, "role": "user"}

    app.dependency_overrides[get_current_user_token] = fake_user

    async def fake_acompletion(**kwargs):
        return {"text": "LLM says: done"}

    monkeypatch.setattr("core.llm.llm_gateway.llm_gateway.acompletion", fake_acompletion)

    tables = {
        "conversations": [
            {"id": OWN_USER_CONV, "title": "My Own Chat", "user_id": SUB},
            {"id": OTHER_USER_CONV, "title": "Someone Else's Chat", "user_id": "user-2"},
        ],
        "messages": [
            {"role": "user", "content": "secret from user-1", "created_at": "t1", "conversation_id": OWN_USER_CONV},
            {"role": "assistant", "content": "reply", "created_at": "t2", "conversation_id": OWN_USER_CONV},
        ],
    }
    shared_db = _FilteringDB(tables)
    monkeypatch.setattr("database.supabase_client.get_db", lambda: shared_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, tables, shared_db

    app.dependency_overrides.clear()


async def _execute(http: AsyncClient, command: str, args: dict | None = None) -> dict:
    resp = await http.post("/api/commands/execute", json={"command": command, "args": args or {}})
    assert resp.status_code == 200, resp.text
    return resp.json()["result"]


def _delete_ops(db_holder) -> int:
    return sum(1 for op in db_holder.ops if op[0] == "delete")


@pytest.mark.unit
class TestConversationIDOR:
    async def test_clear_other_users_conversation_denied(self, idor_env):
        http, _, db_holder = idor_env
        result = await _execute(http, "/clear", {"conversation_id": OTHER_USER_CONV})
        assert result["error"] == "Conversation not found or access denied"
        # No message deletion must have been attempted.
        assert _delete_ops(db_holder) == 0

    async def test_clear_own_conversation_allowed(self, idor_env):
        http, _, db_holder = idor_env
        result = await _execute(http, "/clear", {"conversation_id": OWN_USER_CONV})
        assert result["status"] == "cleared"
        assert result["conversation_id"] == OWN_USER_CONV
        assert _delete_ops(db_holder) == 1

    async def test_summarize_other_users_conversation_denied(self, idor_env):
        http, *_ = idor_env
        result = await _execute(http, "/summarize", {"conversation_id": OTHER_USER_CONV})
        assert result["error"] == "Conversation not found or access denied"

    async def test_export_other_users_conversation_denied(self, idor_env):
        http, *_ = idor_env
        result = await _execute(http, "/export", {"conversation_id": OTHER_USER_CONV})
        assert result["error"] == "Conversation not found or access denied"

    async def test_export_own_conversation_allowed(self, idor_env):
        http, *_ = idor_env
        result = await _execute(http, "/export", {"conversation_id": OWN_USER_CONV})
        assert result.get("format") == "markdown"
        assert result["content"].startswith("# My Own Chat")