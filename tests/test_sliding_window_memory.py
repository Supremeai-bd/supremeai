import os
import tempfile
from typing import Any, Dict, List

import pytest

from memory.sliding_window import SlidingWindowMemory, SlidingWindowConfig, MemoryWindowRecord
from memory.checkpoint_resume import CheckpointResume


@pytest.fixture()
def window_store(tmp_path):
    db_path = str(tmp_path / "sliding_window.db")
    store = SlidingWindowMemory(config=SlidingWindowConfig(max_tokens=20, overlap_ratio=0.2), db_path=db_path)
    yield store


def test_chunk_persists_records(window_store):
    words = " ".join([f"w{i}" for i in range(30)])
    windows = window_store.chunk(words, session_id="s1")
    assert len(windows) > 1
    records = window_store.recall("s1", limit=20)
    assert len(records) == len(windows)
    assert all("text" in rec for rec in records)


def test_recall_returns_latest_first(window_store):
    window_store.chunk("first long text one two three four five six seven eight", session_id="s1")
    window_store.chunk("second long text alpha beta gamma delta epsilon zeta eta theta iota", session_id="s1")
    records = window_store.recall("s1", limit=5)
    assert len(records) > 0
    assert "second long text" in records[0]["text"]


def test_clear_session(window_store):
    window_store.chunk("persistent session text one two three four", session_id="s1")
    assert len(window_store.recall("s1", limit=20)) > 0
    ok = window_store.clear("s1")
    assert ok is True
    assert len(window_store.recall("s1", limit=20)) == 0


def test_build_context_respects_budget(window_store):
    long_doc = " ".join([f"word{idx}" for idx in range(50)])
    context = window_store.build_context([long_doc], "", session_id="s2", budget=20)
    assert context != ""
    token_count = len(context.split())
    assert token_count <= 20


def test_build_context_merges_recalled_chunks(window_store):
    window_store.chunk("two three four five six", session_id="s3")
    window_store.chunk("new document seven eight nine ten", session_id="s3")
    context = window_store.build_context(["new document seven eight nine ten"], "", session_id="s3", budget=50)
    assert "two three four five six" in context


def test_checkpoint_resume_flow(window_store, tmp_path):
    db_path = str(tmp_path / "checkpoints.db")
    store = CheckpointResume(db_path=db_path)
    ok = store.save("flow-1", 1, {"buffer": "alpha"})
    assert ok is True
    loaded = store.load("flow-1")
    assert loaded is not None
    assert loaded["step_index"] == 1
    assert loaded["state"]["buffer"] == "alpha"
    assert store.clear("flow-1") is True
