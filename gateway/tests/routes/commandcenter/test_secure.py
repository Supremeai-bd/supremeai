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


def test_commandcenter_secure_threats():
    resp = client.get("/admin-api/commandcenter/secure/threats", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "findings" in resp.json()


def test_commandcenter_secure_rules():
    resp = client.get("/admin-api/commandcenter/secure/rules", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post(
        "/admin-api/commandcenter/secure/rules",
        json={"rule_name": "test_rule", "action": "allow", "pattern": ".*"},
        headers=ADMIN_HEADERS,
    )
    assert post_resp.status_code == 200


def test_commandcenter_secure_secrets():
    resp = client.get("/admin-api/commandcenter/secure/secrets", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "secrets" in resp.json()


def test_commandcenter_secure_ratelimits():
    resp = client.get("/admin-api/commandcenter/secure/ratelimits", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "current_429_events" in resp.json()
