import logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from core.degraded_mode import SQLiteFallbackDisabledError
from tools.checkpoint_manager import Checkpoint, CheckpointManager


class TestCheckpointManagerComprehensive:
    @pytest.fixture
    def temp_sqlite_file(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as exc:
                logging.getLogger(__name__).warning(
                    "Could not remove temp SQLite file %s: %s", temp_path, exc
                )

    def test_sqlite_save_and_load(self, temp_sqlite_file):
        mgr = CheckpointManager(db_path=temp_sqlite_file)
        assert mgr.mode == "sqlite"
        assert mgr.available is True

        # Save checkpoint
        task_id = "task-100"
        state = {"count": 42, "status": "running"}
        saved = mgr.save(task_id, step_index=3, state=state)
        assert saved is True

        # Load checkpoint (first time -> resumed should be marked)
        loaded = mgr.load(task_id)
        assert loaded is not None
        assert loaded.task_id == task_id
        assert loaded.step_index == 3
        assert loaded.state == state
        assert loaded.resumed is False  # Before this read it wasn't resumed

        # Load checkpoint again -> resumed should be True
        loaded_again = mgr.load(task_id)
        assert loaded_again is not None
        assert loaded_again.resumed is True

        # Load non-existent
        assert mgr.load("non-existent") is None

    def test_sqlite_list_and_clear(self, temp_sqlite_file):
        mgr = CheckpointManager(db_path=temp_sqlite_file)

        mgr.save("task-1", 1, {"step": 1})
        mgr.save("task-2", 2, {"step": 2})

        all_cps = mgr.list_all()
        assert len(all_cps) == 2
        ids = [c["task_id"] for c in all_cps]
        assert "task-1" in ids
        assert "task-2" in ids

        # Clear task-1
        cleared = mgr.clear("task-1")
        assert cleared is True

        # Verify deletion
        remaining = mgr.list_all()
        assert len(remaining) == 1
        assert remaining[0]["task_id"] == "task-2"

        # Clear non-existent
        assert mgr.clear("non-existent") is True

    def test_disabled_fail_closed_mode(self):
        # Simulate fail-closed production environment where SQLite fallback is refused
        with (
            patch("tools.checkpoint_manager.pooled_pg.is_available", return_value=False),
            patch("tools.checkpoint_manager.get_firestore_db", return_value=None),
            patch(
                "tools.checkpoint_manager.require_sqlite_allowed",
                side_effect=SQLiteFallbackDisabledError("Refused"),
            ),
            patch("tools.checkpoint_manager.is_test_environment", return_value=False),
        ):
            mgr = CheckpointManager(db_path=None)
            assert mgr.mode == "disabled"
            assert mgr.available is False
            assert mgr.save("t1", 1, {}) is False
            assert mgr.load("t1") is None
            assert mgr.list_all() == []
            assert mgr.clear("t1") is False

    def test_lazy_checkpoint_manager(self, temp_sqlite_file):
        from tools.checkpoint_manager import LazyCheckpointManager

        lazy_mgr = LazyCheckpointManager(db_path=temp_sqlite_file)
        assert lazy_mgr.save("lazy-1", 1, {"a": 1}) is True
        cp = lazy_mgr.load("lazy-1")
        assert cp is not None
        assert cp.task_id == "lazy-1"
        assert len(lazy_mgr.list_all()) == 1
        assert lazy_mgr.clear("lazy-1") is True

    def test_pg_mode_simulation(self):
        # Test postgres mode logic with mocked pooled_pg and batcher
        with (
            patch("tools.checkpoint_manager.pooled_pg.is_available", return_value=True),
            patch("tools.checkpoint_manager.pooled_pg.execute_ddl"),
            patch("tools.checkpoint_manager.is_test_environment", return_value=False),
        ):
            mock_batcher = MagicMock()
            with patch("tools.checkpoint_manager.CheckpointManager._batcher", mock_batcher):
                mgr = CheckpointManager(db_path=None)
                assert mgr.mode == "pg"

                # Save calls batcher.submit
                saved = mgr.save("pg-task-1", 2, {"key": "val"})
                assert saved is True
                assert mock_batcher.submit.called

                # Load calls pooled_pg.query and batcher.flush
                with (
                    patch(
                        "tools.checkpoint_manager.pooled_pg.query",
                        return_value=[
                            ("pg-task-1", 2, '{"key": "val"}', "2026-09-07T00:00:00Z", False)
                        ],
                    ),
                    patch("tools.checkpoint_manager.pooled_pg.execute") as mock_exec,
                ):
                    cp = mgr.load("pg-task-1")
                    assert cp is not None
                    assert cp.task_id == "pg-task-1"
                    assert cp.state == {"key": "val"}
                    assert mock_batcher.flush.called
                    assert mock_exec.called
