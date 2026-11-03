"""Tests for the governed knowledge importer: validation, import snapshot, rollback.

Gap closure: production knowledge import must carry durable rollback evidence so
a bad import can be reverted (restore prior rows / delete newly inserted rows)
via `--rollback <rollback_id>`. These tests cover the pure helpers with fake
cursors — no live database required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_scripts_dir))

if not (_scripts_dir / "import_knowledge_base.py").is_file():
    pytest.skip(
        "scripts/import_knowledge_base.py not found — un-skip once restored.",
        allow_module_level=True,
    )

from import_knowledge_base import (  # noqa: E402
    capture_rollback_snapshot,
    content_hash,
    rollback_knowledge,
    validate,
)


class FakeCursor:
    """Records executed SQL + returns canned fetchall/fetchone/rowcount."""

    def __init__(self, fetchall=(), rowcount=1):
        self.executed: list[tuple[str, tuple]] = []
        self._fetchall = fetchall
        self.rowcount = rowcount

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return self

    def fetchall(self):
        return self._fetchall

    def fetchone(self):
        return self._fetchall[0] if self._fetchall else None


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_accepts_wellformed_record():
    record = {
        "knowledge_key": "pay.tax.basic",
        "title": "Tax basics",
        "domain": "payments",
        "namespace": "tax",
        "content": "How taxes work",
        "source_document": "docs/tax.md",
        "source_section": "1",
        "confidence": 0.9,
        "risk_level": "medium",
        "status": "approved",
        "tags": ["tax", "payments"],
    }
    assert validate([record]) == []


def test_validate_flags_missing_fields_and_duplicate_keys():
    errors = validate(
        [
            {"knowledge_key": "a.b", "title": "x", "domain": "d", "namespace": "n"},
            {"knowledge_key": "a.b", "title": "y", "domain": "d", "namespace": "n"},
        ]
    )
    assert any("missing" in e for e in errors)
    assert any("duplicate knowledge_key" in e for e in errors)


def test_validate_rejects_bad_confidence_status_risk():
    base = {
        "knowledge_key": "a.b.c",
        "title": "x",
        "domain": "d",
        "namespace": "n",
        "content": "c",
        "source_document": "f",
        "source_section": "1",
        "confidence": 2.5,  # out of [0,1]
        "risk_level": "extreme",  # not allowed
        "status": "banana",  # not allowed
        "tags": ["t"],
    }
    assert validate([base])


def test_validate_rejects_possible_secret_in_record():
    record = {
        "knowledge_key": "a.b.c",
        "title": "leak",
        "domain": "d",
        "namespace": "n",
        "content": "the key is api_key=sk-abc123",
        "source_document": "f",
        "source_section": "1",
        "confidence": 0.5,
        "risk_level": "low",
        "status": "draft",
        "tags": [],
    }
    assert any("possible secret" in e for e in validate([record]))


# ---------------------------------------------------------------------------
# content_hash()
# ---------------------------------------------------------------------------


def test_content_hash_is_deterministic_and_excludes_status():
    a = {"knowledge_key": "x.y", "title": "t", "content": "c", "status": "approved"}
    b = {"knowledge_key": "x.y", "title": "t", "content": "c", "status": "draft"}
    assert content_hash(a) == content_hash(b)  # status must not affect identity
    c = {"knowledge_key": "x.y", "title": "t", "content": "d", "status": "draft"}
    assert content_hash(a) != content_hash(c)  # content change -> new hash


# ---------------------------------------------------------------------------
# capture_rollback_snapshot()
# ---------------------------------------------------------------------------


def test_capture_snapshot_marks_new_and_existing_rows():
    # DB has one existing row for "a.b", none for "c.d".
    cur = FakeCursor(
        fetchall=[
            (
                "a.b",
                "Old title",
                "pay",
                "ns",
                "old content",
                "src",
                '{"old": true}',
                "oldhash",
                "approved",
                0.8,
                "low",
                "v1",
                None,
            )
        ]
    )
    snapshot = capture_rollback_snapshot(cur, ["a.b", "c.d"])
    assert snapshot["a.b"] is not None
    assert snapshot["a.b"]["title"] == "Old title"
    assert snapshot["a.b"]["status"] == "approved"
    assert snapshot["c.d"] is None  # did not exist -> delete on rollback


def test_capture_snapshot_issues_scoped_select():
    cur = FakeCursor()
    capture_rollback_snapshot(cur, ["x", "y"])
    sql = cur.executed[0][0]
    assert "FROM knowledge_base" in sql
    assert "knowledge_key = ANY(%s)" in sql
    assert cur.executed[0][1] == (["x", "y"],)


# ---------------------------------------------------------------------------
# rollback_knowledge()
# ---------------------------------------------------------------------------


def test_rollback_deletes_new_rows_and_restores_existing():
    cur = FakeCursor()
    snapshot = {
        "brand.new": None,  # inserted by import -> delete
        "brand.existing": {"title": "Old", "status": "approved", "metadata": {"k": 1}},
    }
    deleted, restored = rollback_knowledge(cur, snapshot)
    assert (deleted, restored) == (1, 1)

    deletes = [s for s, _ in cur.executed if s.startswith("DELETE")]
    updates = [s for s, _ in cur.executed if s.startswith("UPDATE")]
    assert len(deletes) == 1 and "knowledge_key = %s" in deletes[0]
    assert len(updates) == 1 and "SET title=%s" in updates[0]
    # metadata dict must be JSON-serialized for the ::jsonb parameter.
    params = dict(cur.executed)
    update_params = next(params[sql] for sql in params if sql.startswith("UPDATE"))
    assert update_params[5] == '{"k": 1}'
