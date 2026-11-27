"""Verified guest sessions are isolated; unauthenticated data is never shared."""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from gateway.service import app as edge
from gateway.service import auth_verification, storage
from gateway.service.auth_identity import resolve_user_id
from gateway.service.keygen import generate_key


@pytest.fixture(autouse=True)
def secure_config(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPREMEAI_MASTER_KEY", "fixture-signing-secret-do-not-use-in-production")
    monkeypatch.setenv("SUPREMEAI_API_KEY", "fixture-static-key")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("SUPREMEAI_TEST_GUEST_BYPASS", raising=False)
    monkeypatch.setattr(storage, "_DB_PATH", str(tmp_path / "gateway.db"))
    monkeypatch.setattr(storage, "_USE_MEM_FALLBACK", False)
    storage.init_db()


def request(headers=None):
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [
        (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
    ]})


def test_signed_guests_are_distinct_and_cookie_matches_bearer():
    a = auth_verification._issue_guest_token(300)
    b = auth_verification._issue_guest_token(300)
    bearer_a = request({"authorization": "Bearer " + a})
    cookie_a = request({"cookie": "supremeai_guest_session=" + a})
    bearer_b = request({"authorization": "Bearer " + b})
    assert auth_verification._is_verified_guest(bearer_a, a)
    assert auth_verification._is_verified_guest(cookie_a, None)
    assert auth_verification._verify_client_auth(cookie_a)
    assert auth_verification._is_guest_cost_guard_signal(bearer_a, a)
    assert auth_verification._is_guest_cost_guard_signal(cookie_a, None)
    assert resolve_user_id(bearer_a) == resolve_user_id(cookie_a)
    assert resolve_user_id(bearer_a) != resolve_user_id(bearer_b)
    assert a not in resolve_user_id(bearer_a)
    with pytest.raises(HTTPException):
        resolve_user_id(bearer_a, require_registered=True)


def test_same_named_generic_credentials_do_not_share_private_state():
    first = generate_key("shared-service")
    second = generate_key("shared-service")
    first_req = request({"authorization": "Bearer " + first})
    second_req = request({"authorization": "Bearer " + second})
    assert resolve_user_id(first_req) != resolve_user_id(second_req)
    assert resolve_user_id(first_req) == resolve_user_id(first_req)
    with pytest.raises(HTTPException):
        resolve_user_id(first_req, require_registered=True)
    with pytest.raises(HTTPException):
        resolve_user_id(request({"authorization": "Bearer " + generate_key("usr-notregistered")}), require_registered=True)


def test_bad_or_nonexpiring_guest_never_falls_back_to_cookie():
    good = auth_verification._issue_guest_token(300)
    bad = good[:-1] + ("0" if good[-1] != "0" else "1")
    req = request({"authorization": "Bearer " + bad, "cookie": "supremeai_guest_session=" + good})
    assert not auth_verification._is_verified_guest(req, bad)
    with pytest.raises(HTTPException):
        resolve_user_id(req)
    nonexpiring = generate_key("guest", quota="guest")
    req = request({"authorization": "Bearer " + nonexpiring})
    assert not auth_verification._verify_client_auth(req)
    with pytest.raises(HTTPException):
        resolve_user_id(req)
    with pytest.raises(HTTPException):
        resolve_user_id(request({"cookie": "supremeai_guest_session=" + generate_key("studio-admin")}))


def test_expired_guest_token_is_rejected(monkeypatch):
    from gateway.service import keygen
    now = keygen.time.time()
    token = auth_verification._issue_guest_token(60)
    monkeypatch.setattr(keygen.time, "time", lambda: now + 61)
    req = request({"authorization": "Bearer " + token})
    assert not auth_verification._verify_client_auth(req)
    with pytest.raises(HTTPException):
        resolve_user_id(req)


def test_static_or_missing_key_cannot_access_shared_private_state():
    client = TestClient(edge.app)
    assert client.get("/api/user/knowledge").status_code == 401
    assert client.get("/api/user/knowledge", headers={"authorization": "Bearer bogus"}).status_code == 401
    headers = {"authorization": "Bearer fixture-static-key"}
    assert client.get("/api/v1/conversations", headers=headers).status_code == 401
    assert client.post("/v1/chat/completions", headers=headers, json={
        "conversation_id": "unowned", "messages": [{"role": "user", "content": "hello"}],
    }).status_code == 401


def test_stateless_static_key_does_not_read_or_write_user_memory(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_TRIVIAL_FASTPATH", "0")
    ingest = Mock()
    compiler = Mock(side_effect=RuntimeError("stop before inference"))
    monkeypatch.setattr(edge, "ingest_consented_personal_memory", ingest)
    monkeypatch.setattr(edge, "compile_chat_context", compiler)
    response = TestClient(edge.app).post("/v1/chat/completions", headers={"authorization": "Bearer fixture-static-key"}, json={
        "messages": [{"role": "user", "content": "Explain this"}],
    })
    assert response.status_code == 503
    ingest.assert_not_called()
    assert compiler.call_args.kwargs["user_id"] is None


def test_guest_endpoints_isolate_two_sessions_and_cookie_auth():
    a = auth_verification._issue_guest_token(300)
    b = auth_verification._issue_guest_token(300)
    client = TestClient(edge.app)
    ha = {"cookie": "supremeai_guest_session=" + a}
    hb = {"authorization": "Bearer " + b}
    created = client.post("/api/v1/conversations", headers=ha, json={"id": "guest-conv", "title": "private"})
    assert created.status_code == 200
    assert client.get("/api/v1/conversations/guest-conv", headers=ha).status_code == 200
    assert client.get("/api/v1/conversations/guest-conv", headers=hb).status_code == 404
    assert client.post("/api/user/knowledge", headers=ha, json={"title": "private"}).status_code == 200
    assert client.get("/api/user/knowledge", headers=hb).json()["documents"] == []


def test_legacy_conversation_rejects_cross_owner_writes_and_preserves_metadata():
    storage.save_conversation("legacy-conv", user_id="alice", title="Original", metadata={"note": "fixture"})
    storage.add_message("legacy-conv", "user", "first", user_id="alice")
    with pytest.raises(PermissionError):
        storage.save_conversation("legacy-conv", user_id="bob", title="changed")
    with pytest.raises(PermissionError):
        storage.add_message("legacy-conv", "user", "injected", user_id="bob")
    conv = storage.get_conversation("legacy-conv", user_id="alice")
    assert conv["title"] == "Original"
    assert conv["metadata"] == {"note": "fixture"}
    assert [m["content"] for m in conv["messages"]] == ["first"]


def test_guest_cannot_claim_another_guests_conversation_id():
    a = auth_verification._issue_guest_token(300)
    b = auth_verification._issue_guest_token(300)
    client = TestClient(edge.app)
    ha = {"authorization": "Bearer " + a}
    hb = {"authorization": "Bearer " + b}
    assert client.post("/api/v1/conversations", headers=ha, json={"id": "claim-fixture"}).status_code == 200
    assert client.post("/api/v1/conversations", headers=hb, json={"id": "claim-fixture", "title": "attack"}).status_code == 403


def test_legacy_conversations_fail_closed_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(storage, "_USE_MEM_FALLBACK", True)
    with pytest.raises(RuntimeError, match="Conversation storage unavailable"):
        storage.save_conversation("private", user_id="alice")
    with pytest.raises(RuntimeError, match="Conversation storage unavailable"):
        storage.add_message("private", "user", "secret", user_id="alice")
    with pytest.raises(RuntimeError, match="Conversation storage unavailable"):
        storage.get_conversation("private", user_id="alice")


def test_legacy_cross_process_competing_owner_cannot_insert():
    import os
    import subprocess
    import sys

    storage.save_conversation("cross-process", user_id="alice", title="original")
    script = "\n".join([
        "import sys",
        "from gateway.service import storage",
        "try:",
        "    storage.add_message('cross-process', 'user', 'intruder', user_id='bob')",
        "except PermissionError:",
        "    sys.exit(0)",
        "sys.exit(2)",
    ])
    env = {**os.environ, "SUPREMEAI_DB_PATH": storage._DB_PATH}
    workers = [subprocess.Popen([sys.executable, "-c", script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
    for i in range(6):
        storage.add_message("cross-process", "user", f"owner-{i}", user_id="alice")
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=20)
        assert worker.returncode == 0, (stdout, stderr)
    messages = storage.get_conversation("cross-process", user_id="alice")["messages"]
    assert [m["content"] for m in messages] == [f"owner-{i}" for i in range(6)]
