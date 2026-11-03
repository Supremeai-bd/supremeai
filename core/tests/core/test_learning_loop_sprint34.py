"""Sprint 3/4 regression tests — durable telemetry + learning loop.

Covers the Self-Evolution Zero-Cost plan requirements:
  * every LLM operation produces a structured event (telemetry → durable sink)
  * actual token usage captured alongside estimates (calibration bounded)
  * error fingerprinting (error_class + error_hash)
  * feedback taxonomy validation
  * learning loop: aggregation, fitness snapshots, error-pattern proposals
  * safety: telemetry/learning failures NEVER affect the LLM call outcome
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from core.learning import (
    MAX_RATIO,
    MIN_RATIO,
    MIN_SAMPLES,
    aggregate_provider_metrics,
    get_learning_loop_agent,
    get_learning_store,
    get_ratio,
    record_feedback,
    record_llm_event,
    reset_calibration,
    update_ratio,
)
from core.learning.loop import (
    ERROR_PATTERN_MIN_OCCURRENCES,
    LearningLoopAgent,
)
from core.llm.telemetry import LLMCallRecord, classify_llm_error, track_llm_call

# --------------------------------------------------------------- classification


def test_classify_rate_limit() -> None:
    exc = type("H", (Exception,), {})("429 Too Many Requests")
    assert classify_llm_error(exc) == "rate_limit"


def test_classify_auth_and_server_and_timeout() -> None:
    assert classify_llm_error(Exception("401 unauthorized api key")) == "auth"
    assert classify_llm_error(Exception("gateway 500 error")) == "server_error"
    assert classify_llm_error(Exception("connection timed out")) == "timeout"
    assert classify_llm_error(Exception("weird failure")) == "unknown"
    assert classify_llm_error(None) == ""


# --------------------------------------------------------------- track_llm_call


@pytest.mark.asyncio
async def test_track_llm_call_records_durable_event_on_success() -> None:
    store = get_learning_store()
    store._buffer.clear()
    async with track_llm_call(
        provider="gemini", model="gemini/gemini-2.0-flash", task_type="chat"
    ) as rec:
        rec.tokens_prompt = 100
        rec.tokens_completion = 50
        rec.cost_usd = 0.001
    assert rec.success is True
    rows = [row for row in store._buffer if row.get("provider") == "gemini"]
    assert rows, "durable learning event must be enqueued"
    row = rows[-1]
    assert row["model"] == "gemini/gemini-2.0-flash"
    assert row["success"] is True
    assert row["cache_hit"] is False
    assert row["input_tokens"] == 100
    # privacy: no raw-content fields anywhere
    assert not any(k in row for k in ("prompt", "response", "content"))


@pytest.mark.asyncio
async def test_track_llm_call_records_error_fingerprint_on_failure() -> None:
    store = get_learning_store()
    store._buffer.clear()
    with pytest.raises(RuntimeError):
        async with track_llm_call(provider="groq", model="groq/llama-3", task_type="chat") as rec:
            rec.estimated_tokens = 42
            raise RuntimeError("429 rate limit exceeded")
    rows = [row for row in store._buffer if row.get("provider") == "groq"]
    assert rows, "failed call must still be recorded"
    row = rows[-1]
    assert row["success"] is False
    assert row["error_class"] == "rate_limit"
    assert row["error_hash"], "error fingerprint (hash) must be present"


@pytest.mark.asyncio
async def test_track_llm_call_sink_failure_never_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The durable pipeline must not be able to affect the LLM call outcome."""
    import core.llm.telemetry as telemetry_mod

    def _boom(record):
        raise RuntimeError("durable sink exploded")

    monkeypatch.setattr(telemetry_mod, "_record_durable", _boom)
    async with track_llm_call(provider="x", model="y") as rec:
        pass
    assert rec.success is True  # the call result is untouched


@pytest.mark.asyncio
async def test_metadata_loop_context_merged_into_record() -> None:
    async with track_llm_call(
        provider="p", model="m", metadata={"fallback_count": 2, "estimated_tokens": 77}
    ) as rec:
        pass
    assert rec.fallback_count == 2
    assert rec.estimated_tokens == 77
    assert rec.request_id  # auto-generated


# --------------------------------------------------------------- calibration


def test_calibration_bounded_and_min_samples() -> None:
    reset_calibration()
    # Below MIN_SAMPLES: ratio stays 1.0 (no evidence → no learning)
    for _ in range(MIN_SAMPLES - 1):
        update_ratio("prov", "model", estimated=100, actual=200)
    assert get_ratio("prov", "model") == 1.0
    # One more sample crosses the threshold; step is clamped by MAX_STEP
    update_ratio("prov", "model", estimated=100, actual=200)
    ratio = get_ratio("prov", "model")
    assert MIN_RATIO < ratio <= 1.0 + 0.1 + 1e-9
    # Extreme observations can never push beyond MAX_RATIO
    for _ in range(50):
        update_ratio("prov", "model", estimated=1, actual=1000)
    assert get_ratio("prov", "model") <= MAX_RATIO
    # Invalid inputs ignored
    assert update_ratio("prov", "model", estimated=0, actual=10) is None
    reset_calibration()


# --------------------------------------------------------------- learning loop


def _sample_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for i in range(30):
        events.append(
            {
                "provider": "gemini",
                "model": "gemini/gemini-2.0-flash",
                "task_type": "chat",
                "success": True,
                "latency_ms": 300 + i,
                "actual_cost": 0.0001,
            }
        )
    for i in range(5):
        events.append(
            {
                "provider": "groq",
                "model": "groq/llama-3",
                "task_type": "chat",
                "success": False,
                "latency_ms": 900,
                "error_class": "rate_limit",
                "error_hash": "aa" * 32,
            }
        )
    return events


def test_aggregate_provider_metrics_counts_rate_limits() -> None:
    rows = aggregate_provider_metrics(_sample_events(), "2026-09-02T10:00:00+00:00")
    by_provider = {row["provider"]: row for row in rows}
    assert by_provider["gemini"]["requests"] == 30
    assert by_provider["gemini"]["successes"] == 30
    assert by_provider["gemini"]["rate_limited"] == 0
    assert by_provider["gemini"]["latency_p50_ms"] is not None
    assert by_provider["groq"]["failures"] == 5
    assert by_provider["groq"]["rate_limited"] == 5


def test_error_pattern_proposals_need_min_occurrences() -> None:
    proposals = LearningLoopAgent._error_pattern_proposals(_sample_events())
    assert len(proposals) == 1  # groq error_hash fires 5x (>= 3)
    proposal = proposals[0]
    assert proposal["status"] == "PROPOSED"
    assert proposal["proposal_type"] == "error_pattern"
    assert proposal["baseline"]["occurrences"] == 5
    assert proposal["created_by"] == "learning_loop_agent"
    # below threshold → no proposal (plan §10.2)
    few = [
        dict(e, error_hash="bb" * 32) for e in _sample_events()[: ERROR_PATTERN_MIN_OCCURRENCES - 1]
    ]
    few = [e for e in few if e.get("success") is False]
    assert LearningLoopAgent._error_pattern_proposals(few) == []


def test_fitness_snapshots_require_min_samples() -> None:
    snapshots = LearningLoopAgent._fitness_snapshots(_sample_events())
    # 35 chat samples total → snapshot produced
    assert "chat" in snapshots
    snap = snapshots["chat"]
    assert 0.0 <= snap["composite"] <= 1.0
    assert snap["sample_size"] == 35
    # tiny sample → no snapshot (plan §7.2: <10 = insufficient evidence)
    assert LearningLoopAgent._fitness_snapshots(_sample_events()[:5]) == {}


@pytest.mark.asyncio
async def test_loop_cycle_aggregates_and_proposes_with_mock_db() -> None:
    agent = get_learning_loop_agent()
    agent.cycles_run = 0
    agent.proposals_created = 0

    class _FakeDB:
        def __init__(self) -> None:
            self.provider_rows: list[dict] = []
            self.skill_rows: list[dict] = []
            self.snapshots: list[dict] = []
            self.proposals: list[dict] = []
            self.runs: list[dict] = []

        def get_learning_events(self, **kwargs: Any) -> list[dict]:
            return _sample_events()

        def upsert_provider_metric(self, row: dict) -> bool:
            self.provider_rows.append(row)
            return True

        def upsert_skill_metric(self, row: dict) -> bool:
            self.skill_rows.append(row)
            return True

        def append_fitness_snapshot(self, row: dict) -> bool:
            self.snapshots.append(row)
            return True

        def insert_improvement_proposal(self, row: dict) -> str:
            self.proposals.append(row)
            return "prop_1"

        def insert_improvement_run(self, row: dict) -> bool:
            self.runs.append(row)
            return True

    fake = _FakeDB()
    monkey_patch = pytest.MonkeyPatch()
    monkey_patch.setattr(agent, "_get_db", lambda: fake, raising=False)
    try:
        stats = await agent.run_cycle()
    finally:
        monkey_patch.undo()
    assert stats["provider_rows"] == 2
    assert stats["skill_rows"] >= 1
    assert stats["fitness_snapshots"] == 1
    assert stats["proposals"] == 1
    assert fake.runs and fake.runs[0]["run_type"] == "BASELINE"
    assert agent.cycles_run == 1


@pytest.mark.asyncio
async def test_loop_cycle_survives_db_unavailable() -> None:
    agent = LearningLoopAgent(interval_seconds=60)
    monkey_patch = pytest.MonkeyPatch()
    monkey_patch.setattr(agent, "_get_db", lambda: None, raising=False)
    try:
        stats = await agent.run_cycle()
    finally:
        monkey_patch.undo()
    assert stats["provider_rows"] == 0


# --------------------------------------------------------------- feedback route


def test_record_feedback_validates_type() -> None:
    assert record_feedback("thumbs_up") is True
    assert record_feedback("love_it") is False  # invalid → rejected, never recorded


def test_store_records_feedback_event() -> None:
    store = get_learning_store()
    store._buffer.clear()
    assert store.record_feedback("thumbs_down", task_type="chat", skill_id="s1") is True
    row = store._buffer[-1]
    assert row["feedback"] == "thumbs_down"
    assert row["metadata"]["feedback_type"] == "thumbs_down"
    assert not any("content" in k or "prompt" in k for k in row)
