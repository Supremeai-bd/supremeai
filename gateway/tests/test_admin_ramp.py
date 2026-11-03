"""Coverage ramp for api/routes/admin.py — admin Command Center surface (test-only).

Task 58 round: baseline 445 stmts + 78 branches @ 38% (existing tests/api/test_admin.py
covers only the fixes-auth happy paths and quick-action happy paths). This module drives
every endpoint group through a minimal FastAPI app with dependency overrides — no owner
code is modified (wire-first).

Seams used (all resolved at call time, no owner-code edits):
  - ar.god_layer / ar.redis_manager / ar.get_firestore_db  (module globals, instance-patched)
  - app.dependency_overrides[get_current_admin / ar.get_healer_service]
  - database.session.get_db_session / get_db_session_context (function-local imports)
  - alembic.command.downgrade / alembic.config.Config
  - sys.modules fakes for heavy in-function imports (agents.infrastructure.*,
    services.render_preflight_service) per the g50b optional-dependency doctrine
  - core.config.settings rebound at module level (pydantic settings may be frozen)

OWNER QUIRKS / DECISION ITEMS documented (never patched — wire-first):
  1. GET /api/admin/automation/executions error path returns HTTP 200 with
     {"status": "error", ...} instead of a 5xx — the audit-trail endpoint degrades
     silently; monitoring cannot distinguish "no history" from "history store down".
  2. POST /api/admin/actions/rollback resolves alembic.ini via CWD-relative
     Config("backend/alembic.ini") — breaks if the service CWD is not the repo root
     (owner's Render service runs from repo root today; fragile contract).
  3. POST /api/admin/actions/backup dumps every table with SELECT * and no
     pagination/limits — unbounded memory on production-sized tables.
  4. POST /api/admin/verify-otp deletes the pending key only on SUCCESS — failed
     attempts leave the pending OTP consumable indefinitely (attempt throttling is
     delegated entirely to the issuing middleware).
"""

import json
import sys
import types
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes.admin as ar
from api.dependencies import get_current_admin

ADMIN = {"sub": "admin-ramp", "role": "admin"}


# ─────────────────────────── fakes ───────────────────────────


class FakeResult:
    """Minimal SQLAlchemy result stand-in covering fetchall/keys/scalars."""

    def __init__(self, rows=None, columns=None, scalars_list=None):
        self._rows = rows or []
        self._columns = columns or []
        self._scalars = scalars_list

    def fetchall(self):
        return self._rows

    def keys(self):
        return self._columns

    def scalars(self):
        holder = self

        class _S:
            def all(self):
                return holder._scalars or []

        return _S()


class FakeSession:
    """Async session stand-in: execute returns queued results; add/commit record calls."""

    def __init__(self, results=None):
        self.results = list(results or [])
        self.execute_calls = []
        self.added = []
        self.commits = 0
        # ISSUE-1588 follow-through (#1753 round 2): the backup route now
        # quotes table identifiers through the SQLAlchemy dialect preparer
        # (session.bind.dialect.identifier_preparer). Mirror that surface:
        # valid identifiers (^[A-Za-z0-9_]+$ — the route's regex pre-filter)
        # stay unquoted in SQLAlchemy, so a passthrough is faithful here.
        self.bind = SimpleNamespace(
            dialect=SimpleNamespace(identifier_preparer=SimpleNamespace(quote=lambda name: name))
        )

    async def execute(self, stmt):
        self.execute_calls.append(stmt)
        if not self.results:
            raise AssertionError("FakeSession: unexpected execute (no queued results)")
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def fake_session_gen(session):
    async def _gen():
        yield session

    return _gen()


def fake_session_ctx(session):
    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


class FakeRedisManager:
    """redis_manager stand-in: client + cache methods used by admin routes."""

    def __init__(self, client=None, store=None):
        self.client = client
        self._store = dict(store or {})

    async def get_cache(self, key):
        return self._store.get(key)

    async def set_cache(self, key, value, ex_seconds=None):
        self._store[key] = value
        return True

    async def get(self, key):
        return self._store.get(key)


def install_sysmodule(monkeypatch, name, **attrs):
    """Inject a fake module into sys.modules (g50b seam) and return it."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


# ─────────────────────────── fixtures ───────────────────────────


@pytest.fixture
def client(monkeypatch):
    # permissive god-layer default (real AdminGodLayer.enforce raises PermissionError
    # under test constitutional rules); NOTE: set_rule/enforce are SYNC calls in the
    # route bodies (no await) — must be MagicMock, not AsyncMock
    monkeypatch.setattr(
        ar,
        "god_layer",
        SimpleNamespace(
            set_rule=MagicMock(return_value=None),
            enforce=MagicMock(return_value=None),
            list_rules=lambda: [{"key": "r1", "value": "v1"}],
        ),
    )
    app = FastAPI()
    app.include_router(ar.router)
    app.dependency_overrides[get_current_admin] = lambda: ADMIN
    # default healer override: get_healer_service is a router dependency and would
    # 503 before reaching handler bodies (real get_firestore_db() is None in tests)
    app.dependency_overrides[ar.get_healer_service] = lambda: SimpleNamespace(
        apply_fix=AsyncMock(return_value=True)
    )
    return TestClient(app)


@pytest.fixture
def god():
    return SimpleNamespace(
        set_rule=MagicMock(return_value=None),
        enforce=MagicMock(return_value=None),
        list_rules=lambda: [{"key": "r1", "value": "v1"}],
    )


@pytest.fixture
def healer():
    return SimpleNamespace(apply_fix=AsyncMock(return_value=True))


def install_healer(app, healer):
    app.dependency_overrides[ar.get_healer_service] = lambda: healer


# ─────────────────────── helpers ───────────────────────


class TestHelpers:
    def test_require_tenant_id_rejects_empty_and_default(self):
        from fastapi import HTTPException

        for bad in (None, "", "   ", "default"):
            with pytest.raises(HTTPException) as ei:
                ar.require_tenant_id(bad)
            assert ei.value.status_code == 400
            assert ei.value.detail == "Tenant context required"

    def test_require_tenant_id_normalizes_valid(self):
        assert ar.require_tenant_id("  tenant-x  ") == "tenant-x"

    def test_get_healer_service_503_without_db(self):
        from fastapi import HTTPException

        original = ar.get_firestore_db
        ar.get_firestore_db = lambda: None
        try:
            with pytest.raises(HTTPException) as ei:
                ar.get_healer_service()
            assert ei.value.status_code == 503
            assert ei.value.detail == "Database unavailable"
        finally:
            ar.get_firestore_db = original

    def test_get_healer_service_returns_service_with_db(self):
        from core.health.self_healer import SelfHealerService

        marker = object()
        original = ar.get_firestore_db
        ar.get_firestore_db = lambda: marker
        try:
            svc = ar.get_healer_service()
            assert isinstance(svc, SelfHealerService)
        finally:
            ar.get_firestore_db = original


# ─────────────────────── rules ───────────────────────


class TestRules:
    def test_post_rule_success(self, client, monkeypatch, god):
        monkeypatch.setattr(ar, "god_layer", god)
        resp = client.post("/api/admin/rules", json={"key": "k", "value": "v"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "Rule k updated" in body["message"]
        god.set_rule.assert_called_once_with("k", "v")

    def test_post_rule_god_failure_returns_500_with_correlation_id(self, client, monkeypatch):
        god = SimpleNamespace(set_rule=MagicMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr(ar, "god_layer", god)
        resp = client.post("/api/admin/rules", json={"key": "k", "value": "v"})
        assert resp.status_code == 500
        assert "correlation_id:" in resp.json()["detail"]
        # raw exception text must not reach the client (AUD-2.9)
        assert "boom" not in resp.json()["detail"]

    def test_get_rules(self, client, monkeypatch, god):
        monkeypatch.setattr(ar, "god_layer", god)
        resp = client.get("/api/admin/rules")
        assert resp.status_code == 200
        assert resp.json() == {"rules": [{"key": "r1", "value": "v1"}]}


# ─────────────────────── quick actions ───────────────────────


class TestQuickActions:
    def test_cache_action_zero_keys_skips_delete(self, client, monkeypatch):
        # বাংলা মন্তব্য (#2830): প্রোডাকশন purge SCAN-চুক্তিতে — scan_iter-ই
        # কী-সোর্স; খালি async-iterator = zero keys। পুরনো keys()-মক স্টেল।
        def _empty_scan_iter(*args, **kwargs):
            async def _gen():
                return
                yield  # noqa: B901 — async generator টাইপ নিশ্চিত করতে অপ্রাপ্য শাখা

            return _gen()

        redis_client = SimpleNamespace(scan_iter=_empty_scan_iter, delete=AsyncMock())
        fake = FakeRedisManager(client=redis_client)
        monkeypatch.setattr(ar, "redis_manager", fake)
        resp = client.post("/api/admin/actions/cache")
        assert resp.status_code == 200
        assert "Deleted 0 keys" in resp.json()["message"]
        redis_client.delete.assert_not_awaited()

    def test_cache_action_redis_unavailable_503(self, client, monkeypatch):
        monkeypatch.setattr(ar, "redis_manager", FakeRedisManager(client=None))
        resp = client.post("/api/admin/actions/cache")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Redis client unavailable"

    def test_backup_skips_invalid_table_names(self, client, monkeypatch):
        session = FakeSession(
            results=[
                FakeResult(rows=[("good_table",), ("bad-table!",), ("",)]),
                FakeResult(rows=[("r1",)], columns=["id"]),
            ]
        )
        monkeypatch.setattr("database.session.get_db_session", lambda: fake_session_gen(session))
        resp = client.post("/api/admin/actions/backup")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_backup_serializes_datetime_values(self, client, monkeypatch):
        session = FakeSession(
            results=[
                FakeResult(rows=[("good_table",)]),
                FakeResult(rows=[("r1", datetime(2026, 9, 15, 12, 0, 0))], columns=["id", "at"]),
            ]
        )
        monkeypatch.setattr("database.session.get_db_session", lambda: fake_session_gen(session))
        resp = client.post("/api/admin/actions/backup")
        assert resp.status_code == 200
        assert "backup" in resp.json()["message"]

    def test_backup_failure_500(self, client, monkeypatch):
        session = FakeSession(results=[RuntimeError("db down")])
        monkeypatch.setattr("database.session.get_db_session", lambda: fake_session_gen(session))
        resp = client.post("/api/admin/actions/backup")
        assert resp.status_code == 500
        assert "Database backup failed" in resp.json()["detail"]

    def test_rollback_failure_500(self, client, monkeypatch):
        def boom(cfg, rev):
            raise RuntimeError("downgrade exploded")

        monkeypatch.setattr("alembic.command.downgrade", boom)
        resp = client.post("/api/admin/actions/rollback")
        assert resp.status_code == 500
        assert "Rollback operation failed" in resp.json()["detail"]

    def test_rollback_success(self, client, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            "alembic.command.downgrade",
            lambda cfg, rev: calls.setdefault("rev", rev),
        )
        resp = client.post("/api/admin/actions/rollback")
        assert resp.status_code == 200
        assert calls["rev"] == "-1"

    def test_unknown_action_404(self, client):
        resp = client.post("/api/admin/actions/nope")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Action not found"


# ─────────────────────── fixes lifecycle ───────────────────────


class TestFixesLifecycle:
    def _firestore(self, docs=(), stream_docs=()):
        db = SimpleNamespace(
            collection=lambda *_: SimpleNamespace(
                document=lambda *_: SimpleNamespace(
                    collection=lambda *_: SimpleNamespace(
                        where=lambda *_: SimpleNamespace(
                            get=AsyncMock(return_value=list(docs)),
                            stream=lambda: iter(list(stream_docs)),
                        )
                    ),
                    update=AsyncMock(return_value=None),
                )
            )
        )
        return db

    async def test_get_fixes_async_query(self, client, monkeypatch):
        doc = SimpleNamespace(id="f1", to_dict=lambda: {"status": "pending_review"})
        monkeypatch.setattr(ar, "get_firestore_db", lambda: self._firestore(docs=[doc]))
        resp = client.get("/api/admin/fixes?tenant_id=t1")
        assert resp.status_code == 200
        assert resp.json()["fixes"] == [{"status": "pending_review", "id": "f1"}]

    async def test_get_fixes_sync_fallback_on_typeerror(self, client, monkeypatch):
        doc = SimpleNamespace(id="f2", to_dict=lambda: {"status": "pending_review"})
        # first get() call raises TypeError (sync mock), fallback arm calls get() again
        query_holder = {}

        def make_query():
            class Q:
                def where(self, *_a):
                    return self

                def get(self):
                    if query_holder.get("first") is None:
                        query_holder["first"] = True
                        raise TypeError("sync mock")
                    return [doc]

            return Q()

        db = SimpleNamespace(
            collection=lambda *_: SimpleNamespace(
                document=lambda *_: SimpleNamespace(
                    collection=lambda *_: SimpleNamespace(where=lambda *_: make_query())
                )
            )
        )
        monkeypatch.setattr(ar, "get_firestore_db", lambda: db)
        resp = client.get("/api/admin/fixes?tenant_id=t1")
        assert resp.status_code == 200
        assert resp.json()["fixes"] == [{"status": "pending_review", "id": "f2"}]

    def test_get_fixes_no_firestore_503(self, client, monkeypatch):
        # Issue #1470: the read endpoint now surfaces a clean 503 instead of
        # crashing on a None db when Firestore is unavailable.
        monkeypatch.setattr(ar, "get_firestore_db", lambda: None)
        resp = client.get("/api/admin/fixes")
        assert resp.status_code == 503

    def test_get_fixes_cross_tenant_when_no_tenant_given(self, client, monkeypatch):
        # Issue #1470 (HIGH): GET /api/admin/fixes used to hard-fail with
        # 400 "Tenant context required" for authenticated admins. The read
        # endpoint now falls back to a cross-tenant collectionGroup('fixes')
        # query, tagging each fix with its owning tenant. Mutations still
        # require an explicit tenant_id.
        ref = SimpleNamespace(parent=SimpleNamespace(parent=SimpleNamespace(id="t9")))
        doc = SimpleNamespace(id="f3", to_dict=lambda: {"status": "pending_review"}, reference=ref)
        cg = SimpleNamespace(where=lambda *_: SimpleNamespace(get=AsyncMock(return_value=[doc])))
        db = SimpleNamespace(collection_group=lambda *_: cg)
        monkeypatch.setattr(ar, "get_firestore_db", lambda: db)
        resp = client.get("/api/admin/fixes")
        assert resp.status_code == 200
        assert resp.json()["fixes"] == [{"status": "pending_review", "id": "f3", "tenant_id": "t9"}]

    def test_apply_fixes_no_firestore_returns_zero(self, client, monkeypatch):
        monkeypatch.setattr(ar, "get_firestore_db", lambda: None)
        resp = client.post("/api/admin/fixes/apply?tenant_id=t1")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "status": "success",
            "applied": 0,
            "message": "No Firestore available",
        }

    def test_apply_fixes_counts_applied(self, client, monkeypatch, healer):
        d1 = SimpleNamespace(id="f1")
        d2 = SimpleNamespace(id="f2")
        d3 = SimpleNamespace(id="f3")
        db = SimpleNamespace(
            collection=lambda *_: SimpleNamespace(
                document=lambda *_: SimpleNamespace(
                    collection=lambda *_: SimpleNamespace(
                        where=lambda *_: SimpleNamespace(stream=lambda: iter([d1, d2, d3]))
                    )
                )
            )
        )
        monkeypatch.setattr(ar, "get_firestore_db", lambda: db)
        healer.apply_fix = AsyncMock(side_effect=[True, False, True])
        install_healer(client.app, healer)
        resp = client.post("/api/admin/fixes?tenant_id=t1")
        assert resp.status_code == 200
        assert resp.json()["applied"] == 2
        assert healer.apply_fix.await_count == 3

    def test_approve_fix_failure_400(self, client, monkeypatch, healer):
        healer.apply_fix = AsyncMock(return_value=False)
        install_healer(client.app, healer)
        resp = client.post("/api/admin/fixes/fx9/approve?tenant_id=t1")
        assert resp.status_code == 400
        assert "Failed to apply fix" in resp.json()["detail"]

    def test_approve_fix_success(self, client, monkeypatch, healer):
        install_healer(client.app, healer)
        resp = client.post("/api/admin/fixes/fx1/approve?tenant_id=t1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "fix_id": "fx1"}

    async def test_reject_fix_async_and_sync_update(self, client, monkeypatch):
        doc_ref = SimpleNamespace(update=AsyncMock(return_value=None))
        db = SimpleNamespace(
            collection=lambda *_: SimpleNamespace(
                document=lambda *_: SimpleNamespace(
                    collection=lambda *_: SimpleNamespace(document=lambda *_: doc_ref)
                )
            )
        )
        monkeypatch.setattr(ar, "get_firestore_db", lambda: db)
        resp = client.post("/api/admin/fixes/fx1/reject?tenant_id=t1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "fix_id": "fx1"}
        called = doc_ref.update.await_args.args[0]
        assert called["status"] == "rejected"
        assert called["reviewed_by"] == "admin-ramp"
        assert "applied_at" in called

    def test_reject_fix_sync_fallback_on_typeerror(self, client, monkeypatch):
        updates = {}

        class Ref:
            def update(self, data):
                if updates.get("raised") is None:
                    updates["raised"] = True
                    raise TypeError("sync mock")
                updates["data"] = data
                return "updated"

        db = SimpleNamespace(
            collection=lambda *_: SimpleNamespace(
                document=lambda *_: SimpleNamespace(
                    collection=lambda *_: SimpleNamespace(document=lambda *_: Ref())
                )
            )
        )
        monkeypatch.setattr(ar, "get_firestore_db", lambda: db)
        resp = client.post("/api/admin/fixes/fx2/reject?tenant_id=t1")
        assert resp.status_code == 200
        assert updates["data"]["status"] == "rejected"


# ─────────────────────── verify-otp ───────────────────────


class TestVerifyOtp:
    PENDING = json.dumps({"code": "123456", "signal": {"ip": "10.0.0.9"}})

    def _redis(self, seed):
        fake = FakeRedisManager(client=None, store=seed)
        # wire client.delete into the store so the success path's deletion is observable
        fake.client = SimpleNamespace(
            delete=AsyncMock(side_effect=lambda key: fake._store.pop(key, None))
        )
        return fake

    def test_503_without_redis_client(self, client, monkeypatch):
        monkeypatch.setattr(ar, "redis_manager", FakeRedisManager(client=None))
        resp = client.post("/api/admin/verify-otp", json={"code": "1"})
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Security store unavailable"

    def test_400_without_pending_verification(self, client, monkeypatch):
        monkeypatch.setattr(ar, "redis_manager", self._redis({}))
        resp = client.post("/api/admin/verify-otp", json={"code": "123456"})
        assert resp.status_code == 400
        assert "No pending verification" in resp.json()["detail"]

    def test_401_on_wrong_code(self, client, monkeypatch):
        fake = self._redis({"security:otp_pending:admin-ramp": self.PENDING})
        store = fake._store
        monkeypatch.setattr(ar, "redis_manager", fake)
        resp = client.post("/api/admin/verify-otp", json={"code": "999999"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid code"
        # quirk 4: pending key NOT consumed on failure
        assert "security:otp_pending:admin-ramp" in store

    def test_success_promotes_context_and_deletes_pending(self, client, monkeypatch):
        seed = {"security:otp_pending:admin-ramp": self.PENDING}
        fake = self._redis(seed)
        store = fake._store
        monkeypatch.setattr(ar, "redis_manager", fake)
        resp = client.post("/api/admin/verify-otp", json={"code": "123456"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "verified"}
        assert json.loads(store["security:last_context:admin-ramp"]) == {"ip": "10.0.0.9"}
        assert "security:otp_pending:admin-ramp" not in store
        fake.client.delete.assert_awaited_once_with("security:otp_pending:admin-ramp")


# ─────────────────────── system alerts ───────────────────────


class TestSystemAlerts:
    def _patch_db(self, monkeypatch, session):
        # NOTE: get_db_session is a MODULE-LEVEL import in api/routes/admin.py
        # (line 379), so the route namespace must be patched, not database.session
        monkeypatch.setattr(ar, "get_db_session", lambda: fake_session_gen(session))

    def _settings(self, monkeypatch, key):
        import core.config

        monkeypatch.setattr(
            core.config,
            "settings",
            SimpleNamespace(supremeai_api_key=key),
            raising=False,
        )

    def test_get_alerts(self, client, monkeypatch):
        record = SimpleNamespace(
            id="a1",
            level="warn",
            message="m",
            created_at=datetime.now(UTC),
            resolved=False,
            resolved_at=None,
        )
        session = FakeSession(results=[FakeResult(scalars_list=[record])])
        self._patch_db(monkeypatch, session)
        resp = client.get("/api/admin/alerts")
        assert resp.status_code == 200
        assert resp.json()["alerts"][0]["id"] == "a1"

    def test_create_alert_401_when_key_not_configured(self, client, monkeypatch):
        self._settings(monkeypatch, None)
        resp = client.post("/api/admin/alerts", json={"level": "warn", "message": "m"})
        assert resp.status_code == 401

    def test_create_alert_401_wrong_key(self, client, monkeypatch):
        from pydantic import SecretStr

        self._settings(monkeypatch, SecretStr("right-key"))
        resp = client.post(
            "/api/admin/alerts",
            json={"level": "warn", "message": "m"},
            headers={"x-api-key": "wrong-key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid internal API key"

    def test_create_alert_success(self, client, monkeypatch):
        from pydantic import SecretStr

        self._settings(monkeypatch, SecretStr("right-key"))
        session = FakeSession()
        self._patch_db(monkeypatch, session)
        resp = client.post(
            "/api/admin/alerts",
            json={"level": "warn", "message": "hello"},
            headers={"x-api-key": "right-key"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["id"]
        assert session.commits == 1
        assert session.added[0].level == "warn"

    def test_resolve_alert_success(self, client, monkeypatch):
        session = FakeSession(results=[FakeResult(rows=[])])
        self._patch_db(monkeypatch, session)
        resp = client.post("/api/admin/alerts/a1/resolve")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Alert resolved"
        assert session.commits == 1


# ─────────────────────── model branding + configs refresh ───────────────────────


class TestBrandingAndConfigs:
    def test_model_branding(self, client):
        resp = client.get("/api/admin/model-branding")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["models"], dict)
        assert isinstance(body["providers"], dict)

    def _patch_refresh_stack(self, monkeypatch, fail_on=None):
        session = SimpleNamespace()
        monkeypatch.setattr("database.session.get_db_session_context", fake_session_ctx(session))

        async def sync_ok(db):
            return None

        async def sync_boom(db):
            raise RuntimeError(fail_on or "sync exploded")

        target = sync_boom if fail_on else sync_ok
        monkeypatch.setattr("brain.model_registry.ModelRegistry.sync_from_db", target)
        econ = SimpleNamespace(sync_from_db=target)
        monkeypatch.setattr(
            "brain.economic_optimizer.get_economic_optimizer", AsyncMock(return_value=econ)
        )
        monkeypatch.setattr("utils.branding.sync_from_db", target)
        monkeypatch.setattr("core.resilience.circuit_breaker.sync_from_db", target)
        mon = SimpleNamespace(sync_from_db=target)
        monkeypatch.setattr("core.health.health_monitor.get_health_monitor", lambda: mon)
        monkeypatch.setattr("core.middleware.health_aware_middleware.sync_from_db", target)

    def test_configs_refresh_success(self, client, monkeypatch):
        self._patch_refresh_stack(monkeypatch)
        resp = client.post("/api/admin/configs/refresh")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_configs_refresh_failure_500(self, client, monkeypatch):
        self._patch_refresh_stack(monkeypatch, fail_on="registry exploded")
        resp = client.post("/api/admin/configs/refresh")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "registry exploded"


# ─────────────────────── infrastructure agents ───────────────────────


class TestInfrastructureAgents:
    ALL_ENV = {
        "ENABLE_MEMORY_AUGMENT": "memory_augment",
        "ENABLE_AUTOSCALING_AGENT": "auto_scaling",
        "ENABLE_PERFORMANCE_TUNING_AGENT": "performance_tuning",
        "ENABLE_COST_OPTIMIZATION_AGENT": "cost_optimization",
        "ENABLE_DISASTER_RECOVERY_AGENT": "disaster_recovery",
    }

    def test_status_all_disabled_by_default(self, client, monkeypatch):
        for var in self.ALL_ENV:
            monkeypatch.delenv(var, raising=False)
        resp = client.get("/api/admin/infrastructure/status")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert set(agents) == set(self.ALL_ENV.values())
        assert all(not a["enabled"] for a in agents.values())

    def test_status_all_enabled_via_env(self, client, monkeypatch):
        for var in self.ALL_ENV:
            monkeypatch.setenv(var, "true")
        resp = client.get("/api/admin/infrastructure/status")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert all(a["enabled"] for a in agents.values())

    def test_agent_enabled_env_semantics(self, monkeypatch):
        monkeypatch.setenv("ENABLE_X", "TRUE")
        assert ar._agent_enabled("ENABLE_X") is True
        monkeypatch.setenv("ENABLE_X", "1")
        assert ar._agent_enabled("ENABLE_X") is False
        monkeypatch.delenv("ENABLE_X")
        assert ar._agent_enabled("ENABLE_X") is False

    def test_cost_report_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_COST_OPTIMIZATION_AGENT", raising=False)
        resp = client.get("/api/admin/infrastructure/cost/report")
        assert resp.status_code == 503
        assert "ENABLE_COST_OPTIMIZATION_AGENT" in resp.json()["detail"]

    def _install_cost_agent(self, monkeypatch, report=None, forecast=None, boom=None):
        async def get_report():
            if boom:
                raise RuntimeError(boom)
            return report if report is not None else {"savings": 42}

        async def gen_forecast(days_ahead=30):
            return {"days": days_ahead}

        agent = SimpleNamespace(
            get_cost_optimization_report=get_report,
            generate_cost_forecast=gen_forecast,
        )
        install_sysmodule(
            monkeypatch,
            "agents.infrastructure.cost_optimization_agent",
            cost_optimization_agent=agent,
        )

    def test_cost_report_success(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_COST_OPTIMIZATION_AGENT", "true")
        self._install_cost_agent(monkeypatch, report={"savings": 7})
        resp = client.get("/api/admin/infrastructure/cost/report")
        assert resp.status_code == 200
        assert resp.json() == {"savings": 7}

    def test_cost_report_agent_failure_500(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_COST_OPTIMIZATION_AGENT", "true")
        self._install_cost_agent(monkeypatch, boom="cost engine down")
        resp = client.get("/api/admin/infrastructure/cost/report")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "cost engine down"

    def test_cost_forecast_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_COST_OPTIMIZATION_AGENT", raising=False)
        resp = client.get("/api/admin/infrastructure/cost/forecast?days=30")
        assert resp.status_code == 503

    def test_cost_forecast_passes_days(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_COST_OPTIMIZATION_AGENT", "true")
        self._install_cost_agent(monkeypatch)
        resp = client.get("/api/admin/infrastructure/cost/forecast?days=14")
        assert resp.status_code == 200
        assert resp.json() == {"days": 14}

    def test_performance_summary_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_PERFORMANCE_TUNING_AGENT", raising=False)
        resp = client.get("/api/admin/infrastructure/performance/summary")
        assert resp.status_code == 503

    def _install_perf_agent(self, monkeypatch, boom=None):
        async def summary(hours=24):
            if boom:
                raise RuntimeError(boom)
            return {"hours": hours, "recommendations": []}

        install_sysmodule(
            monkeypatch,
            "agents.infrastructure.performance_tuning_agent",
            performance_tuning_agent=SimpleNamespace(get_performance_summary=summary),
        )

    def test_performance_summary_success(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_PERFORMANCE_TUNING_AGENT", "true")
        self._install_perf_agent(monkeypatch)
        resp = client.get("/api/admin/infrastructure/performance/summary?hours=6")
        assert resp.status_code == 200
        assert resp.json() == {"hours": 6, "recommendations": []}

    def test_performance_summary_failure_500(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_PERFORMANCE_TUNING_AGENT", "true")
        self._install_perf_agent(monkeypatch, boom="perf down")
        resp = client.get("/api/admin/infrastructure/performance/summary")
        assert resp.status_code == 500

    def _install_dr_agent(self, monkeypatch, backup_history_key="dr:backup_history"):
        agent = SimpleNamespace(
            backup_history_key=backup_history_key,
            create_backup=AsyncMock(return_value=None),
            get_backup_schedule_recommendations=AsyncMock(return_value={}),
        )
        install_sysmodule(
            monkeypatch,
            "agents.infrastructure.disaster_recovery_agent",
            disaster_recovery_agent=agent,
        )
        return agent

    def test_backup_history_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_DISASTER_RECOVERY_AGENT", raising=False)
        resp = client.get("/api/admin/infrastructure/disaster-recovery/backups")
        assert resp.status_code == 503

    def test_backup_history_success_with_records(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        self._install_dr_agent(monkeypatch)
        history = [{"backup_id": f"b{i}"} for i in range(5)]
        fake_redis = FakeRedisManager(
            client=SimpleNamespace(), store={"dr:backup_history": json.dumps(history)}
        )
        monkeypatch.setattr(ar, "redis_manager", fake_redis)
        resp = client.get("/api/admin/infrastructure/disaster-recovery/backups?limit=3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_backups"] == 5
        assert len(body["recent"]) == 3
        assert body["recent"][0]["backup_id"] == "b2"

    def test_backup_history_empty_and_broken_json(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        self._install_dr_agent(monkeypatch)
        fake_redis = FakeRedisManager(client=SimpleNamespace(), store={})
        monkeypatch.setattr(ar, "redis_manager", fake_redis)
        resp = client.get("/api/admin/infrastructure/disaster-recovery/backups")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "total_backups": 0, "recent": []}

        # malformed JSON → generic exception arm → 500
        fake_redis._store["dr:backup_history"] = "{not json"
        resp = client.get("/api/admin/infrastructure/disaster-recovery/backups")
        assert resp.status_code == 500

    def test_manual_backup_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_DISASTER_RECOVERY_AGENT", raising=False)
        resp = client.post("/api/admin/infrastructure/disaster-recovery/backup")
        assert resp.status_code == 503

    def test_manual_backup_invalid_type_400(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        self._install_dr_agent(monkeypatch)
        resp = client.post("/api/admin/infrastructure/disaster-recovery/backup?backup_type=delta")
        assert resp.status_code == 400
        assert "backup_type must be one of" in resp.json()["detail"]

    def test_manual_backup_success(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        agent = self._install_dr_agent(monkeypatch)
        result = SimpleNamespace(
            backup_id="b-9",
            timestamp=datetime(2026, 9, 15, 12, 0, 0),
            size_bytes=2048,
            location="/tmp/b9",
            status="completed",
            verification_hash="abc",
            components_backed_up=["db"],
            duration_seconds=1.5,
        )
        agent.create_backup = AsyncMock(return_value=result)
        resp = client.post(
            "/api/admin/infrastructure/disaster-recovery/backup?backup_type=incremental"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["backup_id"] == "b-9"
        assert body["timestamp"] == "2026-09-15T12:00:00"
        assert body["size_bytes"] == 2048
        agent.create_backup.assert_awaited_once_with(backup_type="incremental")

    def test_manual_backup_failure_500(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        agent = self._install_dr_agent(monkeypatch)
        agent.create_backup = AsyncMock(side_effect=RuntimeError("disk full"))
        resp = client.post("/api/admin/infrastructure/disaster-recovery/backup")
        assert resp.status_code == 500

    def test_backup_schedule_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_DISASTER_RECOVERY_AGENT", raising=False)
        resp = client.get("/api/admin/infrastructure/disaster-recovery/schedule")
        assert resp.status_code == 503

    def test_backup_schedule_success(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        agent = self._install_dr_agent(monkeypatch)
        agent.get_backup_schedule_recommendations = AsyncMock(
            return_value={"full": "daily", "incremental": "hourly"}
        )
        resp = client.get("/api/admin/infrastructure/disaster-recovery/schedule")
        assert resp.status_code == 200
        assert resp.json() == {"full": "daily", "incremental": "hourly"}

    def test_auto_scaling_disabled_503(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_AUTOSCALING_AGENT", raising=False)
        resp = client.get("/api/admin/infrastructure/auto-scaling/status")
        assert resp.status_code == 503

    def test_auto_scaling_success(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_AUTOSCALING_AGENT", "true")
        actions = [{"action": f"scale-{i}"} for i in range(4)]
        monkeypatch.setattr(
            ar,
            "redis_manager",
            FakeRedisManager(
                client=SimpleNamespace(),
                store={"auto_scaling:scaling_history": json.dumps(actions)},
            ),
        )
        resp = client.get("/api/admin/infrastructure/auto-scaling/status?limit=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_actions"] == 4
        assert len(body["recent"]) == 2

    def test_auto_scaling_broken_json_500(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_AUTOSCALING_AGENT", "true")
        monkeypatch.setattr(
            ar,
            "redis_manager",
            FakeRedisManager(
                client=SimpleNamespace(),
                store={"auto_scaling:scaling_history": "][bad"},
            ),
        )
        resp = client.get("/api/admin/infrastructure/auto-scaling/status")
        assert resp.status_code == 500

    # ── HTTPException passthrough arms (except HTTPException: raise) ──

    def _http_boom(self, monkeypatch, module, attr, code=418):
        async def raise_http(*args, **kwargs):
            from fastapi import HTTPException

            raise HTTPException(status_code=code, detail="agent-level http error")

        install_sysmodule(
            monkeypatch,
            module,
            **{attr: SimpleNamespace(**{self._http_target(attr): raise_http})},
        )

    @staticmethod
    def _http_target(agent_attr):
        return {
            "cost_optimization_agent": "get_cost_optimization_report",
            "performance_tuning_agent": "get_performance_summary",
            "disaster_recovery_agent": "get_backup_schedule_recommendations",
        }[agent_attr]

    def test_cost_report_http_exception_passthrough(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_COST_OPTIMIZATION_AGENT", "true")
        self._http_boom(
            monkeypatch, "agents.infrastructure.cost_optimization_agent", "cost_optimization_agent"
        )
        resp = client.get("/api/admin/infrastructure/cost/report")
        assert resp.status_code == 418

    def test_cost_forecast_http_exception_and_failure(self, client, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setenv("ENABLE_COST_OPTIMIZATION_AGENT", "true")

        async def raise_http(days_ahead=30):
            raise HTTPException(status_code=418, detail="forecast http error")

        async def boom(days_ahead=30):
            raise RuntimeError("forecast exploded")

        agent = SimpleNamespace(generate_cost_forecast=raise_http)
        install_sysmodule(
            monkeypatch,
            "agents.infrastructure.cost_optimization_agent",
            cost_optimization_agent=agent,
        )
        resp = client.get("/api/admin/infrastructure/cost/forecast?days=7")
        assert resp.status_code == 418

        agent.generate_cost_forecast = boom
        resp = client.get("/api/admin/infrastructure/cost/forecast?days=7")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "forecast exploded"

    def test_performance_summary_http_exception_passthrough(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_PERFORMANCE_TUNING_AGENT", "true")
        self._http_boom(
            monkeypatch,
            "agents.infrastructure.performance_tuning_agent",
            "performance_tuning_agent",
        )
        resp = client.get("/api/admin/infrastructure/performance/summary")
        assert resp.status_code == 418

    def test_backup_history_http_exception_passthrough(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        self._install_dr_agent(monkeypatch)
        monkeypatch.setattr(
            ar,
            "redis_manager",
            FakeRedisManager(
                client=SimpleNamespace(),
                store={"dr:backup_history": json.dumps([{"b": 1}])},
            ),
        )
        from fastapi import HTTPException

        async def raise_http(*args, **kwargs):
            raise HTTPException(status_code=418, detail="history http error")

        # redis read is inside the try block; a raising redis_manager.get
        # exercises the except HTTPException passthrough arm
        class HttpRedis(FakeRedisManager):
            async def get(self, key):
                await raise_http()

        monkeypatch.setattr(ar, "redis_manager", HttpRedis(client=SimpleNamespace()))
        resp = client.get("/api/admin/infrastructure/disaster-recovery/backups")
        assert resp.status_code == 418

    def test_manual_backup_http_exception_passthrough(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        agent = self._install_dr_agent(monkeypatch)
        from fastapi import HTTPException

        async def raise_http(backup_type="full"):
            raise HTTPException(status_code=418, detail="backup http error")

        agent.create_backup = raise_http
        resp = client.post("/api/admin/infrastructure/disaster-recovery/backup")
        assert resp.status_code == 418

    def test_backup_schedule_http_exception_and_failure(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_DISASTER_RECOVERY_AGENT", "true")
        agent = self._install_dr_agent(monkeypatch)
        from fastapi import HTTPException

        async def raise_http():
            raise HTTPException(status_code=418, detail="schedule http error")

        agent.get_backup_schedule_recommendations = raise_http
        resp = client.get("/api/admin/infrastructure/disaster-recovery/schedule")
        assert resp.status_code == 418

        async def boom():
            raise RuntimeError("schedule exploded")

        agent.get_backup_schedule_recommendations = boom
        resp = client.get("/api/admin/infrastructure/disaster-recovery/schedule")
        assert resp.status_code == 500

    def test_auto_scaling_http_exception_passthrough(self, client, monkeypatch):
        monkeypatch.setenv("ENABLE_AUTOSCALING_AGENT", "true")
        from fastapi import HTTPException

        class HttpRedis(FakeRedisManager):
            async def get(self, key):
                raise HTTPException(status_code=418, detail="scaling http error")

        monkeypatch.setattr(ar, "redis_manager", HttpRedis(client=SimpleNamespace()))
        resp = client.get("/api/admin/infrastructure/auto-scaling/status")
        assert resp.status_code == 418


# ─────────────────────── automation + integrations ───────────────────────


class TestAutomationAndIntegrations:
    def test_workflows_listing(self, client):
        resp = client.get("/api/admin/automation/workflows")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["total"], int)
        assert isinstance(body["workflows"], list)
        if body["workflows"]:
            wf = body["workflows"][0]
            for field in (
                "key",
                "route",
                "enabled",
                "timeout_seconds",
                "max_retries",
                "synchronous",
                "sensitive",
                "version",
                "description",
            ):
                assert field in wf

    def test_integrations_listing_summary(self, client):
        from core.integrations import list_integrations

        resp = client.get("/api/admin/integrations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(list_integrations())
        assert set(body["summary"]) == {"enabled", "disabled", "not_adopted"}
        if body["integrations"]:
            integ = body["integrations"][0]
            for field in (
                "key",
                "name",
                "category",
                "scope",
                "enabled",
                "status",
                "required_for_core",
                "fallback",
                "privacy_mode",
                "capabilities",
                "config_note",
            ):
                assert field in integ

    def test_integration_health_unknown_404(self, client):
        resp = client.get("/api/admin/integrations/does-not-exist/health")
        assert resp.status_code == 404
        assert "Unknown integration" in resp.json()["detail"]

    def test_integration_health_success(self, client):
        from core.integrations import list_integrations

        key = list_integrations()[0].key
        resp = client.get(f"/api/admin/integrations/{key}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["key"] == key
        assert "core_independence" in body


# ─────────────────────── automation executions ───────────────────────


def _exec_record(**over):
    base = dict(
        id="x1",
        event_id="ev1",
        workflow_key="wf_a",
        provider="jira",
        status="SUCCESS",
        attempt=1,
        started_at=datetime(2026, 9, 15, 10, 0, 0),
        completed_at=datetime(2026, 9, 15, 10, 0, 1),
        duration_ms=1000,
        http_status=200,
        external_execution_id=None,
        trace_id="tr1",
        error_code=None,
        error_message=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestAutomationExecutions:
    def _patch_ctx(self, monkeypatch, records, raises=None):
        session = FakeSession(results=[FakeResult(scalars_list=records)])
        if raises:

            @asynccontextmanager
            async def ctx():
                raise raises
        else:
            ctx = fake_session_ctx(session)
        monkeypatch.setattr("database.session.get_db_session_context", ctx)

    def test_list_executions_success_with_filters_and_truncation(self, client, monkeypatch):
        records = [
            _exec_record(error_message="x" * 300),
            _exec_record(id="x2", event_id="ev2", error_message="short"),
        ]
        self._patch_ctx(monkeypatch, records)
        resp = client.get(
            "/api/admin/automation/executions?workflow_key=wf_a&status=success&limit=10"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        first = body["executions"][0]
        assert first["error_message"].endswith("...")
        assert len(first["error_message"]) == 203
        assert body["executions"][1]["error_message"] == "short"
        assert first["started_at"] == "2026-09-15T10:00:00"

    def test_list_executions_without_filters_skips_where_arms(self, client, monkeypatch):
        self._patch_ctx(monkeypatch, [_exec_record()])
        resp = client.get("/api/admin/automation/executions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["executions"][0]["workflow_key"] == "wf_a"

    def test_list_executions_error_returns_200_error_payload(self, client, monkeypatch):
        # owner quirk 1: audit-trail endpoint degrades to HTTP 200 {"status": "error"}
        self._patch_ctx(monkeypatch, [], raises=RuntimeError("history store down"))
        resp = client.get("/api/admin/automation/executions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["total"] == 0
        assert body["executions"] == []

    def test_get_event_success(self, client, monkeypatch):
        self._patch_ctx(monkeypatch, [_exec_record(), _exec_record(id="x2", attempt=2)])
        resp = client.get("/api/admin/automation/executions/ev1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["event_id"] == "ev1"
        assert body["total_attempts"] == 2

    def test_get_event_404_when_unknown(self, client, monkeypatch):
        self._patch_ctx(monkeypatch, [])
        resp = client.get("/api/admin/automation/executions/ghost")
        assert resp.status_code == 404

    def test_get_event_error_500(self, client, monkeypatch):
        self._patch_ctx(monkeypatch, [], raises=RuntimeError("db boom"))
        resp = client.get("/api/admin/automation/executions/ev1")
        assert resp.status_code == 500


# ─────────────────────── render preflight ───────────────────────


class TestRenderPreflight:
    def _install(self, monkeypatch, **methods):
        store = SimpleNamespace(get_events=lambda limit=20: [{"event": "e1"}][: min(limit, 1)])

        class FakeSvc:
            def __init__(self):
                self.store = store

            def get_deploy_preflight(self):
                return methods.get("preflight", {"ready": True})

            def refresh_account_status(self, account_role, service_id, api_key, force):
                hook = methods.get("refresh")
                if hook:
                    return hook(
                        account_role=account_role,
                        service_id=service_id,
                        api_key=api_key,
                        force=force,
                    )
                return {"role": account_role, "api_key_present": bool(api_key)}

            def manual_override(self, account_role, approved_by, reason):
                hook = methods.get("override")
                if hook:
                    return hook(account_role=account_role, approved_by=approved_by, reason=reason)
                return {"role": account_role, "overridden": True}

        install_sysmodule(
            monkeypatch, "services.render_preflight_service", RenderPreflightService=FakeSvc
        )

    def test_preflight_success(self, client, monkeypatch):
        self._install(monkeypatch, preflight={"ready": False, "roles": {}})
        resp = client.get("/api/admin/render/preflight")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"] == {"ready": False, "roles": {}}
        assert body["events"] == [{"event": "e1"}]

    def test_preflight_failure_500(self, client, monkeypatch):
        class BoomSvc:
            def __init__(self):
                raise RuntimeError("no preflight for you")

        install_sysmodule(
            monkeypatch, "services.render_preflight_service", RenderPreflightService=BoomSvc
        )
        resp = client.get("/api/admin/render/preflight")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to fetch preflight data"

    def test_recheck_uses_role_env_then_fallback(self, client, monkeypatch):
        seen = []

        def refresh(account_role, service_id, api_key, force):
            seen.append((account_role, api_key))
            return {"ok": True}

        self._install(monkeypatch, refresh=refresh)
        monkeypatch.setenv("RENDER_API_KEY_WEB", "role-key")
        resp = client.post("/api/admin/render/accounts/web/recheck", json={"force": True})
        assert resp.status_code == 200
        assert seen[-1] == ("web", "role-key")

        # no role key → falls back to RENDER_API_KEY (unset → "")
        monkeypatch.delenv("RENDER_API_KEY_WEB")
        resp = client.post("/api/admin/render/accounts/db/recheck", json={"force": False})
        assert resp.status_code == 200
        assert seen[-1] == ("db", "")

    def test_recheck_failure_500(self, client, monkeypatch):
        def boom(account_role, service_id, api_key, force):
            raise RuntimeError("render api down")

        self._install(monkeypatch, refresh=boom)
        resp = client.post("/api/admin/render/accounts/web/recheck")
        assert resp.status_code == 500
        assert "Failed to recheck role web" in resp.json()["detail"]

    def test_override_requires_min_5_char_reason(self, client):
        resp = client.post("/api/admin/render/accounts/web/override", json={"reason": "no"})
        assert resp.status_code == 400
        assert "min 5 chars" in resp.json()["detail"]

    def test_override_success(self, client, monkeypatch):
        self._install(monkeypatch)
        resp = client.post(
            "/api/admin/render/accounts/web/override",
            json={"reason": "deploy window approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"role": "web", "overridden": True}

    def test_override_unknown_role_valueerror_404(self, client, monkeypatch):
        def not_found(account_role, approved_by, reason):
            raise ValueError(f"Unknown role {account_role}")

        self._install(monkeypatch, override=not_found)
        resp = client.post(
            "/api/admin/render/accounts/ghost/override", json={"reason": "valid reason"}
        )
        assert resp.status_code == 404

    def test_override_failure_500(self, client, monkeypatch):
        def boom(account_role, approved_by, reason):
            raise RuntimeError("override store down")

        self._install(monkeypatch, override=boom)
        resp = client.post(
            "/api/admin/render/accounts/web/override", json={"reason": "valid reason"}
        )
        assert resp.status_code == 500
