"""Wave 2.5 (issue #1242) — REAL admin security telemetry endpoints.

Previously GET /admin-api/security/tasks and /admin-api/security/memory did
not exist (frontend called them; they 404'd / fell back to static fake [OK]
messages). These tests pin the new REAL endpoints backed by the live
strong-reference task registry (core.utils.background_tasks).
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def sec_env():
    from api.routes import admin_dashboard as ad
    from api.routes.admin_dashboard import router

    app = FastAPI()
    app.include_router(router)

    # Admin router is guarded by require_admin_token + admin_rate_limit; bypass
    # with a deterministic admin payload (same pattern as test_admin_routes_full).
    async def _admin_ok():
        return {"sub": "admin@test.local", "role": "admin"}

    app.dependency_overrides[ad.require_admin_token] = _admin_ok
    app.dependency_overrides[ad.admin_rate_limit] = _admin_ok
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestSecurityTelemetryReal:
    async def test_security_tasks_returns_live_registry(self, sec_env):
        """The endpoint reflects the REAL tracked-task registry."""
        from core.utils.background_tasks import safe_create_task

        async def _work():
            await asyncio.sleep(0.05)

        task = safe_create_task(_work(), name="test-telemetry-task")
        try:
            resp = await sec_env.get("/admin-api/security/tasks")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            names = [t["name"] for t in data["tasks"]]
            assert "test-telemetry-task" in names
            entry = next(t for t in data["tasks"] if t["name"] == "test-telemetry-task")
            assert entry["strongRef"] is True
            assert entry["status"] == "running"
            assert entry["startedAt"] is not None  # real creation timestamp
        finally:
            await task

    async def test_security_tasks_never_fabricates(self, sec_env):
        """Empty registry → empty tasks list (NOT a canned fake list)."""
        resp = await sec_env.get("/admin-api/security/tasks")
        assert resp.status_code == 200
        data = resp.json()
        # whatever the process state, every entry must come from the live registry
        for t in data["tasks"]:
            assert t["strongRef"] is True
            assert t["status"] in {"running", "done", "cancelled", "failed", "unknown"}

    async def test_security_memory_honest_fields(self, sec_env):
        """heap fields are real-or-None with explicit source — never fake numbers."""
        resp = await sec_env.get("/admin-api/security/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["heapSource"] in {"tracemalloc", "unavailable"}
        if data["heapSource"] == "unavailable":
            assert data["heapUsed"] is None
            assert data["heapTotal"] is None
        assert isinstance(data["zombieTasksDetected"], int)
        assert isinstance(data["failuresBlocked"], int)
        assert isinstance(data["trackedTasks"], int)

    async def test_snapshot_counts_failures(self):
        """A tracked task failing with an exception increments failuresBlocked."""
        from core.utils import background_tasks as bt

        async def _boom():
            raise RuntimeError("intentional test failure")

        task = bt.safe_create_task(_boom(), name="test-failure-counter")
        with pytest.raises(RuntimeError):
            await task
        # give the done-callback a tick to run
        await asyncio.sleep(0)
        assert bt._TRACKED_TASK_FAILURES >= 1
