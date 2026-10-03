"""#3032 (P0) — Test Evidence integrity regression tests.

বাংলা মন্তব্য: auto-heal আর কখনো PR বডিতে ভুয়া evidence লিখতে পারবে না এবং
"0 failed" রেজেক্স ছাড়া "10 failed"-এর ভেতরে ম্যাচ করে ভুলভাবে প্রমাণ গণ্য
হবে না — এই দুটি ভাঙন এই টেস্টগুলো চিরকালের জন্য আটকে রাখে।
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Base3032(unittest.TestCase):
    """Shared: load both target modules fresh (no package import path games)."""

    @classmethod
    def setUpClass(cls):
        cls.merger = _load_module_from(
            ROOT / "scripts" / "ci" / "smart_priority_merger.py",
            "spm_3032",
        )
        gates_init = ROOT / ".github" / "scripts" / "constitution" / "gates.py"
        # constitution package imports are relative — load gates.py standalone
        cls.gates = _load_module_from(gates_init, "gates_3032")
        cls.gate_policy = dict(cls.gates.DEFAULT_VERIFICATION_POLICY)


class FabricatedLineRejectedTests(_Base3032):
    FABRICATED = (
        "- Automated verification evidence: pytest passed "
        "(100% all tests passed and verified)"
    )

    def test_merger_rejects_fabricated_line_only(self):
        body = "## Test Evidence\n" + self.FABRICATED + "\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertFalse(ok, "fabricated evidence line must not validate")

    def test_gates_reject_fabricated_line_only(self):
        body = "## Test Evidence\n" + self.FABRICATED + "\n"
        ok, _ = self.gates.extract_test_evidence(body, self.gate_policy)
        self.assertFalse(ok, "fabricated evidence line must not validate the gate")


class SubstringMarkerHoleTests(_Base3032):
    def test_10_failed_is_not_evidence(self):
        body = "## Test Evidence\n$ pytest -q backend/tests\n10 failed, 2 passed in 8.2s\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertFalse(ok)
        ok, _ = self.gates.extract_test_evidence(body, self.gate_policy)
        self.assertFalse(ok)

    def test_100_failed_is_not_evidence(self):
        body = "## Test Evidence\n$ pytest -q backend/tests\n100 failed in 8.2s\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertFalse(ok)

    def test_zero_failed_is_evidence(self):
        body = "## Test Evidence\n$ pytest -q backend/tests\n42 passed, 0 failed in 8.2s\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertTrue(ok)

    def test_not_passed_is_not_evidence(self):
        body = "## Test Evidence\nthe suite did not pass in this run — needs investigation\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertFalse(ok)

    def test_zero_passed_is_not_evidence(self):
        body = "## Test Evidence\n$ pytest -q\n0 passed, 5 failed in 1.2s\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertFalse(ok)

    def test_real_passed_count_still_validates(self):
        body = "## Test Evidence\n$ pytest -q backend/tests\n42 passed in 1.2s\n"
        ok, _ = self.merger.check_pr_evidence(body)
        self.assertTrue(ok)

    def test_real_pytest_command_still_validates(self):
        body = "## Test Evidence\n$ pytest backend/tests -q\nall green — suite finished successfully with no failures\n"
        ok, _ = self.gates.extract_test_evidence(body, self.gate_policy)
        self.assertTrue(ok)


class HealNeverFabricatesTests(_Base3032):
    def test_heal_returns_body_unchanged(self):
        for body in (
            "## Test Evidence\n(no markers here)\n",
            "no heading at all",
            "",
        ):
            self.assertEqual(
                self.merger.heal_pr_body_evidence(body),
                body,
                "heal must never mutate the body (#3032)",
            )

    def test_heal_cannot_inject_marker(self):
        body = "## Test Evidence\nplaceholder\n"
        out = self.merger.heal_pr_body_evidence(body)
        ok, _ = self.merger.check_pr_evidence(out)
        self.assertFalse(ok, "post-heal body must still fail evidence check")

    def test_auto_heal_short_circuit_no_evidence_path_returns_false(self):
        # evidence valid → heal returns False (nothing to do) — no network path
        body = "## Test Evidence\n$ pytest -q\n42 passed, 0 failed in 8.2s\n"
        self.assertFalse(self.merger.auto_heal_pr_evidence(999999, body))


class RegexSanityTests(unittest.TestCase):
    def test_word_boundary_on_zero_failed(self):
        pat = re.compile(r"\b0 failed\b", re.IGNORECASE)
        self.assertIsNone(pat.search("10 failed"))
        self.assertIsNone(pat.search("100 failed"))
        self.assertIsNotNone(pat.search("0 failed"))

    def test_passed_lookbehind(self):
        pat = re.compile(r"(?<!not )(?<!\b0 )\bpassed\b", re.IGNORECASE)
        self.assertIsNone(pat.search("not passed"))
        self.assertIsNone(pat.search("0 passed"))
        self.assertIsNotNone(pat.search("42 passed"))


if __name__ == "__main__":
    unittest.main()
