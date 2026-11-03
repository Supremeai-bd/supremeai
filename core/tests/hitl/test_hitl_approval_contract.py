"""#481 — consolidated HITL approve-execution contract tests.

Pins the canonical state machine ratified in ``docs/security/HITL_APPROVAL_CONTRACT.md``
for the HITLEngine surface (Firestore ``pending_approvals``, S2):

- states: ``pending_approval → approved | rejected | expired``; terminal states absorb
  every further transition (replay-proof);
- approve dispatches its executor EXACTLY ONCE — duplicate/replayed approves are
  refused by the state guard and never re-execute;
- expired approvals (default 24h TTL) refuse every decision and land in the
  deterministic ``expired`` state (+ canonical mirror resolved to CANCELLED);
- unauthorized approvers (empty actor / cross-tenant) are refused at the engine;
- execution failures keep the approval but record ``execution_status=failed`` and
  block any further decision;
- terminal transitions are CAS-atomic when the store exposes ``transaction()``
  (race loser never dispatches); stores without transactions keep the read-guarded
  flip (the canonical ``pending_tasks`` mirror always provides true CAS).

Canonical-store (S1) transition table: ``tests/security/test_hitl_state_machine.py``.
Dispatch-table contract: ``tests/services/test_hitl_dispatch.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from services.hitl import engine as engine_module
from services.hitl.dispatch import ApprovalDispatchError
from services.hitl.engine import (
    DEFAULT_APPROVAL_TTL_SECONDS,
    STATUS_EXPIRED,
    STATUS_PENDING,
    ApprovalExpiredError,
    ApprovalNotAuthorizedError,
    HITLEngine,
    HITLStateError,
)

try:  # canonical store needs the full `models` package (CI: available)
    import models.pending_tasks as pending_tasks
    from models.pending_tasks import TaskStatus, get_task_by_idempotency

    _CANONICAL_STORE_AVAILABLE = True
except Exception:  # pragma: no cover — degraded envs without the models package deps
    pending_tasks = None  # type: ignore[assignment]
    TaskStatus = None  # type: ignore[assignment]
    get_task_by_idempotency = None  # type: ignore[assignment]
    _CANONICAL_STORE_AVAILABLE = False

pytestmark = [pytest.mark.hitl]

VALID_SKILL_PAYLOAD = {"skill_name": "contract_skill", "code": "def run():\n    return 'ok'\n"}


# ---------------------------------------------------------------------------
# Fake store — HITLEngine contract (`.client` + `.collection()`) WITH a
# versioned CAS transaction (models the Firestore transaction protocol: the
# commit aborts when the record changed since the transactional read).
# ---------------------------------------------------------------------------


class _FakeDocument:
    def __init__(self, store: _FakeStore, path: str):
        self._store = store
        self._path = path
        self.exists = path in store._docs
        self._data: dict[str, Any] = dict(store._docs.get(path, {}))

    def set(self, data: dict[str, Any]) -> None:
        self._store._docs[self._path] = dict(data)
        self._store.version += 1

    def update(self, data: dict[str, Any]) -> None:
        self._store._docs.setdefault(self._path, {}).update(data)
        self._store.version += 1

    def get(self) -> _FakeDocument:
        self.exists = self._path in self._store._docs
        self._data = dict(self._store._docs.get(self._path, {}))
        if self._store.intercept is not None:
            self._data = self._store.intercept(self._path, self._data) or self._data
        return self

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeTransaction:
    def __init__(self, store: _FakeStore):
        self._store = store
        self._ops: list[tuple[_FakeDocument, dict[str, Any]]] = []
        self._seen_version: int | None = None

    def get(self, doc_ref: _FakeDocument) -> _FakeDocument:
        self._seen_version = self._store.version
        return doc_ref.get()

    def update(self, doc_ref: _FakeDocument, fields: dict[str, Any]) -> None:
        self._ops.append((doc_ref, dict(fields)))

    def commit(self) -> None:
        if self._seen_version is not None and self._store.version != self._seen_version:
            raise RuntimeError("concurrent modification — transaction aborted (fake CAS)")
        for doc_ref, fields in self._ops:
            doc_ref.update(fields)


class _FakeCollection:
    def __init__(self, store: _FakeStore, name: str):
        self._store = store
        self._name = name

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self._store, f"{self._name}/{doc_id}")

    def where(self, field: str, op: str, value: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, {field: value})

    def order_by(self, field: str, direction: str | None = None) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, {})

    def limit(self, n: int) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, {})


class _FakeQuery:
    def __init__(self, store: _FakeStore, name: str, filters: dict[str, Any]):
        self._store = store
        self._name = name
        self._filters = filters

    def limit(self, n: int) -> _FakeQuery:
        return self

    def stream(self) -> list[_FakeDocument]:
        out: list[_FakeDocument] = []
        for path, data in self._store._docs.items():
            if not path.startswith(f"{self._name}/"):
                continue
            if all(data.get(k) == v for k, v in self._filters.items()):
                out.append(_FakeDocument(self._store, path))
        return out


class _FakeClient:
    def __init__(self, store: _FakeStore):
        self._store = store

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._store, name)

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction(self._store)


class _FakeClientNoTransaction:
    """Store without transaction support — exercises the read-guarded fallback."""

    def __init__(self, store: _FakeStore):
        self._store = store

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._store, name)


class _FakeStore:
    def __init__(self, client: Any | None = None) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.version: int = 0
        # test hook: mutate/replace the read snapshot (simulates a concurrent writer)
        self.intercept: Any = None
        self.client = client if client is not None else _FakeClient(self)


class _FakeShim:
    """HITLEngine db contract (hitl_admin's _ClientShim shape)."""

    def __init__(self, store: _FakeStore):
        self.client = store.client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def skills_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Isolate the skill-executor write path for the WHOLE module — a contract
    test must never deploy a real file into backend/skills."""
    import services.hitl.dispatch as dispatch

    target = tmp_path / "skills"
    target.mkdir()
    monkeypatch.setattr(dispatch, "_skills_dir", lambda: str(target))
    return target


@pytest.fixture()
def canonical_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Isolate the canonical pending_tasks SQLite file per test (when importable)."""
    if pending_tasks is None:  # pragma: no cover — degraded env
        yield None
        return
    db_file = tmp_path / "pending_tasks_contract.db"
    monkeypatch.setattr(pending_tasks, "DB_PATH", db_file)
    yield db_file


@pytest.fixture()
def engine(canonical_db) -> HITLEngine:
    return HITLEngine(db=_FakeShim(_FakeStore()))


def _make_engine(client_cls: Any) -> tuple[HITLEngine, _FakeStore]:
    store = _FakeStore()
    store.client = client_cls(store)
    return HITLEngine(db=_FakeShim(store)), store


def _seed(
    engine: HITLEngine,
    target: str = "skills/contract_skill",
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    return engine.suspend_for_approval(
        target_resource=target,
        payload=payload if payload is not None else dict(VALID_SKILL_PAYLOAD),
        **kwargs,
    )


def _ledger_actions(store: _FakeStore) -> set[str]:
    return {d["action"] for p, d in store._docs.items() if p.startswith("hitl_audit_ledger/")}


@pytest.fixture()
def execution_counter(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Count executor dispatches (approve-must-execute-exactly-once contract)."""
    calls: list[str] = []

    def _fake_execute(target_resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(target_resource)
        return {"status": "executed", "target": target_resource}

    monkeypatch.setattr(engine_module, "execute_approved", _fake_execute)
    return calls


# ---------------------------------------------------------------------------
# Suspension stamps (#481 §3.4/§3.5)
# ---------------------------------------------------------------------------


def test_suspend_stamps_ttl_and_tenant(engine: HITLEngine) -> None:
    record_id = _seed(engine, tenant_id="tenant-a")
    stored = engine.get_pending_approval(record_id)
    assert stored is not None
    assert stored["status"] == STATUS_PENDING
    assert stored["expires_at"] is not None  # 24h decision window by default
    assert stored["tenant_id"] == "tenant-a"
    assert DEFAULT_APPROVAL_TTL_SECONDS == 24 * 60 * 60  # one contract, both stores


def test_suspend_honors_custom_ttl(engine: HITLEngine) -> None:
    record_id = _seed(engine, ttl_seconds=60)
    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["expires_at"] is not None


# ---------------------------------------------------------------------------
# Required case 1 — duplicate approvals (#481 §3.2 idempotency)
# ---------------------------------------------------------------------------


def test_duplicate_approve_never_reexecutes(
    engine: HITLEngine, execution_counter: list[str]
) -> None:
    record_id = _seed(engine)
    first = engine.approve("admin-1", record_id)
    assert first["execution_status"] == "executed"

    with pytest.raises(HITLStateError, match="not in pending state"):
        engine.approve("admin-2", record_id)

    assert execution_counter == [record_id]  # dispatched EXACTLY once
    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["approved_by"] == "admin-1"  # first decision stands


def test_reject_after_approval_blocked(engine: HITLEngine) -> None:
    record_id = _seed(engine)
    engine.approve("admin-1", record_id)
    with pytest.raises(HITLStateError, match="not in pending state"):
        engine.reject("admin-2", record_id, reason="too late")


def test_approve_after_rejection_blocked(engine: HITLEngine) -> None:
    record_id = _seed(engine)
    engine.reject("admin-1", record_id, reason="no")
    with pytest.raises(HITLStateError, match="not in pending state"):
        engine.approve("admin-2", record_id)


def test_approve_returns_committed_snapshot(engine: HITLEngine) -> None:
    record_id = _seed(engine)
    record = engine.approve("admin-1", record_id)
    assert record["status"] == "approved"  # not the pre-flip read


# ---------------------------------------------------------------------------
# Required case 2 — expired approvals (#481 §3.4)
# ---------------------------------------------------------------------------


def test_expired_approval_cannot_be_approved(
    engine: HITLEngine, execution_counter: list[str]
) -> None:
    record_id = _seed(engine, ttl_seconds=-10)
    with pytest.raises(ApprovalExpiredError):
        engine.approve("admin-1", record_id)

    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["status"] == STATUS_EXPIRED
    assert stored["expired_at"] is not None
    assert execution_counter == []  # expired approval must NOT dispatch
    assert "approval_expired" in _ledger_actions(_store_of(engine))


def test_expired_approval_hidden_from_queue(engine: HITLEngine) -> None:
    _seed(engine, ttl_seconds=-10)
    assert engine.get_pending_approvals() == []


def test_expired_approval_refuses_every_decision(engine: HITLEngine) -> None:
    record_id = _seed(engine, ttl_seconds=-10)
    with pytest.raises(ApprovalExpiredError):
        engine.approve("admin-1", record_id)
    # first touch landed the terminal expired state → further decisions hit the guard
    with pytest.raises(HITLStateError):
        engine.reject("admin-1", record_id, reason="late")
    with pytest.raises(HITLStateError):
        engine.approve("admin-1", record_id)


def test_expired_record_resolves_canonical_mirror_to_cancelled(engine: HITLEngine) -> None:
    record_id = _seed(engine, target="skills/mirror_expiry", ttl_seconds=-10)
    task = get_task_by_idempotency(f"hitl:{record_id}")
    assert task is not None and task.status == TaskStatus.PENDING
    with pytest.raises(ApprovalExpiredError):
        engine.approve("admin-1", record_id)
    mirrored = get_task_by_idempotency(f"hitl:{record_id}")
    assert mirrored is not None
    assert mirrored.status == TaskStatus.CANCELLED  # expiry = authoritative system cancel


# ---------------------------------------------------------------------------
# Required case 3 — unauthorized approvers (#481 §3.1/§3.5)
# ---------------------------------------------------------------------------


def test_unauthorized_empty_actor_rejected(engine: HITLEngine) -> None:
    record_id = _seed(engine)
    with pytest.raises(ApprovalNotAuthorizedError):
        engine.approve("", record_id)
    with pytest.raises(ApprovalNotAuthorizedError):
        engine.approve("   ", record_id)
    with pytest.raises(ApprovalNotAuthorizedError):
        engine.reject(None, record_id)  # type: ignore[arg-type]
    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["status"] == STATUS_PENDING


def test_unauthorized_cross_tenant_approver_rejected(engine: HITLEngine) -> None:
    record_id = _seed(engine, tenant_id="tenant-a")
    with pytest.raises(ApprovalNotAuthorizedError, match="tenant"):
        engine.approve("admin-1", record_id, tenant_id="tenant-b")
    with pytest.raises(ApprovalNotAuthorizedError, match="tenant"):
        engine.reject("admin-1", record_id, reason="x", tenant_id="tenant-b")
    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["status"] == STATUS_PENDING


def test_matching_tenant_approves(engine: HITLEngine, execution_counter: list[str]) -> None:
    record_id = _seed(engine, tenant_id="tenant-a")
    record = engine.approve("admin-1", record_id, tenant_id="tenant-a")
    assert record["status"] == "approved"
    assert execution_counter == [record_id]


def test_global_record_decidable_without_tenant_context(engine: HITLEngine) -> None:
    # records without a tenant stamp remain platform-admin decisions (contract §3.5)
    record_id = _seed(engine)
    record = engine.approve("admin-1", record_id)
    assert record["status"] == "approved"


# ---------------------------------------------------------------------------
# Required case 4 — execution failures (#481 §3.2)
# ---------------------------------------------------------------------------


def test_execution_failure_is_loud_and_recorded(engine: HITLEngine) -> None:
    record_id = _seed(engine, payload={"skill_name": "broken_skill", "code": "def broken(:\n"})
    with pytest.raises(ValueError, match="validation failed"):
        engine.approve("admin-1", record_id)

    stored = engine.get_pending_approval(record_id)
    assert stored is not None
    assert stored["status"] == "approved"  # the decision is immutable
    assert stored["execution_status"] == "failed"
    assert "validation" in stored["execution_error"]
    assert "approval_execution_failed" in _ledger_actions(_store_of(engine))


def test_failed_execution_blocks_replay(engine: HITLEngine) -> None:
    record_id = _seed(engine, payload={"skill_name": "broken_skill", "code": "def broken(:\n"})
    with pytest.raises(ValueError):
        engine.approve("admin-1", record_id)
    # a second approve must NOT re-attempt the executor (terminal guard)
    with pytest.raises(HITLStateError, match="not in pending state"):
        engine.approve("admin-2", record_id)


# ---------------------------------------------------------------------------
# CAS / concurrency determinism (#481 §2.2)
# ---------------------------------------------------------------------------


def test_cas_loser_never_dispatches(canonical_db, execution_counter: list[str]) -> None:
    engine, store = _make_engine(_FakeClient)
    record_id = _seed(engine)

    def _concurrent_winner(path: str, data: dict[str, Any]) -> dict[str, Any]:
        if path.endswith(record_id):
            # another admin's decision lands between our reads
            return {**data, "status": "approved"}
        return data

    store.intercept = _concurrent_winner
    with pytest.raises(HITLStateError, match="not in pending state"):
        engine.approve("admin-1", record_id)
    assert execution_counter == []  # the loser never dispatches


def test_cas_commit_conflict_surfaces_loud(canonical_db, execution_counter: list[str]) -> None:
    engine, store = _make_engine(_FakeClient)
    record_id = _seed(engine)

    original_get = _FakeTransaction.get

    def _bumping_get(self: _FakeTransaction, doc_ref: _FakeDocument) -> _FakeDocument:
        snapshot = original_get(self, doc_ref)
        store.version += 1  # a concurrent transaction commits during ours
        return snapshot

    _FakeTransaction.get = _bumping_get  # type: ignore[method-assign]
    try:
        with pytest.raises(HITLStateError, match="CAS race"):
            engine.approve("admin-1", record_id)
    finally:
        _FakeTransaction.get = original_get  # type: ignore[method-assign]
    assert execution_counter == []
    assert engine.get_pending_approval(record_id) is not None  # store untouched by loser


def test_fallback_store_without_transactions_still_marks_expired(canonical_db) -> None:
    engine, store = _make_engine(_FakeClientNoTransaction)
    record_id = _seed(engine, ttl_seconds=-10)
    with pytest.raises(ApprovalExpiredError):
        engine.approve("admin-1", record_id)
    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["status"] == STATUS_EXPIRED


# ---------------------------------------------------------------------------
# Fail-closed dispatch interplay (M17 P-B regression)
# ---------------------------------------------------------------------------


def test_unknown_target_fails_closed_before_flip(
    engine: HITLEngine, execution_counter: list[str]
) -> None:
    record_id = _seed(engine, target="mystery/resource", payload={"x": 1})
    with pytest.raises(ApprovalDispatchError):
        engine.approve("admin-1", record_id)
    stored = engine.get_pending_approval(record_id)
    assert stored is not None and stored["status"] == STATUS_PENDING
    assert execution_counter == []


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _store_of(engine: HITLEngine) -> _FakeStore:
    """Recover the backing fake store from the engine's db shim."""
    return engine.db.client._store  # noqa: SLF001 — test introspection
