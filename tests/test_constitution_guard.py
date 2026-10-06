"""Roadmap v2.0 Phase 9 regression guards (#4145) — constitution boundary gate.

Deterministic: PRs touching AGENTS.md / AGENT_RULES.md / .github/constitution/**
/ backend/governance/** BLOCK unless the PR carries 'approved-by:admin'.
Gate logic unit-tested with a stubbed gh_api — no network.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

gates = importlib.import_module("constitution.gates")


def _stub_gh_api(files, labels):
    def fake(endpoint, token=None):
        if "/files" in endpoint:
            return files
        return {"labels": [{"name": l} for l in labels]}

    return fake


class ConstitutionGuardTests(unittest.TestCase):
    def test_boundary_file_without_admin_label_blocks(self):
        files = [{"filename": "scripts/foo.py"}, {"filename": "AGENT_RULES.md"}]
        with mock.patch.object(gates, "gh_api", _stub_gh_api(files, [])), \
             mock.patch.object(gates, "_repo", lambda: "o/r"):
            rc = gates.run_constitution_guard_gate(1)
        self.assertEqual(rc, 1)

    def test_boundary_file_with_admin_label_passes(self):
        files = [{"filename": "backend/governance/policy_engine.py"}]
        with mock.patch.object(gates, "gh_api", _stub_gh_api(files, ["approved-by:admin"])), \
             mock.patch.object(gates, "_repo", lambda: "o/r"):
            rc = gates.run_constitution_guard_gate(1)
        self.assertEqual(rc, 0)

    def test_non_boundary_pr_passes(self):
        files = [{"filename": "scripts/agents/worker.py"}, {"filename": "tests/x.py"}]
        with mock.patch.object(gates, "gh_api", _stub_gh_api(files, [])), \
             mock.patch.object(gates, "_repo", lambda: "o/r"):
            rc = gates.run_constitution_guard_gate(1)
        self.assertEqual(rc, 0)

    def test_nested_constitution_path_is_boundary(self):
        files = [{"filename": ".github/constitution/rules.yml"}]
        with mock.patch.object(gates, "gh_api", _stub_gh_api(files, [])), \
             mock.patch.object(gates, "_repo", lambda: "o/r"):
            rc = gates.run_constitution_guard_gate(1)
        self.assertEqual(rc, 1)

    def test_agent_md_is_boundary(self):
        files = [{"filename": "AGENTS.md"}]
        with mock.patch.object(gates, "gh_api", _stub_gh_api(files, [])), \
             mock.patch.object(gates, "_repo", lambda: "o/r"):
            rc = gates.run_constitution_guard_gate(1)
        self.assertEqual(rc, 1)

    def test_gate_registered_in_cli_choices(self):
        src = (REPO_ROOT / ".github" / "scripts" / "constitution" / "gates.py").read_text()
        self.assertIn('"constitution_guard"', src)
        self.assertIn("run_constitution_guard_gate(args.pr)", src)

    def test_block_message_is_actionable(self):
        self.assertIn("approved-by:admin", gates.ADMIN_APPROVAL_LABEL)


if __name__ == "__main__":
    unittest.main()
