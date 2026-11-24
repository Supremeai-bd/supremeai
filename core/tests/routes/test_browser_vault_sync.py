
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# FIX (2026-11-24): these were imported as ``api.*`` (core/ is on pytest's
# pythonpath). That imports the package a second time under a different module
# name, so routes register on ``core.api.routes.browser.router`` while the test
# mounted the ``api.routes.browser`` copy — every request 404'd. Import the
# canonical name.
from core.api.deps import get_current_user_token
from core.api.routes.browser import router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi import FastAPI

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BROWSER_VAULT_KEY", key)
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vaults"))

    app = FastAPI()
    app.include_router(router)

    # Mock user token dependency
    app.dependency_overrides[get_current_user_token] = lambda: {"sub": "test-user-42"}
    return TestClient(app)


def test_vault_session_sync_roundtrip(client, tmp_path):
    cookies = [{"name": "auth_token", "value": "secret_abc", "domain": "example.com"}]
    storage = {"https://example.com": {"user_id": "42"}}

    # 1. Sync session
    res = client.post(
        "/api/browser/automation/vault/sync",
        json={
            "service": "example.com",
            "cookies": cookies,
            "local_storage": storage,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["service"] == "example.com"
    assert data["cookies_count"] == 1

    # 2. List services
    list_res = client.get("/api/browser/automation/vault/services")
    assert list_res.status_code == 200
    services = list_res.json()["services"]
    assert any(s["service"] == "example.com" for s in services)

    # 3. Delete service
    del_res = client.delete("/api/browser/automation/vault/services/example.com")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
