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


def test_commandcenter_money_cost():
    resp = client.get("/admin-api/commandcenter/money/cost", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "report" in resp.json()


def test_commandcenter_money_usage():
    resp = client.get("/admin-api/commandcenter/money/usage", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "cost_projected_monthly" in resp.json()


def test_commandcenter_money_budget():
    resp = client.get("/admin-api/commandcenter/money/budget", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    post_resp = client.post(
        "/admin-api/commandcenter/money/budget", json={"cap": 100}, headers=ADMIN_HEADERS
    )
    assert post_resp.status_code == 200


def test_commandcenter_money_roi():
    resp = client.get("/admin-api/commandcenter/money/roi", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "semantic_cache_hits" in resp.json()
