import json
import tempfile
import unittest
from pathlib import Path

from scripts.ci.capability_integration_gate import validate


class TestCapabilityIntegrationGate(unittest.TestCase):
    def test_required_runtime_nodes_are_present(self):
        payload = {"modules": [{"path": path} for path in ["backend/adaptive_engine/capability_registry.py", "backend/adaptive_engine/capability_node.py", "backend/adaptive_engine/governed_executor.py"]]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(validate(str(path))["ok"])

    def test_missing_runtime_node_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(json.dumps({"modules": []}), encoding="utf-8")
            self.assertFalse(validate(str(path))["ok"])


if __name__ == "__main__":
    unittest.main()
