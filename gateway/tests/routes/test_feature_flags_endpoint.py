"""Issue #1818 bug-3: /admin-api/feature-flags backed by the REAL table.

Pins: canonical runtime flag names surfaced, POST persists via table upsert
+ resets the runtime cache (toggle affects gating without restart), and the
surface degrades honestly (503) when Supabase is unreachable — no more
hardcoded fake flag list.
"""

import pytest
from fastapi.testclient import TestClient

from api.routes.admin_dashboard import require_admin_token
from core.app import app
from core.feature_flags import RUNTIME_FLAG_NAMES, feature_flags

client = TestClient(app)


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    """Minimal supabase-py table chain for the flags surface."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.upserts: list[dict] = []
        self.updates: list[dict] = []

    def select(self, *_a):
        return self

    def upsert(self, payload, on_conflict=None):  # noqa: ARG002
        self.upserts.append(payload)
        return self

    def update(self, updates):
        self._pending_updates = updates
        self.updates.append(updates)
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        if self.updates:
            for row in self.rows:
                row.update(self._pending_updates)
        return _Result(self.rows)


class _FakeDB:
    def __init__(self, rows=None):
        self.table_obj = _FakeTable(rows or [])
        self.client = type("RawClient", (), {})()
        self.client.table = lambda _name: self.table_obj


@pytest.fixture()
def admin_auth():
    saved = app.dependency_overrides.get(require_admin_token)
    app.dependency_overrides[require_admin_token] = lambda: {
        "sub": "admin",
        "uid": "admin",
        "role": "admin",
    }
    yield
    if saved is None:
        app.dependency_overrides.pop(require_admin_token, None)
    else:
        app.dependency_overrides[require_admin_token] = saved


def test_get_lists_canonical_runtime_flag_names(admin_auth, monkeypatch):
    import database.supabase_client as supabase_module

    monkeypatch.setattr(supabase_module, "db", _FakeDB(rows=[]))
    resp = client.get("/admin-api/feature-flags")
    assert resp.status_code == 200
    names = {f["name"] for f in resp.json()["flags"]}
    assert set(RUNTIME_FLAG_NAMES) <= names  # names the runtime actually reads
    for f in resp.json()["flags"]:
        if f["name"] in RUNTIME_FLAG_NAMES and f["source"] == "default":
            assert f["enabled"] is False


def test_post_persists_row_and_resets_runtime_cache(admin_auth, monkeypatch):
    import database.supabase_client as supabase_module

    fake_db = _FakeDB(rows=[])
    monkeypatch.setattr(supabase_module, "db", fake_db)
    # Seed a stale runtime cache entry — the POST must drop it (toggle takes
    # effect on the next request without a restart).
    feature_flags._cache["mem0_enabled"] = True
    resp = client.post(
        "/admin-api/feature-flags",
        json={"name": "mem0_enabled", "enabled": False, "rollout": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert (
        fake_db.table_obj.upserts and fake_db.table_obj.upserts[0]["feature_name"] == "mem0_enabled"
    )
    assert "mem0_enabled" not in feature_flags._cache  # cache was reset


def test_db_unreachable_is_honest_503(admin_auth, monkeypatch):
    import database.supabase_client as supabase_module

    monkeypatch.setattr(supabase_module, "db", None)
    resp = client.get("/admin-api/feature-flags")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()
