"""M17 P-D (seven→one) — HITLEngine → canonical pending_tasks mirror চুক্তি-টেস্ট।

বাংলা: দ্বৈত-লেখা পর্বের সেতু — suspension/approve/reject প্রতিটি
canonical pending_tasks-এ প্রতিফলিত হয় (idempotency-key = ``hitl:<id>``);
mirror best-effort + লাউড — Firestore authority অক্ষুণ্ণ।
"""

from __future__ import annotations

from typing import Any

import pytest

import models.pending_tasks as pending_tasks
from models.pending_tasks import TaskStatus, TaskType, get_task_by_idempotency
from services.hitl.engine import HITLEngine

# ---------------------------------------------------------------------------
# Fake store — test_hitl_dispatch.py-র একই ন্যূনতম যমজ চুক্তি
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


class _FakeClient:
    def __init__(self, store: _FakeStore):
        self._store = store

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._store, name)


class _FakeStore:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        # বাংলা: engine-চুক্তি — `.client` অ্যাট্রিবিউট (method নয়)।
        self.client = _FakeClient(self)


@pytest.fixture()
def canonical_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    # বাংলা: canonical store-এর ফাইল-পথ টেস্ট-বিচ্ছিন্ন — প্রতিটি টেস্ট
    # নিজস্ব তাজা SQLite পায়।
    db_file = tmp_path / "pending_tasks_test.db"
    monkeypatch.setattr(pending_tasks, "DB_PATH", db_file)
    return db_file


@pytest.fixture()
def engine(tmp_path, monkeypatch: pytest.MonkeyPatch) -> HITLEngine:
    # বাংলা: skill-executor-এর লেখা-পথও টেস্ট-বিচ্ছিন্ন — বাস্তব skills/
    # ডিরেক্টরিতে কোনো ফাইল যেন না লেখা হয় (dispatch-টেস্ট-চুক্তি)।
    import services.hitl.dispatch as dispatch

    target = tmp_path / "skills"
    target.mkdir()
    monkeypatch.setattr(dispatch, "_skills_dir", lambda: str(target))
    return HITLEngine(db=_FakeStore())


# ---------------------------------------------------------------------------
# চুক্তি
# ---------------------------------------------------------------------------


def test_suspend_mirrors_to_canonical(engine: HITLEngine, canonical_db) -> None:
    engine.suspend_for_approval("skills/mirror_test", {"skill_name": "m", "code": "x = 1\n"})

    task = get_task_by_idempotency("hitl:skills/mirror_test")
    assert task is not None
    assert task.task_type == TaskType.HITL_SUSPENSION
    assert task.status == TaskStatus.PENDING
    assert task.payload.get("hitl_record_id") == "skills/mirror_test"


def test_suspend_mirror_is_idempotent(engine: HITLEngine, canonical_db) -> None:
    engine.suspend_for_approval("skills/dup", {"a": 1})
    engine.suspend_for_approval("skills/dup", {"a": 1})  # পুনরাবৃত্তি নিরীহ
    task = get_task_by_idempotency("hitl:skills/dup")
    assert task is not None


def test_approve_mirrors_to_canonical(engine: HITLEngine, canonical_db) -> None:
    engine.suspend_for_approval(
        "skills/approved_one",
        {"skill_name": "approved_one", "code": "def run():\n    return 'ok'\n"},
    )
    engine.approve("admin-1", "skills/approved_one")
    # বাংলা: approve-এর রিটার্ন-ডিক্ট flip-পূর্ব স্ন্যাপশট — সত্য store-এ;
    # তাই সত্য-পাঠ ক্যানোনিকাল mirror + store দুটোতেই।
    stored = engine.get_pending_approval("skills/approved_one")
    assert stored is not None and stored["status"] == "approved"

    task = get_task_by_idempotency("hitl:skills/approved_one")
    assert task is not None
    assert task.status == TaskStatus.APPROVED
    assert task.resolved_by == "admin-1"


def test_reject_mirrors_with_reason(engine: HITLEngine, canonical_db) -> None:
    engine.suspend_for_approval("skills/rejected_one", {"x": 1})
    engine.reject("admin-2", "skills/rejected_one", reason="not safe")

    task = get_task_by_idempotency("hitl:skills/rejected_one")
    assert task is not None
    assert task.status == TaskStatus.REJECTED
    assert task.reason == "not safe"


def test_mirror_failure_never_blocks_suspend(
    engine: HITLEngine, canonical_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any):
        raise RuntimeError("canonical store down")

    monkeypatch.setattr(pending_tasks, "create_pending_task", boom)
    # বাংলা: mirror-ব্যর্থতায় suspension ব্যর্থ হয় না — Firestore authority।
    engine.suspend_for_approval("skills/resilient", {"x": 1})
    assert engine.get_pending_approval("skills/resilient") is not None
