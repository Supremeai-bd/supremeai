"""Contracts for active workflow name coupling and registry parsing.

The former bridge and watchdog files are retired; no fake workflow is invented.
Any active workflow_run references, however, must still resolve uniquely.
"""
from collections import Counter
from pathlib import Path
import importlib.util
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = ROOT / ".github" / "workflows"


class ActiveWorkflowContract(unittest.TestCase):
    def test_workflow_names_are_unique_and_run_references_resolve(self):
        paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
        self.assertTrue(paths, "workflow scan must not be empty")
        docs = [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]
        self.assertTrue(all(isinstance(doc, dict) for _, doc in docs))
        names = [doc.get("name") for _, doc in docs if doc.get("name")]
        self.assertTrue(names, "workflow scan must discover named workflows")
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        self.assertFalse(duplicates, f"duplicate workflow names: {duplicates}")
        for path, doc in docs:
            triggers = doc.get("on", doc.get(True, {}))
            if not isinstance(triggers, dict):
                continue
            workflow_run = triggers.get("workflow_run") or {}
            if isinstance(workflow_run, dict):
                for name in workflow_run.get("workflows", []):
                    self.assertIn(name, names, f"{path.name}: unknown workflow_run target {name!r}")

    def test_slot_registry_extracts_only_explicit_branches(self):
        path = ROOT / ".github" / "scripts" / "constitution" / "branch_creation_guard.py"
        spec = importlib.util.spec_from_file_location("branch_guard_contract", path)
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        with tempfile.TemporaryDirectory() as temp:
            registry = Path(temp) / "registry.yaml"
            registry.write_text("slots:\n  - branch: coder-1-fixture\n  - name: no-branch\n  - branch: coder-2-fixture\n", encoding="utf-8")
            self.assertEqual(guard.slot_registry_branches(registry), {"coder-1-fixture", "coder-2-fixture"})
            registry.write_text("slots: [", encoding="utf-8")
            self.assertEqual(guard.slot_registry_branches(registry), set())
            self.assertEqual(guard.slot_registry_branches(Path(temp) / "absent.yaml"), set())
