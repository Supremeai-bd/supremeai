from fastapi.testclient import TestClient

import service.app as app_module
from service.app import app
from service.keygen import generate_key, verify_key


def test_generic_signed_client_key_cannot_access_operator_status(monkeypatch):
    monkeypatch.setattr(app_module, "OPERATOR_KEYS", {"operator-rotation-secret"})
    monkeypatch.setenv("SUPREMEAI_MASTER_KEY", "audit-test-master-key")
    client_key = generate_key(client_name="ordinary-client", quota="standard")
    client = TestClient(app)

    denied = client.get("/internal/status", headers={"X-SupremeAI-Key": client_key})
    allowed = client.get(
        "/internal/status", headers={"X-SupremeAI-Key": "operator-rotation-secret"}
    )

    assert denied.status_code == 401
    assert allowed.status_code != 401


def test_legacy_12_hex_mac_is_rejected(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MASTER_KEY", "audit-test-master-key")
    full_key = generate_key(client_name="ordinary-client", quota="standard")
    payload, signature = full_key.rsplit("-", 1)
    legacy_key = f"{payload}-{signature[:12]}"

    assert verify_key(full_key) is not None
    assert verify_key(legacy_key) is None
