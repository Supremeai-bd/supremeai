"""#2719 slice-1 — chat_search title batch-prefetch contract tests.

Locked contract: the message-search path resolves conversation titles via ONE
batched `.in_()` query (dict lookup) — zero per-conversation title queries in
the result loop (N+1 eliminated).
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from api.routes.chat_search import search_chats


class _FakeTable:
    """বাংলা মন্তব্য: চেইনযোগ্য PostgREST বিল্ডার fake — প্রতিটি কোয়েরি রেকর্ড হয়।"""

    def __init__(self, name, recorder, data_router):
        self._name = name
        self._recorder = recorder
        self._router = data_router
        self._select = ""
        self._ops: list[tuple] = []

    def select(self, cols: str):
        self._select = cols
        return self

    def eq(self, col, val):
        self._ops.append(("eq", col, val))
        return self

    def ilike(self, col, pat):
        self._ops.append(("ilike", col, pat))
        return self

    def order(self, col, desc=False):
        self._ops.append(("order", col, desc))
        return self

    def in_(self, col, vals):
        self._ops.append(("in", col, tuple(vals)))
        return self

    def limit(self, n):
        self._ops.append(("limit", n))
        return self

    def update(self, payload):
        self._ops.append(("update", payload))
        return self

    async def execute(self):
        self._recorder.append((self._name, self._select, tuple(self._ops)))
        data = self._router(self._name, self._select, self._ops)
        return SimpleNamespace(data=data)


def _make_fake_db():
    """বাংলা মন্তব্য: conversation/message রাউটিং — slice-1 কন্ট্র্যাক্ট অনুযায়ী ডেটা।"""
    queries: list[tuple] = []

    def route(name, select, ops):
        op_kinds = [o[0] for o in ops]
        if name == "conversations":
            if "ilike" in op_kinds:
                return []  # title-search phase: কিছু ম্যাচ নেই
            if "in" in op_kinds:
                in_vals = next(o[2] for o in ops if o[0] == "in")
                return [{"id": cid, "title": f"T-{cid}"} for cid in in_vals]
            if "eq" in op_kinds and select == "id":
                return [{"id": f"c{i}"} for i in range(10)]  # user conv ids
            return []
        if name == "messages":
            # বাংলা মন্তব্য: ৫টি ম্যাচ ৫টি ভিন্ন conversation-এ — আগে ৫টি title কোয়েরি খেত
            return [
                {
                    "id": f"m{i}",
                    "conversation_id": f"c{i}",
                    "role": "user",
                    "content": "alpha discussion thread",
                    "created_at": "2026-09-30T00:00:0Z",
                }
                for i in range(5)
            ]
        return []

    def table(name):
        return _FakeTable(name, queries, route)

    db = SimpleNamespace(client=SimpleNamespace(table=table))
    return db, queries


@pytest.mark.asyncio
async def test_message_search_titles_batched_single_query():
    db, queries = _make_fake_db()
    with patch("api.routes.chat_search.get_db", return_value=db):
        resp = await search_chats(q="alpha", limit=20, offset=0, user={"sub": "user-1"})

    conv_queries = [q for q in queries if q[0] == "conversations"]
    # বাংলা মন্তব্য: মোট ৩টি conversations কোয়েরি — title-search + ids + batch;
    # per-row title কোয়েরি শূন্য (আগে N+1: প্রতি match-এ +১)।
    assert len(conv_queries) == 3
    assert not any(q[1] == "title" for q in conv_queries), "per-row title query returned!"
    batched = [q for q in conv_queries if q[1] == "id, title" and any(o[0] == "in" for o in q[2])]
    assert len(batched) == 1, "titles must be fetched in exactly ONE .in_ query"

    # ৫টি ম্যাচ সঠিক title পেয়েছে (batch dict থেকে)
    titles = {r.conversation_id: r.title for r in resp.results}
    for i in range(5):
        assert titles[f"c{i}"] == f"T-c{i}"


@pytest.mark.asyncio
async def test_message_search_preserves_title_phase_titles():
    """title-phase-এ থাকা ভালো score-এর entry-র title batch দিয়ে overwrite হয় না।"""
    db, _queries = _make_fake_db()

    def route(name, select, ops):
        op_kinds = [o[0] for o in ops]
        if name == "conversations":
            if "ilike" in op_kinds:
                return [{"id": "c0", "title": "Alpha Master"}]
            if "in" in op_kinds:
                in_vals = next(o[2] for o in ops if o[0] == "in")
                return [{"id": cid, "title": f"T-{cid}"} for cid in in_vals]
            if "eq" in op_kinds:
                return [{"id": "c0"}]
            return []
        if name == "messages":
            return [
                {
                    "id": "m0",
                    "conversation_id": "c0",
                    "role": "user",
                    "content": "alpha again",
                    "created_at": "2026-09-30T00:00:0Z",
                }
            ]
        return []

    # বাংলা মন্তব্য: এক conversation (c0) — title-phase এটি "Alpha Master" দেয়
    def table(name):
        return _FakeTable(name, _queries, route)

    _queries = []
    with patch(
        "api.routes.chat_search.get_db",
        return_value=SimpleNamespace(client=SimpleNamespace(table=table)),
    ):
        resp = await search_chats(q="alpha", limit=20, offset=0, user={"sub": "user-1"})

    c0 = next(r for r in resp.results if r.conversation_id == "c0")
    assert c0.title == "Alpha Master"
