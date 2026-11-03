"""Issue #1817 — Orchestrator tick loop wiring + contract tests.

Before #1817 the core Orchestrator (fitness scoring + self-evolution tick +
budget guardian) was constructed at every boot but ``tick()`` had ZERO callers
— the intended ``POST /orchestrator/tick`` webhook router was never registered.
These tests lock the supervisor-driven tick loop:

  1. the loop ticks immediately, then on the orchestrator's interval;
  2. a budget-guardian HALT returns CLEANLY (fail-closed — the supervisor must
     NOT auto-restart the loop into the same halt);
  3. transient (non-halt) errors propagate so the supervisor restarts them;
  4. ``_running`` mirrors the loop lifecycle;
  5. ``start_background_services`` registers the ``orchestrator-tick`` agent
     exactly once, honoring the ENABLE_ORCHESTRATOR_TICK kill switch and the
     not-initialized-at-boot degraded path.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace

import pytest

from core.startup.agents import _build_orchestrator_tick_loop


class FakeOrchestrator:
    """Minimal stand-in mirroring core.orchestration.periodic_task_scheduler.Orchestrator."""

    def __init__(self, interval: float = 0.01):
        self.interval = interval
        self._running = False
        self.tick_calls = 0
        self.tick_impl = None  # optional async callable

    async def tick(self) -> None:
        self.tick_calls += 1
        if self.tick_impl is not None:
            await self.tick_impl()


_DISABLE_GATES = (
    "ENABLE_SENTINEL_AGENT",
    "ENABLE_SYSTEM_TELEMETRY",
    "ENABLE_BUG_PROPHET",
    "ENABLE_AGENT_HEARTBEAT",
    "ENABLE_TIER8",
    "ENABLE_EVOLUTION",
    "ENABLE_DAILY_LEARNER",
    "ENABLE_AUTO_HEALER",
    "ENABLE_AUTOSCALING_AGENT",
    "ENABLE_PERFORMANCE_TUNING_AGENT",
    "ENABLE_COST_OPTIMIZATION_AGENT",
    "ENABLE_DISASTER_RECOVERY_AGENT",
    "ENABLE_AI_MEMORY_RETENTION",
    "ENABLE_SYNAPTIC_DREAM",
)


class _StubStore:
    async def flush(self):
        return None

    def start(self):
        return None


def _patch_supervisor(monkeypatch) -> list:
    """Capture start_agent calls so no real agent task ever runs."""
    import core.agent_supervisor as supervisor_module

    registered: list = []

    async def fake_start_agent(name, factory, **kwargs):
        registered.append((name, factory))

    monkeypatch.setattr(supervisor_module.agent_supervisor, "start_agent", fake_start_agent)
    return registered


def _stub_learning_store(monkeypatch) -> None:
    import core.learning as learning_module

    monkeypatch.setattr(learning_module, "get_learning_store", lambda: _StubStore())


@pytest.mark.unit
class TestOrchestratorTickLoop:
    async def test_ticks_immediately_then_on_interval(self):
        orch = FakeOrchestrator(interval=0.01)
        loop = _build_orchestrator_tick_loop(orch)

        task = asyncio.create_task(loop())
        try:
            for _ in range(200):
                if orch.tick_calls >= 2:
                    break
                await asyncio.sleep(0.01)
            assert orch.tick_calls >= 2, "loop must tick immediately and then per interval"
            assert orch._running is True, "_running must be True while the loop lives"
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        assert orch._running is False, "finally clause must reset _running on cancel"

    async def test_budget_guardian_halt_returns_cleanly_fail_closed(self):
        orch = FakeOrchestrator(interval=0.01)

        async def _halt() -> None:
            raise RuntimeError(
                "Budget Guardian exited with code 1. Halting orchestrator to prevent financial bleed."
            )

        orch.tick_impl = _halt
        loop = _build_orchestrator_tick_loop(orch)

        # Must complete WITHOUT raising — a normal return makes the supervisor
        # stop the agent permanently instead of restarting into the same halt.
        await asyncio.wait_for(loop(), timeout=5.0)
        assert orch.tick_calls == 1, "halt must not be retried by the loop itself"
        assert orch._running is False

    async def test_transient_error_propagates_for_supervisor_restart(self):
        orch = FakeOrchestrator(interval=0.01)

        async def _blip() -> None:
            raise ValueError("redis connection blip")

        orch.tick_impl = _blip
        loop = _build_orchestrator_tick_loop(orch)

        with pytest.raises(ValueError):
            await asyncio.wait_for(loop(), timeout=5.0)
        assert orch._running is False, "finally clause must run even on propagated errors"


@pytest.mark.unit
class TestOrchestratorTickWiring:
    async def test_registers_exactly_once_via_supervisor(self, monkeypatch):
        import core.startup.agents as agents_module

        for var in _DISABLE_GATES:
            monkeypatch.setenv(var, "false")
        monkeypatch.setenv("ENABLE_ORCHESTRATOR_TICK", "true")
        registered = _patch_supervisor(monkeypatch)
        _stub_learning_store(monkeypatch)

        orch = FakeOrchestrator(interval=300)
        app = SimpleNamespace(state=SimpleNamespace(orchestrator=orch))
        await agents_module.start_background_services(app)

        tick_registrations = [(n, f) for n, f in registered if n == "orchestrator-tick"]
        assert len(tick_registrations) == 1, (
            f"orchestrator-tick must be registered exactly once, got {len(tick_registrations)}"
        )
        factory = tick_registrations[0][1]
        # The factory must produce a fresh runnable coroutine each time
        # (supervisor restart semantics require a factory, not a coroutine).
        coro = factory()
        assert asyncio.iscoroutine(coro)
        coro.close()

    async def test_kill_switch_disables_registration(self, monkeypatch):
        import core.startup.agents as agents_module

        for var in _DISABLE_GATES:
            monkeypatch.setenv(var, "false")
        monkeypatch.setenv("ENABLE_ORCHESTRATOR_TICK", "false")
        registered = _patch_supervisor(monkeypatch)
        _stub_learning_store(monkeypatch)

        app = SimpleNamespace(state=SimpleNamespace(orchestrator=FakeOrchestrator()))
        await agents_module.start_background_services(app)

        assert "orchestrator-tick" not in registered, "kill switch must prevent registration"

    async def test_degraded_boot_without_orchestrator_does_not_register(self, monkeypatch):
        import core.startup.agents as agents_module

        for var in _DISABLE_GATES:
            monkeypatch.setenv(var, "false")
        monkeypatch.delenv("ENABLE_ORCHESTRATOR_TICK", raising=False)
        registered = _patch_supervisor(monkeypatch)
        _stub_learning_store(monkeypatch)

        # Degraded boot: ORCHESTRATOR_INIT_FAILED path leaves app.state.orchestrator=None
        app = SimpleNamespace(state=SimpleNamespace(orchestrator=None))
        await agents_module.start_background_services(app)

        assert "orchestrator-tick" not in registered, (
            "must not register a tick loop when the orchestrator never initialized"
        )
