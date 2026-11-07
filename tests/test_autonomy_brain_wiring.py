#!/usr/bin/env python3
"""Tests for autonomy brain wiring in continuous_agent_loop (#106, #107, #108)."""
from __future__ import annotations

import unittest

from scripts.agents.continuous_agent_loop import build_autonomy_brain_plan, build_task_envelope


class TestAutonomyBrainWiring(unittest.TestCase):
    def test_build_task_envelope_populates_autonomy_brain(self) -> None:
        issue = {
            "number": 108,
            "title": "feat(autonomy): wire instruction builder, context selector, and dynamic router",
            "body": "Ensure continuous_agent_loop attaches deterministic autonomy_brain plan.",
            "state": "open",
            "labels": [{"name": "P1-high"}, {"name": "group-core"}],
        }
        wrapped = build_task_envelope(issue)
        env = wrapped["task_envelope"]
        self.assertIn("autonomy_brain", env)
        brain = env["autonomy_brain"]
        self.assertIn("instruction", brain)
        self.assertEqual(brain["instruction"]["mode"]["role"], "coder")
        self.assertTrue(brain["context_assembly"]["assembly_id"].startswith("asm-"))
        self.assertEqual(brain["route_plan"]["tier"], 3)
        self.assertEqual(
            brain["persistence_contract"]["router_contract"],
            "api-schemas/task-router.schema.json",
        )

    def test_build_autonomy_brain_plan_handles_auditor_role(self) -> None:
        plan = build_autonomy_brain_plan(
            role="auditor",
            task_id="task-999",
            title="audit: verify pre-landing compliance",
            body="Check boundary rules.",
            priority="P2",
            touching_files=["scripts/agents/continuous_agent_loop.py"],
        )
        self.assertEqual(plan["instruction"]["mode"]["role"], "task-auditor")
        self.assertEqual(plan["context_assembly"]["included_count"], 8)
        self.assertIn(plan["route_plan"]["tier"], (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
