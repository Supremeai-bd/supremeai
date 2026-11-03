"""M06 P-A â€” run_scope + remediation-run_type hygiene tests.

à¦¬à¦¾à¦‚à¦²à¦¾: flag-gated universal run à¦¤à§ˆà¦°à¦¿à¦° à¦šà§à¦•à§à¦¤à¦¿ â€” à¦«à§à¦²à§à¦¯à¦¾à¦—-à¦…à¦«à§‡ byte-à¦¨à¦¿à¦°à¦ªà§‡à¦•à§à¦·
no-op, à¦«à§à¦²à§à¦¯à¦¾à¦—-à¦…à¦¨à§‡ à¦¸à¦®à§à¦ªà§‚à¦°à§à¦£ à¦²à¦¾à¦‡à¦«à¦¸à¦¾à¦‡à¦•à§‡à¦² (REQUESTEDâ†’â€¦â†’RUNNINGâ†’terminal),
run-fabric à¦¬à§à¦¯à¦°à§à¦¥à¦¤à¦¾ à¦†à¦¯à¦¼à§‹à¦œà¦•-à¦¨à¦¿à¦°à§à¦¬à¦¾à¦¹ à¦•à¦–à¦¨à§‹ à¦¬à§à¦²à¦• à¦•à¦°à§‡ à¦¨à¦¾, à¦†à¦° à¦…à¦¬à§ˆà¦§
``"remediation"`` RunType à¦®à¦¾à¦¨à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡ (federation_bridge à¦°à¦¿à¦®à§à¦¯à¦¾à¦ª)à¥¤
"""

from __future__ import annotations

from typing import Any

import pytest

from core.runs.run_scope import RunContext, run_fabric_universal, run_scope


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


class _Result:
    def __init__(self, status: str = "completed"):
        self.status = status


class FakeSession:
    async def commit(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", raising=False)


# ---------------------------------------------------------------------------
# Flag gate
# ---------------------------------------------------------------------------


def test_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_fabric_universal() is False


@pytest.mark.parametrize("raw", ["false", "0", "yes", "garbage", ""])
def test_flag_strict_true_only(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", raw)
    assert run_fabric_universal() is False


async def test_flag_off_yields_none_and_never_touches_db() -> None:
    service = FakeService()
    touched = []

    async with run_scope(object(), service, run_type="agent", user_id="u1") as ctx:
        touched.append(ctx)
    assert touched == [None]
    assert service.calls == []


# ---------------------------------------------------------------------------
# Flag ON â€” full lifecycle
# ---------------------------------------------------------------------------


async def test_flag_on_walks_lifecycle_and_settles_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", "true")
    service = FakeService()
    async with run_scope(FakeSession(), service, run_type="agent", user_id="u1") as ctx:
        assert isinstance(ctx, RunContext)
        assert ctx.run_id == "run-1"
    states = [c[2] for c in service.calls if c[0] == "transition"]
    assert states == ["policy_checked", "planned", "running", "succeeded"]


async def test_finish_failed_maps_to_failed_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", "true")
    service = FakeService()
    async with run_scope(FakeSession(), service, run_type="agent", user_id="u1") as ctx:
        ctx.finish("failed")
    states = [c[2] for c in service.calls if c[0] == "transition"]
    assert states[-1] == "failed"


async def test_host_exception_settles_failed_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPREMEAI_RUN_FABRIC_UNIVERSAL", "true")
    service = FakeService()
    with pytest.raises(RuntimeError, match="boom"):
        async with run_scope(FakeSession(), service, run_type="agent", user_id="u1"):
            raise RuntimeError("boom")
    states = [c[2] for c in service.calls if c[0] == "transition"]
    assert states[-1] == "failed"


async def test_run_fabric_failure_never_blocks_host() -> None:
    service = FakeService(fail=True)
    executed = []

    async with run_scope(object(), service, run_type="agent", user_id="u1") as ctx:
        assert ctx is None  # à¦ªà¦°à§à¦¯à¦¬à§‡à¦•à§à¦·à¦£-à¦…à¦¨à§à¦ªà¦¸à§à¦¥à¦¿à¦¤à¦¿ à¦¸à§Žà¦­à¦¾à¦¬à§‡ à¦œà¦¾à¦¨à¦¾à¦¨à§‹ à¦¹à¦²
        executed.append("dispatch-ran")
    assert executed == ["dispatch-ran"]


# ---------------------------------------------------------------------------
# federation_bridge hygiene â€” "remediation" à¦›à¦¿à¦² à¦…à¦¬à§ˆà¦§ RunType
# ---------------------------------------------------------------------------


async def test_observe_remediation_run_uses_valid_runtype() -> None:
    from backend.ecosystem.federation_bridge import observe_remediation_run

    class FakeRunService:
        def __init__(self):
            self.calls = []

        async def create_run(self, session, **kwargs):
            self.calls.append(kwargs)
            return kwargs

    service = FakeRunService()
    result = await observe_remediation_run(
        object(), service, user_id="u1", fix_id="fix-9", tenant_id="tenant-9", impact_score=0.1
    )
    assert result["run_type"] in {
        "mission",
        "agent",
        "tool",
        "mcp",
        "browser",
        "code",
        "automation",
        "pipeline",
    }
    assert result["run_type"] == "agent"
    assert result["source_type"] == "self_healing"
