"""Task 7-c — Mission Orchestration core test suite.

Covers three layers, all offline:

- the state machine is pure Python;
- the service runs on a dedicated sqlite+aiosqlite in-memory engine with ONLY
  the two missions tables created (the shared conftest ``db_engine`` runs
  ``create_all`` over the FULL ``models.base.Base`` metadata, which cannot
  compile PG-only column types like JSONB on sqlite — the same reason repo CI
  uses a real postgres service; the missions tables themselves are fully
  sqlite-compatible via ``JSON().with_variant(JSONB, "postgresql")``);
- API tests drive the real app through httpx ASGITransport with the conftest
  test-auth bypass environment; distinct principals (owner vs. stranger vs.
  admin) are simulated with a dependency-level override of
  ``get_current_user_token`` because AuthMiddleware's bypass short-circuits
  before JWT decoding in test mode.

Counts: state machine 6, service lifecycle 10, API contract 7.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from missions.service import MissionNotFound, MissionService
from missions.state_machine import (
    APPROVED,
    ASSIGNED,
    CANCELLED,
    FAILED,
    MAX_REPAIRS,
    PLANNED,
    REPAIRING,
    RUNNING,
    STATES,
    SUCCEEDED,
    IllegalTransition,
    assert_transition,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svc() -> MissionService:
    return MissionService()


@pytest_asyncio.fixture
async def mission_db() -> AsyncSession:
    """In-memory sqlite session with ONLY the missions tables created."""
    from missions.models import Mission, MissionTraceEvent
    from models.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=[Mission.__table__, MissionTraceEvent.__table__]
            )
        )
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


_api_tables_ready = False


@pytest_asyncio.fixture
async def missions_api_tables(client):
    """Create the missions tables on the app engine's sqlite test database
    (test.db — the URL the conftest ``app`` fixture injects via env)."""
    global _api_tables_ready
    if not _api_tables_ready:
        import database.session as dbs
        from missions.models import Mission, MissionTraceEvent
        from models.base import Base

        dbs.init_engine()
        engine = dbs.engine
        assert engine.url.get_backend_name() == "sqlite", (
            f"expected sqlite test engine, got {engine.url}"
        )
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[Mission.__table__, MissionTraceEvent.__table__],
                )
            )
        _api_tables_ready = True
    yield


async def _make_mission(session, *, options=("plan-a", "plan-b"), phases=3, **kw):
    return await _svc().create_mission(
        session,
        owner_id=kw.pop("owner_id", "owner-x"),
        title=kw.pop("title", "Integration mission"),
        goal_text=kw.pop("goal_text", "Achieve the thing"),
        strategy=kw.pop("strategy", None),
        strategy_options=list(options),
        phases=[{"name": f"phase-{i + 1}", "note": ""} for i in range(phases)],
        **kw,
    )


# ---------------------------------------------------------------------------
# State machine (pure Python)
# ---------------------------------------------------------------------------


class TestStateMachine:
    def test_happy_chain_edges_all_legal(self):
        """Every edge of the happy path + repair loop validates."""
        chain = [
            (PLANNED, APPROVED),
            (APPROVED, ASSIGNED),
            (ASSIGNED, RUNNING),
            (RUNNING, FAILED),
            (FAILED, REPAIRING),
            (REPAIRING, RUNNING),
            (RUNNING, SUCCEEDED),
        ]
        for current, nxt in chain:
            assert assert_transition(current, nxt) == nxt

    def test_illegal_jump_raises(self):
        with pytest.raises(IllegalTransition, match="illegal mission transition"):
            assert_transition(PLANNED, RUNNING)

    def test_unknown_states_raise(self):
        with pytest.raises(IllegalTransition, match="unknown current mission state"):
            assert_transition("warp-drive", RUNNING)
        with pytest.raises(IllegalTransition, match="unknown next mission state"):
            assert_transition(PLANNED, "hyperspace")

    def test_terminal_states_have_no_outgoing_edges(self):
        for terminal in (SUCCEEDED, CANCELLED):
            for nxt in set(STATES) - {terminal}:
                with pytest.raises(IllegalTransition):
                    assert_transition(terminal, nxt)

    def test_approved_to_assigned_requires_strategy(self):
        assert assert_transition(APPROVED, ASSIGNED, strategy_chosen=True)
        with pytest.raises(IllegalTransition, match="requires a chosen strategy"):
            assert_transition(APPROVED, ASSIGNED, strategy_chosen=False)

    def test_repair_guard_bounded_by_max_repairs(self):
        assert assert_transition(FAILED, REPAIRING, repair_count=MAX_REPAIRS - 1)
        with pytest.raises(IllegalTransition, match="repair"):
            assert_transition(FAILED, REPAIRING, repair_count=MAX_REPAIRS)


# ---------------------------------------------------------------------------
# Service lifecycle (dedicated in-memory sqlite engine)
# ---------------------------------------------------------------------------


class TestMissionService:
    async def test_create_defaults_and_trace(self, mission_db):
        mission = await _make_mission(mission_db)
        assert mission.state == PLANNED
        assert mission.current_phase == 0
        assert [p["name"] for p in mission.phases] == [
            "phase-1",
            "phase-2",
            "phase-3",
        ]
        assert [p["status"] for p in mission.phases] == ["pending"] * 3
        trace = await _svc().get_trace(mission_db, mission.id)
        assert len(trace) == 1 and trace[0].seq == 1
        assert trace[0].detail["to"] == PLANNED

    async def test_create_requires_owner(self, mission_db):
        with pytest.raises(ValueError, match="owner_id"):
            await _svc().create_mission(mission_db, owner_id="", title="t", goal_text="g")

    async def test_create_normalizes_inputs(self, mission_db):
        mission = await _svc().create_mission(
            mission_db,
            owner_id="owner-n",
            title="normalized",
            goal_text="g",
            strategy_options=[" a ", "", "b"],
            phases=[{"name": "P1"}, {"name": "P1", "status": "weird"}],
        )
        assert mission.strategy_options == ["a", "b"]
        assert mission.phases[0]["status"] == "pending"
        assert mission.phases[1]["status"] == "pending"  # invalid status reset

    async def test_approve_auto_fulfills(self, mission_db):
        mission = await _make_mission(mission_db)
        svc = _svc()
        approved = await svc.approve(mission_db, mission.id, actor="admin-x")
        assert approved.state == ASSIGNED  # single-call auto-fulfillment
        assert approved.strategy == "plan-a"
        assert approved.agent_id == "auto-agent-v1"

    async def test_approve_requires_planned_state(self, mission_db):
        mission = await _make_mission(mission_db)
        svc = _svc()
        await svc.approve(mission_db, mission.id)
        with pytest.raises(IllegalTransition):
            await svc.approve(mission_db, mission.id)

    async def test_start_marks_first_phase_in_progress(self, mission_db):
        mission = await _make_mission(mission_db)
        svc = _svc()
        await svc.approve(mission_db, mission.id)
        started = await svc.start(mission_db, mission.id)
        assert started.state == RUNNING
        assert started.phases[0]["status"] == "in_progress"
        assert started.current_phase == 0

    async def test_advance_completes_phases_then_succeeds(self, mission_db):
        mission = await _make_mission(mission_db, phases=2)
        svc = _svc()
        await svc.approve(mission_db, mission.id)
        await svc.start(mission_db, mission.id)
        first = await svc.advance_phase(mission_db, mission.id)
        assert first.state == RUNNING  # one phase left
        assert first.phases[0]["status"] == "completed"
        final = await svc.advance_phase(mission_db, mission.id)
        assert final.state == SUCCEEDED
        assert all(p["status"] == "completed" for p in final.phases)

    async def test_fail_records_reason(self, mission_db):
        mission = await _make_mission(mission_db)
        svc = _svc()
        await svc.approve(mission_db, mission.id)
        await svc.start(mission_db, mission.id)
        failed = await svc.fail(mission_db, mission.id, "boom", actor="op-1")
        assert failed.state == FAILED
        assert failed.failure_reason == "boom"
        trace = await svc.get_trace(mission_db, mission.id)
        assert trace[-1].detail["actor"] == "op-1"

    async def test_repair_rotates_strategy_and_resets_phase(self, mission_db):
        mission = await _make_mission(mission_db, options=("plan-a", "plan-b", "plan-c"), phases=3)
        svc = _svc()
        await svc.approve(mission_db, mission.id)
        await svc.start(mission_db, mission.id)
        await svc.advance_phase(mission_db, mission.id)
        await svc.fail(mission_db, mission.id, "strategy dead")
        repaired = await svc.request_repair(mission_db, mission.id)
        assert repaired.state == RUNNING
        assert repaired.strategy == "plan-b"
        assert repaired.repair_count == 1
        assert repaired.current_phase == 0
        # Phase progress is fully reset to pending (start() re-marks in_progress).
        assert all(p["status"] == "pending" for p in repaired.phases)

    async def test_repairs_exhausted_is_terminal_failure(self, mission_db):
        # (a) A single-option mission exhausts on the FIRST repair attempt:
        # no alternative strategy exists, so the service returns it terminal-FAILED.
        mission = await _make_mission(mission_db, options=("only-plan",))
        svc = _svc()
        await svc.approve(mission_db, mission.id)
        await svc.start(mission_db, mission.id)
        await svc.fail(mission_db, mission.id, "dead")
        exhausted = await svc.request_repair(mission_db, mission.id)
        assert exhausted.state == FAILED
        assert "repair exhausted" in exhausted.failure_reason

        # (b) With >= 2 options the loop is bounded by MAX_REPAIRS: each repair
        # rotates (repair_count += 1) until the entry guard trips.
        mission2 = await _make_mission(mission_db, options=("a", "b"))
        await svc.approve(mission_db, mission2.id)
        await svc.start(mission_db, mission2.id)
        for i in range(MAX_REPAIRS):
            await svc.fail(mission_db, mission2.id, "again")
            mission2 = await svc.request_repair(mission_db, mission2.id)
            assert mission2.repair_count == i + 1
        await svc.fail(mission_db, mission2.id, "final")
        with pytest.raises(IllegalTransition, match="repair"):
            await svc.request_repair(mission_db, mission2.id)

    async def test_custom_assigner_hook_used(self, mission_db):
        mission = await _make_mission(mission_db)
        svc = MissionService(assigner=lambda m: "specialist-7")
        approved = await svc.approve(mission_db, mission.id)
        assert approved.agent_id == "specialist-7"


# ---------------------------------------------------------------------------
# API contract (httpx AsyncClient + ASGITransport over the real app)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def principal(client):
    """Per-test principal factory for the real app.

    WHY an override instead of minted JWTs: in test mode AuthMiddleware
    short-circuits BEFORE decoding tokens when ALLOW_TEST_AUTH_BYPASS=true
    (core/security/authentication/auth_middleware.py:219 — public/bypass paths
    never reach the JWT decode branch), so `get_current_user_token` always
    falls back to the single bypass admin identity. Dependency-level override
    is the only way to exercise the router's multi-principal ownership logic
    against the real app.
    """
    from api.dependencies import get_current_user_token
    from core.app import app as application

    def install(sub: str, role: str = "user") -> str:
        application.dependency_overrides[get_current_user_token] = lambda: {
            "sub": sub,
            "role": role,
            "tenant_id": "test-tenant",
        }
        return sub

    yield install
    application.dependency_overrides.pop(get_current_user_token, None)


async def _http_create(client, principal, *, sub: str | None = None, **overrides):
    """Create a mission over HTTP as a UNIQUE per-run principal."""
    sub = sub or f"user-{uuid.uuid4().hex[:10]}"
    principal(sub)
    payload = {
        "title": "HTTP mission",
        "goal_text": "Goal via HTTP",
        "strategy_options": ["plan-a", "plan-b"],
        "phases": [{"name": "phase-1"}, {"name": "phase-2"}],
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/missions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json(), sub


class TestMissionsAPI:
    async def test_create_get_roundtrip(self, client, missions_api_tables, principal):
        """POST creates a planned mission owned by the JWT principal; GET
        returns it."""
        body, sub = await _http_create(client, principal)
        mission_id = body["id"]
        assert body["state"] == "planned"
        assert body["owner_id"] == sub
        assert len(body["phases"]) == 2

        got = await client.get(f"/api/v1/missions/{mission_id}")
        assert got.status_code == 200
        assert got.json()["id"] == mission_id

        missing = await client.get(f"/api/v1/missions/{uuid.uuid4()}")
        assert missing.status_code == 404

    async def test_list_with_state_filter_and_pagination(
        self, client, missions_api_tables, principal
    ):
        sub = f"list-{uuid.uuid4().hex[:10]}"
        principal(sub)
        for name in ("m1", "m2", "m3"):
            await _http_create(client, principal, sub=sub, title=name)

        listed = await client.get("/api/v1/missions?limit=2&skip=0")
        assert listed.status_code == 200
        data = listed.json()
        assert data["count"] == 2
        assert data["limit"] == 2 and data["skip"] == 0
        assert all(item["owner_id"] == sub for item in data["items"])

        planned_only = await client.get("/api/v1/missions?state=planned&limit=100")
        assert planned_only.status_code == 200
        assert all(item["state"] == "planned" for item in planned_only.json()["items"])

        bad_state = await client.get("/api/v1/missions?state=nope")
        assert bad_state.status_code == 422

    async def test_transition_endpoints_via_http(self, client, missions_api_tables, principal):
        """approve→start→advance drives the mission through the state machine
        over HTTP, writing trace events along the way."""
        body, _sub = await _http_create(client, principal)
        mid = body["id"]
        base = f"/api/v1/missions/{mid}"

        approved = await client.post(f"{base}/approve", json=None)
        assert approved.status_code == 200, approved.text
        assert approved.json()["state"] == "assigned"
        assert approved.json()["strategy"] == "plan-a"
        # #1829: the label now reflects the real routing decision (LLM-gateway
        # executor lane), not the retired "auto-agent-v1" stub badge.
        assert approved.json()["agent_id"] == "llm-gateway-direct"

        started = await client.post(f"{base}/start")
        assert started.status_code == 200
        assert started.json()["state"] == "running"

        advanced = await client.post(f"{base}/advance")
        assert advanced.status_code == 200
        assert advanced.json()["current_phase"] == 1

        # Illegal jump over HTTP → 409 (running→approved is not an edge).
        illegal = await client.post(f"{base}/approve")
        assert illegal.status_code == 409

        trace = await client.get(f"{base}/trace")
        assert trace.status_code == 200
        trace_body = trace.json()
        assert trace_body["count"] >= 5
        seqs = [e["seq"] for e in trace_body["items"]]
        assert seqs == sorted(seqs) and seqs[0] == 1

    async def test_fail_and_repair_via_http(self, client, missions_api_tables, principal):
        body, _sub = await _http_create(client, principal)
        mid = body["id"]
        base = f"/api/v1/missions/{mid}"
        await client.post(f"{base}/approve")
        await client.post(f"{base}/start")

        failed = await client.post(f"{base}/fail", json={"reason": "upstream timeout"})
        assert failed.status_code == 200
        assert failed.json()["state"] == "failed"
        assert failed.json()["failure_reason"] == "upstream timeout"

        repaired = await client.post(f"{base}/repair")
        assert repaired.status_code == 200
        assert repaired.json()["state"] == "running"
        assert repaired.json()["strategy"] == "plan-b"  # rotated
        assert repaired.json()["repair_count"] == 1
        assert repaired.json()["current_phase"] == 0  # phase reset

        cancelled = await client.post(f"{base}/cancel", json={"reason": "done"})
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "cancelled"

    async def test_cross_user_access_returns_404(self, client, missions_api_tables, principal):
        """Non-admin principals cannot see foreign missions — 404, not 403."""
        body, owner_sub = await _http_create(client, principal)
        mid = body["id"]

        # Another (non-admin) user: all reads AND transitions → 404.
        principal(f"bob-{uuid.uuid4().hex[:8]}")
        assert (await client.get(f"/api/v1/missions/{mid}")).status_code == 404
        assert (await client.get("/api/v1/missions")).json()["count"] == 0
        assert (await client.post(f"/api/v1/missions/{mid}/approve")).status_code == 404
        assert (await client.get(f"/api/v1/missions/{mid}/trace")).status_code == 404

        # A third (non-admin) user: still 404 (existence never leaked).
        principal(f"alice-{uuid.uuid4().hex[:8]}")
        assert (await client.get(f"/api/v1/missions/{mid}")).status_code == 404

        # The owner still sees it.
        principal(owner_sub)
        assert (await client.get(f"/api/v1/missions/{mid}")).status_code == 200

    async def test_admin_sees_all_missions(self, client, missions_api_tables, principal):
        """Admin principals bypass the ownership filter (list + direct read)."""
        body, _sub = await _http_create(client, principal)
        mid = body["id"]

        principal("admin-on-call", role="admin")
        listed = await client.get("/api/v1/missions?limit=100")
        assert listed.status_code == 200
        assert any(item["id"] == mid for item in listed.json()["items"])
        assert (await client.get(f"/api/v1/missions/{mid}")).status_code == 200

    async def test_sse_trace_stream_emits_events(self, client, missions_api_tables, principal):
        """GET .../trace/stream emits at least one SSE mission_trace event."""
        body, _sub = await _http_create(client, principal)
        mid = body["id"]
        base = f"/api/v1/missions/{mid}"
        await client.post(f"{base}/approve")
        await client.post(f"{base}/start")

        received: list[str] = []
        async with client.stream("GET", f"{base}/trace/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for chunk in response.aiter_bytes():
                received.append(chunk.decode())
                if any("event: mission_trace" in part for part in received):
                    break

        stream_text = "".join(received)
        assert "event: mission_trace" in stream_text
        assert "data:" in stream_text
