"""M1-C — HITL hook tests (runs/hitl.py + service.request/resolve_approval).

The run-side HITL contract reuses the existing HITL manager shape
(``suspend(target_resource, payload) -> record_id``). This suite proves:
- the injectable hook is called with the run-anchored target resource;
- the suspension records ``approval_requested`` with the external record id
  and a tamper-evident payload hash (AUD-4.4 discipline);
- resolution closes the loop: approved -> RUNNING, rejected -> FAILED
  (terminal), with ``approval_resolved`` events;
- the PendingTaskApprovalHook adapter builds pending_tasks-shaped records
  with the canonical payload hash without importing the sqlite module.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from missions.models import Mission  # noqa: F401 — registers missions table
from models.base import Base
from runs.hitl import InMemoryApprovalHook, PendingTaskApprovalHook, _payload_hash
from runs.models import Run, RunEvent
from runs.service import RunService
from runs.state_machine import (
    FAILED,
    PLANNED,
    POLICY_CHECKED,
    RUNNING,
    WAITING_APPROVAL,
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[Mission.__table__, Run.__table__, RunEvent.__table__],
            )
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _running_run(session) -> tuple[Run, RunService]:
    svc = RunService()
    run = await svc.create_run(session, run_type="tool", user_id="u1")
    await svc.transition(session, run.id, POLICY_CHECKED)
    await svc.transition(session, run.id, PLANNED)
    await svc.transition(session, run.id, RUNNING)
    return run, svc


class TestApprovalHook:
    @pytest.mark.asyncio
    async def test_hook_receives_run_anchored_target(self, db_session):
        hook = InMemoryApprovalHook()
        svc = RunService(approval_hook=hook)
        run = await svc.create_run(db_session, run_type="tool", user_id="u1")
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)

        payload = {"action": "push-code", "repo": "supremeai"}
        await svc.request_approval(db_session, run.id, payload=payload, actor="policy")

        await db_session.refresh(run)
        assert run.status == WAITING_APPROVAL
        assert run.retry_class == "approval_required"
        assert len(hook.records) == 1
        (record_id, record) = next(iter(hook.records.items()))
        assert record_id.startswith("hitl-")
        assert record["target_resource"] == f"run:{run.id}"
        assert record["payload"] == payload

    @pytest.mark.asyncio
    async def test_approval_event_carries_record_id_and_hash(self, db_session):
        hook = InMemoryApprovalHook()
        svc = RunService(approval_hook=hook)
        run, _ = await _running_run(db_session)
        payload = {"action": "vpn-switch"}
        await svc.request_approval(db_session, run.id, payload=payload)

        evt = (
            (
                await db_session.execute(
                    select(RunEvent).where(
                        RunEvent.run_id == run.id, RunEvent.event == "approval_requested"
                    )
                )
            )
            .scalars()
            .one()
        )
        (record_id, record) = next(iter(hook.records.items()))
        assert evt.detail["record_id"] == record_id
        assert evt.detail["payload_hash"] == record["payload_hash"]
        assert evt.detail["payload_hash"] == _payload_hash(payload)

    @pytest.mark.asyncio
    async def test_resolve_approved_returns_to_running(self, db_session):
        hook = InMemoryApprovalHook()
        svc = RunService(approval_hook=hook)
        run, _ = await _running_run(db_session)
        await svc.request_approval(db_session, run.id, payload={"a": 1})

        resolved = await svc.resolve_approval(db_session, run.id, approved=True, actor="admin-1")
        assert resolved.status == RUNNING
        events = (
            (
                await db_session.execute(
                    select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)
                )
            )
            .scalars()
            .all()
        )
        assert events[-1].event == "approval_resolved"
        assert events[-1].detail["approved"] is True

    @pytest.mark.asyncio
    async def test_resolve_rejected_fails_run(self, db_session):
        hook = InMemoryApprovalHook()
        svc = RunService(approval_hook=hook)
        run, _ = await _running_run(db_session)
        await svc.request_approval(db_session, run.id, payload={"a": 1})

        resolved = await svc.resolve_approval(
            db_session, run.id, approved=False, actor="admin-1", reason="not allowed"
        )
        assert resolved.status == FAILED
        assert resolved.terminal_at is not None

    @pytest.mark.asyncio
    async def test_no_hook_still_suspends(self, db_session):
        """Direct-API callers may suspend without an external manager."""
        svc = RunService(approval_hook=None)
        run, _ = await _running_run(db_session)
        await svc.request_approval(db_session, run.id, payload={"a": 1})
        await db_session.refresh(run)
        assert run.status == WAITING_APPROVAL


class TestPendingTaskAdapter:
    @pytest.mark.asyncio
    async def test_builds_pending_tasks_shaped_record(self):
        stored = []

        async def store(record: dict) -> str:
            stored.append(record)
            return "task-123"

        hook = PendingTaskApprovalHook(store=store)
        payload = {"risk": "high", "target": "prod"}
        record_id = await hook.suspend("run:abc", payload)

        assert record_id == "task-123"
        assert len(stored) == 1
        rec = stored[0]
        assert rec["task_type"] == "RUN_APPROVAL"
        assert rec["status"] == "PENDING"
        assert rec["target_resource"] == "run:abc"
        assert rec["payload"] == payload
        # AUD-4.4 discipline: canonical SHA-256 over sorted JSON
        assert rec["payload_hash"] == _payload_hash(payload)
        assert len(rec["payload_hash"]) == 64

    def test_payload_hash_is_deterministic_and_order_insensitive(self):
        a = _payload_hash({"x": 1, "y": 2})
        b = _payload_hash({"y": 2, "x": 1})
        assert a == b
