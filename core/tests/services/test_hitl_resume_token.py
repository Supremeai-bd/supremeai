"""M17 P-A (issue #1278) — HITL resume-token: one-bridge-many-doors tests.

সেতু এক (HITLEngine-এর CAS + dispatch চুক্তি), দরজা অনেক (resume-URL token)।
Chuক্তি: টোকেন HMAC-স্বাক্ত + one-time + record-bound; জাল 403, মেয়াদোত্তীর্ণ
410, রিপ্লে 409 — raw 500 কখনো নয়।
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from services.hitl.engine import HITLEngine
from services.hitl.resume_token import (
    DEFAULT_RESUME_TTL_SECONDS,
    ResumeTokenAlreadyUsedError,
    ResumeTokenError,
    ResumeTokenExpiredError,
    build_resume_url,
    consume_resume_token,
    issue_resume_token,
)

# ---------------------------------------------------------------------------
# Fake store — HITLEngine চুক্তি (`.client` + `.collection()`)
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

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self._store, f"doc:{doc_id}")


class _FakeClient:
    def __init__(self, store: _FakeStore):
        self._store = store

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._store, name)


class _FakeStore:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.client = _FakeClient(self)


class _FakeShim:
    def __init__(self, store: _FakeStore):
        self.client = store.client


def _make_engine() -> tuple[HITLEngine, _FakeStore]:
    store = _FakeStore()
    return HITLEngine(db=_FakeShim(store)), store


def _seed(engine: HITLEngine) -> str:
    return engine.suspend_for_approval(
        target_resource="skills/alpha_skill",
        payload={"skill_name": "alpha_skill", "code": "def run():\n    return 1\n"},
    )


@pytest.mark.unit
class TestResumeTokenLifecycle:
    def test_issue_and_consume_roundtrip(self):
        engine, store = _make_engine()
        rid = _seed(engine)
        token = issue_resume_token(engine, rid, "approver-1")
        # record stores ONLY the hash — raw token never persisted
        stored = store._docs[f"doc:{rid}"]["resume_tokens"]
        assert len(stored) == 1
        assert stored[0]["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
        assert token not in json.dumps(stored)
        assert consume_resume_token(engine, rid, token) == "approver-1"

    def test_token_is_record_bound(self):
        engine, _ = _make_engine()
        # suspend_for_approval keys records by target_resource — distinct targets
        rid1 = engine.suspend_for_approval(
            target_resource="skills/alpha_skill", payload={"skill_name": "a"}
        )
        rid2 = engine.suspend_for_approval(
            target_resource="skills/beta_skill", payload={"skill_name": "b"}
        )
        token = issue_resume_token(engine, rid1, "approver-1")
        with pytest.raises(ResumeTokenError, match="not bound"):
            consume_resume_token(engine, rid2, token)

    def test_forged_signature_rejected(self):
        engine, _ = _make_engine()
        rid = _seed(engine)
        issue_resume_token(engine, rid, "approver-1")
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(
                {"rid": rid, "act": "evil", "exp": "2099-01-01T00:00:00+00:00", "nonce": "x"}
            ).encode()
        ).decode()
        forged = f"{payload_b64}." + "0" * 64
        with pytest.raises(ResumeTokenError, match="signature"):
            consume_resume_token(engine, rid, forged)

    def test_expired_token_rejected(self):
        engine, store = _make_engine()
        rid = _seed(engine)
        token = issue_resume_token(engine, rid, "approver-1", ttl_seconds=-10)
        with pytest.raises(ResumeTokenExpiredError):
            consume_resume_token(engine, rid, token)

    def test_replay_rejected_after_burn(self):
        engine, _ = _make_engine()
        rid = _seed(engine)
        token = issue_resume_token(engine, rid, "approver-1")
        assert consume_resume_token(engine, rid, token) == "approver-1"
        with pytest.raises(ResumeTokenAlreadyUsedError):
            consume_resume_token(engine, rid, token)

    def test_token_cap_prunes_oldest(self):
        engine, store = _make_engine()
        rid = _seed(engine)
        for i in range(12):  # > MAX_TOKENS_PER_RECORD (10)
            issue_resume_token(engine, rid, f"approver-{i}")
        stored = store._docs[f"doc:{rid}"]["resume_tokens"]
        assert len(stored) <= 10

    def test_unknown_record_rejected(self):
        engine, _ = _make_engine()
        with pytest.raises(ValueError, match="not found"):
            issue_resume_token(engine, "no-such-record", "approver-1")

    def test_build_resume_url(self):
        url = build_resume_url("https://app.example.com/", "rid-1", "tok-123")
        assert url == "https://app.example.com/api/v1/hitl/rid-1/resume?token=tok-123"
        assert DEFAULT_RESUME_TTL_SECONDS == 24 * 3600
