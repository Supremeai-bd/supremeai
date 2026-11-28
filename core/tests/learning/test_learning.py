# backend/tests/learning/test_learning.py
"""Tests for the ExperienceStore (live consumer: core/adaptive_engine/experience_db)."""

from learning.experience import ExperienceRecord, get_experience_store


def test_experience_recording_and_retrieval():
    store = get_experience_store()

    record = ExperienceRecord(
        task_id="task_test_101",
        goal="Format JSON payload",
        verified=True,
        verification_score=1.0,
        cost_usd=0.002,
        latency_ms=120.0,
    )

    store.record(record)
    recent = store.get_recent(limit=5)
    assert len(recent) >= 1
    assert any(r.task_id == "task_test_101" for r in recent)
