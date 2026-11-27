"""Local-only regression tests for the compatibility control-plane HITL path."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import service.frontend_compat as fc


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(fc, "_pending_hitl", {})
    monkeypatch.setattr(fc, "_SUPERADMIN_KEY", "test-admin")
    monkeypatch.setattr(fc, "_verify_admin_token", lambda token: False)
    app = FastAPI()
    app.include_router(fc.router)
    return TestClient(app, headers={"X-Superadmin-Key": "test-admin"})


def register(client, context=None):
    response = client.post("/api/v1/hitl/register", json={"id": "one", "action_name": "test", "context": context or {}})
    assert response.status_code == 200


@pytest.mark.parametrize("payload", [b"", b"{", b"{}", b'[]', b'{"decision": "maybe"}', b'{"decision": null}'])
def test_invalid_decision_never_approves(client, monkeypatch, payload):
    register(client, {"pr_number": 123})
    calls = []
    monkeypatch.setattr(fc, "_gh", lambda *args: calls.append(args))
    response = client.post("/api/admin/control-plane/hitl/one/resolve", content=payload, headers={"content-type": "application/json"})
    assert response.status_code == 400
    assert not calls
    assert fc._pending_hitl["one"]["status"] == "pending"


def test_unknown_duplicate_and_replayed_records_fail(client):
    assert client.post("/api/admin/control-plane/hitl/missing/resolve", json={"decision": "approved"}).status_code == 404
    register(client)
    assert client.post("/api/v1/hitl/register", json={"id": "one", "action_name": "again"}).status_code == 409
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).json()["status"] == "approved"
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).status_code == 409


def test_github_failure_is_indeterminate_and_no_retry(client, monkeypatch):
    register(client, {"pr_number": 123})
    calls = []
    def failed(*args):
        calls.append(args)
        return 502, {"error": "secret upstream detail"}
    monkeypatch.setattr(fc, "_gh", failed)
    response = client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"})
    assert response.status_code == 502
    assert "secret" not in response.text
    assert fc._pending_hitl["one"]["status"] == "indeterminate"
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "rejected"}).status_code == 409
    assert len(calls) == 1


def test_multi_target_rejected_before_any_mutation(client, monkeypatch):
    register(client, {"run_id": 7, "pr_number": 123})
    calls = []
    monkeypatch.setattr(fc, "_gh", lambda *args: calls.append(args))
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).status_code == 422
    assert not calls
    assert fc._pending_hitl["one"]["status"] == "pending"


def test_deployment_preflight_failure_does_not_resolve(client, monkeypatch):
    register(client, {"run_id": 7})
    calls = []
    def gh(*args):
        calls.append(args)
        return 500, {"message": "upstream failed"}
    monkeypatch.setattr(fc, "_gh", gh)
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).status_code == 502
    assert [c[0] for c in calls] == ["GET"]
    assert fc._pending_hitl["one"]["status"] == "pending"


def test_github_success_then_replay_is_blocked(client, monkeypatch):
    register(client, {"pr_number": 123})
    calls = []
    def gh(*args):
        calls.append(args)
        return 200, {"id": 1}
    monkeypatch.setattr(fc, "_gh", gh)
    response = client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "rejected", "reason": "not safe"})
    assert response.status_code == 200 and response.json()["status"] == "rejected"
    assert calls[0][2]["event"] == "REQUEST_CHANGES"
    assert "not safe" in calls[0][2]["body"]
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "rejected"}).status_code == 409
    assert len(calls) == 1


def test_admin_guard_is_required(client, monkeypatch):
    register(client)
    response = client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}, headers={"X-Superadmin-Key": "wrong"})
    assert response.status_code == 403
    assert fc._pending_hitl["one"]["status"] == "pending"


@pytest.mark.parametrize("target", [{"pr_number": "1/reviews?x=1"}, {"run_id": -1}, {"pr_number": False}, {"pr_number": ""}])
def test_invalid_target_never_calls_github(client, monkeypatch, target):
    register(client, target)
    calls = []
    monkeypatch.setattr(fc, "_gh", lambda *args: calls.append(args))
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).status_code == 422
    assert not calls


def test_local_resolution_does_not_claim_external_action(client):
    register(client)
    response = client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"})
    assert response.status_code == 200
    assert "no external action was performed" in response.json()["message"]


def test_empty_deployment_list_does_not_resolve(client, monkeypatch):
    register(client, {"run_id": 7})
    monkeypatch.setattr(fc, "_gh", lambda *args: (200, []))
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).status_code == 409
    assert fc._pending_hitl["one"]["status"] == "pending"


def test_malformed_pending_environment_does_not_partially_approve(client, monkeypatch):
    register(client, {"run_id": 7})
    calls = []
    def gh(*args):
        calls.append(args)
        return 200, [{"environment": {"id": 5}}, {"environment": {}}]
    monkeypatch.setattr(fc, "_gh", gh)
    assert client.post("/api/admin/control-plane/hitl/one/resolve", json={"decision": "approved"}).status_code == 502
    assert [c[0] for c in calls] == ["GET"]
    assert fc._pending_hitl["one"]["status"] == "pending"
