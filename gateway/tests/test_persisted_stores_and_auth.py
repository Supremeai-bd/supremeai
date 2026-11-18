import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from gateway.service import storage
from gateway.service.app import app
from gateway.service.auth_identity import resolve_user_id
from gateway.service.keygen import generate_key


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MASTER_KEY", "test-master-key-32-chars-long-xxx")
    monkeypatch.setenv("API_KEY_SIGNING_SECRET", "test-master-key-32-chars-long-xxx")
    monkeypatch.setenv("ADMIN_PASSKEY", "test-admin-passkey")


def make_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()],
    }
    return Request(scope)


class TestAuthIdentity:
    def test_anonymous_user(self):
        req = make_request()
        assert resolve_user_id(req, require_registered=False) == "usr-anonymous"

        with pytest.raises(Exception) as exc:
            resolve_user_id(req, require_registered=True)
        assert exc.value.status_code == 401

    def test_studio_admin_token(self):
        admin_key = generate_key("studio-admin")
        req = make_request({"Authorization": f"Bearer {admin_key}"})
        assert resolve_user_id(req, require_registered=False) == "usr-admin-primary"
        assert resolve_user_id(req, require_registered=True) == "usr-admin-primary"

    def test_registered_user_token(self):
        user_uuid = "usr-a1b2c3d4e5f6"
        user_key = generate_key(f"usr-{user_uuid}")
        req = make_request({"Authorization": f"Bearer {user_key}"})
        assert resolve_user_id(req, require_registered=False) == user_uuid
        assert resolve_user_id(req, require_registered=True) == user_uuid

    def test_guest_token_rejected_for_registered_scope(self):
        guest_key = generate_key("guest")
        req = make_request({"Authorization": f"Bearer {guest_key}"})
        assert resolve_user_id(req, require_registered=False) == "usr-guest"
        with pytest.raises(Exception) as exc:
            resolve_user_id(req, require_registered=True)
        assert exc.value.status_code == 401


class TestStorageUserStores:
    @pytest.mark.parametrize("store_name", ["user_knowledge", "user_webhooks", "user_api_keys", "user_projects"])
    def test_crud_and_isolation(self, store_name):
        user_a = "usr-test-user-a"
        user_b = "usr-test-user-b"
        rec_id = f"test_{store_name}_01"

        # Save record for user A
        saved = storage.save_user_store_record(store_name, user_a, rec_id, {"title": "Doc A", "value": 42})
        assert saved["id"] == rec_id
        assert saved["title"] == "Doc A"

        # User A can get and list
        rec = storage.get_user_store_record(store_name, user_a, rec_id)
        assert rec is not None
        assert rec["title"] == "Doc A"
        list_a = storage.list_user_store(store_name, user_a)
        assert any(r["id"] == rec_id for r in list_a)

        # User B cannot see user A's record (cross-user isolation)
        rec_b = storage.get_user_store_record(store_name, user_b, rec_id)
        assert rec_b is None
        list_b = storage.list_user_store(store_name, user_b)
        assert not any(r["id"] == rec_id for r in list_b)

        # User B cannot delete user A's record
        del_b = storage.delete_user_store_record(store_name, user_b, rec_id)
        assert del_b is False

        # User A can delete
        del_a = storage.delete_user_store_record(store_name, user_a, rec_id)
        assert del_a is True
        assert storage.get_user_store_record(store_name, user_a, rec_id) is None


class TestFrontendCompatEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_knowledge_crud(self, client):
        admin_key = generate_key("studio-admin")
        headers = {"Authorization": f"Bearer {admin_key}"}

        # Add knowledge doc
        res = client.post("/api/user/knowledge", json={"title": "Test Persisted Knowledge", "content": "SupremeAI 2.0"}, headers=headers)
        assert res.status_code == 200
        doc = res.json().get("document", {})
        doc_id = doc.get("id")
        assert doc_id is not None

        # List knowledge docs
        res_list = client.get("/api/user/knowledge", headers=headers)
        assert res_list.status_code == 200
        docs = res_list.json().get("documents", [])
        assert any(d.get("id") == doc_id for d in docs)

        # Delete knowledge doc
        res_del = client.delete(f"/api/user/knowledge/{doc_id}", headers=headers)
        assert res_del.status_code == 200

    def test_webhooks_crud(self, client):
        admin_key = generate_key("studio-admin")
        headers = {"Authorization": f"Bearer {admin_key}"}

        # Create webhook
        res = client.post("/api/user/webhooks", json={"url": "https://example.com/hook", "event": "chat.completion"}, headers=headers)
        assert res.status_code == 200
        wid = res.json().get("webhook", {}).get("id")
        assert wid is not None

        # List webhooks
        res_list = client.get("/api/user/webhooks", headers=headers)
        assert res_list.status_code == 200
        assert any(w.get("id") == wid for w in res_list.json().get("webhooks", []))

        # Delete webhook
        res_del = client.delete(f"/api/user/webhooks/{wid}", headers=headers)
        assert res_del.status_code == 200

    def test_api_keys_crud(self, client):
        admin_key = generate_key("studio-admin")
        headers = {"Authorization": f"Bearer {admin_key}"}

        # Create API key
        res = client.post("/api/api-keys/create", json={"name": "Test Key"}, headers=headers)
        assert res.status_code == 200
        kid = res.json().get("key", {}).get("id")
        assert kid is not None

        # List API keys
        res_list = client.get("/api/api-keys", headers=headers)
        assert res_list.status_code == 200
        assert any(k.get("id") == kid for k in res_list.json().get("keys", []))

    def test_projects_crud(self, client):
        admin_key = generate_key("studio-admin")
        headers = {"Authorization": f"Bearer {admin_key}"}

        # Create project
        res = client.post("/api/v1/projects", json={"name": "Supreme Project"}, headers=headers)
        assert res.status_code == 200
        pid = res.json().get("project", {}).get("id")
        assert pid is not None

        # List projects
        res_list = client.get("/api/v1/projects", headers=headers)
        assert res_list.status_code == 200
        assert any(p.get("id") == pid for p in res_list.json().get("projects", []))

        # Delete project
        res_del = client.delete(f"/api/v1/projects/{pid}", headers=headers)
        assert res_del.status_code == 200

    def test_tts_edge_synthesis(self, client):
        # Empty text fails with 400
        res_empty = client.post("/api/tts/edge", json={"text": ""})
        assert res_empty.status_code == 400

        # Valid text produces audio/mpeg stream
        res_audio = client.post("/api/tts/edge", json={"text": "Hello SupremeAI"})
        # Should be 200 audio/mpeg or 503 if network down, but never empty 200
        assert res_audio.status_code in (200, 503)
        if res_audio.status_code == 200:
            assert res_audio.headers.get("content-type") == "audio/mpeg"
            assert len(res_audio.content) > 0

    def test_transcribe_fails_closed(self, client, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        res = client.post("/api/transcribe", json={})
        assert res.status_code == 503

    def test_control_plane_stubs_fail_closed(self, client):
        admin_key = generate_key("studio-admin")
        headers = {"Authorization": f"Bearer {admin_key}"}

        # Kaggle unconfigured -> 503
        res_kaggle = client.post("/api/admin/control-plane/kaggle-dispatch", json={}, headers=headers)
        assert res_kaggle.status_code == 503

        # Telegram unconfigured -> 503
        res_tg = client.post("/api/admin/control-plane/telegram-dispatch", json={}, headers=headers)
        assert res_tg.status_code == 503

    def test_safety_mode_persists_and_roundtrips(self, client):
        admin_key = generate_key("studio-admin")
        headers = {"Authorization": f"Bearer {admin_key}"}
        url = "/api/admin/control-plane/safety-mode"
        valid = ("read-only", "dry-run-hitl", "operator-override")

        # Establish a deterministic baseline regardless of prior state.
        client.post(url, json={"safetyMode": "dry-run-hitl"}, headers=headers)

        # GET returns a valid posture under both keys for frontend compatibility.
        body = client.get(url, headers=headers).json()
        assert body["safetyMode"] == "dry-run-hitl"
        assert body["mode"] == body["safetyMode"]

        # POST updates the mode and echoes it back.
        res_post = client.post(url, json={"safetyMode": "read-only", "actor": "admin@test"}, headers=headers)
        assert res_post.status_code == 200
        assert res_post.json()["safetyMode"] == "read-only"

        # The new posture is durable across a subsequent read.
        assert client.get(url, headers=headers).json()["safetyMode"] == "read-only"

        # Overview reflects the same persisted posture (no more hardcoded value).
        overview = client.get("/api/admin/control-plane/overview", headers=headers)
        assert overview.status_code == 200
        assert overview.json()["safetyMode"] == "read-only"

        # Invalid posture is rejected fail-closed (the old "normal" value is gone).
        res_bad = client.post(url, json={"safetyMode": "normal"}, headers=headers)
        assert res_bad.status_code == 400
        assert client.get(url, headers=headers).json()["safetyMode"] in valid

        # Reset to default for test hygiene.
        client.post(url, json={"safetyMode": "dry-run-hitl"}, headers=headers)
