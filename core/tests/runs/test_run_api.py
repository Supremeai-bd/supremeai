"""M1-C — canonical Run API contract tests (/api/v1/runs).

Drives the REAL app through httpx ASGITransport with the conftest test-auth
bypass environment (missions-test pattern): the runs tables are created on
the app engine's sqlite test.db, principals are simulated with a
dependency-level override of ``get_current_user_token``.

Covers the async-boundary contract (create -> run_id ack -> poll), the
404-ownership policy (foreign run not leaked), transition 409s, usage
admission control, retry/classify/cancel, and the audit event read path.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

# The runs router is imported for its side effect of registering nothing —
# mounting happens through api/routers.py (registry); these tests go through
# the real app, so no import is needed here beyond the override target.


@pytest_asyncio.fixture
async def runs_api_tables(client):
    """Create the runs tables on the app engine's sqlite test database."""
    global _tables_ready
    if not _tables_ready:
        import database.session as dbs
        from missions.models import Mission
        from models.base import Base
        from runs.models import Run, RunEvent

        dbs.init_engine()
        engine = dbs.engine
        assert engine.url.get_backend_name() == "sqlite", (
            f"expected sqlite test engine, got {engine.url}"
        )
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[Mission.__table__, Run.__table__, RunEvent.__table__],
                )
            )
        _tables_ready = True
    yield


_tables_ready = False


@pytest_asyncio.fixture
async def principal(client):
    """Per-test principal factory (missions-test pattern)."""
    from api.dependencies import get_current_user_token
    from core.app import app as application

    def install(sub: str, role: str = "user"):
        application.dependency_overrides[get_current_user_token] = lambda: {
            "sub": sub,
            "role": role,
            "tenant_id": "test-tenant",
        }
        return sub

    yield install
    application.dependency_overrides.pop(get_current_user_token, None)


async def _create_run(client, principal, *, sub=None, **overrides) -> tuple[dict, str]:
    sub = sub or f"user-{uuid.uuid4().hex[:10]}"
    principal(sub)
    payload = {"run_type": "tool", "title": "HTTP run"}
    payload.update(overrides)
    resp = await client.post("/api/v1/runs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json(), sub


class TestAsyncBoundary:
    @pytest.mark.asyncio
    async def test_create_returns_ack_with_poll_path(self, client, runs_api_tables, principal):
        ack, sub = await _create_run(client, principal)
        assert ack["status"] == "requested"
        assert ack["poll"] == f"/api/v1/runs/{ack['run_id']}"

    @pytest.mark.asyncio
    async def test_poll_ack_then_full_lifecycle(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal)
        rid = ack["run_id"]

        got = await client.get(f"/api/v1/runs/{rid}")
        assert got.status_code == 200
        assert got.json()["status"] == "requested"

        for nxt in ("policy_checked", "planned", "running"):
            resp = await client.post(f"/api/v1/runs/{rid}/transition", json={"to": nxt})
            assert resp.status_code == 200, resp.text
        assert (await client.get(f"/api/v1/runs/{rid}")).json()["started_at"] is not None

        resp = await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "succeeded"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["terminal_at"] is not None

    @pytest.mark.asyncio
    async def test_idempotent_create_returns_same_run(self, client, runs_api_tables, principal):
        ack1, sub = await _create_run(client, principal, idempotency_key="op-key-1")
        principal(sub)  # same principal
        resp = await client.post(
            "/api/v1/runs", json={"run_type": "tool", "idempotency_key": "op-key-1"}
        )
        assert resp.status_code == 201
        assert resp.json()["run_id"] == ack1["run_id"]

    @pytest.mark.asyncio
    async def test_invalid_run_type_422(self, client, runs_api_tables, principal):
        resp = await client.post("/api/v1/runs", json={"run_type": "warp"})
        assert resp.status_code == 422


class TestOwnership:
    @pytest.mark.asyncio
    async def test_foreign_run_404_not_leaked(self, client, runs_api_tables, principal):
        ack, _owner = await _create_run(client, principal, sub="owner-1")
        principal("attacker-1")
        resp = await client.get(f"/api/v1/runs/{ack['run_id']}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_sees_all_runs(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal, sub="owner-2")
        principal("boss-1", role="admin")
        resp = await client.get(f"/api/v1/runs/{ack['run_id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_scopes_to_owner(self, client, runs_api_tables, principal):
        ack, sub = await _create_run(client, principal, sub="owner-3")
        principal("owner-3")
        mine = (await client.get("/api/v1/runs")).json()
        assert any(r["id"] == ack["run_id"] for r in mine)
        principal("stranger-3")
        theirs = (await client.get("/api/v1/runs")).json()
        assert all(r["id"] != ack["run_id"] for r in theirs)

    @pytest.mark.asyncio
    async def test_list_filters_by_status_and_run_type(self, client, runs_api_tables, principal):
        """?status= and ?run_type= query filters narrow the listing (contract)."""
        ack_t, sub = await _create_run(client, principal, sub="filter-owner", run_type="tool")
        await _create_run(client, principal, sub="filter-owner", run_type="agent")

        principal("filter-owner")
        # run_type filter: only the tool run matches
        tools = (await client.get("/api/v1/runs", params={"run_type": "tool"})).json()
        assert tools, "expected at least one tool run"
        assert all(r["run_type"] == "tool" for r in tools)
        assert any(r["id"] == ack_t["run_id"] for r in tools)

        # status filter: nothing is policy_checked yet -> empty
        checked = (await client.get("/api/v1/runs", params={"status": "policy_checked"})).json()
        assert checked == []
        await client.post(
            f"/api/v1/runs/{ack_t['run_id']}/transition", json={"to": "policy_checked"}
        )
        checked = (await client.get("/api/v1/runs", params={"status": "policy_checked"})).json()
        assert [r["id"] for r in checked] == [ack_t["run_id"]]

    @pytest.mark.asyncio
    async def test_non_uuid_run_id_404(self, client, runs_api_tables, principal):
        """A malformed run id must 404 (no 500/422 leak from uuid parsing)."""
        principal("probe-user")
        for path in ("not-a-uuid", "%20", "1234"):
            resp = await client.get(f"/api/v1/runs/{path}")
            assert resp.status_code == 404, (path, resp.status_code, resp.text)

    @pytest.mark.asyncio
    async def test_empty_principal_403(self, client, runs_api_tables):
        """A token payload with no sub/user_id/email must 403 (identity required)."""
        from api.dependencies import get_current_user_token
        from core.app import app as application

        application.dependency_overrides[get_current_user_token] = lambda: {"role": "user"}
        try:
            resp = await client.post("/api/v1/runs", json={"run_type": "tool"})
            assert resp.status_code == 403, (resp.status_code, resp.text)
            assert resp.json()["detail"] == "Authenticated principal required"
        finally:
            application.dependency_overrides.pop(get_current_user_token, None)


class TestTransitionsAndGuards:
    @pytest.mark.asyncio
    async def test_illegal_transition_409(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal)
        resp = await client.post(f"/api/v1/runs/{ack['run_id']}/transition", json={"to": "planned"})
        assert resp.status_code == 409
        assert "illegal run transition" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_usage_admission_control(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal, max_tokens=10)
        rid = ack["run_id"]
        for nxt in ("policy_checked", "planned", "running"):
            await client.post(f"/api/v1/runs/{rid}/transition", json={"to": nxt})
        ok = await client.post(f"/api/v1/runs/{rid}/usage", json={"tokens": 8})
        assert ok.json()["tokens_used"] == 8
        refused = await client.post(f"/api/v1/runs/{rid}/usage", json={"tokens": 8})
        assert refused.json()["tokens_used"] == 8  # overspend did NOT land

    @pytest.mark.asyncio
    async def test_classify_then_retry_then_exhaust(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal, max_retries=1)
        rid = ack["run_id"]
        for nxt in ("policy_checked", "planned", "running"):
            await client.post(f"/api/v1/runs/{rid}/transition", json={"to": nxt})
        resp = await client.post(
            f"/api/v1/runs/{rid}/classify",
            json={"retry_class": "transient", "error": "blip"},
        )
        assert resp.json()["retry_class"] == "transient"

        retry1 = await client.post(f"/api/v1/runs/{rid}/retry", json={})
        assert retry1.json()["status"] == "retrying"
        await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "running"})
        retry2 = await client.post(f"/api/v1/runs/{rid}/retry", json={})
        assert retry2.status_code == 409  # budget exhausted
        assert "retry budget exhausted" in retry2.json()["detail"]

    @pytest.mark.asyncio
    async def test_classify_invalid_class_422(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal)
        resp = await client.post(
            f"/api/v1/runs/{ack['run_id']}/classify", json={"retry_class": "meteor"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_then_finalize_sealed(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal)
        rid = ack["run_id"]
        await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "policy_checked"})
        await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "planned"})
        await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "running"})
        cancelled = await client.post(
            f"/api/v1/runs/{rid}/cancel",
            json={"actor": "user", "reason": "changed mind"},
        )
        assert cancelled.json()["status"] == "cancelled"
        sealed = await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "finalized"})
        assert sealed.json()["status"] == "finalized"
        # FINALIZED is audit-locked: nothing further
        locked = await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "running"})
        assert locked.status_code == 409


class TestAuditStream:
    @pytest.mark.asyncio
    async def test_events_endpoint_returns_ordered_stream(self, client, runs_api_tables, principal):
        ack, _ = await _create_run(client, principal, title="audited")
        rid = ack["run_id"]
        await client.post(f"/api/v1/runs/{rid}/transition", json={"to": "policy_checked"})
        await client.post(f"/api/v1/runs/{rid}/usage", json={"tokens": 5})

        events = (await client.get(f"/api/v1/runs/{rid}/events")).json()
        kinds = [e["event"] for e in events]
        assert kinds[0] == "run_created"
        assert "status_transition" in kinds
        assert "usage_recorded" in kinds
        assert [e["seq"] for e in events] == list(range(1, len(events) + 1))

    @pytest.mark.asyncio
    async def test_missing_run_404(self, client, runs_api_tables, principal):
        missing = await client.get(f"/api/v1/runs/{uuid.uuid4()}")
        assert missing.status_code == 404
