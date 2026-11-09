"""Tests for SupremeAI Studio Compatibility API layer."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

core_path = str(Path(__file__).resolve().parents[2])
if core_path not in sys.path:
    sys.path.insert(0, core_path)

from fastapi.testclient import TestClient

from core.api.routes.auth import create_access_token
from core.api.routes.studio_compat import _format_studio_user
from core.app_builder import create_app
from core.config import settings


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as tc:
        yield tc


def test_format_studio_user_shape():
    user = _format_studio_user(
        user_id="usr_123", email="test@supremeai.com", name="Test User", role="user"
    )
    assert user["id"] == "usr_123"
    assert user["email"] == "test@supremeai.com"
    assert user["name"] == "Test User"
    assert user["role"] == "user"
    assert "permissions" in user
    assert user["permissions"]["chat"]["edit"] is True
    assert user["permissions"]["workspace"]["models"] is False


def test_format_studio_admin_shape():
    admin = _format_studio_user(
        user_id="adm_123", email="admin@supremeai.com", name="Admin User", role="admin"
    )
    assert admin["role"] == "admin"
    assert admin["permissions"]["workspace"]["models"] is True


def test_studio_signin_empty_body_fails_closed(client: TestClient):
    resp = client.post("/api/v1/auths/signin", json={"email": "", "password": ""})
    assert resp.status_code == 400
    assert "required" in resp.json().get("detail", "").lower()


def test_studio_signup_missing_fields(client: TestClient):
    resp = client.post("/api/v1/auths/signup", json={"email": "a@b.com", "password": "", "name": ""})
    assert resp.status_code == 400


def test_studio_get_session_user_no_token_fails_closed(client: TestClient):
    resp = client.get("/api/v1/auths/")
    assert resp.status_code in (401, 403)


def test_studio_get_session_user_with_token(client: TestClient):
    token = create_access_token({"sub": "usr_test123", "role": "user", "email": "test@supremeai.com"})
    resp = client.get("/api/v1/auths/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "usr_test123"
    assert data["email"] == "test@supremeai.com"


def test_studio_get_user_settings_with_token(client: TestClient):
    token = create_access_token({"sub": "usr_test123", "role": "user", "email": "test@supremeai.com"})
    resp = client.get("/api/v1/users/user/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "ui" in data
    assert data["ui"]["theme"] == "dark"


def test_studio_get_models(client: TestClient):
    resp = client.get("/api/models")
    assert resp.status_code == 200
    models = resp.json()
    assert isinstance(models, list)
    model_ids = [m["id"] for m in models]
    assert "auto" in model_ids
    assert "supremeai-turbo" in model_ids


def test_studio_get_version(client: TestClient):
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_studio_signout_without_token_clears_session(client: TestClient):
    resp = client.post("/api/v1/auths/signout")
    assert resp.status_code == 200
    assert resp.json().get("status") is True


def test_studio_signout_with_invalid_token_is_tolerated(client: TestClient):
    resp = client.post("/api/v1/auths/signout", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 200
    assert resp.json().get("status") is True


def test_auths_index_has_no_mock_operator_fallback():
    auths_file = os.path.join("studio", "src", "lib", "apis", "auths", "index.ts")
    assert os.path.exists(auths_file)
    with open(auths_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "supremeai-session-token" not in content, "Privileged mock token must not exist in auths/index.ts"
    assert "supremeai-operator" not in content, "Hardcoded operator session must not exist in auths/index.ts"
    assert "Operator login fallback" not in content, "Operator login fallback must be removed"
