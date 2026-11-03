from unittest.mock import patch

import pytest

from monitoring.log_batcher import LogBatcherError, SupremeLogBatcher


def test_log_batcher_append_and_size_flush():
    with patch.object(SupremeLogBatcher, "flush_buffer") as mock_flush:
        batcher = SupremeLogBatcher(max_batch_size=2)
        batcher.append_log("INFO", "First trace")
        assert mock_flush.call_count == 0

        batcher.append_log("WARNING", "Second trace triggers limit")
        assert mock_flush.call_count == 1


def test_log_batcher_fault_tolerance_requeue():
    batcher = SupremeLogBatcher(max_batch_size=10)
    batcher.append_log("ERROR", "Sensitive transaction log entry")

    with patch(
        "monitoring.log_batcher.db.append_evolution_log",
        side_effect=RuntimeError("Network DropOut"),
    ):
        with pytest.raises(LogBatcherError):
            batcher.flush_buffer()

        with batcher._lock:
            assert len(batcher._buffer) == 1
            assert batcher._buffer[0]["message"] == "Sensitive transaction log entry"
