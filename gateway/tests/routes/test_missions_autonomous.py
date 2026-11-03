"""#1829 — autonomous mission execution tests.

বাংলা: অনুমোদিত mission আর কখনো RUNNING-এ আটকে থাকবে না — start করলেই
LLM-gateway executor-এ goal চলে, completion callback প্রতিটি phase advance
করে; ব্যর্থ হলে সত্যিকারের reason সহ FAILED। Assigner label সত্যিকারের
routing decision প্রতিফলিত করে।
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class FakeMission:
    def __init__(
        self, mission_id: str = "m-1", phases: int = 3, goal: str = "Build the thing"
    ) -> None:
        self.id = mission_id
        self.goal_text = goal
        self.created_by = "user-1"
        self.phases = [{"name": f"p{i}", "status": "pending"} for i in range(phases)]
        self.state = "RUNNING"


class FakeSessionCtx:
    """Async context manager yielding a fake session (get_db_session_context shape)."""

    def __init__(self, missions: dict[str, FakeMission]) -> None:
        self._missions = missions

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_mission(self, _session, mission_id):
        return self._missions[mission_id]


class FakeService:
    def __init__(self, missions: dict[str, FakeMission]) -> None:
        self._missions = missions
        self.advanced: list[str] = []
        self.failed: list[tuple[str, str]] = []

    async def get_mission(self, _session, mission_id):
        return self._missions[mission_id]

    async def advance_phase(self, _session, mission_id, *, actor=None):
        self.advanced.append((mission_id, actor))
        mission = self._missions[mission_id]
        for phase in mission.phases:
            if phase["status"] != "completed":
                phase["status"] = "completed"
                break
        return mission

    async def fail(self, _session, mission_id, reason, *, actor=None):
        self.failed.append((mission_id, reason))
        self._missions[mission_id].state = "FAILED"
        return self._missions[mission_id]


@pytest.fixture()
def wired(monkeypatch):
    """Import the route module with the db session context faked out."""
    import asyncio

    missions = {"m-1": FakeMission()}
    service = FakeService(missions)
    ctx = FakeSessionCtx(missions)

    import api.routes.missions as mmod

    monkeypatch.setattr(mmod, "mission_service", service)
    monkeypatch.setattr(mmod, "get_db_session_context", lambda: ctx)
    fake_exec = AsyncMock(return_value="llm says done")
    monkeypatch.setattr("api.routes.scheduled_tasks._execute_task_prompt", fake_exec)
    return mmod, service, fake_exec, missions


class TestAutonomousExecution:
    @pytest.mark.asyncio
    async def test_goal_executes_and_all_phases_advance(self, wired):
        mmod, service, fake_exec, _missions = wired
        await mmod._execute_mission_goal("m-1")
        fake_exec.assert_awaited_once()
        # 3 phases → 3 advances (the last lands SUCCEEDED via the state machine)
        assert len(service.advanced) == 3
        assert all(actor == "auto-executor" for _m, actor in service.advanced)
        assert not service.failed

    @pytest.mark.asyncio
    async def test_execution_failure_records_failed_state(self, wired):
        mmod, service, fake_exec, _missions = wired
        fake_exec.side_effect = RuntimeError("gateway down")
        await mmod._execute_mission_goal("m-1")
        assert service.failed and service.failed[0][1] == "gateway down"

    @pytest.mark.asyncio
    async def test_empty_goal_fails_without_llm_call(self, wired):
        mmod, service, fake_exec, missions = wired
        missions["m-1"].goal_text = "   "
        await mmod._execute_mission_goal("m-1")
        fake_exec.assert_not_awaited()
        assert service.failed and "empty goal_text" in service.failed[0][1]


class TestAssignerRouting:
    def test_assigner_label_reflects_real_executor_lane(self, wired):
        mmod, _service, _fake_exec, _missions = wired
        label = mmod._llm_assigner(FakeMission())
        assert label == mmod.EXECUTOR_LANE_LABEL
        assert label != "auto-agent-v1", "the fake stub label must be retired"

    def test_default_service_uses_llm_assigner(self, wired):
        mmod, _service, _fake_exec, _missions = wired
        source = __import__("pathlib").Path(mmod.__file__).read_text(encoding="utf-8")
        assert "MissionService(assigner=_llm_assigner)" in source

    def test_start_route_spawns_executor(self, wired):
        source = wired[0].__file__ and __import__("pathlib").Path(wired[0].__file__).read_text(
            encoding="utf-8"
        )  # noqa: SIM115
        assert "asyncio.create_task(_execute_mission_goal" in source, (
            "start endpoints must enqueue the autonomous executor"
        )
