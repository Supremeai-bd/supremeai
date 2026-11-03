"""GovernanceCore tests — the Global Governance Core of the FCC."""

import asyncio
import unittest

from core.circles.bootstrap import (  # Issue #2476: singleton moved to composition root
    build_federation,
    get_governance_core,
    reset_governance_core,
)
from core.circles.centers.base import CircleCenter, LocalCapability
from core.circles.contracts import (
    CircleName,
    ExecutionStatus,
    PolicyDecision,
    RiskLevel,
)
from core.circles.envelopes import (
    ExecutionEnvelope,
    result_envelope_from_execution,
)
from core.circles.event_journal import CircleEventJournal
from core.circles.governance_core import GovernanceCore


def _envelope(**overrides) -> ExecutionEnvelope:
    values = dict(
        circle=CircleName.LLM,
        capability="test.ping",
        tenant_id="tenant-1",
        actor_id="user-1",
        payload={},
        deadline_ms=30_000,
    )
    values.update(overrides)
    return ExecutionEnvelope(**values)


class _PingCenter(CircleCenter):
    circle = CircleName.LLM
    display_name = "Ping"
    owner = "tests"

    def __init__(self) -> None:
        super().__init__()
        self.register(
            LocalCapability(name="test.ping", risk_level=RiskLevel.LOW),
            lambda request: {"pong": True},
        )
        self.register(
            LocalCapability(name="test.risky", approval_required=True, risk_level=RiskLevel.HIGH),
            lambda request: {"never": True},
        )
        self.register(
            LocalCapability(name="test.slow", timeout_ms=60_000, risk_level=RiskLevel.LOW),
            lambda request: _slow(),
        )


def _slow() -> str:
    import time

    time.sleep(0.4)
    return "late"


class GovernanceCoreTests(unittest.TestCase):
    def _core(self, **kwargs) -> tuple[GovernanceCore, CircleEventJournal]:
        journal = CircleEventJournal(max_events=64)
        core = GovernanceCore(journal=journal, **kwargs)
        core.register_center(_PingCenter())
        return core, journal

    def test_route_success_fans_out_to_journal_and_subscribers(self) -> None:
        core, journal = self._core()
        seen: list[str] = []
        core.subscribe(lambda event: seen.append(event.event_type))
        result = asyncio.run(core.route(_envelope()))
        self.assertEqual(result.status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(result.data, {"pong": True})
        self.assertEqual(len(journal.replay(tenant_id="tenant-1")), 1)
        self.assertIn("execution.succeeded", seen)

    def test_unknown_circle_is_unavailable(self) -> None:
        core, _ = self._core()
        result = asyncio.run(core.route(_envelope(circle=CircleName.MCP)))
        self.assertEqual(result.status, ExecutionStatus.UNAVAILABLE)
        assert result.error is not None
        self.assertEqual(result.error.code, "unknown_circle")

    def test_unknown_capability_is_unavailable(self) -> None:
        core, _ = self._core()
        result = asyncio.run(core.route(_envelope(capability="test.missing")))
        self.assertEqual(result.status, ExecutionStatus.UNAVAILABLE)
        assert result.error is not None
        self.assertEqual(result.error.code, "unknown_capability")

    def test_global_policy_deny_is_audited(self) -> None:
        core, journal = self._core(
            policy_evaluator=lambda envelope: PolicyDecision(
                allowed=False, reason="tenant suspended"
            )
        )
        result = asyncio.run(core.route(_envelope()))
        self.assertEqual(result.status, ExecutionStatus.REJECTED)
        assert result.error is not None
        self.assertEqual(result.error.code, "central_policy_denied")
        events = journal.replay(tenant_id="tenant-1")
        self.assertEqual(events[0].event_type, "capability.rejected")

    def test_async_policy_evaluator_supported(self) -> None:
        async def evaluator(envelope) -> bool:
            return True

        core, _ = self._core(policy_evaluator=evaluator)
        result = asyncio.run(core.route(_envelope()))
        self.assertEqual(result.status, ExecutionStatus.SUCCEEDED)

    def test_approval_gate_is_audited(self) -> None:
        core, journal = self._core()
        result = asyncio.run(core.route(_envelope(capability="test.risky")))
        self.assertEqual(result.status, ExecutionStatus.APPROVAL_REQUIRED)
        assert result.error is not None
        self.assertEqual(result.error.code, "human_approval_required")
        # the approval request itself is audit-worthy and MUST hit the journal
        events = journal.replay(tenant_id="tenant-1")
        self.assertEqual(events[0].event_type, "execution.approval_required")

    def test_overall_deadline_enforced_by_core(self) -> None:
        core, _ = self._core()
        result = asyncio.run(core.route(_envelope(capability="test.slow", deadline_ms=50)))
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        assert result.error is not None
        self.assertEqual(result.error.code, "deadline_exceeded")

    def test_dispatch_to_convenience(self) -> None:
        core, _ = self._core()
        result = asyncio.run(
            core.dispatch_to(
                "llm",
                "test.ping",
                actor_id="user-1",
                tenant_id="tenant-1",
            )
        )
        self.assertEqual(result.status, ExecutionStatus.SUCCEEDED)

    def test_topology_and_health_cover_all_circles(self) -> None:
        core, _ = self._core()
        topology = core.topology()
        self.assertEqual(len(topology), len(CircleName))
        llm_entry = next(item for item in topology if item["circle"] == "llm")
        self.assertIn("test.ping", [spec["name"] for spec in llm_entry["capabilities"]])
        health = core.federation_health()
        self.assertEqual(health["centers"], 1)
        self.assertEqual(health["status"], "healthy")

    def test_federation_bootstrap_wires_ten_centers_and_realtime_sync(self) -> None:
        core = build_federation()
        self.assertEqual(len(core.centers()), 10)
        self.assertIn("memory.recall", core.capabilities())
        self.assertIn("system.health.read", core.capabilities())
        realtime = core.resolve(CircleName.REALTIME)
        assert realtime is not None
        result = asyncio.run(
            core.dispatch_to(
                "memory", "memory.recall", {"query": "x"}, actor_id="user-1", tenant_id="tenant-1"
            )
        )
        # Handler may fail if the vector store is unavailable in tests — the
        # contract we assert is that the EVENT reaches the realtime mirror.
        self.assertIn(result.status, {ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED})
        recent = realtime.recent()
        self.assertTrue(any(evt["circle"] == "memory" for evt in recent))

    def test_envelope_round_trip_through_legacy_contracts(self) -> None:
        envelope = _envelope(execution_id="exec_fixed", correlation_id="corr_fixed")
        request = envelope.to_capability_request()
        back = ExecutionEnvelope.from_capability_request(request)
        self.assertEqual(back.execution_id, "exec_fixed")
        self.assertEqual(back.correlation_id, "corr_fixed")
        self.assertEqual(back.circle, CircleName.LLM)
        self.assertEqual(back.capability, "test.ping")

    def test_legacy_execution_result_bridges_to_result_envelope(self) -> None:
        from core.circles.contracts import ExecutionResult

        legacy = ExecutionResult(
            execution_id="exec_fixed",
            status=ExecutionStatus.FAILED,
            error_code="boom",
            error_message="it broke",
            circle=CircleName.LLM,
            capability="test.ping",
        )
        bridged = result_envelope_from_execution(legacy)
        self.assertEqual(bridged.status, ExecutionStatus.FAILED)
        assert bridged.error is not None
        self.assertEqual(bridged.error.code, "boom")
        payload = bridged.to_dict()
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["circle"], "llm")
        self.assertIsNone(payload["data"])

    def test_get_governance_core_is_singleton(self) -> None:
        reset_governance_core()
        try:
            first = get_governance_core()
            second = get_governance_core()
            self.assertIs(first, second)
            self.assertEqual(len(first.centers()), 10)
        finally:
            reset_governance_core()


if __name__ == "__main__":
    unittest.main()
