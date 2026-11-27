"""Private user stores must not turn corruption or outages into success."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from gateway.service import frontend_compat as fc
from gateway.service import storage


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_DB_PATH", str(tmp_path / "user-store.sqlite"))
    monkeypatch.setattr(storage, "_USE_MEM_FALLBACK", False)
    storage.init_db()
    monkeypatch.setattr(fc, "_require_uid", lambda request: "alice")
    app = FastAPI()
    app.include_router(fc.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("table,path,field", [
    ("user_knowledge", "/api/user/knowledge", "documents"),
    ("user_webhooks", "/api/user/webhooks", "webhooks"),
    ("user_api_keys", "/api/api-keys", "keys"),
    ("user_projects", "/api/v1/projects", "projects"),
])
def test_corruption_never_returns_partial_or_fake_empty(client, table, path, field):
    storage.save_user_store_record(table, "alice", "good", {"value": "visible"})
    with storage.get_db() as conn:
        conn.execute(f"INSERT INTO {table} (id, user_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                     ("bad", "alice", "{private invalid", 2, 2))
    response = client.get(path)
    assert response.status_code == 503
    assert "private invalid" not in response.text
    assert field not in response.json()
    assert storage.list_user_store(table, "bob") == []


def test_user_store_database_down_never_succeeds_in_memory(client, monkeypatch):
    monkeypatch.setattr(storage, "_USE_MEM_FALLBACK", True)
    assert client.get("/api/user/knowledge").status_code == 503
    assert client.post("/api/user/knowledge", json={"title": "secret"}).status_code == 503
    assert client.delete("/api/user/knowledge/id").status_code == 503
    assert "alice" not in storage._MEM_FALLBACK["user_knowledge"]


def test_invalid_json_or_non_object_fails_individual_read(client):
    with storage.get_db() as conn:
        conn.execute("INSERT INTO user_knowledge (id, user_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                     ("bad", "alice", '[]', 2, 2))
    with pytest.raises(storage.UserStoreUnavailable):
        storage.get_user_store_record("user_knowledge", "alice", "bad")
    with pytest.raises(storage.UserStoreUnavailable):
        storage.list_user_store("user_knowledge", "alice")


def test_cross_owner_id_collision_does_not_report_save_success(client):
    storage.save_user_store_record("user_knowledge", "bob", "shared-id", {"title": "owned"})
    with pytest.raises(PermissionError):
        storage.save_user_store_record("user_knowledge", "alice", "shared-id", {"title": "fake"})
    assert storage.get_user_store_record("user_knowledge", "bob", "shared-id")["title"] == "owned"


def test_real_connection_and_query_failure_return_503(client, monkeypatch):
    real_connect = storage.sqlite3.connect
    monkeypatch.setattr(storage.sqlite3, "connect", lambda *a, **kw: (_ for _ in ()).throw(OSError("secret details")))
    response = client.get("/api/user/knowledge")
    assert response.status_code == 503 and "secret details" not in response.text
    monkeypatch.setattr(storage.sqlite3, "connect", real_connect)
    with storage.get_db() as conn:
        conn.execute("DROP TABLE user_knowledge")
    assert client.get("/api/user/knowledge").status_code == 503


def test_commit_failure_not_acknowledged(client, monkeypatch):
    real_connect = storage.sqlite3.connect

    class BrokenCommit(storage.sqlite3.Connection):
        def commit(self):
            raise storage.sqlite3.OperationalError("private commit detail")

    monkeypatch.setattr(storage.sqlite3, "connect", lambda *a, **kw: real_connect(*a, **kw, factory=BrokenCommit))
    response = client.post("/api/user/knowledge", json={"title": "fixture"})
    assert response.status_code == 503 and "private commit detail" not in response.text
    monkeypatch.setattr(storage.sqlite3, "connect", real_connect)
    assert storage.list_user_store("user_knowledge", "alice") == []


def test_seed_collision_rolls_back_entire_batch(client):
    storage.save_user_store_record("user_knowledge", "bob", "foreign", {"title": "bob"})
    response = client.post("/api/v1/knowledge/seed", json=[
        {"id": "first", "title": "alice"}, {"id": "foreign", "title": "overwrite"},
    ])
    assert response.status_code == 409
    assert storage.get_user_store_record("user_knowledge", "alice", "first") is None
    assert storage.get_user_store_record("user_knowledge", "bob", "foreign")["title"] == "bob"


def test_created_id_and_key_are_not_overridden_by_request(client):
    response = client.post("/api/api-keys/create", json={"id": "attacker", "key": "injected"})
    assert response.status_code == 200
    key = response.json()["key"]
    assert key["id"] != "attacker" and key["key"] != "injected"
    assert storage.get_user_store_record("user_api_keys", "alice", key["id"])["key"] == key["key"]
