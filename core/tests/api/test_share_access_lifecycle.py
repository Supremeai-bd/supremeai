"""বাংলা মন্তব্য: real FastAPI router + in-memory DB double; expiry/revoke cache-hit regression.

DB/auth transport আলাদা রাখা হয়েছে; production JWT, full-app boot বা live Supabase E2E নয়।
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

SHARE = Path(__file__).resolve().parents[2] / "api/routes/share.py"


class FakeDatabase:
    def __init__(self):
        self.rows = {
            "shared_conversations": [
                {
                    "share_id": "AbCdEf123456",
                    "user_id": "owner",
                    "conversation_id": "conversation",
                    "is_public": True,
                    "view_count": 0,
                    "created_at": "2026-01-01T00:00:00Z",
                    "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                }
            ],
            "conversations": [{"id": "conversation", "user_id": "owner", "title": "বাংলা আলাপ"}],
            "messages": [
                {
                    "id": "message",
                    "conversation_id": "conversation",
                    "role": "user",
                    "content": "private shared content",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
        self.down = False
        self.client = self
        self.reads = {}

    def table(self, name):
        return Query(self, name)


class Query:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.filters = []
        self.action, self.payload = "select", None

    def select(self, *_):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self.action, self.payload = "update", payload
        return self

    def delete(self):
        self.action = "delete"
        return self

    def execute(self):
        if self.db.down:
            raise RuntimeError("DB unavailable")
        rows = self.db.rows[self.name]
        matches = [r for r in rows if all(r.get(k) == v for k, v in self.filters)]
        if self.action == "delete":
            self.db.rows[self.name] = [r for r in rows if r not in matches]
        elif self.action == "update":
            for row in matches:
                row.update(self.payload)
        else:
            self.db.reads[self.name] = self.db.reads.get(self.name, 0) + 1
        return SimpleNamespace(data=deepcopy(matches))


@pytest.fixture
def harness(monkeypatch):
    db = FakeDatabase()

    async def auth():
        raise HTTPException(status_code=401, detail="test unauthenticated")

    for name, attrs in {
        "api.deps": {"get_current_user_token": auth},
        "database.supabase_client": {"get_db": lambda: db},
        "core.monitoring.logging_config": {"logger": logging.getLogger("share-test")},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)

    def worker(name, user=None):
        spec = importlib.util.spec_from_file_location(name, SHARE)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router)
        if user is not None:
            app.dependency_overrides[auth] = lambda: {"sub": user}
        return module, TestClient(app, raise_server_exceptions=False)

    return db, worker


def test_warm_cache_is_not_authorization(harness):
    db, worker = harness
    module, client = worker("share_visibility")
    assert client.get("/api/share/AbCdEf123456").status_code == 200
    db.rows["shared_conversations"][0]["is_public"] = False
    response = client.get("/api/share/AbCdEf123456")
    assert response.headers.get("cache-control") == "no-store"
    assert response.status_code == 404
    assert "private shared content" not in response.text
    assert "AbCdEf123456" not in module._share_cache


def test_warm_cache_checks_fresh_expiry(harness):
    db, worker = harness
    _, client = worker("share_expiry")
    assert client.get("/api/share/AbCdEf123456").status_code == 200
    db.rows["shared_conversations"][0]["expires_at"] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    response = client.get("/api/share/AbCdEf123456")
    assert response.headers.get("cache-control") == "no-store"
    assert response.status_code == 410
    assert "private shared content" not in response.text


def test_revocation_in_other_worker_invalidates_access(harness):
    _, worker = harness
    module, reader = worker("share_reader")
    _, owner = worker("share_owner", user="owner")
    assert reader.get("/api/share/AbCdEf123456").status_code == 200
    assert "AbCdEf123456" in module._share_cache
    assert owner.delete("/api/share/AbCdEf123456").status_code == 200
    assert reader.get("/api/share/AbCdEf123456").status_code == 404


def test_database_outage_does_not_serve_cached_content(harness):
    db, worker = harness
    _, client = worker("share_db_failure")
    assert client.get("/api/share/AbCdEf123456").status_code == 200
    db.down = True
    response = client.get("/api/share/AbCdEf123456")
    assert response.status_code == 500
    assert "private shared content" not in response.text


def test_success_is_no_store_and_still_caches_messages(harness):
    db, worker = harness
    _, client = worker("share_cache_efficiency")
    for _ in range(2):
        response = client.get("/api/share/AbCdEf123456")
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-store"
        assert response.json()["messages"][0]["content"] == "private shared content"
    assert db.reads["shared_conversations"] == 2
    assert db.reads["messages"] == 1
    assert response.json()["view_count"] == 2


@pytest.mark.parametrize("user,status", [(None, 401), ("intruder", 403), ("owner", 200)])
def test_revoke_keeps_auth_ownership_checks(harness, user, status):
    db, worker = harness
    _, client = worker("share_auth", user=user)
    assert client.delete("/api/share/AbCdEf123456").status_code == status
    assert bool(db.rows["shared_conversations"]) is (status != 200)


def test_lru_cache_is_bounded_and_does_not_mutate_input(harness):
    _, worker = harness
    module, _ = worker("share_lru")
    payload = {"payload": "original"}
    for i in range(600):
        module._cache_set(str(i), payload)
    assert payload == {"payload": "original"}
    assert len(module._share_cache) == module._SHARE_CACHE_MAX_SIZE == 500
    assert module._cache_get("0") is None
    assert module._cache_get("100") is not None
    module._cache_set("600", payload)
    assert module._cache_get("101") is None
    assert module._cache_get("100") is not None


def test_cache_ttl_boundary_and_update(harness, monkeypatch):
    _, worker = harness
    module, _ = worker("share_ttl")
    clock = [1.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    module._cache_set("one", {"data": 1})
    clock[0] += module._CACHE_TTL_SECONDS
    assert module._cache_get("one") is None
    module._cache_set("one", {"data": 2})
    assert module._cache_get("one")["data"] == 2


def test_cache_cannot_cross_conversation_identity(harness):
    db, worker = harness
    _, client = worker("share_identity")
    assert client.get("/api/share/AbCdEf123456").status_code == 200
    db.rows["shared_conversations"][0]["conversation_id"] = "missing-conversation"
    response = client.get("/api/share/AbCdEf123456")
    assert response.status_code == 404
    assert "private shared content" not in response.text
