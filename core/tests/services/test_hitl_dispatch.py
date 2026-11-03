"""M17 P-B — approval-dispatch contract tests (নির্বাহক-জন্ম).

বাংলা: approve-পরবর্তী কার্যকরী-অর্ধের চুক্তি এখানে পিন —

১. dispatch-table resolve: পরিচিত prefix → executor; অজানা target →
   ApprovalDispatchError (fail-closed loud — নীরব no-op নিষিদ্ধ)।
২. skill executor: AICodeValidator + realpath-guard + bounded write —
   অবৈধ কোড/নাম হলে loud, ফাইল আংশিক লেখা হয় না।
৩. HITLEngine.approve(): executor-অনুপস্থিতে status-flip-এর আগেই
   ব্যর্থ (রেকর্ড pending-ই); সফল execution-এ execution_status=
   "executed" + ledger 'approval_executed'; রানটাইম-ব্যর্থতায়
   execution_status="failed" + ledger 'approval_execution_failed' +
   loud re-raise।
৪. state-machine অক্ষত: duplicate approve → ValueError।
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from services.hitl.dispatch import (
    APPROVAL_EXECUTORS,
    ApprovalDispatchError,
    execute_approved,
    execute_approved_skill,
    resolve_executor,
)
from services.hitl.engine import HITLEngine

# ---------------------------------------------------------------------------
# Fake store — HITLEngine চুক্তি: `.client` + `.collection()`
# ---------------------------------------------------------------------------


class _FakeDocument:
    def __init__(self, store: _FakeStore, path: str):
        self._store = store
        self._path = path
        self.exists = path in store._docs
        self._data: dict[str, Any] = store._docs.get(path, {})

    def set(self, data: dict[str, Any]) -> None:
        self._store._docs[self._path] = dict(data)

    def update(self, data: dict[str, Any]) -> None:
        self._store._docs.setdefault(self._path, {}).update(data)

    def get(self) -> _FakeDocument:
        self.exists = self._path in self._store._docs
        self._data = self._store._docs.get(self._path, {})
        return self

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


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
                doc = _FakeDocument(self._store, path)
                out.append(doc)
        return out


class _FakeClient:
    def __init__(self, store: _FakeStore):
        self._store = store

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._store, name)


class _FakeStore:
    """engine-চুক্তির ন্যূনতম ইন-মেমরি যমজ (`.client` + `.collection()`)।"""

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.client = _FakeClient(self)


class _FakeShim:
    """HITLEngine-এর db-চুক্তি (hitl_admin-এর _ClientShim-অনুরূপ)।"""

    def __init__(self, store: _FakeStore):
        self.client = store.client


def _make_engine() -> tuple[HITLEngine, _FakeStore]:
    store = _FakeStore()
    return HITLEngine(db=_FakeShim(store)), store


def _seed_skill_record(
    engine: HITLEngine, target: str = "skills/alpha_skill", payload: dict | None = None
) -> str:
    payload = payload or {"skill_name": "alpha_skill", "code": "def run():\n    return 1\n"}
    return engine.suspend_for_approval(target_resource=target, payload=payload)


# ---------------------------------------------------------------------------
# ১) dispatch-table resolve চুক্তি
# ---------------------------------------------------------------------------


def test_known_prefix_resolves_to_skill_executor() -> None:
    prefix, executor = resolve_executor("skills/my_skill")
    assert prefix == "skills/"
    assert executor is execute_approved_skill


def test_unknown_target_fails_closed_loud() -> None:
    with pytest.raises(ApprovalDispatchError) as exc:
        resolve_executor("mystery/resource")
    assert "fail-closed" in str(exc.value)
    assert "mystery/resource" in str(exc.value)


def test_empty_target_fails_closed_loud() -> None:
    with pytest.raises(ApprovalDispatchError):
        resolve_executor("")


def test_dispatch_table_is_data_file() -> None:
    # registry একটি সাধারণ dict (data-file) — নতুন producer এখানেই নিবন্ধিত হয়
    assert isinstance(APPROVAL_EXECUTORS, dict)
    assert "skills/" in APPROVAL_EXECUTORS


def test_execute_approved_routes_by_prefix(skills_dir) -> None:
    result = execute_approved("skills/routed_one", {"skill_name": "routed_one", "code": "x = 1\n"})
    assert result["status"] == "executed"
    assert (skills_dir / "routed_one.py").exists()


# ---------------------------------------------------------------------------
# ২) skill executor — validate + guard + write
# ---------------------------------------------------------------------------


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    import services.hitl.dispatch as dispatch

    target = tmp_path / "skills"
    target.mkdir()
    monkeypatch.setattr(dispatch, "_skills_dir", lambda: str(target))
    return target


def test_skill_executor_writes_validated_code(skills_dir) -> None:
    code = "def run():\n    return 'ok'\n"
    result = execute_approved_skill({"skill_name": "good_skill", "code": code})
    assert result["status"] == "executed"
    written = (skills_dir / "good_skill.py").read_text(encoding="utf-8")
    assert written == code


def test_skill_executor_accepts_generated_code_alias(skills_dir) -> None:
    result = execute_approved_skill({"skill_name": "alias_skill", "generated_code": "x = 1\n"})
    assert result["status"] == "executed"


def test_skill_executor_rejects_invalid_code(skills_dir) -> None:
    with pytest.raises(ValueError, match="validation failed"):
        execute_approved_skill({"skill_name": "bad_skill", "code": "def broken(:\n"})
    assert not (skills_dir / "bad_skill.py").exists()  # আংশিক লেখা নেই


def test_skill_executor_rejects_path_traversal_name(skills_dir) -> None:
    with pytest.raises(ValueError, match="Invalid skill name"):
        execute_approved_skill({"skill_name": "../evil", "code": "x = 1\n"})
    # skills-dir-এর বাইরে কিছু লেখা হয়নি
    assert list(skills_dir.iterdir()) == []


def test_skill_executor_rejects_missing_payload_fields(skills_dir) -> None:
    with pytest.raises(ValueError, match="missing skill_name or code"):
        execute_approved_skill({"skill_name": "no_code_skill"})
    with pytest.raises(ValueError):
        execute_approved_skill({"code": "x = 1\n"})


# ---------------------------------------------------------------------------
# ৩) HITLEngine.approve() — dispatch wire চুক্তি
# ---------------------------------------------------------------------------


def test_approve_unknown_target_fails_before_status_flip() -> None:
    engine, store = _make_engine()
    record_id = _seed_skill_record(engine, target="mystery/thing", payload={"x": 1})
    with pytest.raises(ApprovalDispatchError):
        engine.approve(admin_user_id="admin-1", record_id=record_id)
    stored = store._docs[f"pending_approvals/{record_id}"]
    assert stored["status"] == "pending_approval"  # fail-closed: flip হয়নি


def test_approve_executes_skill_and_records_result(skills_dir) -> None:
    engine, store = _make_engine()
    code = "def run():\n    return 'ok'\n"
    record_id = _seed_skill_record(engine, payload={"skill_name": "deployed_skill", "code": code})
    record = engine.approve(admin_user_id="admin-1", record_id=record_id)

    assert record["execution_status"] == "executed"
    assert record["execution_result"]["status"] == "executed"
    stored = store._docs[f"pending_approvals/{record_id}"]
    assert stored["status"] == "approved"
    assert stored["execution_status"] == "executed"
    assert (skills_dir / "deployed_skill.py").read_text(encoding="utf-8") == code

    ledger_blocks = [d for p, d in store._docs.items() if p.startswith("hitl_audit_ledger/")]
    actions = {b["action"] for b in ledger_blocks}
    assert "skill_approved" in actions
    assert "approval_executed" in actions


def test_approve_execution_failure_is_loud_and_recorded(skills_dir, monkeypatch) -> None:
    engine, store = _make_engine()
    record_id = _seed_skill_record(
        engine, payload={"skill_name": "broken_skill", "code": "def broken(:\n"}
    )
    with pytest.raises(ValueError, match="validation failed"):
        engine.approve(admin_user_id="admin-1", record_id=record_id)

    stored = store._docs[f"pending_approvals/{record_id}"]
    assert stored["status"] == "approved"
    assert stored["execution_status"] == "failed"
    assert "validation failed" in stored["execution_error"]

    ledger_blocks = [d for p, d in store._docs.items() if p.startswith("hitl_audit_ledger/")]
    assert {b["action"] for b in ledger_blocks} >= {"approval_execution_failed"}


def test_duplicate_approve_rejected_by_state_machine(skills_dir) -> None:
    engine, _ = _make_engine()
    record_id = _seed_skill_record(engine)
    engine.approve(admin_user_id="admin-1", record_id=record_id)
    with pytest.raises(ValueError, match="not in pending state"):
        engine.approve(admin_user_id="admin-2", record_id=record_id)


def test_approve_missing_record_is_loud() -> None:
    engine, _ = _make_engine()
    with pytest.raises(ValueError, match="not found"):
        engine.approve(admin_user_id="admin-1", record_id="ghost-record")


def test_skills_dir_stays_inside_backend_layout() -> None:
    # realpath-guard চুক্তি: canonical dir backend/skills — module-layout ভাঙলে টেস্ট ধরবে
    import services.hitl.dispatch as dispatch

    real = os.path.realpath(dispatch._skills_dir())
    backend_root = os.path.realpath(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    assert real.startswith(backend_root)
