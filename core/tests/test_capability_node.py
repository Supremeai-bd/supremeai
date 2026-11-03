import unittest

from adaptive_engine.capability_node import CapabilityNodeBridge, NodeContext
from adaptive_engine.capability_registry import (
    Capability,
    CapabilityLifecycleState,
    CapabilityRegistry,
)


class TestCapabilityNodeBridge(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.bridge = CapabilityNodeBridge(self.registry)
        # Ensure fresh state in case previous test run left data in DB
        existing = self.registry.find_by_signature("test.echo.v1")
        if existing:
            self.capability = existing
        else:
            self.capability = Capability(
                name="Echo",
                purpose="test",
                signature="test.echo.v1",
                lifecycle_state=CapabilityLifecycleState.ACTIVE,
                tenant_id=None,
            )
        self.bridge.register(self.capability, lambda request: {"echo": request["payload"]["value"]})

    def context(self, capability="test.echo.v1"):
        return NodeContext("tenant-a", "actor-a", "corr-a", capability)

    def test_dispatches_in_process_and_records_usage(self):
        initial_usage = self.registry.get(self.capability.capability_id).usage_count
        result = self.bridge.dispatch_sync("test.echo.v1", self.context(), {"value": "ok"})
        self.assertTrue(result.ok)
        self.assertEqual(result.output, {"echo": "ok"})
        self.assertEqual(
            self.registry.get(self.capability.capability_id).usage_count, initial_usage + 1
        )

    def test_context_mismatch_is_rejected(self):
        result = self.bridge.dispatch_sync("test.echo.v1", self.context("other.v1"), {})
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "capability_context_mismatch")

    def test_duplicate_handlers_are_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.register(self.capability, lambda _: None)


if __name__ == "__main__":
    unittest.main()
