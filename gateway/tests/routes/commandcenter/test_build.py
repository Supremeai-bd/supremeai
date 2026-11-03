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


def test_commandcenter_build_router():
    resp = client.get("/admin-api/commandcenter/build/router", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "cost_quality_preference" in resp.json()


def test_commandcenter_build_providers():
    resp = client.get("/admin-api/commandcenter/build/providers", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_build_skills():
    resp = client.get("/admin-api/commandcenter/build/skills", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_build_memory():
    resp = client.get("/admin-api/commandcenter/build/memory", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "semantic_cache_hit_rate" in resp.json()


def test_commandcenter_build_knowledge():
    resp = client.get("/admin-api/commandcenter/build/knowledge", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "rag_index_status" in resp.json()
