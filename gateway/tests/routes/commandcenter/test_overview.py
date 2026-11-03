from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_admin, get_current_user_token
from core.app import app

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


@pytest.fixture(autouse=True)
def override_admin_auth():
    """Default override for admin routes and JWT validation in AuthMiddleware."""
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


def test_commandcenter_overview_success():
    response = client.get("/admin-api/commandcenter/overview", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "active_agents" in data
    assert "active_tasks" in data
    assert "health_percent" in data
    assert data["health_percent"] == 100.0


def test_commandcenter_overview_forbidden():
    app.dependency_overrides[get_current_admin] = lambda: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(status_code=403, detail="Admin access required")
    )
    response = client.get("/admin-api/commandcenter/overview", headers=ADMIN_HEADERS)
    assert response.status_code == 403
