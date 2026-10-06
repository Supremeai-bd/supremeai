"""Roadmap v2.0 Phase 0.3 + 0.4 regression guards (issue #4139).

Verifies the .github/workflows/pr.yml text contract:
  * Phase 0.3 — Template Gate runs FIRST in the system-gates step
    (before constitution.gates / freshness), and is invoked exactly once.
  * Phase 0.4 — every BLOCK emitted by pr.yml's own steps is actionable:
    Branch Naming Guard echoes the required pattern + fix hint; the Unified
    PR Gate synthesizer names each failed required job.

Text-structure assertions (no workflow execution needed) — same approach as
the repo's other workflow-contract tests.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PR_YML = REPO_ROOT / ".github" / "workflows" / "pr.yml"


class GateOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PR_YML.read_text(encoding="utf-8")

    def test_yaml_parses(self):
        import yaml

        data = yaml.safe_load(self.text)
        self.assertIn("jobs", data)

    def test_template_gate_runs_before_gate_runner(self):
        """Phase 0.3: template gate is the FIRST gate in system-gates step."""
        t_idx = self.text.index("template_gate.py --pr")
        g_idx = self.text.index("python -m constitution.gates all --pr")
        f_idx = self.text.index("freshness_gate.py --pr")
        self.assertLess(t_idx, g_idx, "template gate must run before constitution.gates")
        self.assertLess(t_idx, f_idx, "template gate must run before freshness gate")

    def test_template_gate_invoked_exactly_once(self):
        """Order-only change: the gate must not be duplicated (double-run)."""
        count = self.text.count('template_gate.py --pr "$PR_NUMBER"')
        self.assertEqual(count, 1)


class ActionableBlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PR_YML.read_text(encoding="utf-8")

    def test_branch_naming_guard_echoes_pattern(self):
        """Phase 0.4: failure path prints the required pattern + a fix hint."""
        self.assertIn('echo "   Required pattern: $VALID_PATTERN"', self.text)
        self.assertIn('echo "   Fix: rename the branch', self.text)

    def test_synthesizer_names_failing_jobs(self):
        """Phase 0.4: BLOCK names each failed required job, not a generic line."""
        self.assertIn("Constitutional System Gates: $GATES_RESULT", self.text)
        self.assertIn("Test & Build Verification: $TESTS_RESULT", self.text)

    def test_full_suite_block_names_where_to_look(self):
        """Phase 0.4: cross-tier BLOCK points to the failing check's log."""
        self.assertIn("Full Backend Suite (cross-tier gate #2893)' check log", self.text)


if __name__ == "__main__":
    unittest.main()
