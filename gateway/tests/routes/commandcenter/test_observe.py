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


def test_commandcenter_observe_metrics():
    resp = client.get("/admin-api/commandcenter/observe/metrics", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_commandcenter_observe_logs():
    resp = client.get("/admin-api/commandcenter/observe/logs", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_observe_events():
    resp = client.get("/admin-api/commandcenter/observe/events", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_observe_health():
    resp = client.get("/admin-api/commandcenter/observe/health", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "overall_health_percent" in resp.json()


def test_commandcenter_observe_traffic():
    resp = client.get("/admin-api/commandcenter/observe/traffic", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "current_rps" in resp.json()
