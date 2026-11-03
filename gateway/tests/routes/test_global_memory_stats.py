"""Wave-3 backend perf — /api/preferences/memory/stats contract tests.

বাংলা: আগে এই endpoint ইউজারের প্রতিটি ai_memory row (id, metadata, created_at)
ডাউনলোড করে Python-এ গুনে ৩টা সংখ্যা বানাত (full-scan অপচয়)। এখন total
PostgREST-এর server-side `count=exact` header থেকে আসে, আর row fetch-এ শুধু
দরকারি (metadata, created_at) কলাম নামে। Supabase sandbox-এ নেই — তাই fake
builder-chain দিয়ে (tenant-isolation টেস্টের FakeResult স্টাইলে) contract lock।
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeResult:
    """Awaitable-once result with the postgrest `count` echo attribute."""

    def __init__(self, data: list[dict[str, Any]], count: int | None) -> None:
        self.data = data
        self.count = count

    def __await__(self):
        async def _self() -> FakeResult:
            return self

        return _self().__await__()


class FakeTable:
    """Builder-chain recorder — select-এ count/head kwargs সহ সব op ধরে রাখে।"""

    def __init__(self, rows: list[dict[str, Any]], count: int | None) -> None:
        self._rows = rows
        self._count = count
        self.ops: list[tuple] = []

    def select(self, *cols: str, count: Any = None, head: bool = False) -> FakeTable:
        self.ops.append(("select", cols, count, head))
        return self

    def eq(self, col: str, val: Any) -> FakeTable:
        self.ops.append(("eq", col, val))
        return self

    def execute(self) -> FakeResult:
        return FakeResult(self._rows, self._count)


_ROWS = [
    {"metadata": {"content_type": "fact"}, "created_at": "2026-01-02T00:00:00Z"},
    {"metadata": {"content_type": "preference"}, "created_at": "2026-01-05T00:00:00Z"},
    # বাংলা: string metadata (parse-যোগ্য) ও parse-broken দুই case-ই আগের আচরণে "fact"
    {"metadata": '{"content_type": "instruction"}', "created_at": "2026-01-03T00:00:00Z"},
    {"metadata": "not-valid-json", "created_at": "2026-01-01T00:00:00Z"},
    {"metadata": None, "created_at": None},  # last_updated-এ None timestamp বাদ যায়
]


@pytest.fixture()
def client(monkeypatch):
    import api.routes.global_memory as gmod
    from api.routes.global_memory import router as memory_router

    captured: dict[str, FakeTable] = {}

    class FakeDBHolder:
        def __init__(self, count: int | None) -> None:
            self.client = self
            self._count = count

        def table(self, name: str) -> FakeTable:
            assert name == "ai_memory"
            tbl = FakeTable([dict(r) for r in _ROWS], self._count)
            captured["table"] = tbl
            return tbl

    holder = FakeDBHolder(count=len(_ROWS))

    monkeypatch.setattr(gmod, "supabase_db", holder)

    app = FastAPI()
    app.include_router(memory_router)
    return TestClient(app), captured, holder


class TestMemoryStatsServerSideCount:
    def test_response_shape_and_values(self, client):
        tc, captured, _ = client
        res = tc.get("/api/preferences/memory/stats")
        assert res.status_code == 200
        body = res.json()
        # বাংলা: MemoryStatsResponse contract হুবহু — total_memories/by_type/last_updated;
        # string metadata (parse হয়), broken JSON ও None তিনটাই "fact"-এ গোনা হয় (আগের মতোই)
        assert body == {
            "total_memories": 5,
            "by_type": {"fact": 3, "preference": 1, "instruction": 1},
            "last_updated": "2026-01-05T00:00:00Z",
        }

    def test_query_uses_server_side_count_and_minimal_columns(self, client):
        tc, captured, _ = client
        tc.get("/api/preferences/memory/stats")
        (select_op,) = [op for op in captured["table"].ops if op[0] == "select"]
        # বাংলা: ব্যবহৃত না হওয়া `id` কলাম আর নামানো হয় না + count=exact জারি হয়
        assert select_op[1] == ("metadata, created_at",)
        assert select_op[2] == "exact"
        assert select_op[3] is False

    def test_missing_count_header_falls_back_to_row_len(self, client):
        # বাংলা: কোনো transport count echo না করলে (None) len(rows) একই সংখ্যা দেয় —
        # deterministic fallback, fabricated নয়
        tc, _, holder = client
        holder._count = None
        res = tc.get("/api/preferences/memory/stats")
        assert res.status_code == 200
        assert res.json()["total_memories"] == 5

    def test_user_scoping_preserved(self, client):
        tc, captured, _ = client
        tc.get("/api/preferences/memory/stats")
        assert ("eq", "user_id", "test_admin@supremeai.com") in captured["table"].ops
