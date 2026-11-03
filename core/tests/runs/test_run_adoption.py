"""M06 P-A â€” observe_run + à§®/à§® RunType adoption à¦šà§à¦•à§à¦¤à¦¿-à¦Ÿà§‡à¦¸à§à¦Ÿà¥¤

à¦¬à¦¾à¦‚à¦²à¦¾: à¦¸à¦¬ à¦¸à¦¾à¦‡à¦Ÿà§‡à¦° (tool/mcp/mission/browser/code) à¦°à¦¾à¦¨-à¦ªà¦°à§à¦¯à¦¬à§‡à¦•à§à¦·à¦£ à¦à¦•à¦‡ à¦šà§à¦•à§à¦¤à¦¿
à¦®à¦¾à¦¨à§‡ â€” flag-off = byte-à¦¨à¦¿à¦°à¦ªà§‡à¦•à§à¦· no-op, session-à¦…à¦¨à§à¦ªà¦¸à§à¦¥à¦¿à¦¤à¦¿ = à¦²à¦¾à¦‰à¦¡ + à¦†à¦¯à¦¼à§‹à¦œà¦•
à¦…à¦ªà§à¦°à¦­à¦¾à¦¬à¦¿à¦¤, à¦†à¦¯à¦¼à§‹à¦œà¦•-à¦¬à§à¦¯à¦¤à¦¿à¦•à§à¦°à¦® = à¦°à¦¾à¦¨ FAILED à¦¹à¦¯à¦¼à§‡ à¦¬à§à¦¯à¦¤à¦¿à¦•à§à¦°à¦® à¦†à¦¯à¦¼à§‹à¦œà¦•à§‡à¦° à¦•à¦¾à¦›à§‡à¦‡ à¦¯à¦¾à¦¯à¦¼à¥¤
pipeline RunType-à¦à¦° à¦ªà§à¦°à§‹à¦¡à¦¾à¦•à¦¶à¦¨-à¦¨à¦¿à¦°à§à¦¬à¦¾à¦¹ à¦ªà¦¥ à¦à¦–à¦¨à§‹ à¦¨à§‡à¦‡ â€” à¦®à§ƒà¦¤-à¦•à§‹à¦¡à§‡à¦° à¦œà¦¾à¦² à¦ªà¦°à§à¦¯à¦¬à§‡à¦•à§à¦·à¦£
à¦¨à¦¿à¦·à¦¿à¦¦à§à¦§ (False-Assurance), à¦¤à¦¾à¦‡ à¦¸à§‡à¦–à¦¾à¦¨à§‡ à¦²à§‡à¦–à¦• à¦¨à§‡à¦‡ â€” à¦à¦‡ à¦…à¦¨à§à¦ªà¦¸à§à¦¥à¦¿à¦¤à¦¿à¦‡ à¦¸à§Ž-à¦¦à¦²à¦¿à¦²à¥¤
"""

from __future__ import annotations

from typing import Any

import pytest

import database.session as db_session
from core.runs.run_scope import observe_run


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
# observe_run à¦šà§à¦•à§à¦¤à¦¿
# ---------------------------------------------------------------------------


async def test_observe_run_flag_off_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom():
        raise AssertionError("flag-off-à¦ DB à¦¸à§à¦ªà¦°à§à¦¶ à¦¨à¦¿à¦·à¦¿à¦¦à§à¦§")

    monkeypatch.setattr(db_session, "get_db_session_context", lambda: _boom())

    async with observe_run(run_type="tool", title="t") as ctx:
        assert ctx is None


async def test_observe_run_session_unavailable_loud_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail():
        raise RuntimeError("no database")

    monkeypatch.setattr(db_session, "get_db_session_context", _fail)

    # à¦¬à¦¾à¦‚à¦²à¦¾: à¦†à¦¯à¦¼à§‹à¦œà¦•à§‡à¦° à¦«à¦² à¦…à¦•à§à¦·à¦¤ â€” à¦°à¦¾à¦¨-à¦«à§à¦¯à¦¾à¦¬à§à¦°à¦¿à¦• à¦¬à§à¦¯à¦°à§à¦¥à¦¤à¦¾ à¦•à¦–à¦¨à§‹ à¦†à¦¯à¦¼à§‹à¦œà¦•à¦•à§‡ à¦¬à§à¦²à¦• à¦•à¦°à§‡ à¦¨à¦¾à¥¤
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
    # à¦¬à¦¾à¦‚à¦²à¦¾: à¦§à¦¾à¦ªà§‡ à¦§à¦¾à¦ªà§‡ à¦²à¦¾à¦‡à¦«à¦¸à¦¾à¦‡à¦•à§‡à¦² + terminal settle â€” à¦•à§‹à¦¨à§‹ skip-ahead à¦¨à¦¯à¦¼à¥¤
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

    # à¦¬à¦¾à¦‚à¦²à¦¾: à¦¸à¦¤à§à¦¯ à¦ªà§à¦°à¦¤à¦¿à¦«à¦²à¦¨ â€” à¦†à¦¯à¦¼à§‹à¦œà¦•-à¦¬à§à¦¯à¦°à§à¦¥à¦¤à¦¾ à¦°à¦¾à¦¨-à¦“ FAILED à¦•à¦°à§‡, à¦†à¦° à¦¬à§à¦¯à¦¤à¦¿à¦•à§à¦°à¦®
    # à¦•à¦–à¦¨à§‹ à¦—à¦¿à¦²à§‡ à¦«à§‡à¦²à¦¾ à¦¹à¦¯à¦¼ à¦¨à¦¾à¥¤
    assert service.calls[-1][0] == "transition"
    assert cm.exited is True


# ---------------------------------------------------------------------------
# à¦¸à¦¾à¦‡à¦Ÿ-à¦¸à§à¦¤à¦°à§‡à¦° à¦¸à¦‚à¦¯à§‹à¦— à¦šà§à¦•à§à¦¤à¦¿ (flag-off = à¦†à¦œà¦•à§‡à¦° à¦†à¦šà¦°à¦£)
# ---------------------------------------------------------------------------


async def test_tool_loop_flag_off_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.tool_loop import execute_tool_decision

    monkeypatch.delenv("SUPREMEAI_AGENT_TOOLS", raising=False)
    result = await execute_tool_decision({"tool": "anything", "args": {}})
    # à¦¬à¦¾à¦‚à¦²à¦¾: gate-refusal à¦ªà¦¥ à¦…à¦•à§à¦·à¦¤ â€” à¦°à¦¾à¦¨-à¦«à§à¦¯à¦¾à¦¬à§à¦°à¦¿à¦• à¦¸à§à¦ªà¦°à§à¦¶ à¦›à¦¾à¦¡à¦¼à¦¾à¦‡ à¦¸à§à¦ªà¦·à§à¦Ÿ à¦•à¦¾à¦°à¦£à¥¤
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
