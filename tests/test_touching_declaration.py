"""#2464 — claim-জেনারেশনে tests-গাছ অটো-ডিক্লিয়ারেশন।

কভারেজ:
  * compose_touching_declaration — norm/covers/compose চুক্তি
    (খালি → Rule 2 fallback; tests-গাছ নেই → `, tests/` অটো-অ্যাপেন্ড;
     গাছ আছে → byte-exact পাসথ্রু)
  * Scope Gate harvest-কম্প্যাটিবিলিটি — অ্যানোটেশন `(...)` স্ট্রিপ
    হওয়ার পর টোকেন `tests/` (directory-declaration) অক্ষত
  * গ্রুপ-বাউন্ড্রি (#2378) overlap_pair (#2464 exemption) —
    atomic_claim.sh-এর inline GROUP_BOUNDARY_PY ব্লক থেকে ফাংশন-স্লাইস
    dry-run (Task 42-d প্যাটার্ন): ট্রি-টোকেন vs নির্দিষ্ট ফাইলের ম্যাচ
    exempt, একই-ফাইল ও non-tests ম্যাচ অপরিবর্তিত
  * CLI smoke — offline, exit 0

No network access — সব ফাংশন pure, ইনলাইন ব্লক কেবল পড়া হয়।
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.compose_touching_declaration import (
    AUTO_ANNOTATION,
    FALLBACK_DECLARATION,
    compose,
    covers_tests_tree,
    norm_token,
)


class TestNormToken(unittest.TestCase):
    def test_bare_tree_root_forms(self) -> None:
        for tok in ("tests", "tests/", "tests/**", "`tests`", " tests ", "tests/ (auto)"):
            self.assertEqual(norm_token(tok), "tests", msg=tok)

    def test_specific_file_untouched(self) -> None:
        self.assertEqual(norm_token("tests/test_x.py"), "tests/test_x.py")
        self.assertEqual(norm_token("src/a.py"), "src/a.py")

    def test_empty(self) -> None:
        self.assertEqual(norm_token(""), "")


class TestCoversTestsTree(unittest.TestCase):
    def test_bare_tree_covers(self) -> None:
        for decl in ("tests", "tests/", "tests/**", "src/a.py, tests/",
                     "src/a.py, `tests/`", "docs/b.md, tests/**"):
            self.assertTrue(covers_tests_tree(decl), msg=decl)

    def test_specific_test_file_is_not_tree(self) -> None:
        # নির্দিষ্ট টেস্ট-ফাইল গাছের কভারেজ নয় — ভবিষ্যৎ ফাইলের জন্য গাছই লাগবে
        self.assertFalse(covers_tests_tree("src/a.py, tests/test_x.py"))

    def test_empty_and_none(self) -> None:
        self.assertFalse(covers_tests_tree(""))
        self.assertFalse(covers_tests_tree(None))  # type: ignore[arg-type]


class TestCompose(unittest.TestCase):
    def test_empty_falls_back_to_rule2(self) -> None:
        self.assertEqual(compose(""), FALLBACK_DECLARATION)
        self.assertEqual(compose(None), FALLBACK_DECLARATION)
        self.assertEqual(compose("   "), FALLBACK_DECLARATION)

    def test_plain_declaration_appends_tests_tree(self) -> None:
        self.assertEqual(
            compose("src/a.py, docs/b.md"),
            f"src/a.py, docs/b.md, tests/{AUTO_ANNOTATION}",
        )

    def test_tree_already_present_passthrough(self) -> None:
        for decl in ("src/a.py, tests/", "tests/**", "src/a.py, `tests/`"):
            self.assertEqual(compose(decl), decl, msg=decl)

    def test_specific_test_file_still_gets_tree(self) -> None:
        out = compose("src/a.py, tests/test_x.py")
        self.assertIn("tests/test_x.py", out)
        self.assertIn("tests/", out)
        self.assertNotEqual(out, "src/a.py, tests/test_x.py")  # গাছ যোগ হয়েছে

    def test_scope_gate_harvest_strips_annotation(self) -> None:
        # gates.py parse_declared_files-এর চুক্তি: `(...)` স্ট্রিপের পরেও
        # টোকেন `tests/` (trailing-slash directory-declaration) অক্ষত থাকে
        line = compose("src/a.py")
        segment = line  # full line == declaration content
        stripped = re.sub(r"\([^)]*\)", " ", segment)
        tokens = [t for t in re.split(r"[,\s]+", stripped) if t]
        self.assertIn("src/a.py", tokens)
        self.assertIn("tests/", tokens)

    def test_fallback_is_italic_prose_not_path(self) -> None:
        # খালি ঘোষণায় ফলব্যাক ইটালিক প্রসেঙ্গ — gate-এর harvest এটাকে
        # path হিসেবে নেবে না (আগের আচরণের byte-exact ধারাবাহিকতা)
        self.assertTrue(FALLBACK_DECLARATION.startswith("_("))
        self.assertNotIn("tests/", FALLBACK_DECLARATION)


class TestGroupBoundaryExemption(unittest.TestCase):
    """STEP 4.5-এর inline GROUP_BOUNDARY_PY (#2378) — overlap_pair-এর #2464 exemption।

    atomic_claim.sh-এর heredoc ব্লক থেকে `def norm` → `my_files =`-এর আগ
    পর্যন্ত ফাংশন-স্লাইস exec করা হয় (env-dependent অংশ বাদ)।
    """

    @classmethod
    def setUpClass(cls) -> None:
        src = (REPO_ROOT / "scripts" / "ci" / "atomic_claim.sh").read_text(encoding="utf-8")
        start = src.index("def norm(p):")
        end = src.index("\nmy_files = harvest(")
        block = src[start:end]
        cls.ns: dict = {}
        exec(compile(block, "<GROUP_BOUNDARY_PY-slice>", "exec"), cls.ns)  # noqa: S102
        cls.overlap_pair = staticmethod(cls.ns["overlap_pair"])

    def test_tree_vs_specific_file_exempt(self) -> None:
        # sibling-এর auto `tests/` vs আমার নির্দিষ্ট টেস্ট-ফাইল — ভুল কলিশন নয়
        self.assertIsNone(self.overlap_pair({"tests/test_a.py"}, {"src/b.py", "tests"}))
        self.assertIsNone(self.overlap_pair({"src/b.py", "tests"}, {"tests/test_a.py"}))

    def test_same_file_collision_still_caught(self) -> None:
        hit = self.overlap_pair({"tests/test_a.py"}, {"src/b.py", "tests/test_a.py"})
        self.assertIsNotNone(hit)
        self.assertEqual(hit, ("tests/test_a.py", "tests/test_a.py"))

    def test_non_tests_tree_match_unchanged(self) -> None:
        # `src` গাছের টোকেনের বিপরীতে src-ফাইল — exemption নয়, কলিশনই থাকে
        hit = self.overlap_pair({"src/deep/x.py"}, {"src"})
        self.assertIsNotNone(hit)

    def test_disjoint_files_no_collision(self) -> None:
        self.assertIsNone(self.overlap_pair({"src/a.py"}, {"docs/b.md", "tests"}))


class TestCliSmoke(unittest.TestCase):
    def test_cli_offline(self) -> None:
        proc = subprocess.run(  # returncode নিজেই assert করি — check=False explicit (PLW1510)
            [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "compose_touching_declaration.py"),
             "--files", "src/a.py"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("tests/", proc.stdout)
        self.assertIn("#2464", proc.stdout)


if __name__ == "__main__":
    unittest.main()
