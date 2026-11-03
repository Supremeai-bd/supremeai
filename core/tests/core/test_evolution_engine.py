from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from core.self_evolution.evolution_engine import EvolutionEngine


def _make_engine(monkeypatch=None):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "evolution.db")
    engine = EvolutionEngine(db_path=db_path)
    if monkeypatch:
        monkeypatch.setattr("database.supabase_client.db.client", False)
    return engine, db_path, tmpdir


@pytest.mark.anyio
async def test_run_daily_evolution_empty_history(monkeypatch):
    engine, _, _ = _make_engine(monkeypatch)
    # বাংলা মন্তব্য: run_daily_evolution অ্যাসিঙ্ক হওয়ায় এখানে await করা হলো।
    report = await engine.run_daily_evolution([])
    assert report["total_tasks_processed"] == 0
    assert report["success_rate"] == 100.0
    assert report["repeated_failures"] == 0
    assert report["new_skills_proposed"] == []


@pytest.mark.anyio
async def test_run_daily_evolution_all_success(monkeypatch):
    engine, _, _ = _make_engine(monkeypatch)
    history = [
        {"success": True, "task": "t1"},
        {"success": True, "task": "t2"},
        {"success": True, "task": "t3"},
    ]
    # বাংলা মন্তব্য: run_daily_evolution অ্যাসিঙ্ক হওয়ায় এখানে await করা হলো।
    report = await engine.run_daily_evolution(history)
    assert report["total_tasks_processed"] == 3
    assert report["success_rate"] == 100.0
    assert report["repeated_failures"] == 0


@pytest.mark.anyio
async def test_run_daily_evolution_all_failure_triggers_repeated_failures(monkeypatch):
    engine, _, _ = _make_engine(monkeypatch)
    for _ in range(5):
        engine.learn_from_failure("flaky_task", "approach_a", "timeout")
    # বাংলা মন্তব্য: run_daily_evolution অ্যাসিঙ্ক হওয়ায় এখানে await করা হলো।
    report = await engine.run_daily_evolution([])
    assert report["repeated_failures"] >= 1


def test_evolution_engine_uses_supabase_when_available(monkeypatch):
    mock_db = MagicMock()
    mock_db.client = True
    mock_db.insert_task_history.return_value = {"id": 1, "task": "supabase_task"}
    mock_db.get_repeated_failures.return_value = [
        {
            "task": "supabase_task",
            "approach": "good_approach",
            "failures": 3,
            "last_failed": "2026-06-27T17:00:00Z",
        }
    ]

    monkeypatch.setattr("database.supabase_client.db", mock_db)

    engine, _, _ = _make_engine()
    result = engine.learn_from_success("supabase_task", "good_approach", "ok")
    assert result["stored"] is True
    assert result["task"] == "supabase_task"
    mock_db.insert_task_history.assert_called_once()

    failures = engine.detect_repeated_failures(min_occurrences=1)
    assert failures == mock_db.get_repeated_failures.return_value
