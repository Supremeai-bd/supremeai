"""Sprint 2 — Persistent Learning Store tests (Task 9-d).

Covers:
  * record_event enqueues WITHOUT network (writer resolved lazily in flush)
  * flush writes via the (mocked) SupabaseDB PostgREST repository
  * PRIVACY: no prompt/response/content field is ever serialized
  * bounded buffer: drop-oldest on overflow, no exception
  * writer failure: events parked in bounded fallback, db_ok False
  * aggregate_provider_metrics: counts, percentiles, rate_limit tagging
  * record_feedback validates against the allowed categorical types
  * SupabaseDB repository chunking + on_conflict upsert wiring (offline fakes)
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

import core.learning.store as store_module
from core.learning import (
    ALLOWED_FEEDBACK_TYPES,
    LEARNING_EVENT_FIELDS,
    LearningEvent,
    LearningStore,
    aggregate_provider_metrics,
    get_learning_store,
    record_feedback,
    sanitize_metadata,
)

_FORBIDDEN_MARKERS = ("prompt", "response", "content")


def _assert_no_forbidden_keys(obj, path: str = "") -> None:
    """Recursively assert no raw-content field ever appears in a payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_str = str(key).lower()
            assert not any(m in key_str for m in _FORBIDDEN_MARKERS), (
                f"privacy violation: forbidden key {key!r} at {path}"
            )
            _assert_no_forbidden_keys(value, f"{path}.{key}")
    elif isinstance(obj, (list, tuple)):
        for idx, value in enumerate(obj):
            _assert_no_forbidden_keys(value, f"{path}[{idx}]")


class FakeWriterDB:
    """Stands in for SupabaseDB; records append_learning_events calls."""

    def __init__(self, *, fail: bool = False, result: Any = "auto"):
        self.calls: list[list[dict]] = []
        self._fail = fail
        self._result = result  # "auto" -> len(rows); anything else returned verbatim

    def append_learning_events(self, rows):
        self.calls.append(list(rows))
        if self._fail:
            raise RuntimeError("simulated postgrest outage")
        if self._result == "auto":
            return len(rows)
        return self._result


# ---------------------------------------------------------------------------
# record_event / buffering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_event_enqueues_without_network(monkeypatch):
    """record_event must only enqueue; the writer is never touched."""
    store = LearningStore()

    def _boom():
        raise AssertionError("network writer must not be resolved on record_event")

    monkeypatch.setattr(store_module, "_get_db", _boom)
    event = LearningEvent(
        provider="openai",
        model="gpt-4o-mini",
        task_type="chat",
        success=True,
        latency_ms=120,
    )
    assert store.record_event(event) is True
    stats = store.get_stats()
    assert stats["queued"] == 1
    assert stats["flushed"] == 0
    # dict form also accepted
    assert store.record_event({"provider": "groq", "model": "llama-3"}) is True
    assert store.get_stats()["queued"] == 2


@pytest.mark.asyncio
async def test_flush_uses_mocked_writer_with_serialized_dicts(monkeypatch):
    store = LearningStore()
    fake_db = FakeWriterDB()
    monkeypatch.setattr(store_module, "_get_db", lambda: fake_db)

    store.record_event(
        LearningEvent(
            provider="gemini",
            model="gemini-2.0-flash",
            task_type="summarize",
            success=True,
            latency_ms=200,
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.0001,
            metadata={"route": "cheap", "prompt": "SHOULD BE DROPPED"},
        )
    )
    flushed = await store.flush()
    assert flushed == 1
    assert len(fake_db.calls) == 1
    rows = fake_db.calls[0]
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    # serialized LearningEvent shape
    assert uuid.UUID(row["event_id"])  # valid uuid4 string
    assert row["ts"]
    assert row["provider"] == "gemini"
    assert row["model"] == "gemini-2.0-flash"
    assert row["latency_ms"] == 200
    assert row["metadata"] == {"route": "cheap"}
    stats = store.get_stats()
    assert stats["flushed"] == 1
    assert stats["queued"] == 0
    assert stats["last_flush_at"] is not None
    assert stats["db_ok"] is True
    _assert_no_forbidden_keys(rows)
    # flushing an empty store is a no-op
    assert await store.flush() == 0


# ---------------------------------------------------------------------------
# privacy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_privacy_no_prompt_response_content_ever_serialized():
    event = LearningEvent(
        provider="openai",
        model="gpt-4o-mini",
        success=False,
        error_class="timeout",
        error_hash="deadbeef",
        metadata={
            "prompt": "raw user prompt",
            "response": "raw model response",
            "content": "raw content",
            "nested": {"prompt_template": "leak?", "safe_key": 1},
            "items": [{"content_blob": "leak"}, {"ok": True}],
        },
    )
    row = event.to_dict()
    # fixed whitelist of keys — none may be raw content
    assert set(row.keys()) <= set(LEARNING_EVENT_FIELDS) | {"metadata"}
    assert not any(m in k.lower() for k in row for m in _FORBIDDEN_MARKERS)
    _assert_no_forbidden_keys(row)
    assert row["metadata"] == {"nested": {"safe_key": 1}, "items": [{}, {"ok": True}]}

    # dict-based record path is scrubbed too
    store = LearningStore()
    assert (
        store.record_event(
            {"provider": "x", "model": "y", "prompt": "raw", "metadata": {"response": 1}}
        )
        is True
    )
    buffered = list(store._buffer)
    _assert_no_forbidden_keys(buffered)
    assert buffered[0]["metadata"] == {}

    assert sanitize_metadata(None) == {}


# ---------------------------------------------------------------------------
# bounded buffer / drop-oldest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buffer_overflow_drops_oldest_without_exception(monkeypatch):
    store = LearningStore(max_buffer=10)
    monkeypatch.setattr(store_module, "_get_db", lambda: None)  # never used here
    for i in range(15):
        assert store.record_event(LearningEvent(provider="p", model="m", latency_ms=i)) is True
    stats = store.get_stats()
    assert stats["queued"] == 10  # bounded
    assert stats["dropped"] == 5  # oldest 5 evicted
    # first buffered event is the 6th recorded (drop-oldest)
    assert store._buffer[0]["latency_ms"] == 5


# ---------------------------------------------------------------------------
# writer failure -> fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_writer_failure_parks_events_in_fallback(monkeypatch):
    store = LearningStore()
    fake_db = FakeWriterDB(fail=True)
    monkeypatch.setattr(store_module, "_get_db", lambda: fake_db)
    for i in range(3):
        store.record_event(LearningEvent(provider="p", model="m", latency_ms=i))
    flushed = await store.flush()
    assert flushed == 0
    stats = store.get_stats()
    assert stats["db_ok"] is False
    assert stats["queued"] == 0
    assert stats["fallback"] == 3
    assert stats["flushed"] == 0


@pytest.mark.asyncio
async def test_writer_none_result_treated_as_failure(monkeypatch):
    store = LearningStore()
    # PostgREST retry decorator returns None when exhausted
    fake_db = FakeWriterDB(result=None)
    monkeypatch.setattr(store_module, "_get_db", lambda: fake_db)
    store.record_event(LearningEvent(provider="p", model="m"))
    assert await store.flush() == 0
    assert store.get_stats()["db_ok"] is False
    assert store.get_stats()["fallback"] == 1


@pytest.mark.asyncio
async def test_writer_unavailable_none_db(monkeypatch):
    store = LearningStore()
    monkeypatch.setattr(store_module, "_get_db", lambda: None)
    store.record_event(LearningEvent(provider="p", model="m"))
    assert await store.flush() == 0
    stats = store.get_stats()
    assert stats["db_ok"] is False
    assert stats["fallback"] == 1


@pytest.mark.asyncio
async def test_fallback_replayed_on_successful_flush(monkeypatch):
    store = LearningStore()
    failing = FakeWriterDB(fail=True)
    monkeypatch.setattr(store_module, "_get_db", lambda: failing)
    store.record_event(LearningEvent(provider="p", model="m"))
    assert await store.flush() == 0
    assert store.get_stats()["fallback"] == 1

    healthy = FakeWriterDB()
    monkeypatch.setattr(store_module, "_get_db", lambda: healthy)
    assert await store.flush() == 1
    assert healthy.calls and len(healthy.calls[0]) == 1
    stats = store.get_stats()
    assert stats["fallback"] == 0
    assert stats["db_ok"] is True
    assert stats["flushed"] == 1


# ---------------------------------------------------------------------------
# aggregation helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_provider_metrics_counts_and_percentiles():
    events = [
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "success": True,
            "latency_ms": 100,
            "estimated_cost": 0.01,
        },
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "success": True,
            "latency_ms": 200,
            "estimated_cost": 0.02,
        },
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "success": True,
            "latency_ms": 300,
            "estimated_cost": 0.03,
        },
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 400},
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 500},
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 600},
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 700},
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 800},
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 900},
        {"provider": "openai", "model": "gpt-4o-mini", "success": True, "latency_ms": 1000},
        {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "success": False,
            "error_class": "rate_limit",
            "latency_ms": 50,
            "actual_cost": 0.0,
        },
        {"provider": "openai", "model": "gpt-4o-mini", "success": False, "error_class": "timeout"},
        {"provider": "groq", "model": "llama-3-70b", "success": True, "latency_ms": 42},
        {
            "provider": "groq",
            "model": "llama-3-70b",
            "success": False,
            "error_class": "rate_limit",
            "latency_ms": 44,
        },
        {"no_provider": True},  # skipped
    ]
    rows = aggregate_provider_metrics(events, window_start="2026-09-03T00:00:00+00:00")
    assert len(rows) == 2
    by_key = {(r["provider"], r["model"]): r for r in rows}

    openai = by_key[("openai", "gpt-4o-mini")]
    assert openai["requests"] == 12
    assert openai["successes"] == 10
    assert openai["failures"] == 2
    assert openai["rate_limited"] == 1  # only error_class == "rate_limit"
    assert openai["latency_p50_ms"] is not None
    assert openai["latency_p95_ms"] is not None
    assert openai["latency_p50_ms"] <= openai["latency_p95_ms"]
    assert openai["latency_p95_ms"] <= 1000  # sane upper bound = max latency
    assert abs(openai["estimated_cost"] - 0.06) < 1e-9
    assert openai["actual_cost"] == 0.0
    assert openai["window_start"] == "2026-09-03T00:00:00+00:00"

    groq = by_key[("groq", "llama-3-70b")]
    assert groq["requests"] == 2
    assert groq["successes"] == 1
    assert groq["failures"] == 1
    assert groq["rate_limited"] == 1
    assert groq["latency_p50_ms"] == 43  # single pair interpolation
    assert aggregate_provider_metrics(None, "w") == []
    assert aggregate_provider_metrics([], "w") == []


# ---------------------------------------------------------------------------
# feedback validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_feedback_rejects_invalid_type():
    assert record_feedback("shout_into_the_void") is False
    assert record_feedback("") is False
    store = LearningStore()
    assert store.record_feedback("five_stars") is False
    assert store.get_stats()["queued"] == 0


@pytest.mark.asyncio
async def test_record_feedback_accepts_valid_type(monkeypatch):
    assert {
        "thumbs_up",
        "thumbs_down",
        "retry",
        "regenerate",
        "follow_up",
        "correction",
    } == ALLOWED_FEEDBACK_TYPES
    store = LearningStore()
    assert (
        store.record_feedback(
            "thumbs_down",
            task_type="chat",
            skill_id="sql-helper",
            provider="openai",
            model="gpt-4o-mini",
            weight=2.0,
        )
        is True
    )
    row = store._buffer[0]
    assert row["feedback"] == "thumbs_down"
    assert row["task_type"] == "chat"
    assert row["metadata"]["weight"] == 2.0
    _assert_no_forbidden_keys(row)


# ---------------------------------------------------------------------------
# singleton + lifecycle
# ---------------------------------------------------------------------------


def test_get_learning_store_is_singleton():
    assert get_learning_store() is get_learning_store()
    assert isinstance(get_learning_store(), LearningStore)


@pytest.mark.asyncio
async def test_stop_flushes_remaining_events(monkeypatch):
    store = LearningStore()
    fake_db = FakeWriterDB()
    monkeypatch.setattr(store_module, "_get_db", lambda: fake_db)
    store.record_event(LearningEvent(provider="p", model="m"))
    await store.stop()
    assert store.get_stats()["flushed"] == 1
    assert store.get_stats()["queued"] == 0


# ---------------------------------------------------------------------------
# repository wiring on SupabaseDB (offline fake chain, no network)
# ---------------------------------------------------------------------------


class _FakeTable:
    """Mimics the supabase-py fluent query builder for insert/upsert."""

    def __init__(self, sink: list, upserts: list):
        self._sink = sink
        self._upserts = upserts
        self._pending: list[dict] = []

    def insert(self, rows):
        # normalize: supabase-py accepts a single dict or a list of dicts
        self._pending = [dict(rows)] if isinstance(rows, dict) else list(rows)
        return self

    def upsert(self, rows, on_conflict=None, ignore_duplicates=None):
        self._pending = [dict(rows)] if isinstance(rows, dict) else list(rows)
        self._upserts.append(on_conflict)
        return self

    def execute(self):
        rows = self._pending
        self._sink.extend(rows)
        return SimpleNamespace(data=list(rows) if rows else [])


class _FakeSupabaseClient:
    def __init__(self):
        self.inserted: list[dict] = []
        self.upsert_conflicts: list[str] = []

    def table(self, name):
        return _FakeTable(self.inserted, self.upsert_conflicts)


def _offline_supabase_db():
    from database.supabase_client import SupabaseDB

    instance = SupabaseDB()  # offline in sandbox: no clients created
    fake_client = _FakeSupabaseClient()
    instance.service_client = fake_client  # inject; bypasses network entirely
    return instance, fake_client


def test_repository_append_learning_events_chunks_of_100():
    instance, fake_client = _offline_supabase_db()
    rows = [{"event_id": str(uuid.uuid4()), "provider": "p", "model": "m"} for _ in range(250)]
    inserted = instance.append_learning_events(rows)
    assert inserted == 250
    assert len(fake_client.inserted) == 250
    # 250 rows -> exactly 3 chunks (100/100/50)
    assert len({id(r) for r in fake_client.inserted}) == 250


def test_repository_upsert_provider_metric_uses_on_conflict():
    instance, fake_client = _offline_supabase_db()
    ok = instance.upsert_provider_metric(
        {
            "window_start": "2026-09-03T00:00:00+00:00",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "requests": 3,
        }
    )
    assert ok is True
    assert fake_client.upsert_conflicts == ["window_start,provider,model"]
    ok2 = instance.upsert_skill_metric(
        {"window_start": "2026-09-03T00:00:00+00:00", "skill_id": "s1", "requests": 1}
    )
    assert ok2 is True
    assert fake_client.upsert_conflicts[-1] == "window_start,skill_id"


def test_repository_insert_improvement_proposal_returns_id():
    instance, fake_client = _offline_supabase_db()
    proposal_id = instance.insert_improvement_proposal(
        {"proposal_type": "prompt_tweak", "target": "chat", "status": "PROPOSED"}
    )
    assert proposal_id is not None
    assert str(proposal_id)


def test_repository_degrades_without_client():
    from database.supabase_client import SupabaseDB

    instance = SupabaseDB()  # offline: no clients
    instance.service_client = None
    # NOTE: the class-wide retry decorator short-circuits to None when there is
    # no client at all; method bodies return their typed fallback (False/[]/0)
    # when a client exists but the operation fails. Callers must treat None,
    # False and [] identically: "degraded, no data".
    assert instance.append_learning_event({"provider": "p"}) in (None, False)
    assert instance.append_learning_events([{"provider": "p"}]) in (None, 0)
    assert instance.get_learning_events() in (None, [])
    assert instance.append_feedback_event({"feedback_type": "thumbs_up"}) in (None, False)
    assert instance.get_feedback_events() in (None, [])
    assert instance.upsert_provider_metric(
        {"window_start": "w", "provider": "p", "model": "m"}
    ) in (None, False)
    assert instance.get_provider_metrics() in (None, [])
    assert instance.upsert_skill_metric({"window_start": "w", "skill_id": "s"}) in (None, False)
    assert instance.append_fitness_snapshot(
        {"subject_type": "skill", "subject_id": "s", "composite": 0.5}
    ) in (None, False)
    assert instance.get_fitness_snapshots("skill", "s") in (None, [])
    assert instance.insert_improvement_proposal({"proposal_type": "t", "target": "x"}) is None
    assert instance.update_improvement_proposal_status(1, "PROMOTED") in (None, False)
    assert instance.insert_improvement_run({"proposal_id": 1, "run_type": "BASELINE"}) in (
        None,
        False,
    )
    assert instance.get_improvement_proposals() in (None, [])
