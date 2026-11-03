import asyncio
import unittest

from adaptive_engine.capability_node import CapabilityNodeBridge, NodeContext
from adaptive_engine.capability_registry import (
    Capability,
    CapabilityLifecycleState,
    CapabilityRegistry,
)
from adaptive_engine.governed_executor import GovernedCapabilityExecutor


class TestGovernedExecutor(unittest.TestCase):
    def test_emits_start_and_terminal_events(self):
        registry = CapabilityRegistry()
        bridge = CapabilityNodeBridge(registry)
        capability = Capability(
            name="Echo",
            purpose="test",
            signature="test.governed.v1",
            lifecycle_state=CapabilityLifecycleState.ACTIVE,
        )
        bridge.register(capability, lambda request: request["payload"])
        events = []
        executor = GovernedCapabilityExecutor(
            bridge, lambda kind, payload: events.append((kind, payload))
        )
        result = asyncio.run(
            executor.execute(
                "test.governed.v1", NodeContext("t", "a", "c", "test.governed.v1"), {"ok": True}
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(
            [event[0] for event in events], ["execution.started", "execution.succeeded"]
        )


if __name__ == "__main__":
    unittest.main()
