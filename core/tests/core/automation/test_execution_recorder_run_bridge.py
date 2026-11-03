"""ExecutionRecorder → canonical Run bridge tests (ERR-F01 wiring, M1-C).

Gap closure: the four ``runs.bridges`` adapters had ZERO production callers —
the canonical Run fabric was reachable only through the direct ``/api/v1/runs``
API. This suite pins the NEW production wiring: every automation dispatch
(``ExecutionRecorder.record_start`` / ``record_completion`` /
``persist_execution``) is now observed as a canonical Run.

Doctrine under test (Plan Section 10 — core-operation isolation):
run-fabric writes are BEST-EFFORT and land AFTER the authoritative
``automation_executions`` commit; a missing ``runs`` table or any bridge
failure must never break dispatch persistence.

Uses the runs-suite pattern: dedicated sqlite+aiosqlite in-memory engine,
explicit ``create_all`` over the needed tables (the PG-only partitioned
``execution_logs`` table must NOT be compiled on sqlite).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.automation.execution_recorder import ExecutionRecorder
from core.automation.models import AutomationEvent, AutomationResult, AutomationStatus
from core.orchestration.conversation_orchestrator import ExecutionRecord
from missions.models import Mission  # noqa: F401 — registers missions table (runs FK target)
from models.base import Base
from runs.models import Run, RunEvent


def _make_engine(tables: list):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine, tables


@pytest_asyncio.fixture
async def full_session():
    """Session with BOTH the automation tables and the canonical run tables."""
    from models.automation_execution import (  # noqa: F401
        AutomationExecution,
        AutomationExecutionAttempt,
    )

    engine, _ = _make_engine([])
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Mission.__table__,
                    AutomationExecution.__table__,
                    AutomationExecutionAttempt.__table__,
                    Run.__table__,
                    RunEvent.__table__,
                ],
            )
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def automation_only_session():
    """Session WITHOUT the run-fabric tables (legacy/old DB simulation)."""
    from models.automation_execution import AutomationExecution  # noqa: F401

    engine, _ = _make_engine([])
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=[AutomationExecution.__table__]
            )
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


def _patched(session):
    @asynccontextmanager
    async def _ctx():
        yield session

    return patch("database.session.get_db_session_context", side_effect=_ctx)


def _event() -> AutomationEvent:
    return AutomationEvent(workflow_key="USER_REGISTERED", trace_id="trace-abc")


@pytest.mark.asyncio
async def test_record_start_observes_canonical_run(full_session):
    """record_start creates an observing Run in RUNNING state, source-anchored."""
    recorder = ExecutionRecorder()
    event = _event()

    with _patched(full_session):
        execution_id = await recorder.record_start(event)

    assert execution_id is not None
    row = (
        await full_session.execute(
            select(Run).where(Run.source_type == "automation", Run.source_ref == execution_id)
        )
    ).scalar_one()
    assert row.status == "running"  # REQUESTED → RUNNING at dispatch start
    assert row.run_type == "automation"
    assert row.idempotency_key == f"automation-obs:{event.event_id}"
    assert row.title.startswith("automation:USER_REGISTERED")
    assert row.started_at is not None
    # Audit stream recorded both lifecycle events
    events = (
        (
            await full_session.execute(
                select(RunEvent).where(RunEvent.run_id == row.id).order_by(RunEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    # run_created + the stamped pre-execution path (policy_checked/planned/running)
    assert [e.event for e in events] == [
        "run_created",
        "status_transition",
        "status_transition",
        "status_transition",
    ]
    assert [e.detail["to"] for e in events[1:]] == ["policy_checked", "planned", "running"]


@pytest.mark.asyncio
async def test_record_start_is_idempotent_on_event_id(full_session):
    """Re-dispatching the same event_id must not duplicate observing runs.

    (Two automation rows with the SAME event id can legitimately coexist —
    the table's unique key is (workflow_key, idempotency_key) — but the run
    fabric must still dedup them via ``automation-obs:<event_id>``.)
    """
    from uuid import uuid4

    recorder = ExecutionRecorder()
    event = _event()
    redis_event = event.model_copy(update={"idempotency_key": str(uuid4())})
    with _patched(full_session):
        await recorder.record_start(event)
        await recorder.record_start(redis_event)
    runs = (
        (
            await full_session.execute(
                select(Run).where(Run.idempotency_key == f"automation-obs:{event.event_id}")
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_record_completion_settles_delivered_to_succeeded(full_session):
    recorder = ExecutionRecorder()
    event = _event()
    with _patched(full_session):
        execution_id = await recorder.record_start(event)
        await recorder.record_completion(
            execution_id,
            event,
            AutomationResult(
                status=AutomationStatus.DELIVERED,
                provider="WebhookProvider",
                message="ok",
                event_id=event.event_id,
            ),
            provider_name="WebhookProvider",
            started_at=None,
        )
    row = (
        await full_session.execute(
            select(Run).where(Run.source_type == "automation", Run.source_ref == execution_id)
        )
    ).scalar_one()
    assert row.status == "succeeded"
    assert row.terminal_at is not None


@pytest.mark.asyncio
async def test_record_completion_maps_failed_and_surfaces_error(full_session):
    recorder = ExecutionRecorder()
    event = _event()
    with _patched(full_session):
        execution_id = await recorder.record_start(event)
        await recorder.record_completion(
            execution_id,
            event,
            AutomationResult(
                status=AutomationStatus.FAILED,
                provider="WebhookProvider",
                message="connection refused",
                event_id=event.event_id,
            ),
            provider_name="WebhookProvider",
            started_at=None,
        )
    row = (
        await full_session.execute(
            select(Run).where(Run.source_type == "automation", Run.source_ref == execution_id)
        )
    ).scalar_one()
    assert row.status == "failed"
    assert row.error == "connection refused"


@pytest.mark.asyncio
async def test_record_completion_maps_skipped_to_cancelled(full_session):
    recorder = ExecutionRecorder()
    event = _event()
    with _patched(full_session):
        execution_id = await recorder.record_start(event)
        await recorder.record_completion(
            execution_id,
            event,
            AutomationResult(
                status=AutomationStatus.SKIPPED,
                provider="none",
                message="Automation is disabled globally.",
                event_id=event.event_id,
            ),
            provider_name="none",
            started_at=None,
        )
    row = (
        await full_session.execute(
            select(Run).where(Run.source_type == "automation", Run.source_ref == execution_id)
        )
    ).scalar_one()
    assert row.status == "cancelled"


@pytest.mark.asyncio
async def test_bridge_failure_never_breaks_dispatch_persistence(automation_only_session):
    """No run tables (old DB) → automation row still persists, no exception."""
    from models.automation_execution import AutomationExecution

    recorder = ExecutionRecorder()
    event = _event()
    with _patched(automation_only_session):
        execution_id = await recorder.record_start(event)

    assert execution_id is not None  # authoritative path succeeded
    row = (
        await automation_only_session.execute(
            select(AutomationExecution).where(AutomationExecution.id == execution_id)
        )
    ).scalar_one()
    assert row.status == "PENDING"  # unchanged behavior


@pytest.mark.asyncio
async def test_persist_execution_observes_and_settles_run(full_session):
    """Orchestration path: run lands settled in one step (completed → SUCCEEDED)."""
    recorder = ExecutionRecorder()
    record = ExecutionRecord(
        execution_id="exec_bridge1",
        correlation_id="corr_bridge1",
        user_id="user-42",
        tenant_id="tenant-a",
        project_id=None,
        conversation_id=None,
        capability="task",
        status="completed",
    )
    with _patched(full_session):
        execution_id = await recorder.persist_execution(record)

    row = (
        await full_session.execute(
            select(Run).where(Run.source_type == "automation", Run.source_ref == execution_id)
        )
    ).scalar_one()
    assert row.status == "succeeded"
    assert row.user_id == "user-42"
    assert row.correlation_id == "corr_bridge1"
    assert row.idempotency_key == "orchestration-obs:corr_bridge1"


@pytest.mark.asyncio
async def test_persist_execution_maps_failed_status(full_session):
    recorder = ExecutionRecorder()
    record = ExecutionRecord(
        execution_id="exec_bridge2",
        correlation_id="corr_bridge2",
        user_id="user-42",
        tenant_id="tenant-a",
        project_id=None,
        conversation_id=None,
        capability="task",
        status="failed",
    )
    with _patched(full_session):
        execution_id = await recorder.persist_execution(record)
    row = (
        await full_session.execute(
            select(Run).where(Run.source_type == "automation", Run.source_ref == execution_id)
        )
    ).scalar_one()
    assert row.status == "failed"
    assert row.error is not None
