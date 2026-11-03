"""Mission Orchestration API — error-path & boundary contracts.

Complement to tests/missions/test_mission_orchestration.py (which covers the
happy-path lifecycle over the real app). This suite pins the routes' FAILURE
contracts using the repo-standard minimal-app pattern (same as
tests/api/routes/test_mcp_hub.py — owner-approved for contract suites):

    minimal FastAPI app + the missions router + an in-memory SQLite engine
    with ONLY the two missions tables + ``get_db_session`` dependency
    overridden + per-test principal via ``get_current_user_token`` override.

WHY not the shared conftest app here: the CI api/security matrix jobs run the
app engine against the real postgres test service, whose driver config rejects
SSL upgrades for raw engine connections; these contracts are about the ROUTER's
behavior (status mapping, ownership gates, SSE framing), not the DB backend.
The real-app mount itself is guaranteed by tests/api/test_router_mount_
hygiene.py.

Contracts pinned:

- principal hardening: a token payload WITHOUT any subject claim is a 403
  (identity is ALWAYS derived from the principal, never the body)
- malformed mission ids are 404 — never 500 from uuid parsing
- cross-user access is 404 (existence not leaked) on EVERY endpoint family,
  while admins may read AND operate cross-owner
- the illegal-transition 409 mapping for every transition endpoint
- the fail endpoint's reason contract (body reason vs 'unspecified failure')
- cancel legality from PLANNED and illegality from SUCCEEDED
- repair exhaustion surfaces as 409 over HTTP once strategy options are gone
- the trace endpoint's shape (mission_id echo, sorted seqs)
- the SSE stream's auth/ownership gate BEFORE streaming + event framing
- pagination validation bounds (ge/le on skip/limit)
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio

# বাংলা মন্তব্য: SQLAlchemy asyncio ইঞ্জিনের (sqlite+aiosqlite) জন্য greenlet আবশ্যক — CI runner-এ অনুপস্থিত থাকলে টেস্ট স্কিপ
pytest.importorskip(
    "greenlet", reason="greenlet not installed — required for SQLAlchemy asyncio engine"
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.dependencies import get_current_user_token
from database.session import get_db_session

# ---------------------------------------------------------------- fixtures ----


def _make_app() -> FastAPI:
    from api.routes.missions import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def missions_env(monkeypatch):
    """(http, principal_factory) on a fresh in-memory missions DB.

    The SSE endpoint opens its own sessions through
    ``missions.get_db_session_context``; point that at the same engine so the
    stream reads the same data the endpoints write.
    """
    from missions.models import Mission, MissionTraceEvent
    from models.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[Mission.__table__, MissionTraceEvent.__table__],
            )
        )
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_session():
        async with maker() as session:
            yield session

    @asynccontextmanager
    async def _override_session_context():
        async with maker() as session:
            yield session

    import api.routes.missions as missions_module

    app = _make_app()
    app.dependency_overrides[get_db_session] = _override_session
    monkeypatch.setattr(missions_module, "get_db_session_context", _override_session_context)

    def install_principal(sub: str, role: str = "user") -> str:
        app.dependency_overrides[get_current_user_token] = lambda: {
            "sub": sub,
            "role": role,
            "tenant_id": "test-tenant",
        }
        return sub

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        yield http, install_principal

    app.dependency_overrides.clear()
    await engine.dispose()


async def _create(http, principal, *, sub: str | None = None, **overrides) -> str:
    """Create a mission over HTTP; returns its id."""
    sub = sub or f"user-{uuid.uuid4().hex[:10]}"
    principal(sub)
    payload = {
        "title": "Boundary mission",
        "goal_text": "Probe the contract",
        "strategy_options": ["plan-a", "plan-b"],
        "phases": [{"name": "phase-1"}, {"name": "phase-2"}],
    }
    payload.update(overrides)
    resp = await http.post("/api/v1/missions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ------------------------------------------------------------- identity ------


@pytest.mark.asyncio
async def test_missing_principal_claims_403(missions_env):
    """A token payload with no usable subject cannot create missions —
    ownership MUST be derivable (403, not an anonymous-owned row). install("")
    yields a principal whose stripped subject is empty, which is exactly the
    rejected shape."""
    http, install = missions_env
    install("")

    resp = await http.post(
        "/api/v1/missions",
        json={"title": "t", "goal_text": "g"},
    )
    assert resp.status_code == 403, resp.text
    assert "Authenticated principal required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_bad_uuid_is_404_not_500(missions_env):
    """Malformed mission ids parse-fail into 404 across endpoint families."""
    http, install = missions_env
    install("user-baduuid")
    for method, path in (
        ("GET", "/api/v1/missions/not-a-uuid"),
        ("POST", "/api/v1/missions/not-a-uuid/approve"),
        ("GET", "/api/v1/missions/not-a-uuid/trace"),
        ("GET", "/api/v1/missions/not-a-uuid/trace/stream"),
    ):
        resp = await http.request(method, path)
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"
        assert resp.json()["detail"] == "Mission not found"


# --------------------------------------------------------- cross-user 404 ----


@pytest.mark.asyncio
async def test_foreign_mission_404_on_approve_and_trace(missions_env):
    """Ownership gate covers every route family — operations and audit reads
    must not be usable against a foreign mission either."""
    http, install = missions_env
    owner_sub = f"owner-{uuid.uuid4().hex[:8]}"
    mid = await _create(http, install, sub=owner_sub)

    stranger = f"stranger-{uuid.uuid4().hex[:8]}"
    install(stranger)
    for method, path in (
        ("GET", f"/api/v1/missions/{mid}"),
        ("POST", f"/api/v1/missions/{mid}/approve"),
        ("GET", f"/api/v1/missions/{mid}/trace"),
        ("GET", f"/api/v1/missions/{mid}/trace/stream"),
    ):
        resp = await http.request(method, path)
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_admin_reads_and_operates_cross_owner(missions_env):
    """Admins are the ONLY cross-owner principals: read + transition must work
    against a user-owned mission (404 for users, 200 for admin)."""
    http, install = missions_env
    owner_sub = f"owner-{uuid.uuid4().hex[:8]}"
    mid = await _create(http, install, sub=owner_sub)

    install("the-admin", role="admin")
    got = await http.get(f"/api/v1/missions/{mid}")
    assert got.status_code == 200, got.text
    assert got.json()["owner_id"] == owner_sub

    approved = await http.post(f"/api/v1/missions/{mid}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "assigned"


# ------------------------------------------------- transition error maps -----


@pytest.mark.asyncio
async def test_illegal_transitions_map_to_409(missions_env):
    """Every transition endpoint funnels IllegalTransition -> 409."""
    http, install = missions_env
    mid = await _create(http, install)  # planned
    cases = (
        ("POST", f"/api/v1/missions/{mid}/start"),  # planned -> start illegal
        ("POST", f"/api/v1/missions/{mid}/advance"),  # planned -> advance illegal
        ("POST", f"/api/v1/missions/{mid}/repair"),  # planned -> repair illegal
    )
    for method, path in cases:
        resp = await http.request(method, path)
        assert resp.status_code == 409, f"{method} {path} -> {resp.status_code}: {resp.text}"

    # approve on RUNNING (approve again after the first approve -> assigned;
    # approve from assigned is illegal too).
    await http.post(f"/api/v1/missions/{mid}/approve")
    again = await http.post(f"/api/v1/missions/{mid}/approve")
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_cancel_from_planned_ok_but_from_succeeded_409(missions_env):
    """cancel is legal from planned/approved/assigned/running and terminal
    states reject it."""
    http, install = missions_env
    mid1 = await _create(http, install)
    cancelled = await http.post(f"/api/v1/missions/{mid1}/cancel", json={"reason": "changed mind"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "cancelled"

    # Drive one to SUCCEEDED then try to cancel it.
    mid2 = await _create(http, install, phases=[{"name": "only"}])
    await http.post(f"/api/v1/missions/{mid2}/approve")
    await http.post(f"/api/v1/missions/{mid2}/start")
    await http.post(f"/api/v1/missions/{mid2}/advance")  # last phase -> succeeded
    late = await http.post(f"/api/v1/missions/{mid2}/cancel")
    assert late.status_code == 409, late.text


@pytest.mark.asyncio
async def test_fail_reason_from_body_and_default(missions_env):
    """fail stamps the body's reason; with NO body it stamps the documented
    'unspecified failure' default."""
    http, install = missions_env
    mid1 = await _create(http, install)
    await http.post(f"/api/v1/missions/{mid1}/approve")
    await http.post(f"/api/v1/missions/{mid1}/start")
    failed = await http.post(f"/api/v1/missions/{mid1}/fail", json={"reason": "sandbox exploded"})
    assert failed.status_code == 200, failed.text
    body = failed.json()
    assert body["state"] == "failed"
    assert body["failure_reason"] == "sandbox exploded"

    mid2 = await _create(http, install)
    await http.post(f"/api/v1/missions/{mid2}/approve")
    await http.post(f"/api/v1/missions/{mid2}/start")
    failed2 = await http.post(f"/api/v1/missions/{mid2}/fail")
    assert failed2.status_code == 200, failed2.text
    assert failed2.json()["failure_reason"] == "unspecified failure"


@pytest.mark.asyncio
async def test_repair_exhaustion_409_over_http(missions_env):
    """After MAX_REPAIRS rotations the next repair request is a 409 — the
    mission is terminally failed."""
    from missions.state_machine import MAX_REPAIRS

    http, install = missions_env
    mid = await _create(http, install, options=("a", "b"))
    await http.post(f"/api/v1/missions/{mid}/approve")
    await http.post(f"/api/v1/missions/{mid}/start")
    for _ in range(MAX_REPAIRS):
        await http.post(f"/api/v1/missions/{mid}/fail", json={"reason": "again"})
        repaired = await http.post(f"/api/v1/missions/{mid}/repair")
        assert repaired.status_code == 200, repaired.text
        assert repaired.json()["state"] == "running"

    await http.post(f"/api/v1/missions/{mid}/fail", json={"reason": "final"})
    exhausted = await http.post(f"/api/v1/missions/{mid}/repair")
    assert exhausted.status_code == 409, exhausted.text
    assert "repair" in exhausted.json()["detail"].lower()


# ----------------------------------------------------------------- trace -----


@pytest.mark.asyncio
async def test_trace_shape_and_mission_id_echo(missions_env):
    http, install = missions_env
    mid = await _create(http, install)
    await http.post(f"/api/v1/missions/{mid}/approve")

    trace = await http.get(f"/api/v1/missions/{mid}/trace")
    assert trace.status_code == 200, trace.text
    body = trace.json()
    assert body["mission_id"] == mid
    assert body["count"] >= 2  # created + approved
    seqs = [e["seq"] for e in body["items"]]
    assert seqs == sorted(seqs) and seqs[0] == 1
    assert all(e["mission_id"] == mid for e in body["items"])


# ------------------------------------------------------------------- SSE -----


@pytest.mark.asyncio
async def test_sse_stream_frames_events(missions_env):
    """The stream emits 'event: mission_trace' SSE frames for existing events;
    the client disconnect close is a normal exit (CancelledError re-raised
    inside the generator)."""
    http, install = missions_env
    mid = await _create(http, install)
    await http.post(f"/api/v1/missions/{mid}/approve")

    async with http.stream("GET", f"/api/v1/missions/{mid}/trace/stream") as resp:
        assert resp.status_code == 200, await resp.aread()
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache"
        frames = []
        async for line in resp.aiter_lines():
            frames.append(line)
            if len([f for f in frames if f.startswith("event: mission_trace")]) >= 2:
                break  # got the existing events; close early (bounded loop)
    data_lines = [f for f in frames if f.startswith("data: ")]
    assert data_lines, "SSE frames must carry data payloads"


@pytest.mark.asyncio
async def test_sse_stream_gated_before_streaming(missions_env):
    """Authz happens BEFORE the stream opens: bad id and foreign mission both
    get a plain 404 response, not a half-open event stream."""
    http, install = missions_env
    owner_sub = f"owner-{uuid.uuid4().hex[:8]}"
    mid = await _create(http, install, sub=owner_sub)

    install(f"other-{uuid.uuid4().hex[:8]}")
    foreign = await http.get(f"/api/v1/missions/{mid}/trace/stream")
    assert foreign.status_code == 404, foreign.text


# ------------------------------------------------------------ list bounds ----


@pytest.mark.asyncio
async def test_list_pagination_bounds_422(missions_env):
    http, install = missions_env
    install(f"user-{uuid.uuid4().hex[:8]}")
    for query in ("limit=0", "limit=101", "skip=-1"):
        resp = await http.get(f"/api/v1/missions?{query}")
        assert resp.status_code == 422, f"{query} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_list_limit_caps_at_100(missions_env):
    http, install = missions_env
    install(f"user-{uuid.uuid4().hex[:8]}")
    listed = await http.get("/api/v1/missions?limit=100&skip=0")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["limit"] == 100 and body["skip"] == 0
    assert set(body.keys()) == {"items", "count", "skip", "limit"}
