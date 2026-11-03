"""M1-A — canonical Run / RunEvent model tests (offline, sqlite in-memory).

Dedicated sqlite+aiosqlite engine with ONLY the runs tables created (same
pattern as tests/missions — the shared conftest ``db_engine`` runs
``create_all`` over the FULL ``models.base.Base`` metadata which cannot
compile PG-only column types on sqlite; the runs tables are fully
sqlite-compatible via ``JSON().with_variant(JSONB, "postgresql")``).

Covers: defaults, counters, artifacts JSON round-trip, per-run event seq
uniqueness, cascade delete of events, mission anchor + parent-run
self-reference, and state-machine ↔ model integration (status stays a plain
string; the machine validates transitions before the model is updated).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from missions.models import Mission  # noqa: F401 — registers missions table for the FK
from models.base import Base
from runs.models import Run, RunEvent
from runs.state_machine import (
    CANCELLED,
    FINALIZED,
    PLANNED,
    POLICY_CHECKED,
    REQUESTED,
    RUNNING,
    SUCCEEDED,
    assert_transition,
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite skips FK enforcement (incl. ON DELETE CASCADE) unless the
    # pragma is on — the cascade test must exercise the REAL constraint.
    @event.listens_for(engine.sync_engine, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        # missions + runs + run_events only (same pattern as tests/missions:
        # the shared conftest db_engine create_all over the FULL Base
        # metadata cannot compile PG-only types on sqlite). The missions
        # table must exist because runs.mission_id FK references it — and
        # having it lets the anchor test exercise a REAL FK link.
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


def _make_run(**overrides) -> Run:
    defaults: dict = {
        "run_type": "tool",
        "user_id": "user-abc",
    }
    defaults.update(overrides)
    return Run(**defaults)


# ---------------------------------------------------------------------------
# Defaults + columns
# ---------------------------------------------------------------------------


class TestRunModel:
    @pytest.mark.asyncio
    async def test_create_defaults(self, db_session: AsyncSession):
        run = _make_run()
        db_session.add(run)
        await db_session.flush()

        assert run.id is not None and isinstance(run.id, uuid.UUID)
        assert run.status == REQUESTED
        assert run.tokens_used == 0
        assert run.tool_calls_used == 0
        assert run.retries_used == 0
        assert run.artifacts == []
        assert run.error is None
        assert run.retry_class is None
        assert run.requested_at is not None
        assert run.created_at is not None

    @pytest.mark.asyncio
    async def test_artifacts_json_roundtrip(self, db_session: AsyncSession):
        artifacts = [
            {"artifact_id": "a1", "kind": "file", "ref": "ref://run/x/artifact/a1"},
            {"artifact_id": "a2", "kind": "screenshot", "ref": "ref://run/x/artifact/a2"},
        ]
        run = _make_run(artifacts=artifacts)
        db_session.add(run)
        await db_session.flush()
        await db_session.refresh(run)
        assert run.artifacts == artifacts

    @pytest.mark.asyncio
    async def test_budget_columns_persist(self, db_session: AsyncSession):
        run = _make_run(
            max_wall_clock_ms=30_000,
            max_tokens=8_192,
            max_tool_calls=10,
            max_retries=3,
        )
        db_session.add(run)
        await db_session.flush()
        await db_session.refresh(run)
        assert run.max_wall_clock_ms == 30_000
        assert run.max_tokens == 8_192
        assert run.max_tool_calls == 10
        assert run.max_retries == 3

    @pytest.mark.asyncio
    async def test_user_id_required(self, db_session: AsyncSession):
        run = Run(run_type="tool")  # user_id missing
        db_session.add(run)
        with pytest.raises(Exception, match="NOT NULL"):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_scope_anchors_persist(self, db_session: AsyncSession):
        run = _make_run(
            user_id="u1",
            workspace_id="ws-77",
            chat_id="chat-42",
            trace_id="trace-9",
            correlation_id="corr-9",
        )
        db_session.add(run)
        await db_session.flush()
        await db_session.refresh(run)
        assert run.workspace_id == "ws-77"
        assert run.chat_id == "chat-42"
        assert run.trace_id == "trace-9"
        assert run.correlation_id == "corr-9"

    @pytest.mark.asyncio
    async def test_mission_anchor_real_fk(self, db_session: AsyncSession):
        """Run.mission_id is a REAL FK to missions.id (extend-not-replace)."""
        mission = Mission(title="M", goal_text="do the thing", owner_id="user-abc", state="running")
        db_session.add(mission)
        await db_session.flush()
        run = _make_run(run_type="mission", mission_id=mission.id)
        db_session.add(run)
        await db_session.flush()
        await db_session.refresh(run)
        assert run.mission_id == mission.id

    @pytest.mark.asyncio
    async def test_parent_run_self_reference(self, db_session: AsyncSession):
        parent = _make_run(run_type="mission", title="parent")
        db_session.add(parent)
        await db_session.flush()
        child = _make_run(run_type="tool", title="step", parent_run_id=parent.id)
        db_session.add(child)
        await db_session.flush()
        await db_session.refresh(child)
        assert child.parent_run_id == parent.id


# ---------------------------------------------------------------------------
# RunEvent stream
# ---------------------------------------------------------------------------


class TestRunEventModel:
    @pytest.mark.asyncio
    async def test_event_append_and_ordering(self, db_session: AsyncSession):
        run = _make_run()
        db_session.add(run)
        await db_session.flush()
        for seq, kind in enumerate(
            ["run_created", "status_transition", "status_transition"], start=1
        ):
            db_session.add(RunEvent(run_id=run.id, seq=seq, event=kind, detail={"n": seq}))
        await db_session.flush()

        rows = (await db_session.execute(select(RunEvent).order_by(RunEvent.seq))).scalars().all()
        assert [r.event for r in rows] == ["run_created", "status_transition", "status_transition"]

    @pytest.mark.asyncio
    async def test_event_seq_unique_per_run(self, db_session: AsyncSession):
        run = _make_run()
        db_session.add(run)
        await db_session.flush()
        db_session.add(RunEvent(run_id=run.id, seq=1, event="run_created"))
        await db_session.flush()
        db_session.add(RunEvent(run_id=run.id, seq=1, event="duplicate"))
        with pytest.raises(Exception):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_events_cascade_delete_with_run(self, db_session: AsyncSession):
        run = _make_run()
        db_session.add(run)
        await db_session.flush()
        db_session.add(RunEvent(run_id=run.id, seq=1, event="run_created"))
        await db_session.flush()
        await db_session.delete(run)
        await db_session.flush()
        remaining = (await db_session.execute(select(RunEvent))).scalars().all()
        assert remaining == []

    @pytest.mark.asyncio
    async def test_event_detail_json_roundtrip(self, db_session: AsyncSession):
        run = _make_run()
        db_session.add(run)
        await db_session.flush()
        detail = {"from": REQUESTED, "to": POLICY_CHECKED, "actor": "policy-engine"}
        db_session.add(RunEvent(run_id=run.id, seq=1, event="status_transition", detail=detail))
        await db_session.flush()
        row = (await db_session.execute(select(RunEvent))).scalars().one()
        assert row.detail == detail


# ---------------------------------------------------------------------------
# State machine ↔ model integration
# ---------------------------------------------------------------------------


class TestLifecycleIntegration:
    @pytest.mark.asyncio
    async def test_lifecycle_transitions_on_real_row(self, db_session: AsyncSession):
        run = _make_run(run_type="mission", user_id="u2")
        db_session.add(run)
        await db_session.flush()

        path = [
            (POLICY_CHECKED, "status_transition"),
            (PLANNED, "status_transition"),
            (RUNNING, "status_transition"),
            (SUCCEEDED, "status_transition"),
            (FINALIZED, "finalized"),
        ]
        for seq, (nxt, kind) in enumerate(path, start=1):
            assert_transition(run.status, nxt)  # guard before mutation
            run.status = nxt
            db_session.add(RunEvent(run_id=run.id, seq=seq, event=kind, detail={"to": nxt}))
            await db_session.flush()

        assert run.status == FINALIZED
        assert run.finalized_at is None  # service layer (M1-B) stamps this
        events = (await db_session.execute(select(RunEvent).order_by(RunEvent.seq))).scalars().all()
        assert len(events) == 5
        assert events[-1].event == "finalized"

    @pytest.mark.asyncio
    async def test_illegal_transition_never_touches_row(self, db_session: AsyncSession):
        from runs.state_machine import IllegalTransition

        run = _make_run()
        db_session.add(run)
        await db_session.flush()
        with pytest.raises(IllegalTransition):
            assert_transition(run.status, SUCCEEDED)
        await db_session.refresh(run)
        assert run.status == REQUESTED

    @pytest.mark.asyncio
    async def test_cancelled_run_records_event(self, db_session: AsyncSession):
        run = _make_run()
        db_session.add(run)
        await db_session.flush()
        assert_transition(run.status, CANCELLED)
        run.status = CANCELLED
        db_session.add(RunEvent(run_id=run.id, seq=1, event="cancelled", detail={"actor": "user"}))
        await db_session.flush()
        await db_session.refresh(run)
        assert run.status == CANCELLED
