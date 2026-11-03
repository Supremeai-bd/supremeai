"""ExecutionRecorder durable ExecutionRecord bridge tests.

Gap closure: the canonical orchestration `ExecutionRecord` must land in a
durable database row (automation_executions) with correlation/tenant/
project/conversation links + evidence, while DB unavailability must never
block the dispatch (core-operation isolation, Plan Section 10).
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from core.automation.execution_recorder import ExecutionRecorder
from core.orchestration.conversation_orchestrator import ExecutionRecord


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_persist_execution_maps_every_record_field():
    recorder = ExecutionRecorder()
    record = ExecutionRecord(
        execution_id="exec_abc123",
        correlation_id="corr_xyz",
        user_id="u1",
        tenant_id="tenant-a",
        project_id="proj-1",
        conversation_id="conv-1",
        capability="task",
        status="completed",
        evidence=[{"type": "orchestration.completed", "status": "completed"}],
    )
    fake = FakeSession()

    @asynccontextmanager
    async def _fake_session():
        yield fake

    with patch("database.session.get_db_session_context", side_effect=_fake_session):
        execution_id = await recorder.persist_execution(record, policy={"allowed": True})

    assert execution_id is not None
    assert len(fake.added) == 1
    row = fake.added[0]
    assert row.event_id == "exec_abc123"  # canonical execution id bridged
    assert row.idempotency_key == "corr_xyz"  # correlation id enables dedup/lookup
    assert row.trace_id == "corr_xyz"
    assert row.workflow_key == "orchestrator:task"
    assert row.provider == "orchestrator"
    assert row.status == "COMPLETED"
    assert row.tenant_id == "tenant-a"  # tenant isolation column persisted
    assert row.project_id == "proj-1"
    assert row.conversation_id == "conv-1"
    assert row.capability == "task"
    assert row.evidence == [{"type": "orchestration.completed", "status": "completed"}]
    assert row.policy == {"allowed": True}
    assert row.correlation_id == "corr_xyz"


@pytest.mark.asyncio
async def test_persist_execution_graceful_when_db_unavailable():
    """DB failure must return None and never raise (dispatch unaffected)."""
    recorder = ExecutionRecorder()
    record = ExecutionRecord(
        execution_id="exec_1",
        correlation_id="corr_1",
        user_id="u1",
        tenant_id="t1",
        project_id=None,
        conversation_id=None,
        capability="chat",
        status="completed",
    )

    @asynccontextmanager
    async def _boom():
        raise RuntimeError("connection refused")
        yield  # pragma: no cover

    with patch("database.session.get_db_session_context", side_effect=_boom):
        execution_id = await recorder.persist_execution(record)

    assert execution_id is None  # caller must not crash


@pytest.mark.asyncio
async def test_persist_execution_none_record_returns_none():
    recorder = ExecutionRecorder()
    assert await recorder.persist_execution(None) is None  # type: ignore[arg-type]
