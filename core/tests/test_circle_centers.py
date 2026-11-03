"""FCC circle center unit tests — local concerns of every circle."""

import asyncio
import time
import unittest

from core.circles.centers.base import (
    CircleCenter,
    LocalCapability,
    RetryPolicy,
)
from core.circles.contracts import CircleName, ExecutionStatus, RiskLevel
from core.circles.envelopes import ExecutionEnvelope


def _envelope(
    capability: str,
    circle: CircleName = CircleName.MEMORY,
    payload: dict | None = None,
    deadline_ms: int = 30_000,
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        circle=circle,
        capability=capability,
        tenant_id="tenant-1",
        actor_id="user-1",
        payload=payload or {},
        deadline_ms=deadline_ms,
    )


class _HarnessCenter(CircleCenter):
    circle = CircleName.MEMORY
    display_name = "Harness"
    owner = "tests"


class CircleCenterTests(unittest.TestCase):
    def _center(self, **kwargs) -> _HarnessCenter:
        center = _HarnessCenter(**kwargs)
        center.register(
            LocalCapability(name="memory.recall", risk_level=RiskLevel.LOW), lambda r: {"ok": 1}
        )
        return center

    def test_registers_and_rejects_duplicates(self) -> None:
        center = self._center()
        with self.assertRaises(ValueError):
            center.register(LocalCapability(name="memory.recall"), lambda r: None)
        self.assertEqual(center.capabilities(), ("memory.recall",))

    def test_handle_success_returns_result_envelope_with_event(self) -> None:
        center = self._center()
        result = asyncio.run(center.handle(_envelope("memory.recall")))
        self.assertEqual(result.status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(result.data, {"ok": 1})
        self.assertIsNone(result.error)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].event_type, "execution.succeeded")
        self.assertEqual(result.circle, CircleName.MEMORY)

    def test_unknown_capability_is_unavailable(self) -> None:
        center = self._center()
        result = asyncio.run(center.handle(_envelope("memory.unknown")))
        self.assertEqual(result.status, ExecutionStatus.UNAVAILABLE)
        assert result.error is not None
        self.assertEqual(result.error.code, "capability_not_registered")

    def test_local_permission_denial(self) -> None:
        class Guarded(_HarnessCenter):
            def local_permission(self, envelope):
                return "not allowed here"

        center = Guarded()
        center.register(LocalCapability(name="memory.recall"), lambda r: {"ok": 1})
        result = asyncio.run(center.handle(_envelope("memory.recall")))
        self.assertEqual(result.status, ExecutionStatus.REJECTED)
        assert result.error is not None
        self.assertEqual(result.error.code, "local_permission_denied")

    def test_approval_gate_blocks_handler(self) -> None:
        center = _HarnessCenter()
        ran = {"called": False}

        def handler(request):
            ran["called"] = True
            return {}

        center.register(
            LocalCapability(
                name="browser.navigate",
                approval_required=True,
                risk_level=RiskLevel.HIGH,
            ),
            handler,
        )
        result = asyncio.run(
            center.handle(_envelope("browser.navigate", circle=CircleName.BROWSER))
        )
        self.assertEqual(result.status, ExecutionStatus.APPROVAL_REQUIRED)
        assert result.error is not None
        self.assertEqual(result.error.code, "human_approval_required")
        self.assertFalse(ran["called"])

    def test_retry_succeeds_after_transient_failure(self) -> None:
        center = _HarnessCenter(retry_policy=RetryPolicy(max_attempts=3, backoff_ms=1))
        calls = {"count": 0}

        def flaky(request):
            calls["count"] += 1
            if calls["count"] < 2:
                raise RuntimeError("transient")
            return {"attempt": calls["count"]}

        center.register(LocalCapability(name="memory.recall"), flaky)
        result = asyncio.run(center.handle(_envelope("memory.recall")))
        self.assertEqual(result.status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(result.data, {"attempt": 2})
        self.assertEqual(calls["count"], 2)

    def test_retry_exhaustion_fails(self) -> None:
        center = _HarnessCenter(retry_policy=RetryPolicy(max_attempts=2, backoff_ms=1))

        def broken(request):
            raise RuntimeError("always broken")

        center.register(LocalCapability(name="memory.recall"), broken)
        result = asyncio.run(center.handle(_envelope("memory.recall")))
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        assert result.error is not None
        self.assertEqual(result.error.code, "circle_handler_failed")
        self.assertIn("always broken", result.error.message or "")

    def test_timeout_becomes_deadline_exceeded(self) -> None:
        center = _HarnessCenter()
        center.register(LocalCapability(name="memory.recall", timeout_ms=50), lambda r: _sleep())
        result = asyncio.run(center.handle(_envelope("memory.recall")))
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        assert result.error is not None
        self.assertEqual(result.error.code, "deadline_exceeded")

    def test_cache_hit_skips_handler(self) -> None:
        center = _HarnessCenter()
        calls = {"count": 0}

        def counted(request):
            calls["count"] += 1
            return {"value": calls["count"]}

        center.register(LocalCapability(name="memory.recall", cache_ttl_ms=5_000), counted)
        first = asyncio.run(center.handle(_envelope("memory.recall", payload={"q": "x"})))
        second = asyncio.run(center.handle(_envelope("memory.recall", payload={"q": "x"})))
        self.assertEqual(first.status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(second.status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(first.data, {"value": 1})
        self.assertEqual(second.data, {"value": 1})  # cached
        self.assertEqual(calls["count"], 1)
        self.assertEqual(second.events[0].payload.get("cache"), "hit")

    def test_health_snapshot_reflects_executions(self) -> None:
        center = self._center()
        health = center.health()
        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.total_executions, 0)
        asyncio.run(center.handle(_envelope("memory.recall")))
        health = center.health()
        self.assertEqual(health.total_executions, 1)
        self.assertEqual(health.failed_executions, 0)
        self.assertIsNotNone(health.avg_latency_ms)
        self.assertEqual(health.capabilities, ("memory.recall",))

    def test_missing_context_is_rejected(self) -> None:
        center = self._center()
        envelope = _envelope("memory.recall")
        envelope.actor_id = ""
        result = asyncio.run(center.handle(envelope))
        self.assertEqual(result.status, ExecutionStatus.REJECTED)
        assert result.error is not None
        self.assertEqual(result.error.code, "execution_context_incomplete")


def _sleep() -> str:
    time.sleep(0.2)
    return "too late"


if __name__ == "__main__":
    unittest.main()
