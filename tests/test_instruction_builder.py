"""Step-intelligence.1 regression guards (#104) — Instruction Builder contract.

Instruction Builder = pure-function 5-section envelope (MODE/RULES/ACTIONS/
FORBIDDEN/VALIDATION) composed from role_registry SSOT + AGENT_RULES.md parsed
policy. Deterministic, zero-cost, zero-LLM. Wiring into continuous_agent_loop
is seq:5 (same group merge-train) — this module must stand alone.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents.instruction_builder import (  # noqa: E402
    VALIDATION_TIERS,
    build_and_render,
    build_instruction,
    render_instruction,
)
from scripts.agents.role_registry import UnknownRoleError  # noqa: E402

FIVE_SECTIONS = ("MODE", "RULES", "ACTIONS", "FORBIDDEN", "VALIDATION")


class EnvelopeShapeTests(unittest.TestCase):
    """#104 মিশন: ৫-সেকশন standard contract — গঠন প্রতি run-এ অভিন্ন।"""

    def test_coder_envelope_has_all_five_sections(self):
        b = build_instruction("coder")
        for key in ("mode", "rules", "actions", "forbidden", "validation"):
            self.assertIn(key, b)
        self.assertIn("source", b)

    def test_mode_composes_real_authority_ssot(self):
        b = build_instruction("coder")
        self.assertEqual(b["mode"]["role"], "coder")
        self.assertEqual(b["mode"]["authority"], "governed_autonomous")

    def test_rules_parsed_live_from_agent_rules_md(self):
        b = build_instruction("coder")
        self.assertTrue(b["rules"], "RULES খালি হতে পারে না — AGENT_RULES.md §3 লাইভ পার্স")
        joined = " ".join(b["rules"]).lower()
        self.assertIn("smallest safe change", joined)

    def test_forbidden_nonempty_and_marker_derived(self):
        b = build_instruction("coder")
        self.assertTrue(b["forbidden"], "FORBIDDEN খালি হতে পারে না — নেতিবাচক-মার্কার বাক্য থাকতেই হবে")

    def test_actions_compose_credential_ssots(self):
        b = build_instruction("coder")
        self.assertIn("GH_TOKEN", b["actions"]["allowed_env_keys"])
        self.assertIn("contents:write", b["actions"]["gh_scopes"])

    def test_zero_secrets_in_envelope(self):
        b = build_and_render("coder")
        self.assertNotIn("ghs_", b)
        self.assertNotIn("github_pat_", b)

    def test_validation_carries_3_tier_contract(self):
        b = build_instruction("coder")
        self.assertEqual(len(b["validation"]["tiers"]), 3)
        self.assertEqual(tuple(b["validation"]["tiers"]), VALIDATION_TIERS)
        self.assertIn("3-tier", b["validation"]["requirement"])


class DeterminismTests(unittest.TestCase):
    """#104 PROBLEM: "প্রতি run-এ একই contract আলাদা গঠনে" — এখন অভিন্নতা বাধ্যতামূলক।"""

    def test_two_builds_identical_dict(self):
        self.assertEqual(build_instruction("coder"), build_instruction("coder"))

    def test_two_renders_identical_text(self):
        self.assertEqual(build_and_render("coder"), build_and_render("coder"))

    def test_render_contains_all_five_headers_in_order(self):
        text = build_and_render("coder")
        positions = [text.find(s) for s in FIVE_SECTIONS]
        self.assertTrue(all(p >= 0 for p in positions), f"header মিসিং: {positions}")
        self.assertEqual(positions, sorted(positions), "সেকশন-ক্রম অবশ্যই MODE→VALIDATION")


class PurityAndGracefulDegradationTests(unittest.TestCase):
    """Inject-করা rules/contract সম্মানিত হয় — ফাইল-নিরপেক্ষ pure function।"""

    def test_injected_rules_override_live_parse(self):
        b = build_instruction(
            "coder",
            rules=(["keep scope tight"], ["no drive-by refactoring"]),
        )
        self.assertEqual(b["rules"], ["keep scope tight"])
        self.assertEqual(b["forbidden"], ["no drive-by refactoring"])
        self.assertEqual(b["source"]["rules_source"], "injected")

    def test_injected_minimal_contract_respected(self):
        c = {
            "role": "watcher",
            "authority": "autonomous",
            "verification": "evidence-backed issue",
            "allowed_env_keys": [],
            "gh_scopes": [],
            "constraints": [],
        }
        b = build_instruction("watcher", contract=c, rules=([], []))
        self.assertEqual(b["mode"]["authority"], "autonomous")
        self.assertEqual(b["actions"]["allowed_env_keys"], [])

    def test_empty_rules_render_gracefully_not_crash(self):
        text = render_instruction(build_instruction("coder", rules=([], [])))
        self.assertIn("- none declared", text)
        for s in FIVE_SECTIONS:
            self.assertIn(s, text)

    def test_unknown_role_raises(self):
        with self.assertRaises(UnknownRoleError):
            build_instruction("warlord")

    def test_empty_env_keys_render_none_not_blank(self):
        text = render_instruction({
            "mode": {"role": "x", "authority": "autonomous"},
            "rules": [], "forbidden": [],
            "actions": {"allowed_env_keys": [], "gh_scopes": []},
            "validation": {"requirement": "r", "tiers": list(VALIDATION_TIERS)},
            "source": {"rules_source": "test", "deterministic": True},
        })
        self.assertIn("env_keys: none", text)
        self.assertIn("gh_scopes: none", text)


if __name__ == "__main__":
    unittest.main()
