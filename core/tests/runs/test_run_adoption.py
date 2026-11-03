"""M06 P-A — observe_run + ৮/৮ RunType adoption চুক্তি-টেস্ট।

বাংলা: সব সাইটের (tool/mcp/mission/browser/code) রান-পর্যবেক্ষণ একই চুক্তি
মানে — flag-off = byte-নিরপেক্ষ no-op, session-অনুপস্থিতি = লাউড + আয়োজক
অপ্রভাবিত, আয়োজক-ব্যতিক্রম = রান FAILED হয়ে ব্যতিক্রম আয়োজকের কাছেই যায়।
pipeline RunType-এর প্রোডাকশন-নির্বাহ পথ এখনো নেই — মৃত-কোডের জাল পর্যবেক্ষণ
নিষিদ্ধ (False-Assurance), তাই সেখানে লেখক নেই — এই অনুপস্থিতিই সৎ-দলিল।
"""

from __future__ import annotations

from typing import Any

import pytest

import database.session as db_session
from runs.run_scope import observe_run


class FakeService:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, Any]] = []
        self.fail = fail

    async def create_run(self, session, **kwargs):
        if self.fail:
            raise RuntimeError("runs table unavailable")
        self.calls.append(("create", kwargs))
        return type("Run", (), {"id": "run-1"})

    async def transition(self, session, run_id, state, actor="", detail=None):
        if self.fail:
            raise RuntimeError("transition unavailable")
        self.calls.append(("transition", run_id, state))


class FakeSession:
    async def commit(self) -> None:
        return None


class FakeSessionCM:
    def __init__(self, session: FakeSession | None = None):
        self.session = session or FakeSession()
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.session

    async def __aexit__(self, *exc: Any) -> bool:
        self.exited = True
        return False


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", raising=False)


# ---------------------------------------------------------------------------
# observe_run চুক্তি
# ---------------------------------------------------------------------------


async def test_observe_run_flag_off_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom():
        raise AssertionError("flag-off-এ DB স্পর্শ নিষিদ্ধ")

    monkeypatch.setattr(db_session, "get_db_session_context", lambda: _boom())

    async with observe_run(run_type="tool", title="t") as ctx:
        assert ctx is None


async def test_observe_run_session_unavailable_loud_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail():
        raise RuntimeError("no database")

    monkeypatch.setattr(db_session, "get_db_session_context", _fail)

    # বাংলা: আয়োজকের ফল অক্ষত — রান-ফ্যাব্রিক ব্যর্থতা কখনো আয়োজককে ব্লক করে না।
    async with observe_run(run_type="mcp", title="m") as ctx:
        assert ctx is None


async def test_observe_run_happy_path_full_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeService()
    cm = FakeSessionCM()

    monkeypatch.setenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", "true")
    monkeypatch.setattr(db_session, "get_db_session_context", lambda: cm)
    monkeypatch.setattr("runs.service.RunService", lambda: service)

    async with observe_run(
        run_type="tool", user_id="u1", title="tool:web", source_ref="web"
    ) as ctx:
        assert ctx is not None
        assert ctx.run_id == "run-1"

    kinds = [c[0] for c in service.calls]
    assert kinds[0] == "create"
    assert service.calls[0][1]["run_type"] == "tool"
    assert service.calls[0][1]["user_id"] == "u1"
    # বাংলা: ধাপে ধাপে লাইফসাইকেল + terminal settle — কোনো skip-ahead নয়।
    assert kinds[-1] == "transition"
    assert cm.exited is True


async def test_observe_run_host_exception_propagates_and_settles_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeService()
    cm = FakeSessionCM()

    monkeypatch.setenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", "true")
    monkeypatch.setattr(db_session, "get_db_session_context", lambda: cm)
    monkeypatch.setattr("runs.service.RunService", lambda: service)

    with pytest.raises(RuntimeError, match="host broke"):
        async with observe_run(run_type="code", title="c") as ctx:
            assert ctx is not None
            raise RuntimeError("host broke")

    # বাংলা: সত্য প্রতিফলন — আয়োজক-ব্যর্থতা রান-ও FAILED করে, আর ব্যতিক্রম
    # কখনো গিলে ফেলা হয় না।
    assert service.calls[-1][0] == "transition"
    assert cm.exited is True


# ---------------------------------------------------------------------------
# সাইট-স্তরের সংযোগ চুক্তি (flag-off = আজকের আচরণ)
# ---------------------------------------------------------------------------


async def test_tool_loop_flag_off_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.tool_loop import execute_tool_decision

    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    result = await execute_tool_decision({"tool": "anything", "args": {}})
    # বাংলা: gate-refusal পথ অক্ষত — রান-ফ্যাব্রিক স্পর্শ ছাড়াই স্পষ্ট কারণ।
    assert result["executed"] is False
    assert result["status"] == "disabled"


async def test_mcp_call_tool_disconnect_propagates_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.mcp_client import ControlTowerClient

    monkeypatch.delenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", raising=False)
    client = ControlTowerClient(use_sse=False)
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.call_tool("health.sweep", {})
