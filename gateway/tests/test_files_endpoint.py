"""
বাংলা মন্তব্য: /api/files/{path} endpoint-এর জন্য quick manual verification test —
functional (GET/PUT round-trip) + security (path traversal, blocked extension,
oversized file) coverage। AUDIT-018 (৩য় আইটেম)।
"""

import os

os.environ["ALLOW_TEST_AUTH_BYPASS"] = "true"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.files import router


@pytest.fixture
def client(tmp_path, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "workspace_base_dir", str(tmp_path))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer mock_test_jwt_token"}


def test_write_then_read_roundtrip(client):
    r = client.put("/api/files/notes/todo.md", json={"content": "hello world"}, headers=_auth())
    assert r.status_code == 200, r.text
    r2 = client.get("/api/files/notes/todo.md", headers=_auth())
    assert r2.status_code == 200
    assert r2.json()["content"] == "hello world"


def test_path_traversal_dotdot_blocked(client):
    r = client.put("/api/files/../../../etc/passwd", json={"content": "pwned"}, headers=_auth())
    assert r.status_code in (400, 404), r.text


def test_path_traversal_encoded_blocked(client):
    r = client.put(
        "/api/files/%2e%2e%2f%2e%2e%2fetc%2fpasswd", json={"content": "pwned"}, headers=_auth()
    )
    assert r.status_code in (400, 404), r.text


def test_blocked_extension(client):
    r = client.put(
        "/api/files/evil.sh",
        json={"content": "#!/bin/bash\necho malicious_payload_blocked"},
        headers=_auth(),
    )
    assert r.status_code == 400, r.text


def test_oversized_file_rejected(client):
    r = client.put("/api/files/big.txt", json={"content": "A" * (3 * 1024 * 1024)}, headers=_auth())
    assert r.status_code == 413, r.text


def test_read_nonexistent_file_404(client):
    r = client.get("/api/files/does/not/exist.md", headers=_auth())
    assert r.status_code == 404
