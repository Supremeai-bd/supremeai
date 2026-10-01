"""Branch Naming Guard contract tests (#2850) — single-source from pr.yml.

বাংলা মন্তব্য: টেস্টটি .github/workflows/pr.yml থেকেই লাইভ VALID_PATTERN পড়ে
(একক-উৎস — কোনো কপি নয়)। গার্ডের রেগেক্স বদলালে এই চুক্তি-টেস্টগুলোও সাথে
সাথে আপডেট হয় কিনা তা ধরা পড়বে। #2841 সিরিজের plan-2841-* শাখাগুলো এই গার্ডে
আটকেছিল — plan- লেন স্বীকৃতির পরে পাস করবে; পুরনো ২৪+ লেন অক্ষত থাকবে।
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PR_YML = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pr.yml"


def load_valid_pattern() -> str:
    """Extract the live VALID_PATTERN from pr.yml (single source of truth)."""
    text = PR_YML.read_text(encoding="utf-8")
    m = re.search(r"VALID_PATTERN='([^']+)'", text)
    if not m:
        raise AssertionError("VALID_PATTERN not found in pr.yml — guard contract unreadable")
    return m.group(1)


class BranchNamingGuardTests(unittest.TestCase):
    def setUp(self):
        self.pattern = load_valid_pattern()

    def assert_branch_allowed(self, branch: str):
        self.assertRegex(branch, self.pattern)

    def assert_branch_blocked(self, branch: str):
        self.assertIsNone(re.fullmatch(self.pattern, branch),
                          f"'{branch}' should be BLOCKED by the guard")

    # --- #2841 series: the three victim branches (plan-<issue>-<desc>) ---
    def test_plan_lane_victim_branches_pass(self):
        self.assert_branch_allowed("plan-2841-pr1-constitution-slim")
        self.assert_branch_allowed("plan-2841-pr2-doc-consolidation")
        self.assert_branch_allowed("plan-2841-pr3-script-dedup")

    def test_plan_lane_minimal_and_variants(self):
        self.assert_branch_allowed("plan-9999")
        self.assert_branch_allowed("plan-123-my-slug-2")

    def test_plan_lane_dotted_suffix_blocked_by_design(self):
        # চুক্তি: লেন-স্লাগে ডট নেই (কেবল group/ শাখায় [a-z0-9._-]) — ডট-সাফিক্স ব্লকডই থাকবে
        self.assert_branch_blocked("plan-123-my-slug.2")

    # --- legacy lanes must remain intact ---
    def test_legacy_lane_branches_still_pass(self):
        for lane in ("planner", "coder", "pr-helper", "ci", "platform", "browser", "super"):
            self.assert_branch_allowed(f"{lane}-1001")
            self.assert_branch_allowed(f"{lane}-1001-my-fix")

    def test_slash_form_and_group_branches_still_pass(self):
        self.assert_branch_allowed("feat/anything-goes")
        self.assert_branch_allowed("fix/2853-role-ssot-rules-source")
        self.assert_branch_allowed("test/some-suite")
        self.assert_branch_allowed("group/foundation-closeout")
        self.assert_branch_allowed("agent-3-issue-42-some-task")

    def test_develop_and_main_still_pass(self):
        self.assert_branch_allowed("develop")
        self.assert_branch_allowed("main")

    # --- junk names must stay blocked ---
    def test_junk_branches_still_blocked(self):
        self.assert_branch_blocked("rogue-branch")
        self.assert_branch_blocked("plan-notanumber")
        self.assert_branch_blocked("plan--")
        self.assert_branch_blocked("feature/typo-prefix")   # 'feature' is not 'feat'
        self.assert_branch_blocked("PLAN-2841-uppercase")
        self.assert_branch_blocked("")

    def test_guard_contract_is_anchored(self):
        # চুক্তি: প্যাটার্ন অবশ্যই ^ ও $ দিয়ে anchored — নইলে আংশিক মিলে জাংক ঢুকবে
        self.assertTrue(self.pattern.startswith("^"))
        self.assertTrue(self.pattern.endswith("$"))


if __name__ == "__main__":
    unittest.main()
