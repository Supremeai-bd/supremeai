"""Freshness Gate tests (#2935) — root-level old-code-push prevention.

# বাংলা মন্তব্য: fake-git/fake-API ইনজেকশন — নেটওয়ার্ক/রিয়েল-git কল নেই।
# চুক্তি: merge-base ≠ main-HEAD → BLOCK (strict-ডিফল্ট) · synced → PASS ·
# overlap-মোডে ফাইল-সংঘর্ষ শূন্য হলে WARN · exempt-actor bypass ·
# deletion-advisory। অ্যাডমিন-ডকট্রিন: "new main er sathe mil thakle e push hobe"।
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # constitution pkg parent (test_gates-প্যাটার্ন)

import freshness_gate as fg  # noqa: E402

STRICT = {"mode": "strict", "main_ref": "origin/main", "exempt_actors": ["dependabot[bot]"]}


class FakeGit:
    """in-memory git — প্রয়োজনীয় সাব-কমান্ডগুলোর সৎ-উত্তর।"""

    def __init__(self, *, head="H1", main="M1", base="M1",
                 main_side_files=(), pr_side_files=(), status_files=()):
        self.head, self.main, self.base = head, main, base
        self.main_side_files = set(main_side_files)
        self.pr_side_files = set(pr_side_files)
        self.status_files = status_files  # (status, file) টাপল

    def __call__(self, *args):
        if args[0] == "rev-parse":
            return {"HEAD": self.head, "origin/main": self.main}[args[1]]
        if args[0] == "merge-base":
            return self.base
        if args[0] == "diff" and "--name-only" in args:
            rev = args[args.index("--name-only") + 1]
            # main-পাশ: <base>..origin/main · PR-পাশ: <base>..HEAD
            return "\n".join(
                self.main_side_files if rev.endswith("origin/main")
                else self.pr_side_files
            )
        if args[0] == "diff" and "--name-status" in args:
            return "\n".join(f"{s}\t{f}" for s, f in self.status_files)
        if args[0] == "rev-list":
            return "3"
        raise AssertionError(f"unexpected git {args}")


def _api_actor(actor):
    def api(endpoint):
        if "/pulls/" in endpoint:
            return {"user": {"login": actor}}
        raise AssertionError(f"unexpected GET {endpoint}")
    return api


class TestFreshness(unittest.TestCase):
    def test_synced_pr_passes(self):
        git = FakeGit(base="M1", main="M1", status_files=[("M", "scripts/a.py")])
        result = fg.evaluate(git=git, pol=STRICT, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(result["synced"])

    def test_synced_pr_with_deletions_gets_advisory_only(self):
        git = FakeGit(base="M1", main="M1", status_files=[("D", "old/legacy.py")])
        result = fg.evaluate(git=git, pol=STRICT, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "PASS")  # deletion = warning, block নয়
        self.assertTrue(any("মুছছে" in w for w in result["warnings"]))

    def test_behind_main_blocks_in_strict_mode(self):
        # কোর-চুক্তি: old-code-push root-block — overlap নির্বিশেষে behind হলেই BLOCK
        git = FakeGit(head="H1", main="M9", base="M1",
                      main_side_files={"rules.yml"}, pr_side_files={"other.py"})
        result = fg.evaluate(git=git, pol=STRICT, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertEqual(result["behind_by"], 3)
        self.assertTrue(any("old-code push" in r for r in result["reasons"]))
        # self-heal নির্দেশনা আছে
        self.assertTrue(any("git merge origin/main" in r for r in result["reasons"]))

    def test_behind_main_with_overlap_lists_files(self):
        git = FakeGit(head="H1", main="M9", base="M1",
                      main_side_files={"rules.yml", "pr.yml", "x.py"},
                      pr_side_files={"rules.yml", "x.py", "y.py"})
        result = fg.evaluate(git=git, pol=STRICT, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertEqual(result["overlap"], ["rules.yml", "x.py"])
        self.assertTrue(any("rules.yml" in r for r in result["reasons"]))

    def test_overlap_mode_warns_when_no_file_conflict(self):
        pol = {**STRICT, "mode": "overlap"}
        git = FakeGit(head="H1", main="M9", base="M1",
                      main_side_files={"rules.yml"}, pr_side_files={"other.py"})
        result = fg.evaluate(git=git, pol=pol, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "WARN")

    def test_overlap_mode_blocks_on_file_conflict(self):
        pol = {**STRICT, "mode": "overlap"}
        git = FakeGit(head="H1", main="M9", base="M1",
                      main_side_files={"rules.yml"}, pr_side_files={"rules.yml"})
        result = fg.evaluate(git=git, pol=pol, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "BLOCK")

    def test_advisory_mode_never_blocks(self):
        pol = {**STRICT, "mode": "advisory"}
        git = FakeGit(head="H1", main="M9", base="M1",
                      main_side_files={"rules.yml"}, pr_side_files={"rules.yml"})
        result = fg.evaluate(git=git, pol=pol, pr_number=5, api=_api_actor("agent-x"))
        self.assertEqual(result["verdict"], "WARN")

    def test_exempt_trusted_bot_passes(self):
        git = FakeGit(head="H1", main="M9", base="M1")  # behind, তবু exempt
        result = fg.evaluate(git=git, pol=STRICT, pr_number=5, api=_api_actor("dependabot[bot]"))
        self.assertTrue(result["exempt"])
        self.assertEqual(result["verdict"], "PASS")

    def test_policy_loaded_from_rules_yml(self):
        pol = fg.load_policy()
        # SSOT: rules.yml freshness_policy — strict-ডিফল্ট (#2935)
        self.assertEqual(pol["mode"], "strict")
        self.assertIn("dependabot[bot]", pol["exempt_actors"])


if __name__ == "__main__":
    unittest.main()
