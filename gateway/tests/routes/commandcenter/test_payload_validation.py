"""Tests for #1656 — command center payload validation (Pydantic models).

বাংলা: নিশ্চিত করে যে bare dict-এর বদলে Pydantic model validation কাজ করছে —
invalid payload এখন 422 (এর আগে silent accept + state corruption হতো)।
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_admin
from api.routes.commandcenter.money import router as money_router
from api.routes.commandcenter.secure import router as secure_router
from api.routes.commandcenter.system import router as system_router


@pytest.fixture
def app():
    app = FastAPI()
    app.dependency_overrides[get_current_admin] = lambda: {"sub": "admin", "role": "admin"}
    # Command Center sub-routers are included under /admin-api/commandcenter
    # by the parent router (commandcenter/__init__.py:43-49).
    app.include_router(system_router, prefix="/admin-api/commandcenter")
    app.include_router(secure_router, prefix="/admin-api/commandcenter")
    app.include_router(money_router, prefix="/admin-api/commandcenter")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ─── POST /system/config ─────────────────────────────────────────────────────


class TestConfigUpdate:
    def test_valid_payload_accepted(self, client):
        resp = client.post(
            "/admin-api/commandcenter/system/config", json={"key": "MAX_TOKENS", "value": 4096}
        )
        assert resp.status_code == 200
        assert resp.json() == {"message": "updated"}

    def test_missing_key_rejected(self, client):
        resp = client.post("/admin-api/commandcenter/system/config", json={"value": 100})
        assert resp.status_code == 422  # validation error

    def test_empty_key_rejected(self, client):
        resp = client.post("/admin-api/commandcenter/system/config", json={"key": "", "value": "x"})
        assert resp.status_code == 422

    def test_unknown_field_rejected(self, client):
        resp = client.post(
            "/admin-api/commandcenter/system/config",
            json={"key": "K", "value": "V", "extra": "bad"},
        )
        assert resp.status_code == 422


# ─── POST /system/flags ──────────────────────────────────────────────────────


class TestFlagsUpdate:
    def test_valid_flag_accepted(self, client):
        resp = client.post(
            "/admin-api/commandcenter/system/flags", json={"flag": "beta_feature", "enabled": True}
        )
        assert resp.status_code == 200

    def test_non_bool_enabled_rejected(self, client):
        resp = client.post(
            "/admin-api/commandcenter/system/flags", json={"flag": "x", "enabled": "yes"}
        )
        assert resp.status_code == 422


# ─── POST /system/deploy-gate ────────────────────────────────────────────────


class TestDeployGateToggle:
    def test_valid_lock_accepted(self, client):
        resp = client.post(
            "/admin-api/commandcenter/system/deploy-gate", json={"locked": True, "reason": "hotfix"}
        )
        assert resp.status_code == 200

    def test_lock_without_reason_accepted(self, client):
        resp = client.post("/admin-api/commandcenter/system/deploy-gate", json={"locked": False})
        assert resp.status_code == 200

    def test_missing_locked_rejected(self, client):
        resp = client.post("/admin-api/commandcenter/system/deploy-gate", json={"reason": "x"})
        assert resp.status_code == 422


# ─── POST /secure/rules ──────────────────────────────────────────────────────


class TestRulesUpdate:
    def test_valid_rule_accepted(self, client):
        resp = client.post(
            "/admin-api/commandcenter/secure/rules",
            json={"rule_name": "block_sql", "action": "block", "pattern": "DROP TABLE"},
        )
        assert resp.status_code == 200

    def test_invalid_action_rejected(self, client):
        resp = client.post(
            "/admin-api/commandcenter/secure/rules",
            json={"rule_name": "x", "action": "delete", "pattern": "p"},
        )
        assert resp.status_code == 422

    def test_empty_pattern_rejected(self, client):
        resp = client.post(
            "/admin-api/commandcenter/secure/rules",
            json={"rule_name": "x", "action": "allow", "pattern": ""},
        )
        assert resp.status_code == 422


# ─── POST /money/budget ──────────────────────────────────────────────────────


class TestBudgetUpdate:
    def test_valid_budget_accepted(self, client):
        resp = client.post(
            "/admin-api/commandcenter/money/budget", json={"cap": 100.0, "period": "monthly"}
        )
        assert resp.status_code == 200

    def test_negative_budget_rejected(self, client):
        resp = client.post("/admin-api/commandcenter/money/budget", json={"cap": -50.0})
        assert resp.status_code == 422  # ge=0 validator

    def test_invalid_period_rejected(self, client):
        resp = client.post(
            "/admin-api/commandcenter/money/budget", json={"cap": 100.0, "period": "yearly"}
        )
        assert resp.status_code == 422  # pattern validator

    def test_tenant_budget_accepted(self, client):
        resp = client.post(
            "/admin-api/commandcenter/money/budget",
            json={"tenant_id": "t-123", "cap": 50.0, "period": "daily"},
        )
        assert resp.status_code == 200
