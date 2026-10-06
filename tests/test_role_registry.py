"""Roadmap v2.0 Phase 1+2+6 regression guards (issue #4143).

Role Registry composes EXISTING sources (credential_manager SSOTs +
AGENT_RULES.md §3) into a machine-usable per-role contract, the Phase 2.2
Dynamic Prompt, and the Phase 6 Rule B advisory planner. AGENTS.md §0
carries the One Simple Entry Point loop contract.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents.role_registry import (
    AUTHORITY_TIERS,
    UnknownRoleError,
    build_dynamic_prompt,
    canonical_role,
    get_role_contract,
    plan_task_execution,
)


class AuthorityMatrixTests(unittest.TestCase):
    """Phase 4's simple 3-tier matrix — deterministic, complete."""

    def test_all_fleet_roles_have_authority(self):
        for role in ("coder", "planner", "auditor", "watcher", "breaker",
                     "human-eyes", "pr-helper", "ci-fixer", "merge-agent"):
            self.assertIn(role, AUTHORITY_TIERS)

    def test_tiers_are_only_the_roadmap_three(self):
        self.assertEqual(set(AUTHORITY_TIERS.values()),
                         {"autonomous", "governed_autonomous", "human_required"})

    def test_write_lanes_are_governed_and_merge_is_human(self):
        self.assertEqual(AUTHORITY_TIERS["coder"], "governed_autonomous")
        self.assertEqual(AUTHORITY_TIERS["merge-agent"], "human_required")
        self.assertEqual(AUTHORITY_TIERS["breaker"], "autonomous")

    def test_unknown_role_raises(self):
        with self.assertRaises(UnknownRoleError):
            get_role_contract("warlord")

    def test_aliases_normalize(self):
        self.assertEqual(canonical_role("ci"), "ci-fixer")
        self.assertEqual(canonical_role("browser"), "human-eyes")
        self.assertEqual(canonical_role("coder-1"), "coder")


class RoleContractTests(unittest.TestCase):
    def test_coder_contract_composes_real_ssots(self):
        c = get_role_contract("coder")
        # env keys come from credential_manager (includes #4134 MCP tower keys)
        self.assertIn("GH_TOKEN", c["allowed_env_keys"])
        self.assertIn("MCP_API_KEY", c["allowed_env_keys"])
        # gh scopes come from BOT_SLOT_CREDENTIALS (agent-3: contents:write …)
        self.assertIn("contents:write", c["gh_scopes"])
        # constraints parsed LIVE from AGENT_RULES.md §3 Coder section
        self.assertTrue(c["constraints"], "constraints must not be empty")
        self.assertIn("smallest safe change", " ".join(c["constraints"]))
        self.assertEqual(c["authority"], "governed_autonomous")
        self.assertIn("3-tier", c["verification"])

    def test_zero_key_roles_have_no_env_keys(self):
        c = get_role_contract("breaker")
        self.assertNotIn("GH_TOKEN", c["allowed_env_keys"])

    def test_scopes_never_contain_secret_values(self):
        c = get_role_contract("coder")
        for scope in c["gh_scopes"]:
            self.assertNotIn("ghs_", scope)


class DynamicPromptTests(unittest.TestCase):
    def test_prompt_contains_all_phase_2_sections(self):
        prompt = build_dynamic_prompt("coder", "fix the flaky reconcile test")
        self.assertIn("ROLE: coder", prompt)
        self.assertIn("authority: governed_autonomous", prompt)
        self.assertIn("VERIFICATION REQUIRED:", prompt)
        self.assertIn("ALLOWED TOOLS/ENV KEYS:", prompt)
        self.assertIn("TASK: fix the flaky reconcile test", prompt)
        self.assertIn("deterministic gates outrank", prompt)

    def test_prompt_is_deterministic(self):
        a = build_dynamic_prompt("planner", "plan x")
        b = build_dynamic_prompt("planner", "plan x")
        self.assertEqual(a, b)


class RuleBPlannerTests(unittest.TestCase):
    def test_security_sensitive_goes_multi_with_breaker(self):
        plan = plan_task_execution("fix auth bypass vulnerability in login")
        self.assertEqual(plan["mode"], "multi")
        self.assertIn("breaker", plan["agents"])
        self.assertIn("adversarial", plan["verification"])

    def test_security_label_triggers_multi(self):
        plan = plan_task_execution("update token flow", labels=["security"])
        self.assertEqual(plan["mode"], "multi")

    def test_large_task_decomposes_with_planner(self):
        plan = plan_task_execution("redesign the architecture of the queue layer")
        self.assertEqual(plan["mode"], "multi_decompose")
        self.assertIn("planner", plan["agents"])

    def test_simple_task_stays_single(self):
        plan = plan_task_execution("fix typo in README")
        self.assertEqual(plan["mode"], "single")
        self.assertEqual(plan["agents"], ["coder"])
        self.assertIn("simplest", plan["rationale"])


class EntryPointDocTests(unittest.TestCase):
    """Phase 1: AGENTS.md §0 carries the 8-step loop contract."""

    def test_agents_md_has_loop_section_with_eight_steps(self):
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 0. The Agent Loop — One Simple Entry Point", text)
        for step in ("Understand", "Rules", "Inspect state", "Claim",
                     "Work", "Verify", "Record", "Return"):
            self.assertIn(step, text)
        self.assertIn("atomic_claim.sh", text)


if __name__ == "__main__":
    unittest.main()
