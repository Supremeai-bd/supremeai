"""M1-C — evidence bridges: missions + tool + MCP + automation as Runs.

Roadmap M1 exit criteria: "missions + one tool path + one MCP path
observable as Runs in a test DB." This suite IS that exit evidence.

Doctrine checks (no duplicate subsystem):
- mission run carries the mission_id extend-anchor FK;
- tool / MCP runs carry source_type + source_ref bridging back to the
  invocation without owning its behavior;
- automation runs carry trace/correlation hand-off while the automation row
  stays authoritative;
- all bridges funnel through RunService (idempotency + lifecycle + audit
  stream enforced at ONE boundary).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from missions.models import Mission, MissionTraceEvent
from models.base import Base
from runs.bridges import (
    observe_automation_run,
    observe_mcp_run,
    observe_mission_run,
    observe_task_run,
    observe_tool_run,
)
from runs.models import Run, RunEvent
from runs.service import RunService


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
                tables=[
                    Mission.__table__,
                    MissionTraceEvent.__table__,
                    Run.__table__,
                    RunEvent.__table__,
                ],
            )
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


class TestMissionBridge:
    @pytest.mark.asyncio
    async def test_mission_execution_observable_as_run(self, db_session):
        """THE exit-criteria path: a mission's execution IS a run."""
        mission = Mission(title="Deploy", goal_text="ship it", owner_id="user-1")
        db_session.add(mission)
        await db_session.flush()

        svc = RunService()
        run = await observe_mission_run(
            db_session,
            svc,
            mission_id=mission.id,
            user_id="user-1",
            title="Deploy execution",
            idempotency_key=f"mission:{mission.id}:exec-1",
        )
        assert run.run_type == "mission"
        assert run.mission_id == mission.id  # extend-anchor FK
        assert run.source_type == "mission"
        assert run.source_ref == str(mission.id)

        # The run lifecycle observes the mission's execution.
        from runs.state_machine import RUNNING, SUCCEEDED

        await svc.transition(db_session, run.id, "policy_checked")
        await svc.transition(db_session, run.id, "planned")
        await svc.transition(db_session, run.id, RUNNING)
        await svc.transition(db_session, run.id, SUCCEEDED)
        await db_session.refresh(run)
        assert run.status == SUCCEEDED

    @pytest.mark.asyncio
    async def test_mission_run_idempotent_per_execution(self, db_session):
        mission = Mission(title="M", goal_text="g", owner_id="user-1")
        db_session.add(mission)
        await db_session.flush()
        svc = RunService()
        key = f"mission:{mission.id}:exec-1"
        r1 = await observe_mission_run(
            db_session, svc, mission_id=mission.id, user_id="user-1", idempotency_key=key
        )
        r2 = await observe_mission_run(
            db_session, svc, mission_id=mission.id, user_id="user-1", idempotency_key=key
        )
        assert r1.id == r2.id


class TestToolBridge:
    @pytest.mark.asyncio
    async def test_tool_path_observable_as_run(self, db_session):
        """THE exit-criteria path: one tool invocation observed as a run."""
        svc = RunService()
        call_id = f"call-{uuid.uuid4().hex[:8]}"
        run = await observe_tool_run(
            db_session,
            svc,
            user_id="user-1",
            tool_name="web_search",
            tool_call_ref=call_id,
            chat_id="chat-9",
            workspace_id="ws-1",
        )
        assert run.run_type == "tool"
        assert run.title == "tool:web_search"
        assert run.source_type == "tool"
        assert run.source_ref == call_id
        assert run.chat_id == "chat-9"

        # tool executes -> usage lands on the run (budget enforcement active)
        from runs.state_machine import POLICY_CHECKED, RUNNING

        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, "planned")
        await svc.transition(db_session, run.id, RUNNING)
        updated = await svc.record_usage(db_session, run.id, tool_calls=1, tokens=120)
        assert updated.tool_calls_used == 1
        assert updated.tokens_used == 120

    @pytest.mark.asyncio
    async def test_tool_run_budget_refuses_overspend(self, db_session):
        svc = RunService()
        run = await observe_tool_run(
            db_session,
            svc,
            user_id="user-1",
            tool_name="expensive_tool",
            max_tool_calls=1,
        )
        from runs.state_machine import POLICY_CHECKED, RUNNING

        await svc.transition(db_session, run.id, POLICY_CHECKED)
        await svc.transition(db_session, run.id, "planned")
        await svc.transition(db_session, run.id, RUNNING)
        await svc.record_usage(db_session, run.id, tool_calls=1)  # 1/1 OK
        refused = await svc.record_usage(db_session, run.id, tool_calls=1)  # 2/1 refused
        assert refused.tool_calls_used == 1


class TestMCPBridge:
    @pytest.mark.asyncio
    async def test_mcp_path_observable_as_run(self, db_session):
        """THE exit-criteria path: one MCP invocation observed as a run."""
        svc = RunService()
        run = await observe_mcp_run(
            db_session,
            svc,
            user_id="user-1",
            server="github-mcp",
            tool="create_issue",
            invocation_ref="inv-777",
        )
        assert run.run_type == "mcp"
        assert run.title == "mcp:github-mcp/create_issue"
        assert run.source_type == "mcp"
        assert run.source_ref == "inv-777"

        # full lifecycle to terminal — run survives as the audit record
        from runs.state_machine import FAILED, FINALIZED

        await svc.transition(db_session, run.id, "policy_checked")
        await svc.transition(db_session, run.id, "planned")
        await svc.transition(db_session, run.id, "running")
        await svc.transition(db_session, run.id, FAILED)
        await svc.finalize(db_session, run.id)
        await db_session.refresh(run)
        assert run.status == FINALIZED

    @pytest.mark.asyncio
    async def test_mcp_run_failure_classification(self, db_session):
        svc = RunService()
        run = await observe_mcp_run(
            db_session, svc, user_id="user-1", server="slack-mcp", tool="post"
        )
        await svc.transition(db_session, run.id, "policy_checked")
        await svc.transition(db_session, run.id, "planned")
        await svc.transition(db_session, run.id, "running")
        await svc.classify_failure(db_session, run.id, "rate_limited", error="429")
        await db_session.refresh(run)
        assert run.retry_class == "rate_limited"


class TestAutomationBridge:
    @pytest.mark.asyncio
    async def test_automation_dispatch_observable_as_run(self, db_session):
        svc = RunService()
        exec_id = str(uuid.uuid4())
        run = await observe_automation_run(
            db_session,
            svc,
            user_id="user-1",
            execution_id=exec_id,
            workflow_key="daily-digest",
            provider="resend",
            trace_id="trace-42",
            correlation_id="corr-42",
        )
        assert run.run_type == "automation"
        assert run.title == "automation:daily-digest@resend"
        assert run.source_type == "automation"
        assert run.source_ref == exec_id
        assert run.trace_id == "trace-42"
        assert run.correlation_id == "corr-42"

    @pytest.mark.asyncio
    async def test_automation_run_idempotent_on_execution_id(self, db_session):
        svc = RunService()
        exec_id = str(uuid.uuid4())
        key = f"automation:{exec_id}"
        r1 = await observe_automation_run(
            db_session, svc, user_id="user-1", execution_id=exec_id, idempotency_key=key
        )
        r2 = await observe_automation_run(
            db_session, svc, user_id="user-1", execution_id=exec_id, idempotency_key=key
        )
        assert r1.id == r2.id


class TestUnifiedView:
    @pytest.mark.asyncio
    async def test_all_subsystems_queryable_in_one_run_table(self, db_session):
        """The 'one execution contract' query: every subsystem in runs."""
        mission = Mission(title="M", goal_text="g", owner_id="user-1")
        db_session.add(mission)
        await db_session.flush()
        svc = RunService()
        await observe_mission_run(db_session, svc, mission_id=mission.id, user_id="user-1")
        await observe_tool_run(db_session, svc, user_id="user-1", tool_name="search")
        await observe_mcp_run(db_session, svc, user_id="user-1", server="gh", tool="issues")
        await observe_automation_run(
            db_session, svc, user_id="user-1", execution_id=str(uuid.uuid4())
        )

        types = (
            (await db_session.execute(select(Run.run_type).order_by(Run.run_type))).scalars().all()
        )
        assert types == ["automation", "mcp", "mission", "tool"]


class TestTaskBridgeM02PB:
    """M02 P-B (ERR-F01): scheduled-task execution observed as a canonical run.

    বাংলা: sweep-এর প্রকৃত নির্বাহ এখন Run fabric-এ দেখা যায় — M05/M06/M17-এর
    run-তথ্য-খোঁজার প্রবেশদ্বার।
    """

    @pytest.mark.asyncio
    async def test_task_run_carries_scheduled_task_anchor(self, db_session):
        task_id = str(uuid.uuid4())
        run = await observe_task_run(
            db_session,
            RunService(),
            task_id=task_id,
            user_id="user-9",
            title="Scheduled task: nightly report",
            idempotency_key=f"scheduled-task:{task_id}:2026-09-18T00:00:00+00:00",
        )
        assert run.run_type == "agent"
        assert run.source_type == "scheduled_task"
        assert run.source_ref == task_id
        assert run.status == "requested"

    @pytest.mark.asyncio
    async def test_task_run_idempotent_per_attempt_key(self, db_session):
        task_id = str(uuid.uuid4())
        key = f"scheduled-task:{task_id}:t1"
        r1 = await observe_task_run(
            db_session, RunService(), task_id=task_id, user_id="u", idempotency_key=key
        )
        r2 = await observe_task_run(
            db_session, RunService(), task_id=task_id, user_id="u", idempotency_key=key
        )
        assert r1.id == r2.id
