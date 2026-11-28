"""Phase 0.3 feedback-capture tests: cost_estimate + user_correction flow.

The unified training plan's Capture phase requires every LLM call record to be
able to carry (a) a caller-supplied cost estimate (feeds provider scoring) and
(b) a human correction of an AI outcome — without ever blocking the call path.
"""

from __future__ import annotations

import json

from core.llm.telemetry import LLMCallRecord, track_llm_call


def test_record_fields_default_to_none():
    record = LLMCallRecord(provider="groq", model="llama-3.3-70b-versatile")
    assert record.cost_estimate is None
    assert record.user_correction is None
    payload = json.loads(record.to_log_line())
    assert "cost_estimate" in payload and "user_correction" in payload


def test_metadata_kwargs_populate_feedback_fields():
    import asyncio

    async def run():
        async with track_llm_call(
            provider="gemini",
            model="gemini-flash-lite-latest",
            metadata={"cost_estimate": 0.0001, "user_correction": "route should prefer groq here"},
        ) as record:
            pass
        return record

    record = asyncio.get_event_loop().run_until_complete(run())
    assert record.cost_estimate == 0.0001
    assert record.user_correction == "route should prefer groq here"
    assert record.success is True


def test_learning_event_fields_project_estimated_cost_and_correction():
    record = LLMCallRecord(cost_estimate=0.002, user_correction="wrong tool chosen")
    fields = record.to_learning_event_fields()
    metadata = fields["metadata"]
    assert metadata["estimated_cost"] == 0.002
    assert metadata["user_correction"] == "wrong tool chosen"
    # privacy-safe: no prompt/response content keys ever appear
    assert not any(k in metadata for k in ("prompt", "response", "content"))


def test_durable_sink_maps_estimated_cost_to_column():
    import asyncio
    from unittest.mock import patch


    captured: dict = {}

    def fake_record_llm_event(**kwargs):
        captured.update(kwargs)
        return True

    async def run():
        async with track_llm_call(
            provider="openai",
            model="gpt-4o-mini",
            metadata={"cost_estimate": 0.5, "user_correction": "prefer flash-lite"},
        ):
            pass

    with patch("core.learning.record_llm_event", fake_record_llm_event):
        asyncio.get_event_loop().run_until_complete(run())

    assert captured.get("estimated_cost") == 0.5
    # correction stays in the persisted metadata for Phase 1 reorder logic
    assert captured.get("metadata", {}).get("user_correction") == "prefer flash-lite"
    # estimated_cost is lifted out of metadata into the real column
    assert "estimated_cost" not in captured.get("metadata", {})
