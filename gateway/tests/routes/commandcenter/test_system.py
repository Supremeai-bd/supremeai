from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_admin, get_current_user_token
from core.app import app

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


@pytest.fixture(autouse=True)
def override_admin_auth():
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin@supremeai.test",
        "role": "admin",
    }
    app.dependency_overrides[get_current_admin] = lambda: {
        "sub": "admin@supremeai.test",
        "role": "admin",
    }
    with patch("core.security.authentication.auth_middleware._decode_jwt") as mock_jwt:
        mock_jwt.return_value = {"sub": "admin@supremeai.test", "role": "admin"}
        yield
    app.dependency_overrides.pop(get_current_user_token, None)
    app.dependency_overrides.pop(get_current_admin, None)


def test_commandcenter_system_config():
    resp = client.get("/admin-api/commandcenter/system/config", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post(
        "/admin-api/commandcenter/system/config",
        json={"key": "test_key", "value": "test_val"},
        headers=ADMIN_HEADERS,
    )
    assert post_resp.status_code == 200


def test_commandcenter_system_flags():
    resp = client.get("/admin-api/commandcenter/system/flags", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post(
        "/admin-api/commandcenter/system/flags",
        json={"flag": "test_flag", "enabled": True},
        headers=ADMIN_HEADERS,
    )
    assert post_resp.status_code == 200


def test_commandcenter_system_backups():
    resp = client.get("/admin-api/commandcenter/system/backups", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post("/admin-api/commandcenter/system/backups", headers=ADMIN_HEADERS)
    assert post_resp.status_code == 200
    restore_resp = client.post(
        "/admin-api/commandcenter/system/backups/b1/restore", headers=ADMIN_HEADERS
    )
    assert restore_resp.status_code == 200


def test_commandcenter_system_deploy_gate():
    resp = client.get("/admin-api/commandcenter/system/deploy-gate", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "status" in resp.json()
    post_resp = client.post(
        "/admin-api/commandcenter/system/deploy-gate",
        json={"locked": True, "reason": "test"},
        headers=ADMIN_HEADERS,
    )
    assert post_resp.status_code == 200
