# backend/tests/learning/test_learning.py
"""Tests for ExperienceStore and OutcomeAnalyzer."""

from learning.experience import ExperienceRecord, get_experience_store
from learning.outcome_analyzer import OutcomeClassification, get_outcome_analyzer


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


def test_outcome_analyzer_success_and_failure_classification():
    analyzer = get_outcome_analyzer()

    success_record = ExperienceRecord(
        task_id="task_succ",
        goal="Task passed",
        verified=True,
        verification_score=0.95,
    )
    assert analyzer.classify_outcome(success_record) == OutcomeClassification.SUCCESS

    syntax_record = ExperienceRecord(
        task_id="task_syn",
        goal="Broken Python Code",
        verified=False,
        verification_score=0.2,
        failures=["Python Syntax Error: invalid syntax at line 4"],
    )
    assert analyzer.classify_outcome(syntax_record) == OutcomeClassification.SYNTAX_ERROR

    lessons = analyzer.analyze_and_extract_lessons(syntax_record)
    assert len(lessons) >= 1
    assert "AST verification failed" in lessons[0]
