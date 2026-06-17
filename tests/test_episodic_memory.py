import os
import tempfile
from typing import Any, Dict, List, Optional

import pytest

from memory.episodic_memory import EpisodicMemory


@pytest.fixture()
def memory_store():
    store = EpisodicMemory(db_path=":memory:", session_id="test-session")
    yield store
    store._memory_conn.close() if store._memory_conn else None


def test_store_episode_basic(memory_store):
    result = memory_store.store_episode(event_type="task.completed", context="Ran OCR for document 1", outcome="success", importance=5.0)
    assert result["status"] == "ok"
    assert "episode_id" in result


def test_recall_episodes_empty(memory_store):
    episodes = memory_store.recall_episodes()
    assert episodes == []


def test_recall_episodes_with_filter(memory_store):
    memory_store.store_episode("task.completed", "doc-1", "success", importance=5.0)
    memory_store.store_episode("task.failed", "doc-2", "timeout", importance=2.0)
    memory_store.store_episode("task.completed", "doc-3", "success", importance=4.0)

    completed = memory_store.recall_episodes(event_type="task.completed")
    assert len(completed) == 2
    assert all(ep["event_type"] == "task.completed" for ep in completed)

    high_importance = memory_store.recall_episodes(min_importance=3.0)
    assert len(high_importance) == 2
    for ep in high_importance:
        assert ep["importance"] >= 3.0


def test_recall_episodes_limit(memory_store):
    for idx in range(25):
        memory_store.store_episode("task.completed", f"doc-{idx}", "success", importance=float(idx))

    episodes = memory_store.recall_episodes(limit=10)
    assert len(episodes) == 10


def test_summarize_recent_empty(memory_store):
    text = memory_store.summarize_recent(limit=5)
    assert text == ""


def test_summarize_recent_with_episodes(memory_store):
    memory_store.store_episode("task.completed", "doc-1", "success", importance=5.0)
    memory_store.store_episode("auth.login", "user-1", "success", importance=3.0)

    text = memory_store.summarize_recent(limit=5)
    assert "Recent episodes:" in text
    assert "task.completed" in text
    assert "auth.login" in text
    assert "doc-1" in text


def test_summarize_recent_limit(memory_store):
    for idx in range(10):
        memory_store.store_episode("task.completed", f"doc-{idx}", "success", importance=float(idx))

    text = memory_store.summarize_recent(limit=3)
    assert "Recent episodes:" in text
    assert len(text.splitlines()) == 4
    assert len(text.splitlines()[1:]) == 3
