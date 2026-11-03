"""Issue #1657 (P1 security audit) — typed Pydantic request models for the
``api/routes/browser`` package's crown-jewel + surf-control endpoints.

Previously nine POST endpoints accepted bare ``dict`` bodies (no model, no
URL validation, no action-type check):

    _surf_controls.py  : resume_surf, skip_auth, pause_manual  (dict[str, str])
    _learning.py       : toggle_learning                       (dict[str, bool])
    _crown_jewel.py    : browse_session, ai_action, security_scan,
                         capture_screenshot                    (dict[str, Any])
    _surf_actions.py   : simulate_activity                     (dict)

Every handler now takes a Pydantic model. These tests pin:

* model-level validation (bad URL scheme → error, unknown action → error,
  wrong types → error, forbidden extras → error);
* live-router behaviour — frontend-shaped payloads still succeed (backward
  compatibility with the real callers in CrownJewelBrowser.tsx /
  useBrowserActions.ts) and the retired /simulate-activity still 501s.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

# ──────────────────────────────────────────────
# Model-level validation (no app, no network)
# ──────────────────────────────────────────────


@pytest.mark.unit
class TestCrownJewelRequestModels:
    """Direct validation contract of the new request models."""

    def test_ai_action_accepts_all_documented_actions(self):
        from api.routes.browser._crown_jewel import AIActionRequest

        for action in ("summarize", "explain", "extract_links", "find_issues", "interact"):
            req = AIActionRequest(action=action, url="https://example.com", context="page")
            assert req.action == action

    def test_ai_action_rejects_unknown_action(self):
        from api.routes.browser._crown_jewel import AIActionRequest

        with pytest.raises(ValidationError):
            AIActionRequest(action="mystery", url="https://example.com", context="ctx")

    def test_ai_action_rejects_non_http_url(self):
        from api.routes.browser._crown_jewel import AIActionRequest

        with pytest.raises(ValidationError):
            AIActionRequest(action="summarize", url="ftp://example.com", context="ctx")

    def test_ai_action_allows_empty_url_and_defaults(self):
        from api.routes.browser._crown_jewel import AIActionRequest

        req = AIActionRequest(context="just context")
        assert req.action == "summarize"
        assert req.url == ""
        assert req.payload is None

    def test_security_scan_requires_url(self):
        from api.routes.browser._crown_jewel import SecurityScanRequest

        with pytest.raises(ValidationError):
            SecurityScanRequest()  # missing required url
        with pytest.raises(ValidationError):
            SecurityScanRequest(url="not-a-url")  # no scheme
        assert SecurityScanRequest(url="https://example.com").url == "https://example.com"

    def test_screenshot_model_defaults_and_url_check(self):
        from api.routes.browser._crown_jewel import ScreenshotRequest

        req = ScreenshotRequest(url="http://example.com")
        assert req.full_page is False
        with pytest.raises(ValidationError):
            ScreenshotRequest(url="javascript:alert(1)")

    def test_browse_session_ignores_frontend_extras(self):
        from api.routes.browser._crown_jewel import BrowseSessionRequest

        # Exact shape sent by CrownJewelBrowser.tsx — timestamp/tabId must be
        # tolerated (ignored), url must still be scheme-checked.
        req = BrowseSessionRequest(url="https://example.com", timestamp=1, tabId="t1")
        assert req.url == "https://example.com"
        with pytest.raises(ValidationError):
            BrowseSessionRequest(url="internal-thing", timestamp=1)

    def test_toggle_learning_strict_bool_and_forbidden_extras(self):
        from api.routes.browser._learning import ToggleLearningRequest

        assert ToggleLearningRequest().enabled is True
        assert ToggleLearningRequest(enabled=False).enabled is False
        with pytest.raises(ValidationError):
            ToggleLearningRequest(enabled="false")  # string, not bool
        with pytest.raises(ValidationError):
            ToggleLearningRequest(enabled=True, rogue="x")  # forbidden extra

    def test_surf_control_request_forbids_any_field(self):
        from api.routes.browser._surf_controls import SurfControlRequest

        SurfControlRequest()  # empty body is valid
        with pytest.raises(ValidationError):
            SurfControlRequest(anything="x")

    def test_simulate_activity_model_is_typed_and_permissive(self):
        from api.routes.browser._surf_actions import SimulateActivityRequest

        req = SimulateActivityRequest()  # no fields required
        assert req.model_dump() == {}
        # Legacy payload keys are accepted and silently dropped (ignored).
        assert SimulateActivityRequest.model_validate({"url": "https://x.com"}).model_dump() == {}


# ──────────────────────────────────────────────
# Live-router behaviour (real api.routes.browser router)
# ──────────────────────────────────────────────


@pytest_asyncio.fixture
async def pkg_env():
    """Mount the REAL browser package router with auth dependencies overridden.

    The production router-level guards (``get_current_user_token``) and the
    admin-token guard used by the surf-control routes are replaced by a stub
    admin identity — this suite validates request-model behaviour, not auth.
    """
    from api.deps import get_current_user_token
    from api.routes.admin_dashboard import require_admin_token
    from api.routes.browser import router

    stub = {"sub": "pkg-test-admin", "role": "admin", "tenant_id": "t1"}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_token] = lambda: stub
    app.dependency_overrides[require_admin_token] = lambda: stub
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestRouterModelEnforcement:
    """The registered routes must reject what the models reject — at HTTP."""

    async def test_browse_session_frontend_shape_still_works(self, pkg_env):
        resp = await pkg_env.post(
            "/api/browser/browse-session",
            json={"url": "https://example.com", "timestamp": 12, "tabId": "t9"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
        assert resp.json()["session_id"].startswith("sess_")

    async def test_browse_session_bad_url_is_422(self, pkg_env):
        resp = await pkg_env.post("/api/browser/browse-session", json={"url": "nope"})
        assert resp.status_code == 422

    async def test_security_scan_bad_url_is_422(self, pkg_env):
        resp = await pkg_env.post("/api/browser/security-scan", json={"url": "not-a-url"})
        assert resp.status_code == 422

    async def test_ai_action_unknown_action_is_422(self, pkg_env):
        resp = await pkg_env.post(
            "/api/browser/ai-action", json={"action": "mystery", "context": "ctx"}
        )
        assert resp.status_code == 422

    async def test_ai_action_empty_context_is_422_with_known_detail(self, pkg_env):
        resp = await pkg_env.post(
            "/api/browser/ai-action",
            json={"action": "summarize", "context": "   "},
        )
        assert resp.status_code == 422
        assert "No page context provided" in resp.json()["detail"]

    async def test_screenshot_bad_url_is_422(self, pkg_env):
        resp = await pkg_env.post("/api/browser/screenshot", json={"url": "file:///etc"})
        assert resp.status_code == 422

    async def test_toggle_learning_toggles_state(self, pkg_env):
        from api.routes.browser._learning import SYSTEM_LEARNING

        resp = await pkg_env.post("/api/browser/system-learning/toggle", json={"enabled": False})
        assert resp.status_code == 200
        assert SYSTEM_LEARNING["enabled"] is False
        resp = await pkg_env.post("/api/browser/system-learning/toggle", json={"enabled": True})
        assert resp.status_code == 200
        assert SYSTEM_LEARNING["enabled"] is True

    async def test_toggle_learning_rejects_wrong_type(self, pkg_env):
        resp = await pkg_env.post("/api/browser/system-learning/toggle", json={"enabled": "false"})
        assert resp.status_code == 422

    async def test_surf_resume_rejects_extra_fields(self, pkg_env):
        resp = await pkg_env.post("/api/browser/surf/resume", json={"unexpected": 1})
        assert resp.status_code == 422

    async def test_surf_pause_resume_roundtrip(self, pkg_env):
        resp = await pkg_env.post("/api/browser/surf/pause-manual", json={})
        assert resp.status_code == 200
        assert resp.json() == {"status": "paused_for_manual"}
        assert (await pkg_env.get("/api/browser/surf/paused-state")).json() == {"paused": True}
        resp = await pkg_env.post("/api/browser/surf/resume", json={})
        assert resp.status_code == 200
        assert (await pkg_env.get("/api/browser/surf/paused-state")).json() == {"paused": False}

    async def test_simulate_activity_still_retired_501(self, pkg_env):
        resp = await pkg_env.post(
            "/api/browser/simulate-activity",
            json={"url": "https://x.com", "action": "surf", "title": "fake"},
        )
        assert resp.status_code == 501
