"""M1-B — Run service tests (lifecycle + budgets + retry + cancellation).

Dedicated sqlite+aiosqlite in-memory engine (missions-test pattern; the
root conftest's autouse cleanup fixture requires a parseable DATABASE_URL
in the environment but the runs tables live on THIS engine).

Covers the roadmap M1 service contract:
- creation: defaults, run_type validation, idempotency (same key returns
  the SAME run, no double-create), mission/parent anchoring;
- transitions: happy path stamps started_at/terminal_at/finalized_at,
  event detail records from/to, illegal transition mutates nothing;
- budgets: admission control refuses overspend (counters untouched,
  budget_exceeded event recorded), check_run_budgets reports violations;
- retry: classify_failure validates the 8-class enum, request_retry
  consumes budget, exhausted budget raises IllegalTransition;
- cancellation: legal from every cancellable state, terminal race keeps
  first outcome and records cancel_ignored;
- audit events: complete ordered stream for a full lifecycle.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from missions.models import Mission  # noqa: F401 — registers missions table
from models.base import Base
from runs.budgets import BudgetDimension
from runs.models import Run, RunEvent
from runs.retry import RetryClass
from runs.service import RunNotFound, RunService
from runs.state_machine import (
    BLOCKED,
    CANCELLED,
    FAILED,
    FINALIZED,
    PLANNED,
    POLICY_CHECKED,
    REQUESTED,
    RETRYING,
    RUNNING,
    SUCCEEDED,
    IllegalTransition,
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


@pytest.fixture
def svc() -> RunService:
    return RunService()


async def _mk_run(session, svc: RunService, **overrides) -> Run:
    defaults: dict = {"run_type": "tool", "user_id": "u1"}
    defaults.update(overrides)
    return await svc.create_run(session, **defaults)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestCreation:
    @pytest.mark.asyncio
    async def test_create_defaults_and_event(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        assert run.status == REQUESTED
        assert run.artifacts == []
        events = (
            (await db_session.execute(select(RunEvent).where(RunEvent.run_id == run.id)))
            .scalars()
            .all()
        )
        assert [e.event for e in events] == ["run_created"]

    @pytest.mark.asyncio
    async def test_invalid_run_type_rejected(self, db_session, svc):
        with pytest.raises(ValueError, match="invalid run_type"):
            await _mk_run(db_session, svc, run_type="teleport")

    @pytest.mark.asyncio
    async def test_idempotency_returns_same_run(self, db_session, svc):
        r1 = await _mk_run(db_session, svc, idempotency_key="op-42")
        r2 = await _mk_run(db_session, svc, idempotency_key="op-42")
        assert r1.id == r2.id
        rows = (
            (await db_session.execute(select(Run).where(Run.idempotency_key == "op-42")))
            .scalars()
            .all()
        )
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_mission_and_parent_anchor(self, db_session, svc):
        mission = Mission(title="M", goal_text="g", owner_id="u1")
        db_session.add(mission)
        await db_session.flush()
        parent = await _mk_run(db_session, svc, run_type="mission")
        child = await _mk_run(
            db_session,
            svc,
            run_type="tool",
            mission_id=mission.id,
            parent_run_id=parent.id,
        )
        assert child.mission_id == mission.id
        assert child.parent_run_id == parent.id

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, db_session, svc):
        with pytest.raises(RunNotFound):
            await svc.get_run(db_session, uuid.uuid4())
        with pytest.raises(RunNotFound):
            await svc.get_run(db_session, "not-a-uuid")


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


class TestTransitions:
    @pytest.mark.asyncio
    async def test_full_lifecycle_stamps_timestamps(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await db_session.refresh(run)
        assert run.started_at is not None
        started = run.started_at

        await svc.transition(db_session, run.id, SUCCEEDED)
        await db_session.refresh(run)
        assert run.terminal_at is not None

        await svc.finalize(db_session, run.id)
        await db_session.refresh(run)
        assert run.status == FINALIZED
        assert run.finalized_at is not None
        assert run.started_at == started  # not restamped

    @pytest.mark.asyncio
    async def test_event_detail_records_from_and_to(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        await svc.transition(db_session, run.id, POLICY_CHECKED, actor="policy-engine")
        row = (
            (
                await db_session.execute(
                    select(RunEvent).where(
                        RunEvent.run_id == run.id, RunEvent.event == "status_transition"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.detail["from"] == REQUESTED
        assert row.detail["to"] == POLICY_CHECKED
        assert row.detail["actor"] == "policy-engine"

    @pytest.mark.asyncio
    async def test_illegal_transition_never_mutates(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        with pytest.raises(IllegalTransition):
            await svc.transition(db_session, run.id, PLANNED)  # skips policy check
        await db_session.refresh(run)
        assert run.status == REQUESTED

    @pytest.mark.asyncio
    async def test_finalized_event_kind(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.transition(db_session, run.id, SUCCEEDED)
        await svc.finalize(db_session, run.id, actor="reaper")
        row = (
            (
                await db_session.execute(
                    select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.event == "finalized")
                )
            )
            .scalars()
            .one()
        )
        assert row.detail["actor"] == "reaper"


# ---------------------------------------------------------------------------
# Budget enforcement through the service
# ---------------------------------------------------------------------------


class TestServiceBudgets:
    @pytest.mark.asyncio
    async def test_record_usage_within_budget(self, db_session, svc):
        run = await _mk_run(db_session, svc, max_tokens=100)
        await svc.record_usage(db_session, run.id, tokens=40)
        await db_session.refresh(run)
        assert run.tokens_used == 40

    @pytest.mark.asyncio
    async def test_record_usage_overspend_refused(self, db_session, svc):
        run = await _mk_run(db_session, svc, max_tokens=50)
        await svc.record_usage(db_session, run.id, tokens=40)
        refused = await svc.record_usage(db_session, run.id, tokens=40)  # 80 > 50
        await db_session.refresh(refused)
        assert refused.tokens_used == 40  # second increment did NOT land
        events = (
            (await db_session.execute(select(RunEvent).where(RunEvent.run_id == run.id)))
            .scalars()
            .all()
        )
        assert [e.event for e in events] == [
            "run_created",
            "usage_recorded",
            "budget_exceeded",
        ]
        assert events[-1].detail["violations"] == ["tokens"]

    @pytest.mark.asyncio
    async def test_check_run_budgets_records_violation(self, db_session, svc):
        run = await _mk_run(db_session, svc, max_tool_calls=0, max_wall_clock_ms=1_000)
        # Simulate historical consumption + elapsed wall-clock directly on the
        # row (record_usage would refuse overspend by design).
        from datetime import UTC, datetime, timedelta

        run.tool_calls_used = 1
        run.started_at = datetime.now(UTC) - timedelta(seconds=10)
        await db_session.flush()
        snap = await svc.check_run_budgets(db_session, run.id)
        assert not check_ok(snap)
        row = (
            (
                await db_session.execute(
                    select(RunEvent).where(
                        RunEvent.run_id == run.id, RunEvent.event == "budget_exceeded"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert BudgetDimension.wall_clock.value in row.detail["violations"]
        assert BudgetDimension.tool_calls.value in row.detail["violations"]


def check_ok(snapshot) -> bool:
    from runs.budgets import check_budgets

    return check_budgets(snapshot).ok


# ---------------------------------------------------------------------------
# Failure classification + retry
# ---------------------------------------------------------------------------


class TestRetryFlow:
    @pytest.mark.asyncio
    async def test_classify_failure_records_class_and_error(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.classify_failure(
            db_session, run.id, RetryClass.rate_limited, error="429 from provider"
        )
        await db_session.refresh(run)
        assert run.retry_class == "rate_limited"
        assert run.error == "429 from provider"

    @pytest.mark.asyncio
    async def test_classify_failure_validates_enum(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        with pytest.raises(ValueError, match="invalid retry_class"):
            await svc.classify_failure(db_session, run.id, "meteor")

    @pytest.mark.asyncio
    async def test_request_retry_consumes_budget(self, db_session, svc):
        run = await _mk_run(db_session, svc, max_retries=3)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.classify_failure(db_session, run.id, "transient")
        await svc.request_retry(db_session, run.id)
        await db_session.refresh(run)
        assert run.status == RETRYING
        assert run.retries_used == 1

    @pytest.mark.asyncio
    async def test_request_retry_exhausted_budget_raises(self, db_session, svc):
        run = await _mk_run(db_session, svc, max_retries=1)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.classify_failure(db_session, run.id, "transient")
        await svc.request_retry(db_session, run.id)  # 1/1 used
        await svc.transition(db_session, run.id, RUNNING)
        await svc.classify_failure(db_session, run.id, "transient")
        with pytest.raises(IllegalTransition, match="retry budget exhausted"):
            await svc.request_retry(db_session, run.id)

    @pytest.mark.asyncio
    async def test_request_retry_non_retryable_class_raises(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.classify_failure(db_session, run.id, "invalid_input")
        with pytest.raises(IllegalTransition, match="not retryable"):
            await svc.request_retry(db_session, run.id)

    @pytest.mark.asyncio
    async def test_retry_then_fail_then_finalize(self, db_session, svc):
        run = await _mk_run(db_session, svc, max_retries=2)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.classify_failure(db_session, run.id, "dependency_unavailable")
        await svc.request_retry(db_session, run.id)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.transition(db_session, run.id, FAILED)
        await svc.finalize(db_session, run.id)
        await db_session.refresh(run)
        assert run.status == FINALIZED
        assert run.retries_used == 1


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        [
            [POLICY_CHECKED],
            [POLICY_CHECKED, PLANNED],
            [POLICY_CHECKED, PLANNED, RUNNING],
            [POLICY_CHECKED, PLANNED, RUNNING, BLOCKED],
            [POLICY_CHECKED, PLANNED, RUNNING, RETRYING],
        ],
        ids=["requested", "planned", "running", "blocked", "retrying"],
    )
    async def test_cancel_from_cancellable_states(self, db_session, svc, path):
        run = await _mk_run(db_session, svc)
        for nxt in path:
            if nxt == RETRYING:
                await svc.classify_failure(db_session, run.id, "transient")
                await svc.request_retry(db_session, run.id)
            else:
                await svc.transition(db_session, run.id, nxt)
        await svc.cancel(db_session, run.id, actor="user-1", reason="no longer needed")
        await db_session.refresh(run)
        assert run.status == CANCELLED
        assert run.terminal_at is not None

    @pytest.mark.asyncio
    async def test_cancel_finalized_records_cancel_ignored(self, db_session, svc):
        run = await _mk_run(db_session, svc)
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.transition(db_session, run.id, SUCCEEDED)
        await svc.finalize(db_session, run.id)
        await svc.cancel(db_session, run.id, actor="late-user")
        await db_session.refresh(run)
        assert run.status == FINALIZED  # first outcome kept
        events = (
            (await db_session.execute(select(RunEvent).where(RunEvent.run_id == run.id)))
            .scalars()
            .all()
        )
        assert events[-1].event == "cancel_ignored"


# ---------------------------------------------------------------------------
# Audit stream integrity
# ---------------------------------------------------------------------------


class TestAuditStream:
    @pytest.mark.asyncio
    async def test_full_lifecycle_event_sequence_ordered(self, db_session, svc):
        run = await _mk_run(db_session, svc, idempotency_key="audit-1")
        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, PLANNED)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.record_usage(db_session, run.id, tokens=10, tool_calls=1)
        await svc.classify_failure(db_session, run.id, "transient", error="boom")
        await svc.request_retry(db_session, run.id)
        await svc.transition(db_session, run.id, RUNNING)
        await svc.transition(db_session, run.id, SUCCEEDED)
        await svc.finalize(db_session, run.id)

        events = (
            (
                await db_session.execute(
                    select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)
                )
            )
            .scalars()
            .all()
        )
        assert [e.event for e in events] == [
            "run_created",
            "status_transition",  # policy_checked
            "status_transition",  # planned
            "status_transition",  # running
            "usage_recorded",
            "retry_classified",
            "retry_scheduled",
            "status_transition",  # running again
            "status_transition",  # succeeded
            "finalized",
        ]
        assert [e.seq for e in events] == list(range(1, len(events) + 1))
