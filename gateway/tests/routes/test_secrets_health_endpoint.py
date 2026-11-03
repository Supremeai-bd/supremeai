"""Issue #1820: GET /admin-api/secrets-health contract tests.

The Command Center Secrets Health module polls this endpoint; before this
endpoint existed every poll 404'd and the module rendered OVERALL: UNKNOWN.
These tests pin: (a) the route exists (no 404), (b) the response shape the
frontend expects, (c) deterministic degradation signal, (d) no secret
material ever leaks (structural checks only).
"""

import pytest
from fastapi.testclient import TestClient

from api.routes.admin_dashboard import require_admin_token
from core.app import app

client = TestClient(app)

_EXPECTED_CHECK_NAMES = {"jwt_secret", "stripe_api_key", "credential_encryption_key"}


@pytest.fixture()
def admin_auth():
    """Override the admin router guard; snapshot→restore only the keys this
    fixture owns (never replace the shared dependency_overrides dict — see
    the #1869 test-isolation fix in test_browser_credentials.py)."""
    saved_admin = app.dependency_overrides.get(require_admin_token)
    app.dependency_overrides[require_admin_token] = lambda: {
        "sub": "admin",
        "uid": "admin",
        "role": "admin",
    }
    yield
    if saved_admin is None:
        app.dependency_overrides.pop(require_admin_token, None)
    else:
        app.dependency_overrides[require_admin_token] = saved_admin


def _secret_names(payload: dict) -> set[str]:
    return {entry["name"] for entry in payload.get("secrets", [])}


def test_secrets_health_endpoint_exists_and_returns_shape(admin_auth):
    resp = client.get("/admin-api/secrets-health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in {"healthy", "degraded"}
    assert isinstance(body["secrets"], list) and body["secrets"]
    assert _secret_names(body) == _EXPECTED_CHECK_NAMES
    for entry in body["secrets"]:
        assert isinstance(entry["healthy"], bool)


def test_secrets_health_degrades_when_encryption_key_absent(monkeypatch, admin_auth):
    for name in (
        "SUPREMEAI_CREDENTIAL_ENC_KEY",
        "BROWSER_CREDENTIALS_ENCRYPTION_KEY",
        "ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    resp = client.get("/admin-api/secrets-health")
    assert resp.status_code == 200
    body = resp.json()
    by_name = {e["name"]: e for e in body["secrets"]}
    # Fail-closed store (#1570) without any key MUST surface unhealthy.
    assert by_name["credential_encryption_key"]["healthy"] is False
    assert body["status"] == "degraded"


def test_secrets_health_never_leaks_secret_material(admin_auth):
    resp = client.get("/admin-api/secrets-health")
    body = resp.json()
    raw = str(body)
    # Structural checks only: entries carry name+healthy (and nothing that
    # looks like secret value material).
    for entry in body["secrets"]:
        assert set(entry.keys()) <= {"name", "healthy", "note"}
        assert "value" not in entry
    assert "BEGIN" not in raw and "sk_" not in raw and "sk_live" not in raw
