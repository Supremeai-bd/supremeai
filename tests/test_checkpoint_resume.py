import json
import os
import tempfile
from typing import Any, Dict

import pytest


@pytest.fixture()
def checkpoint_store(tmp_path):
    db_path = str(tmp_path / "checkpoints.db")
    from memory.checkpoint_resume import CheckpointResume
    store = CheckpointResume(db_path=db_path)
    yield store


def test_save_and_load_checkpoint(checkpoint_store):
    state = {"step": 1, "output": "alpha"}
    saved = checkpoint_store.save("task-1", step_index=1, state=state)
    assert saved is True

    loaded = checkpoint_store.load("task-1")
    assert loaded is not None
    assert loaded["task_id"] == "task-1"
    assert loaded["step_index"] == 1
    assert loaded["state"] == state


def test_load_missing_checkpoint(checkpoint_store):
    result = checkpoint_store.load("missing-task")
    assert result is None


def test_list_after_save(checkpoint_store):
    for idx in range(3):
        assert checkpoint_store.save(f"task-{idx}", step_index=idx, state={"idx": idx}) is True

    all_checkpoints = checkpoint_store.list_all()
    assert len(all_checkpoints) == 3
    task_ids = {cp["task_id"] for cp in all_checkpoints}
    assert task_ids == {"task-0", "task-1", "task-2"}


def test_clear_checkpoint(checkpoint_store):
    checkpoint_store.save("task-x", step_index=1, state={"key": "value"})
    all_cp = checkpoint_store.list_all()
    assert len(all_cp) == 1

    cleared = checkpoint_store.clear("task-x")
    assert cleared is True

    after_clear = checkpoint_store.list_all()
    assert len(after_clear) == 0

    reloaded = checkpoint_store.load("task-x")
    assert reloaded is None


def test_save_overrides_previous_state(checkpoint_store):
    checkpoint_store.save("task-1", step_index=1, state={"version": 1})
    first = checkpoint_store.load("task-1")
    assert first["state"]["version"] == 1

    checkpoint_store.save("task-1", step_index=2, state={"version": 2, "extra": True})
    reloaded = checkpoint_store.load("task-1")
    assert reloaded["step_index"] == 2
    assert reloaded["state"]["version"] == 2
    assert reloaded["state"]["extra"] is True


def test_list_empty_initially(checkpoint_store):
    all_cp = checkpoint_store.list_all()
    assert all_cp == []
