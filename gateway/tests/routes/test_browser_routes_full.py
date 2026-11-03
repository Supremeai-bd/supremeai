"""Live-contract tests for the consolidated browser route surface (Task #2258).

History: this file was full-coverage for the retired
``api/routes/browser_routes.py`` — a legacy module whose admin router was
permanently shadowed by the ``api.routes.browser`` package (registered first
in ALL_ROUTERS) and whose public router only carried the #1490 health probe.
The Phase 3.2 consolidation (#2258) ported the two LIVE contracts into the
package (``_health.py`` public probe + ``_crown_jewel.py`` gallery endpoint)
and deleted the module, so this suite now pins:

    - /api/browser/health is dependency-free and public (#1490 contract);
    - /api/browser/screenshots gallery entry shape (live FE caller);
    - the crown-jewel surface still resolves on the package router;
    - the retired legacy-only endpoint (/browse-sessions) is really gone.

The shadowed legacy behaviours (InferenceContext ai-action, external
security-scan checkers, shared-browser screenshot, RAG browse-sessions)
were never reachable at runtime and are intentionally NOT re-pinned here —
the live implementations of those paths are the package's, covered by
``test_browser_package_request_models.py``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

PUBLIC_URL = "https://example.com/page"


@pytest_asyncio.fixture
async def pkg_env():
    """Mount the REAL browser package with auth guards overridden (user token).

    Mirrors the pkg_env fixture in test_browser_package_request_models.py:
    this suite validates the consolidated surface's behaviour, not auth.
    """
    from api.deps import get_current_user_token
    from api.routes.admin_dashboard import require_admin_token
    from api.routes.browser import public_router, router

    stub = {"sub": "pkg-test-user", "role": "user", "tenant_id": "t1"}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_token] = lambda: stub
    app.dependency_overrides[require_admin_token] = lambda: stub
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def public_env():
    """Mount ONLY the dependency-free public router — no auth overrides at all.

    This is the #1490 production shape for the health probe: it must answer
    without any credentials, like the core /health/* contract.
    """
    from api.routes.browser import public_router

    app = FastAPI()
    app.include_router(public_router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestHealthProbe:
    """#1490 contract: /api/browser/health is public and dependency-free."""

    async def test_health_public_no_auth(self, public_env):
        resp = await public_env.get("/api/browser/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["service"] == "browser-integration"
        assert body["status"] in ("healthy", "degraded")
        assert len(body["capabilities"]) == 4

    async def test_health_all_available(self, public_env, monkeypatch):
        import api.routes.browser._health as h

        async def ok():
            return True

        for fn in (
            "check_llm_gateway",
            "check_security_modules",
            "check_playwright",
            "check_unified_memory",
        ):
            monkeypatch.setattr(h, fn, ok)
        resp = await public_env.get("/api/browser/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert len(body["capabilities"]) == 4

    async def test_health_degraded_and_error(self, public_env, monkeypatch):
        import api.routes.browser._health as h

        async def ok():
            return True

        async def unavailable():
            return False

        async def explodes():
            raise RuntimeError("check crashed")

        monkeypatch.setattr(h, "check_llm_gateway", ok)
        monkeypatch.setattr(h, "check_security_modules", unavailable)
        monkeypatch.setattr(h, "check_playwright", explodes)
        monkeypatch.setattr(h, "check_unified_memory", ok)
        resp = await public_env.get("/api/browser/health")
        body = resp.json()
        assert body["status"] == "degraded"
        caps = {c["name"]: c for c in body["capabilities"]}
        assert caps["security-scan"]["available"] is False
        assert caps["screenshot"]["available"] is False
        assert "check crashed" in caps["screenshot"]["error"]
        assert caps["ai-action"]["available"] is True

    async def test_real_capability_checks(self, public_env):
        """check_* helpers with real imports (all deps exist in this env)."""
        from api.routes.browser._health import (
            check_llm_gateway,
            check_playwright,
            check_security_modules,
            check_unified_memory,
        )

        assert await check_llm_gateway() is True
        assert await check_security_modules() is True
        assert await check_playwright() is True
        assert await check_unified_memory() is True


@pytest.mark.unit
class TestScreenshotGallery:
    """POST /screenshots — ported from the legacy module (live FE caller:
    admin-browser/useBrowserActions.ts fires it after each capture)."""

    async def test_screenshot_gallery_entry(self, pkg_env):
        resp = await pkg_env.post(
            "/api/browser/screenshots",
            params={"userId": "u1", "url": PUBLIC_URL, "timestamp": 42},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        entry = body["galleryEntry"]
        assert entry["userId"] == "u1"
        assert entry["url"] == PUBLIC_URL
        assert entry["capturedAt"] == 42
        assert "screenshots/u1/" in entry["storageLocation"]

    async def test_gallery_defaults_when_no_params(self, pkg_env):
        resp = await pkg_env.post("/api/browser/screenshots")
        assert resp.status_code == 200
        entry = resp.json()["galleryEntry"]
        assert entry["userId"] is None
        assert "anonymous" in entry["storageLocation"]


@pytest.mark.unit
class TestConsolidationContract:
    """#2258 route-parity guards: the double mount is gone, the live
    crown-jewel surface resolves on the package, the dead legacy-only
    endpoint is retired."""

    async def test_crown_jewel_paths_resolve_on_package(self, pkg_env):
        """The four formerly-shadowed paths still exist (now solely on the
        package router). Method-mismatch (405) proves the route is
        registered; we avoid invoking real browser/LLM work."""
        for path in (
            "/api/browser/ai-action",
            "/api/browser/security-scan",
            "/api/browser/screenshot",
            "/api/browser/browse-session",
        ):
            resp = await pkg_env.get(path)
            assert resp.status_code == 405, f"{path} should be POST-only: {resp.status_code}"

    async def test_browse_sessions_retired(self, pkg_env):
        """GET /browse-sessions had 0 callers and 0 writers (its only writer
        was the shadowed legacy POST) — retired with the legacy module."""
        resp = await pkg_env.get("/api/browser/browse-sessions")
        assert resp.status_code == 404

    async def test_legacy_module_gone(self):
        """The retired module must not be importable (boot-time guarantee)."""
        import importlib.util

        assert importlib.util.find_spec("api.routes.browser_routes") is None

    async def test_registry_has_no_legacy_entry(self):
        from api.routers import ALL_ROUTERS

        paths = [r["path"] for r in ALL_ROUTERS]
        assert "api.routes.browser_routes" not in paths
        assert "api.routes.browser" in paths
