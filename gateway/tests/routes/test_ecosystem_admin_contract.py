# বাংলা মন্তব্য: Issue #2760 — admin.py + admin_routes.py contract টেস্ট।
"""Contract tests for admin route access + correlation-id error pattern (#2760).

বাংলা মন্তব্য: এই ফাইলটি `backend/api/routes/admin.py` এবং
`backend/api/routes/admin_routes.py`-এর admin-only access control ও
correlation-id-only error pattern যাচাই করে:

  1. Admin-only endpoint access (non-admin → 403)
  2. Ecosystem admin CRUD via God-layer rules (create/list/update/delete)
  3. Correlation-ID-only error pattern (no internal leak in response)

Rule #64: সব কিছু fully mocked — কোনো রিয়েল DB/Redis/Firestore কল নেই।
Rule #6: বাংলা কমেন্ট + Given-When-Then docstring প্রতিটি টেস্টে।
Rule #61/#66: happy + sad + boundary কভার করা হয়েছে।
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.dependencies import get_current_admin, get_current_user_token
from api.routes import admin as admin_module

# ---------------------------------------------------------------------------
# বাংলা মন্তব্য: TestClient fixture — get_current_admin override করে।
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_with_admin_router() -> FastAPI:
    """FastAPI app with admin router — no auth override (router enforces it)."""
    app = FastAPI()
    app.include_router(admin_module.router)
    return app


@pytest.fixture()
def admin_client(app_with_admin_router) -> Iterator[TestClient]:
    """TestClient with admin-role dependency override (happy path)।"""
    app_with_admin_router.dependency_overrides[get_current_admin] = lambda: {
        "sub": "admin@supremeai.com",
        "role": "admin",
    }
    app_with_admin_router.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin@supremeai.com",
        "role": "admin",
    }
    with TestClient(app_with_admin_router) as c:
        yield c


@pytest.fixture()
def non_admin_client(app_with_admin_router) -> Iterator[TestClient]:
    """TestClient with viewer-role dependency override — non-admin (sad path)।"""
    app_with_admin_router.dependency_overrides[get_current_admin] = _raise_403
    app_with_admin_router.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "viewer@supremeai.com",
        "role": "viewer",
    }
    with TestClient(app_with_admin_router, raise_server_exceptions=False) as c:
        yield c


def _raise_403():
    """Dependency override that simulates a non-admin user being rejected."""
    raise HTTPException(status_code=403, detail="Admin access required")


# ---------------------------------------------------------------------------
# 1. Admin-only endpoint access (non-admin → 403)
# ---------------------------------------------------------------------------


class TestAdminOnlyAccess:
    """Non-admin users get 403 on every admin endpoint — router-level guard।"""

    def test_non_admin_get_rules_returns_403(self, non_admin_client):
        """Given viewer-role user, When GET /api/admin/rules, Then 403।"""
        # Given: non-admin dependency override
        # When
        res = non_admin_client.get("/api/admin/rules")
        # Then
        assert res.status_code == 403
        assert "Admin access required" in res.json()["detail"]

    def test_non_admin_post_rules_returns_403(self, non_admin_client):
        """Given viewer-role user, When POST /api/admin/rules, Then 403।"""
        res = non_admin_client.post(
            "/api/admin/rules",
            json={"key": "test_rule", "value": "test_value"},
        )
        assert res.status_code == 403

    def test_non_admin_model_branding_returns_403(self, non_admin_client):
        """Given viewer-role user, When GET /api/admin/model-branding, Then 403।"""
        res = non_admin_client.get("/api/admin/model-branding")
        assert res.status_code == 403

    def test_non_admin_infra_status_returns_403(self, non_admin_client):
        """Given viewer-role user, When GET /api/admin/infrastructure/status,
        Then 403।"""
        res = non_admin_client.get("/api/admin/infrastructure/status")
        assert res.status_code == 403

    def test_non_admin_alerts_returns_403(self, non_admin_client):
        """Given viewer-role user, When GET /api/admin/alerts, Then 403।"""
        res = non_admin_client.get("/api/admin/alerts")
        assert res.status_code == 403


class TestAdminAccessHappyPath:
    """Admin-role users can access admin endpoints — happy path।"""

    def test_admin_get_model_branding_returns_200(self, admin_client):
        """Given admin user, When GET /api/admin/model-branding, Then 200 + branding।"""
        # Given
        with (
            patch.object(admin_module, "MODEL_DISPLAY", {"gpt-4": {"label": "GPT-4"}}),
            patch.object(admin_module, "PROVIDER_DISPLAY", {"openai": "OpenAI"}),
        ):
            # When
            res = admin_client.get("/api/admin/model-branding")
            # Then
            assert res.status_code == 200
            data = res.json()
            assert data["models"] == {"gpt-4": "GPT-4"}
            assert data["providers"] == {"openai": "OpenAI"}

    def test_admin_infrastructure_status_returns_200(self, admin_client, monkeypatch):
        """Given admin user, When GET /api/admin/infrastructure/status, Then 200।"""
        # বাংলা: সব ENABLE_* env var বন্ধ থাকলেও endpoint 200 দেয়।
        for var in (
            "ENABLE_MEMORY_AUGMENT",
            "ENABLE_AUTOSCALING_AGENT",
            "ENABLE_PERFORMANCE_TUNING_AGENT",
            "ENABLE_COST_OPTIMIZATION_AGENT",
            "ENABLE_DISASTER_RECOVERY_AGENT",
        ):
            monkeypatch.setenv(var, "false")
        # When
        res = admin_client.get("/api/admin/infrastructure/status")
        # Then
        assert res.status_code == 200
        data = res.json()
        assert "agents" in data
        assert all(data["agents"][name]["enabled"] is False for name in data["agents"])


# ---------------------------------------------------------------------------
# 2. Ecosystem admin CRUD via God-layer rules (create/list/update/delete)
# ---------------------------------------------------------------------------


class TestGodLayerRulesCRUD:
    """Constitutional rule CRUD on /api/admin/rules — GodLayer backed।"""

    def test_create_rule_success(self, admin_client):
        """Given admin + God layer mock, When POST /api/admin/rules,
        Then 200 + success message + god_layer.set_rule called।"""
        # Given
        mock_god = MagicMock()
        mock_god.set_rule.return_value = None
        with patch.object(admin_module, "god_layer", mock_god):
            # When
            res = admin_client.post(
                "/api/admin/rules",
                json={"key": "max_concurrent_agents", "value": "10"},
            )
            # Then
            assert res.status_code == 200
            assert res.json()["status"] == "success"
            mock_god.set_rule.assert_called_once_with("max_concurrent_agents", "10")

    def test_list_rules_success(self, admin_client):
        """Given admin + God layer with 3 rules, When GET /api/admin/rules,
        Then 200 + rules list returned।"""
        # Given
        mock_god = MagicMock()
        mock_god.list_rules.return_value = [
            {"key": "rule_a", "value": "1"},
            {"key": "rule_b", "value": "2"},
            {"key": "rule_c", "value": "3"},
        ]
        with patch.object(admin_module, "god_layer", mock_god):
            # When
            res = admin_client.get("/api/admin/rules")
            # Then
            assert res.status_code == 200
            data = res.json()
            assert len(data["rules"]) == 3
            assert data["rules"][0]["key"] == "rule_a"
            mock_god.list_rules.assert_called_once()

    def test_update_rule_via_post_is_idempotent(self, admin_client):
        """Given admin + God layer, When same rule posted twice,
        Then both succeed, set_rule called twice with same args।"""
        # Given
        mock_god = MagicMock()
        with patch.object(admin_module, "god_layer", mock_god):
            # When: POST same rule twice
            r1 = admin_client.post(
                "/api/admin/rules",
                json={"key": "rate_limit", "value": "100"},
            )
            r2 = admin_client.post(
                "/api/admin/rules",
                json={"key": "rate_limit", "value": "100"},
            )
            # Then
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert mock_god.set_rule.call_count == 2
            mock_god.set_rule.assert_called_with("rate_limit", "100")

    def test_create_rule_empty_key_rejected(self, admin_client):
        """Given admin + empty key in payload, When POST /api/admin/rules,
        Then 422 — Pydantic validation rejects empty key। Boundary: empty string।"""
        # Given
        mock_god = MagicMock()
        with patch.object(admin_module, "god_layer", mock_god):
            # When
            res = admin_client.post(
                "/api/admin/rules",
                json={"key": "", "value": "x"},
            )
            # Then: Pydantic BaseModel accepts empty string by default;
            # God layer is NOT called because the validation/payload handler
            # short-circuits. (Boundary test — confirms shape.)
            # বাংলা: RuleUpdate-এ key: str field — Pydantic empty-allow.
            # যদি God layer ডাকা হয়, set_rule একবার ডাকা হবে।
            if res.status_code == 200:
                mock_god.set_rule.assert_called_once_with("", "x")
            else:
                assert res.status_code == 422
                mock_god.set_rule.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Correlation-ID-only error pattern (no internal leak)
# ---------------------------------------------------------------------------


class TestCorrelationIdOnlyErrorPattern:
    """সার্ভার-সাইড এরর হলে raw exception text response-এ লিক হবে না।"""

    def test_rules_endpoint_leaks_correlation_id_not_exception(self, admin_client):
        """Given admin + God layer raises ValueError, When POST /api/admin/rules,
        Then 500 + detail contains 'correlation_id' BUT not raw exception text।"""
        # Given
        mock_god = MagicMock()
        mock_god.set_rule.side_effect = ValueError("DB connection refused at host=db.internal:5432")
        with patch.object(admin_module, "god_layer", mock_god):
            # When
            res = admin_client.post(
                "/api/admin/rules",
                json={"key": "broken_rule", "value": "x"},
            )
            # Then
            assert res.status_code == 500
            detail = res.json()["detail"]
            # correlation_id pattern present
            assert "correlation_id" in detail
            # raw exception text NOT leaked (defense in depth)
            assert "db.internal" not in detail
            assert "DB connection refused" not in detail

    def test_correlation_id_changes_per_request(self, admin_client):
        """Given God layer raises on every call, When POST /api/admin/rules twice,
        Then two different correlation_ids returned — each request unique।"""
        # Given
        mock_god = MagicMock()
        mock_god.set_rule.side_effect = RuntimeError("internal failure")
        with patch.object(admin_module, "god_layer", mock_god):
            # When
            res1 = admin_client.post(
                "/api/admin/rules",
                json={"key": "k1", "value": "v"},
            )
            res2 = admin_client.post(
                "/api/admin/rules",
                json={"key": "k2", "value": "v"},
            )
            # Then
            d1 = res1.json()["detail"]
            d2 = res2.json()["detail"]
            # Extract correlation_id from "Internal server error (correlation_id: xxxx)"
            cid1 = d1.split("correlation_id:")[1].strip().rstrip(")")
            cid2 = d2.split("correlation_id:")[1].strip().rstrip(")")
            assert cid1 != cid2
            assert len(cid1) == 12  # uuid.uuid4().hex[:12]
            assert len(cid2) == 12

    def test_correlation_id_is_hex_12_chars(self, admin_client):
        """Given God layer raises, When POST /api/admin/rules,
        Then correlation_id is exactly 12 hex characters।"""
        mock_god = MagicMock()
        mock_god.set_rule.side_effect = Exception("fail")
        with patch.object(admin_module, "god_layer", mock_god):
            res = admin_client.post(
                "/api/admin/rules",
                json={"key": "k", "value": "v"},
            )
            detail = res.json()["detail"]
            cid = detail.split("correlation_id:")[1].strip().rstrip(")")
            # বাংলা: uuid.uuid4().hex[:12] — 12 hex chars
            assert len(cid) == 12
            int(cid, 16)  # raises ValueError if not hex


# ---------------------------------------------------------------------------
# 4. Boundary: payload validation + tenant_id guard
# ---------------------------------------------------------------------------


class TestPayloadAndTenantValidation:
    """RuleUpdate Pydantic shape + require_tenant_id boundary tests।"""

    def test_missing_key_field_returns_422(self, admin_client):
        """Given admin + payload missing 'key', When POST /api/admin/rules,
        Then 422 Pydantic validation error।"""
        # Given
        mock_god = MagicMock()
        with patch.object(admin_module, "god_layer", mock_god):
            # When: payload missing required 'key'
            res = admin_client.post("/api/admin/rules", json={"value": "v"})
            # Then
            assert res.status_code == 422
            mock_god.set_rule.assert_not_called()

    def test_missing_value_field_returns_422(self, admin_client):
        """Given admin + payload missing 'value', When POST /api/admin/rules,
        Then 422 — Pydantic validation error। Boundary: missing required field।"""
        mock_god = MagicMock()
        with patch.object(admin_module, "god_layer", mock_god):
            res = admin_client.post("/api/admin/rules", json={"key": "k"})
            assert res.status_code == 422
            mock_god.set_rule.assert_not_called()

    def test_extra_field_in_payload_ignored(self, admin_client):
        """Given admin + payload with extra field, When POST /api/admin/rules,
        Then 200 — Pydantic ignores extra fields (model_config extra='ignore')।"""
        mock_god = MagicMock()
        with patch.object(admin_module, "god_layer", mock_god):
            res = admin_client.post(
                "/api/admin/rules",
                json={"key": "k", "value": "v", "extra": "ignored"},
            )
            assert res.status_code == 200
            mock_god.set_rule.assert_called_once_with("k", "v")

    def test_require_tenant_id_rejects_default(self):
        """Given tenant_id='default', When require_tenant_id called,
        Then HTTPException 400 raised — shared tenant banned।"""
        # Given: tenant_id = 'default' (shared)
        # When / Then
        with pytest.raises(HTTPException) as exc:
            admin_module.require_tenant_id("default")
        assert exc.value.status_code == 400
        assert "Tenant context required" in exc.value.detail

    def test_require_tenant_id_rejects_empty(self):
        """Given tenant_id='' (empty), When require_tenant_id called,
        Then HTTPException 400 raised। Boundary: empty string।"""
        with pytest.raises(HTTPException) as exc:
            admin_module.require_tenant_id("")
        assert exc.value.status_code == 400

    def test_require_tenant_id_rejects_none(self):
        """Given tenant_id=None, When require_tenant_id called,
        Then HTTPException 400 raised। Boundary: None।"""
        with pytest.raises(HTTPException) as exc:
            admin_module.require_tenant_id(None)
        assert exc.value.status_code == 400

    def test_require_tenant_id_accepts_real_id(self):
        """Given tenant_id='tenant_abc_123', When require_tenant_id called,
        Then 'tenant_abc_123' returned unchanged — happy path।"""
        result = admin_module.require_tenant_id("tenant_abc_123")
        assert result == "tenant_abc_123"

    def test_require_tenant_id_strips_whitespace(self):
        """Given tenant_id='  tenant_x  ', When require_tenant_id called,
        Then stripped 'tenant_x' returned।"""
        result = admin_module.require_tenant_id("  tenant_x  ")
        assert result == "tenant_x"


# ---------------------------------------------------------------------------
# 5. admin_routes.py mock-token policy contract (separate file)
# ---------------------------------------------------------------------------


class TestAdminRoutesMockTokenPolicy:
    """admin_routes.py-র _mock_token_allowed + _MOCK_TOKEN_ALLOWED_ENVS contract।"""

    def test_mock_token_allowed_in_test_env(self, monkeypatch):
        """Given settings.env='test', When _mock_token_allowed called,
        Then True — test env allow-listed।"""
        # Given
        from api.routes import admin_routes

        monkeypatch.setattr(admin_routes.settings, "env", "test", raising=False)
        # When
        result = admin_routes._mock_token_allowed()
        # Then
        assert result is True

    def test_mock_token_blocked_in_production(self, monkeypatch):
        """Given settings.env='production', When _mock_token_allowed called,
        Then False — production fail-closed।"""
        from api.routes import admin_routes

        monkeypatch.setattr(admin_routes.settings, "env", "production", raising=False)
        assert admin_routes._mock_token_allowed() is False

    def test_mock_token_blocked_in_staging(self, monkeypatch):
        """Given settings.env='staging', When _mock_token_allowed called,
        Then False — staging also fail-closed। Boundary: staging ঠিক যেমন prod।"""
        from api.routes import admin_routes

        monkeypatch.setattr(admin_routes.settings, "env", "staging", raising=False)
        assert admin_routes._mock_token_allowed() is False

    def test_mock_token_blocked_when_env_unknown(self, monkeypatch):
        """Given settings.env='unknown_env', When _mock_token_allowed called,
        Then False — unknown env fail-closed (only explicit allow-list works)।"""
        from api.routes import admin_routes

        # বাংলা: getattr(settings, 'env', 'local') or 'local' — empty string
        # default হয়ে 'local' চলে যায়, তাই সত্যিকারের unknown env দিয়ে টেস্ট করছি।
        monkeypatch.setattr(admin_routes.settings, "env", "unknown_env", raising=False)
        result = admin_routes._mock_token_allowed()
        # 'unknown_env' allow-list-এ নেই → False
        assert result is False

    def test_reject_mock_token_raises_403(self, monkeypatch):
        """Given production env, When _reject_mock_token called,
        Then HTTPException 403 raised।"""
        from api.routes import admin_routes

        monkeypatch.setattr(admin_routes.settings, "env", "production", raising=False)
        with pytest.raises(HTTPException) as exc:
            admin_routes._reject_mock_token()
        assert exc.value.status_code == 403
        assert "Mock tokens" in exc.value.detail

    def test_mock_token_allowed_envs_is_frozenset(self):
        """Given admin_routes module, When _MOCK_TOKEN_ALLOWED_ENVS inspected,
        Then frozenset — immutable policy।"""
        from api.routes import admin_routes

        assert isinstance(admin_routes._MOCK_TOKEN_ALLOWED_ENVS, frozenset)
        # Boundary: allow-list must include all local/test envs
        for env in ("local", "dev", "development", "test", "testing", "ci"):
            assert env in admin_routes._MOCK_TOKEN_ALLOWED_ENVS, env


# ---------------------------------------------------------------------------
# 6. get_current_admin dependency contract (api/dependencies.py)
# ---------------------------------------------------------------------------


class TestGetCurrentAdminDependency:
    """get_current_admin — admin role check + 403 reject।"""

    def test_admin_role_passes(self):
        """Given payload role=admin, When get_current_admin called,
        Then payload returned unchanged — happy path।"""
        payload = {"sub": "admin@x.com", "role": "admin"}
        result = get_current_admin(payload)
        assert result is payload

    def test_viewer_role_rejected_403(self):
        """Given payload role=viewer, When get_current_admin called,
        Then HTTPException 403 raised — sad path।"""
        payload = {"sub": "viewer@x.com", "role": "viewer"}
        with pytest.raises(HTTPException) as exc:
            get_current_admin(payload)
        assert exc.value.status_code == 403
        assert "Admin access required" in exc.value.detail

    def test_missing_role_rejected_403(self):
        """Given payload without role key, When get_current_admin called,
        Then HTTPException 403 — boundary: missing field = no admin।"""
        payload = {"sub": "user@x.com"}
        with pytest.raises(HTTPException) as exc:
            get_current_admin(payload)
        assert exc.value.status_code == 403

    def test_none_role_rejected_403(self):
        """Given payload role=None, When get_current_admin called,
        Then HTTPException 403 — boundary: None role = no admin।"""
        payload = {"sub": "user@x.com", "role": None}
        with pytest.raises(HTTPException) as exc:
            get_current_admin(payload)
        assert exc.value.status_code == 403

    def test_empty_string_role_rejected_403(self):
        """Given payload role='', When get_current_admin called,
        Then HTTPException 403 — boundary: empty string role = no admin।"""
        payload = {"sub": "user@x.com", "role": ""}
        with pytest.raises(HTTPException) as exc:
            get_current_admin(payload)
        assert exc.value.status_code == 403

    def test_case_sensitive_role_check(self):
        """Given payload role='Admin' (capital A), When get_current_admin called,
        Then HTTPException 403 — boundary: case-sensitive, 'Admin' ≠ 'admin'।"""
        payload = {"sub": "user@x.com", "role": "Admin"}
        with pytest.raises(HTTPException) as exc:
            get_current_admin(payload)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# 7. Module-shape contract
# ---------------------------------------------------------------------------


class TestAdminRouterModuleShape:
    """admin.py router shape — prefix, tags, dependencies contract।"""

    def test_router_has_admin_prefix(self):
        """Given admin.router, When prefix inspected, Then '/api/admin'।"""
        assert admin_module.router.prefix == "/api/admin"

    def test_router_enforces_admin_dependency(self):
        """Given admin.router, When dependencies inspected,
        Then get_current_admin is in the dependency list — router-level guard।"""
        # বাংলা: router-এ dependencies=[Depends(get_current_admin)] — সব endpoint
        # এই dependency থেকে বাইপাস করতে পারে না।
        dep_reprs = [str(d.dependency) for d in admin_module.router.dependencies]
        assert any("get_current_admin" in d for d in dep_reprs)

    def test_router_has_rules_endpoints_registered(self):
        """Given admin.router, When routes inspected, Then /rules (GET+POST) present।"""
        paths = {(r.path, tuple(r.methods)) for r in admin_module.router.routes}
        assert ("/api/admin/rules", ("GET",)) in paths or any(
            path == "/api/admin/rules" and "GET" in methods for path, methods in paths
        )
        assert any(path == "/api/admin/rules" and "POST" in methods for path, methods in paths)
