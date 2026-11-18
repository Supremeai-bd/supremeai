"""Contract tests for studio_data-backed routes in gateway.service.frontend_compat."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.service.app import app
from gateway.service.keygen import generate_key


client = TestClient(app)


def _admin_headers() -> dict[str, str]:
    with patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": "test-master-key-32-bytes-supersecret-token"}):
        token = generate_key(client_name="studio-admin", quota="unlimited")
    return {"Authorization": f"Bearer {token}"}


def _user_headers(user_id: str = "usr-abcdef123456") -> dict[str, str]:
    with patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": "test-master-key-32-bytes-supersecret-token"}):
        token = generate_key(client_name=f"usr-{user_id}", quota="standard")
    return {"Authorization": f"Bearer {token}"}


def test_platform_config_503_when_unconfigured():
    with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}):
        res = client.get("/api/platform/config")
    assert res.status_code == 503


def test_platform_config_returns_public_projection():
    sample_config = {
        "maintenanceMode": False,
        "maintenanceMessage": "",
        "announcementBanner": {"active": False, "message": "", "level": "info"},
        "allowNewSignups": True,
        "defaultModelId": "supreme-spark",
        "featureFlags": {"maintenance_mode": False},
        "modelPolicies": {"supreme-spark": {"enabled": True, "minTier": "Free"}},
    }
    with patch("service.studio_data.platform_state", new=AsyncMock(return_value=(sample_config, {}, "2026-11-18T00:00:00Z"))):
        res = client.get("/api/platform/config")
    assert res.status_code == 200
    assert res.json()["defaultModelId"] == "supreme-spark"


def test_customers_requires_admin_auth():
    res = client.get("/api/customers")
    assert res.status_code == 403


def test_customers_list_with_admin_auth():
    with patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": "test-master-key-32-bytes-supersecret-token"}):
        headers = _admin_headers()
        with patch("service.studio_data.customers", new=AsyncMock(return_value=[{"id": "c1", "name": "Acme"}])):
            res = client.get("/api/customers", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"customers": [{"id": "c1", "name": "Acme"}]}


def test_billing_wallet_requires_registered_account():
    res = client.get("/api/billing/wallet")
    assert res.status_code == 401


def test_billing_add_funds_never_fakes_paid_invoice():
    with patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": "test-master-key-32-bytes-supersecret-token"}):
        headers = _user_headers()
        res = client.post("/api/billing/add-funds", json={"amount": 25}, headers=headers)
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_admin_feature_flags_requires_admin_and_reads_state():
    assert client.get("/api/admin/feature-flags").status_code == 403
    sample_config = {"featureFlags": {"maintenance_mode": False}, "modelPolicies": {}}
    with patch.dict(os.environ, {"SUPREMEAI_MASTER_KEY": "test-master-key-32-bytes-supersecret-token"}):
        headers = _admin_headers()
        with patch("service.studio_data.platform_state", new=AsyncMock(return_value=(sample_config, {}, "2026-11-18T00:00:00Z"))):
            res = client.get("/api/admin/feature-flags", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"flags": {"maintenance_mode": False}}
