"""Wave 2.3 truth purge (issue #1240) — legacy /surf/* endpoint retirement.

The legacy surf endpoints in ``api/routes/browser/_surf_actions.py`` previously
returned fabricated success: a hardcoded 1x1 transparent PNG as "screenshot",
navigate/click/fill handlers that only appended to an in-memory list, a canned
accessibility tree, and an activity-injection endpoint. Per the "real work or
loud failure" doctrine (issue #445) they now raise 501 with a pointer to the
real owner-scoped automation stack (``/api/browser/automation/*``).

These tests mount the REAL ``api.routes.browser`` package router (the one the
server registers via ``api/routers.py``) and pin the loud-fail contract.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def surf_env():
    """Mount the real browser package router (conftest provides the auth bypass)."""
    from api.routes.browser import router

    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


RETIRED_ENDPOINTS = (
    ("GET", "/api/browser/surf/screenshot", None),
    ("POST", "/api/browser/surf/navigate", {"url": "https://example.com"}),
    ("POST", "/api/browser/surf/click", {"selector": "#btn"}),
    ("POST", "/api/browser/surf/fill", {"selector": "#input", "value": "x"}),
    ("POST", "/api/browser/surf/click-at", {"x": 1, "y": 2}),
    ("POST", "/api/browser/surf/type-key", {"key": "Enter"}),
    ("GET", "/api/browser/surf/accessibility", None),
    ("POST", "/api/browser/simulate-activity", {"url": "https://x.com", "action": "surf"}),
)


@pytest.mark.unit
class TestSurfEndpointsRetired:
    """Class-G false-assurance regression gate: no fabricated success allowed."""

    @pytest.mark.parametrize("method,path,payload", RETIRED_ENDPOINTS)
    async def test_retired_endpoints_fail_loudly_501(self, surf_env, method, path, payload):
        fn = getattr(surf_env, method.lower())
        kwargs = {"json": payload} if payload is not None else {}
        resp = await fn(path, **kwargs)
        assert resp.status_code == 501, f"{method} {path} must fail loudly, got {resp.status_code}"
        detail = resp.json()["detail"]
        assert "retired" in detail
        # The loud failure must route callers to the REAL automation stack.
        assert "/api/browser/automation/sessions" in detail

    async def test_screenshot_never_returns_placeholder_png(self, surf_env):
        """Regression: the old handler returned a hardcoded 1x1 transparent PNG."""
        resp = await surf_env.get("/api/browser/surf/screenshot")
        body = resp.json()
        assert "screenshot" not in body, "fabricated screenshot payload must be gone"

    async def test_no_fabricated_activity_injection(self, surf_env):
        """Regression: /simulate-activity previously let callers inject fake entries."""
        from api.routes.browser._state import RECENT_ACTIVITIES

        before = len(RECENT_ACTIVITIES)
        resp = await surf_env.post(
            "/api/browser/simulate-activity",
            json={"url": "https://x.com", "action": "surf", "title": "fake"},
        )
        assert resp.status_code == 501
        assert len(RECENT_ACTIVITIES) == before, "no fabricated activity may be injected"

    async def test_real_automation_stack_still_live(self):
        """The REAL owner-scoped automation routes must remain registered."""
        from api.routes.browser import router

        routes = {getattr(r, "path", "") for r in router.routes}
        assert "/api/browser/automation/sessions" in routes
        assert "/api/browser/automation/saved-sessions" in routes
