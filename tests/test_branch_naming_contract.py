"""Branch Naming Guard ↔ Persistent Branch SSOT contract (#4241).

বাংলা: #4200 Persistent Branch Workflow (default-ON, #4227) ক্যানোনিকাল নাম
`agent/<issue>-<slug>` তৈরি করে (continuous_agent_loop.PERSISTENT_BRANCH_PREFIX +
_issue_slug) — কিন্তু pr.yml Branch Naming Guard-এর VALID_PATTERN-এ লেনটি ছিল না,
ফলে PR #4229-এর মতো live BLOCK চক্র হতো। এই চুক্তি-টেস্ট তিন স্তর যাচাই করে:

  ১. গার্ডের লাইভ VALID_PATTERN (pr.yml, একক-উৎস) loop-জেনারেটেড নাম মেনে নেয়
  ২. SSOT অখণ্ডতা — loop-এর প্যাটার্ন-জেনারেটর ফাংশনই টেস্টে চলে (কোনো কপি নয়)
  ৩. Constitution-সংগতি — rules.yml persistent_branch_glob / pr_integration_patterns
     একই namespace ঘোষণা করে (guard = Constitution-এর স্টেল প্রয়োগকারী ছিল)
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "agents"))

from continuous_agent_loop import PERSISTENT_BRANCH_PREFIX, _issue_slug  # noqa: E402

PR_YML = REPO_ROOT / ".github" / "workflows" / "pr.yml"
RULES_YML = REPO_ROOT / ".github" / "constitution" / "rules.yml"


def load_valid_pattern() -> str:
    """Extract the live VALID_PATTERN from pr.yml (single source of truth)."""
    text = PR_YML.read_text(encoding="utf-8")
    m = re.search(r"VALID_PATTERN='([^']+)'", text)
    if not m:
        raise AssertionError("VALID_PATTERN not found in pr.yml — guard contract unreadable")
    return m.group(1)


def loop_branch_name(issue_number: int, title: str) -> str:
    """The exact name discover_or_create_branch() produces (#4200 §3)."""
    return f"{PERSISTENT_BRANCH_PREFIX}{int(issue_number)}-{_issue_slug(title)}"


class PersistentBranchLaneTests(unittest.TestCase):
    """#4241: loop-generated names MUST pass the live guard pattern."""

    def setUp(self):
        self.pattern = load_valid_pattern()

    def assert_branch_allowed(self, branch: str):
        self.assertRegex(branch, self.pattern)

    def assert_branch_blocked(self, branch: str):
        self.assertIsNone(re.fullmatch(self.pattern, branch),
                          f"'{branch}' should be BLOCKED by the guard")

    def test_live_victim_branch_from_4229_passes(self):
        # PR #4229-এর আসল ব্লক-হওয়া নাম (run 37709135711)
        self.assert_branch_allowed("agent/4138-feat-frontend-dashboard-implement-intell")

    def test_loop_generated_names_pass_guard(self):
        # SSOT: loop-এর নিজের জেনারেটর ফাংশন দিয়ে নাম বানিয়ে গার্ডে খুঁচড়ানো
        cases = [
            (4138, "feat(frontend,dashboard): Implement Intelligent Frontend"),
            (4200, "Persistent Branch Workflow — resume across sessions"),
            (99, "### Титул с unicode и 空格 ###"),
            (7, "a" * 200),  # slug cap 40 chars + rstrip('-')
            (5, "!!!"),
        ]
        for issue, title in cases:
            self.assert_branch_allowed(loop_branch_name(issue, title))

    def test_empty_slug_fallback_still_passes(self):
        # _issue_slug fallback = "work" (শূন্য-ascii টাইটেল) → agent/5-work
        self.assertEqual(_issue_slug("🎉🎊✨"), "work")
        self.assert_branch_allowed(loop_branch_name(5, "🎉🎊✨"))

    def test_agent_namespace_negatives_stay_blocked(self):
        self.assert_branch_blocked("agent/4138")            # slug ছাড়া (glob agent/<issue>-*)
        self.assert_branch_blocked("agent/abc-slug")        # issue-number বাধ্যতামূলক
        self.assert_branch_blocked("agent/-x")              # নাম্বার-হীন
        self.assert_branch_blocked("agent/")                # খালি namespace
        self.assert_branch_blocked("agent/4138-UPPER")      # slug lowercase-ই (loop নিজেই lower করে)

    def test_legacy_lanes_regression(self):
        for name in ("coder-1-4139-gate-order-first", "fix/4136-alembic-heads",
                     "agent-3-coder-1", "agent-2/issue-99-desc", "plan-2841-pr1-constitution-slim",
                     "group/foundation-closeout", "dependabot/pnpm/lockfile", "main"):
            self.assert_branch_allowed(name)


class ConstitutionCoherenceTests(unittest.TestCase):
    """গার্ড = Constitution-এর প্রয়োগকারী — দুই পাশ এক namespace-এ একমত হতে হবে।"""

    def setUp(self):
        self.rules = yaml.safe_load(RULES_YML.read_text(encoding="utf-8"))

    def test_rules_yml_declares_agent_issue_glob(self):
        # rules.yml branch_discovery (section: ইস্যু-ডিটারমিনিস্টিক discovery, #4205)
        found_glob = False
        for key, node in self._walk(self.rules):
            if key == "persistent_branch_glob":
                found_glob = True
                self.assertEqual(node, "agent/<issue>-*")
            if key == "pr_integration_patterns":
                self.assertIn("agent/*", node)
        self.assertTrue(found_glob, "rules.yml-এ persistent_branch_glob অনুপস্থিত")

    def test_guard_pattern_accepts_rules_glob_shape(self):
        # rules.yml glob "agent/<issue>-*" এর প্রাকৃতিক উদাহরণ গার্ডে পাস করে
        pattern = load_valid_pattern()
        self.assertIsNotNone(re.fullmatch(pattern, "agent/4241-naming-guard-fix"))

    @staticmethod
    def _walk(node, key=None):
        yield key, node
        if isinstance(node, dict):
            for k, v in node.items():
                yield from ConstitutionCoherenceTests._walk(v, k)
        elif isinstance(node, list):
            for item in node:
                yield from ConstitutionCoherenceTests._walk(item, key)


if __name__ == "__main__":
    unittest.main()
