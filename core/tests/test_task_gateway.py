import pytest
from httpx import ASGITransport, AsyncClient

from core.app import app


@pytest.mark.asyncio
async def test_task_gateway_lifecycle():
    # ── Self-sufficient schema setup (CI FIX 2026-09-16) ────────────────────
    # This test drives the app directly (no db_engine fixture), so NOTHING
    # guarantees the `task_records` table exists: on a clean CI checkout the
    # app's SQLite fallback engine starts with zero tables and the first
    # INSERT failed with "no such table: task_records" — passing only through
    # ordering-dependent cross-test pollution. Create the exact table this
    # endpoint owns (checkfirst). NOTE: Base.metadata.create_all() is NOT
    # usable here — the app imports only a subset of models, and a partial
    # metadata raises NoReferencedTableError (execution_logs → agent_sessions).
    import models.task_record  # noqa: F401  (model registration side-effect)
    from database import session as db_session

    db_session.init_engine()
    engine = db_session._engine_instance
    assert engine is not None, (
        "task gateway requires a working DB engine — SQLite fallback must be active in test env"
    )
    from models.task_record import TaskRecord

    async with engine.begin() as conn:
        await conn.run_sync(TaskRecord.__table__.create, checkfirst=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test submit task
        submit_res = await client.post(
            "/api/v1/tasks",
            json={"goal": "Test background task", "metadata": {"priority": "high"}},
            headers={"Authorization": "Bearer mock-token", "X-Tenant-ID": "tenant_test"},
        )
        assert submit_res.status_code == 200
        data = submit_res.json()
        task_id = data["task_id"]
        assert data["status"] == "pending"

        # 2. Test get status
        status_res = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers={"Authorization": "Bearer mock-token", "X-Tenant-ID": "tenant_test"},
        )
        assert status_res.status_code == 200
        assert status_res.json()["task_id"] == task_id

        # 3. Test cancel task
        cancel_res = await client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers={"Authorization": "Bearer mock-token", "X-Tenant-ID": "tenant_test"},
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # A different tenant must not be able to discover the task.
        # NOTE (contract update, CI FIX 2026-09-16): tenant scoping now comes
        # from VERIFIED JWT claims ONLY (AuthMiddleware hardening — AUDIT-SEC-9
        # class fixes; the X-Tenant-ID header is intentionally ignored, and the
        # test-auth bypass yields a fixed tenant). So cross-tenant isolation is
        # asserted against the endpoint's ownership contract directly: looking
        # the task up under a foreign tenant must raise 404.
        from fastapi import HTTPException as _HTTPException

        from api.routes.task_gateway import _owned_record

        with pytest.raises(_HTTPException) as excinfo:
            await _owned_record(task_id, "tenant_other")
        assert excinfo.value.status_code == 404
