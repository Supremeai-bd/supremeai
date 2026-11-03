"""Full-coverage tests for api/routes/deep_research.py (Task 7-c).

Strategy:
    - Minimal FastAPI app mounting ONLY deep_research.router (prefix
      /api/research); auth comes from the conftest test-bypass via a
      deterministic dependency override (sub=user-1).
    - The shared ``database.supabase_client.db`` singleton gets a dict-backed
      fake ``.client`` whose builder-chain returns awaitable-and-sync results
      (deep_research mixes awaited and non-awaited supabase calls).
    - LLM / web-search / indexing / memory-store are monkeypatched at the
      deep_research module level; scout persistence is patched to return no
      policy (honest zero-source mode).
    - SSE streaming endpoint is consumed with httpx streaming.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import api.routes.deep_research as dr
from api.deps import get_current_user_token

SUB = "user-1"

SUBQUERY_JSON = json.dumps(["sub q one about topic", "sub q two about topic"])
GAP_JSON = json.dumps(["gap query one", "gap query two"])
REPORT_JSON = json.dumps(
    {
        "title": "Structured Report",
        "summary": "All the findings summarized.",
        "sections": [
            {
                "title": "Findings",
                "content": "Content with [Source A] citation.",
                "sources": ["Source A"],
            }
        ],
        "sources": [{"title": "Source A", "url": "https://a.example/1", "snippet": "snip"}],
    }
)

SEARCH_RESULTS = [
    {"title": "Source A", "url": "https://a.example/1", "snippet": "snippet a"},
    {"title": "Source B", "url": "https://b.example/2", "snippet": "snippet b"},
]


class SyncAsync:
    """Object that is both the execute() result and awaitable to itself."""

    def __init__(self, data: list[dict[str, Any]]):
        self.data = data

    def __await__(self):
        async def _self() -> SyncAsync:
            return self

        return _self().__await__()


class FakeTable:
    """Supabase builder-chain recorder: every op returns self; execute returns SyncAsync."""

    def __init__(self, rows: list[dict[str, Any]], ops: list[tuple], fail: bool = False):
        self._rows = rows
        self._ops = ops
        self._fail = fail

    def _record(self, name: str, args: tuple, kwargs: dict) -> FakeTable:
        self._ops.append((name, args, kwargs))
        return self

    def select(self, *a, **k):
        return self._record("select", a, k)

    def insert(self, a=None, **k):
        return self._record("insert", (a,), k)

    def upsert(self, a=None, **k):
        return self._record("upsert", (a,), k)

    def update(self, a=None, **k):
        return self._record("update", (a,), k)

    def delete(self, *a, **k):
        return self._record("delete", a, k)

    def eq(self, *a, **k):
        return self._record("eq", a, k)

    def order(self, *a, **k):
        return self._record("order", a, k)

    def limit(self, *a, **k):
        return self._record("limit", a, k)

    def or_(self, *a, **k):
        return self._record("or_", a, k)

    def in_(self, *a, **k):
        return self._record("in_", a, k)

    def execute(self) -> SyncAsync:
        self._ops.append(("execute", (), {}))
        if self._fail:
            raise RuntimeError("supabase down")
        return SyncAsync(list(self._rows))


class FakeSupabase:
    def __init__(
        self,
        tables: dict[str, list[dict[str, Any]]] | None = None,
        fail_tables: set[str] | None = None,
    ):
        self.tables = tables or {}
        self.fail_tables = fail_tables or set()
        self.ops: list[tuple[str, tuple, dict]] = []

    def table(self, name: str) -> FakeTable:
        return FakeTable(self.tables.get(name, []), self.ops, fail=name in self.fail_tables)

    def rpc(self, name: str, params: dict) -> FakeTable:
        self.ops.append(("rpc", (name, params), {}))
        return FakeTable([], self.ops)


@pytest_asyncio.fixture
async def research_env(monkeypatch):
    """App + fake supabase + pipeline mocks (with sources by default)."""
    app = FastAPI()
    app.include_router(dr.router)

    async def fake_user():
        return {"sub": SUB, "role": "user", "tenant_id": "tenant-1"}

    app.dependency_overrides[get_current_user_token] = fake_user

    fake_db = FakeSupabase()
    monkeypatch.setattr(dr.supabase_db, "client", fake_db)
    monkeypatch.setattr(dr, "_research_bootstrapped", False)

    async def fake_llm(prompt: str, user_id: str, task_type: str = "deep_research") -> str:
        if "Generate 4 specific sub-queries" in prompt:
            return SUBQUERY_JSON
        if "Identify 2-3 important gaps" in prompt:
            return GAP_JSON
        if "Return a JSON object with this exact structure" in prompt:
            return REPORT_JSON
        if "research query optimiser" in prompt:
            return "refined research question"
        return "llm text"

    monkeypatch.setattr(dr, "_llm_call", fake_llm)

    search_calls: list[str] = []

    async def fake_search(query: str, user_id: str = "") -> list[dict[str, str]]:
        search_calls.append(query)
        return [dict(r) for r in SEARCH_RESULTS]

    monkeypatch.setattr(dr, "_web_search", fake_search)
    monkeypatch.setattr(dr, "_index_findings", lambda findings, user_id: 3)

    async def fake_save_memory(**kwargs):
        fake_db.ops.append(("save_memory", (kwargs.get("summary"),), {}))

    monkeypatch.setattr("services.memory_service.save_memory", fake_save_memory)

    emitted: list[tuple] = []

    def fake_emit(session_id, step, content):
        emitted.append((session_id, step, content))

    monkeypatch.setattr("core.observability.reasoning_stream.emit_reasoning_step", fake_emit)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, fake_db, search_calls, emitted

    app.dependency_overrides.clear()


@pytest.mark.unit
class TestDeepResearchSync:
    async def test_success_with_sources(self, research_env):
        http, fake_db, search_calls, _ = research_env
        resp = await http.post("/api/research/deep", json={"query": "what is quantum?"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["report"]["title"] == "Structured Report"
        assert body["report"]["summary"] == "All the findings summarized."
        assert body["report"]["sections"][0]["sources"] == ["Source A"]
        assert body["steps_completed"] == 10
        assert body["total_sources"] >= 4  # 2 per sub-query × 2 + follow-ups
        # both sub-queries and follow-up gap queries were searched
        assert "sub q one about topic" in search_calls
        assert "gap query one" in search_calls
        # session recorded as completed
        upserts = [op for op in fake_db.ops if op[0] == "upsert"]
        assert upserts[-1][1][0]["status"] == "completed"
        assert any(op[0] == "save_memory" for op in fake_db.ops)

    async def test_conversation_attach_inserts_message(self, research_env):
        http, fake_db, *_ = research_env
        resp = await http.post(
            "/api/research/deep",
            json={"query": "what is quantum?", "conversation_id": "conv-9"},
        )
        assert resp.status_code == 200
        inserts = [op for op in fake_db.ops if op[0] == "insert"]
        assert inserts, "message insert into conversation expected"
        assert inserts[-1][1][0]["conversation_id"] == "conv-9"

    async def test_honest_no_sources_report(self, research_env, monkeypatch):
        http, fake_db, _, _ = research_env

        async def no_results(query: str, user_id: str = ""):
            return []

        monkeypatch.setattr(dr, "_web_search", no_results)
        resp = await http.post("/api/research/deep", json={"query": "empty topic?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_sources"] == 0
        assert body["steps_completed"] == 10
        # CURRENT BEHAVIOUR NOTE: the pipeline marks the report dict with
        # ``no_web_sources: True`` but the DeepResearchResponse pydantic
        # response_model has no such field, so the marker is stripped before
        # the client sees it. The honest content itself does survive.
        assert body["report"].get("no_web_sources") is None
        assert "No web sources could be retrieved" in body["report"]["sections"][0]["content"]
        assert "No live web sources" in body["report"]["summary"]

    async def test_invalid_token_401(self, research_env):
        http, *_ = research_env
        app = http._transport.app
        app.dependency_overrides[get_current_user_token] = lambda: {"role": "user"}
        try:
            resp = await http.post("/api/research/deep", json={"query": "valid query"})
        finally:
            app.dependency_overrides[get_current_user_token] = fake_user_fn()
        assert resp.status_code == 401

    async def test_validation_422(self, research_env):
        http, *_ = research_env
        short = await http.post("/api/research/deep", json={"query": "ab"})
        assert short.status_code == 422
        bad_steps = await http.post(
            "/api/research/deep", json={"query": "valid query", "max_steps": 2}
        )
        assert bad_steps.status_code == 422

    async def test_db_unavailable_503(self, research_env, monkeypatch):
        http, *_ = research_env
        monkeypatch.setattr(dr.supabase_db, "client", None)
        monkeypatch.setattr(dr, "_research_bootstrapped", False)
        resp = await http.post("/api/research/deep", json={"query": "valid query"})
        assert resp.status_code == 503
        assert "Database is not available" in resp.json()["detail"]

    async def test_schema_bootstrap_rpc(self, research_env):
        http, fake_db, *_ = research_env
        await http.post("/api/research/deep", json={"query": "bootstrap me"})
        assert fake_db.ops[0][0] == "rpc"  # exec_sql schema bootstrap ran

    async def test_pipeline_failure_500(self, research_env, monkeypatch):
        http, fake_db, *_ = research_env

        async def boom(**kwargs):
            raise RuntimeError("pipeline exploded")

        monkeypatch.setattr(dr, "_run_research_pipeline", boom)
        resp = await http.post("/api/research/deep", json={"query": "valid query"})
        assert resp.status_code == 500
        assert "Deep research pipeline failed" in resp.json()["detail"]
        failed = [op for op in fake_db.ops if op[0] == "upsert"]
        assert failed[-1][1][0]["status"] == "failed"

    async def test_llm_failure_still_reports(self, research_env, monkeypatch):
        http, *_ = research_env

        async def bad_llm(prompt: str, user_id: str, task_type: str = "x") -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(dr, "_llm_call", bad_llm)
        resp = await http.post("/api/research/deep", json={"query": "valid query"})
        assert resp.status_code == 200
        body = resp.json()
        # fallback report keeps the refined (original) title and raw sources
        assert body["report"]["title"] == "valid query"
        assert body["total_sources"] >= 2


def fake_user_fn():
    async def _f():
        return {"sub": SUB, "role": "user"}

    return _f


@pytest.mark.unit
class TestDeepResearchStream:
    async def test_stream_events_and_report(self, research_env):
        http, fake_db, _, emitted = research_env
        events: list[dict[str, Any]] = []
        async with http.stream(
            "POST", "/api/research/deep/stream", json={"query": "streaming query"}
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    payload = line[len("data: ") :]
                    if payload == "[DONE]":
                        break
                    events.append(json.loads(payload))
        steps = [e for e in events if e["type"] == "step"]
        report_events = [e for e in events if e["type"] == "report"]
        assert [s["step"] for s in steps] == list(range(1, 11))
        assert steps[0]["name"] == "Parsing query"
        assert len(report_events) == 1
        report = report_events[0]
        assert report["content"]["title"] == "Structured Report"
        assert report["total_sources"] >= 2
        assert report["id"]
        # reasoning steps were emitted against the session id
        assert emitted and all(e[0] == report["id"] for e in emitted)
        # persisted as completed
        upserts = [op for op in fake_db.ops if op[0] == "upsert"]
        assert upserts[-1][1][0]["status"] == "completed"

    async def test_stream_pipeline_error_event(self, research_env, monkeypatch):
        """REGRESSION GUARD (#2506): when the pipeline raises mid-stream the
        generator must (a) exit its loop — ``done_event`` flips True via the
        ``finally`` — and (b) deliver exactly one ``error`` event followed by
        ``[DONE]`` instead of hanging the connection forever. The old version
        of this test ended in ``assert True`` (constitution rule 1 violation)
        because the bug made any raising pipeline hang the test."""
        http, fake_db, *_ = research_env

        async def boom(**kwargs):
            raise RuntimeError("pipeline exploded mid-stream")

        monkeypatch.setattr(dr, "_run_research_pipeline", boom)

        events: list[dict[str, Any]] = []
        async with http.stream(
            "POST", "/api/research/deep/stream", json={"query": "failing stream"}
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            # If the hang ever regresses, this loop never terminates and the
            # test times out — that timeout IS the failure signal.
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    payload = line[len("data: ") :]
                    if payload == "[DONE]":
                        break
                    events.append(json.loads(payload))

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "pipeline exploded mid-stream" in error_events[0]["content"]
        # no partial success artifacts may be emitted
        assert not any(e["type"] in ("step", "report") for e in events)
        # terminal failure persisted (no row stuck in "running")
        upserts = [op for op in fake_db.ops if op[0] == "upsert"]
        assert upserts[-1][1][0]["status"] == "failed"


@pytest.mark.unit
class TestHistoryAndReport:
    async def test_history_returns_rows(self, research_env):
        http, fake_db, *_ = research_env
        fake_db.tables["deep_research_sessions"] = [
            {
                "id": "r1",
                "query": "q",
                "status": "completed",
                "steps_completed": 10,
                "total_sources": 2,
                "created_at": "2026-01-01T00:00:00Z",
                "report": {"title": "T"},
            }
        ]
        resp = await http.get("/api/research/history")
        assert resp.status_code == 200
        rows = resp.json()
        assert rows[0]["id"] == "r1"
        assert rows[0]["report"] == {"title": "T"}  # report column contract
        # user filter applied
        eq_ops = [op for op in fake_db.ops if op[0] == "eq"]
        assert eq_ops[-1][1] == ("user_id", SUB)

    async def test_history_db_failure_500(self, research_env, monkeypatch):
        http, fake_db, *_ = research_env
        fake_db.fail_tables = {"deep_research_sessions"}
        monkeypatch.setattr(dr, "_research_bootstrapped", False)
        resp = await http.get("/api/research/history")
        assert resp.status_code == 500

    async def test_history_limit_param(self, research_env):
        http, fake_db, *_ = research_env
        resp = await http.get("/api/research/history", params={"limit": 5})
        assert resp.status_code == 200
        limits = [op for op in fake_db.ops if op[0] == "limit"]
        assert limits[-1][1] == (5,)

    async def test_get_report_found(self, research_env):
        http, fake_db, *_ = research_env
        fake_db.tables["deep_research_sessions"] = [{"id": "abc", "query": "q"}]
        resp = await http.get("/api/research/abc")
        assert resp.status_code == 200
        assert resp.json()["id"] == "abc"

    async def test_get_report_not_found_404(self, research_env):
        http, *_ = research_env
        resp = await http.get("/api/research/missing-id")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_get_report_db_failure_500(self, research_env):
        http, fake_db, *_ = research_env
        fake_db.fail_tables = {"deep_research_sessions"}
        resp = await http.get("/api/research/abc")
        assert resp.status_code == 500

    async def test_history_invalid_token_401(self, research_env):
        http, *_ = research_env
        app = http._transport.app
        app.dependency_overrides[get_current_user_token] = lambda: {}
        try:
            resp = await http.get("/api/research/history")
        finally:
            app.dependency_overrides[get_current_user_token] = fake_user_fn()
        assert resp.status_code == 401
