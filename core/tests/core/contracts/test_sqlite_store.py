import tempfile
from pathlib import Path

import pytest

from core.contracts.canonical import (
    EventEnvelope,
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
)
from core.contracts.sqlite_store import SQLiteExecutionStore


def make_context(key="key-1"):
    return ExecutionContext(
        tenant_id="tenant-a",
        actor_id="actor-a",
        workspace_id="workspace-a",
        correlation_id="corr-a",
        idempotency_key=key,
        capability="task.execute",
    )


def test_sqlite_store_survives_reopen_and_replays_idempotency():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "control-plane.db"
        context = make_context()
        store = SQLiteExecutionStore(path)
        assert store.start(context)
        event = EventEnvelope("execution.accepted", context, {"safe": True})
        stored = store.append_event(event)
        store.finish(context.execution_id, ExecutionResult(ExecutionStatus.SUCCEEDED, {"ok": True}))
        store.close()

        reopened = SQLiteExecutionStore(path)
        assert not reopened.start(make_context("key-1"))
        replayed = reopened.append_event(event)
        assert replayed.sequence == stored.sequence
        reopened.close()


def test_sqlite_store_rejects_unknown_finish():
    store = SQLiteExecutionStore()
    try:
        with pytest.raises(KeyError):
            store.finish("missing", ExecutionResult(ExecutionStatus.FAILED))
    finally:
        store.close()
