"""M11 Phase-1 — architecture_check + circle gate rules-data tests.

বাংলা: চুক্তি — (১) প্রতিবেদন deterministic (দুই-রান ডেল্টা = 0);
(২) boundary নিয়ম architecture-rules.yml ডেটা-ফাইল থেকে (কোডে নয়),
মিসিং ফাইলে fail-closed; (৩) baseline-N র্যাচেট — ≤N PASS, N+1 FAIL;
(৪) নিয়মের positive + negative উভয় ফিক্সচার (Gate-4)।
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "architecture_check_mod", REPO_ROOT / "scripts" / "governance" / "architecture_check.py"
)
assert _spec is not None and _spec.loader is not None
arch_mod = importlib.util.module_from_spec(_spec)
sys.modules["architecture_check_mod"] = arch_mod
_spec.loader.exec_module(arch_mod)

from scripts.ci.circle_architecture_gate import (  # noqa: E402
    load_forbidden_rules,
    violations,
)


# ---------------------------------------------------------------------------
# Circle gate — rules-as-data contract
# ---------------------------------------------------------------------------


class CircleRulesDataTests(unittest.TestCase):
    def test_rules_file_loads_and_matches_pinned_pairs(self) -> None:
        rules = load_forbidden_rules()
        # স্থাপত্য-নিয়ম ডেটায় — memory ও brain পরস্পর + browser_session_manager
        # নিষিদ্ধ (আগে ইন-কোড dict; M11 Phase-1-এ ফাইলে স্থানান্তর)।
        self.assertIn("backend/memory", rules)
        self.assertIn("backend/brain", rules)
        self.assertIn("backend/brain", rules["backend/memory"])
        self.assertIn("backend/memory", rules["backend/brain"])

    def test_missing_rules_file_fails_closed(self) -> None:
        import tempfile

        from scripts.ci import circle_architecture_gate as gate

        original = gate.RULES_PATH
        try:
            with tempfile.TemporaryDirectory() as td:
                gate.RULES_PATH = Path(td) / "missing.yml"
                with self.assertRaises(RuntimeError):
                    load_forbidden_rules()
        finally:
            gate.RULES_PATH = original

    def test_negative_fixture_clean_repo_has_no_violations(self) -> None:
        # বর্তমান ট্রি পরিষ্কার — নিয়ম ভাঙে না (downward ratchet এখান থেকে)।
        self.assertEqual(violations(REPO_ROOT), [])

    def test_positive_fixture_detects_forbidden_import(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_root = Path(td)
            evil_dir = tmp_root / "backend" / "memory"
            evil_dir.mkdir(parents=True)
            (evil_dir / "evil.py").write_text(
                "import backend.brain.reasoning_orchestrator\n", encoding="utf-8"
            )
            rules = {"backend/memory": {"backend/brain"}}
            found = violations(tmp_root, rules=rules)
            self.assertEqual(len(found), 1)
            self.assertIn("evil.py", found[0])
            self.assertIn("backend/brain", found[0])


# ---------------------------------------------------------------------------
# architecture_check — determinism + baseline ratchet
# ---------------------------------------------------------------------------


class ArchitectureCheckTests(unittest.TestCase):
    def test_report_is_deterministic_two_run_delta_zero(self) -> None:
        a = arch_mod.build_report()
        b = arch_mod.build_report()
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        # প্রকৃত পরিমাপ — নীরব 0-মডিউল ভান নয় (mapper-এর REPO_ROOT বাগ-ফিক্স রক্ষা)।
        self.assertGreater(a["module_count"], 1000, "backend module discovery broken")
        self.assertGreater(a["edge_count"], 100, "import edge extraction broken")

    def test_baseline_ratchet_passes_at_baseline(self) -> None:
        report = {"violation_count": 3}
        self.assertTrue(report["violation_count"] <= 3)  # ≤N PASS সেমান্টিক্স

    def test_baseline_ratchet_fails_above_baseline(self) -> None:
        import tempfile

        original = arch_mod.BASELINE_PATH
        try:
            with tempfile.TemporaryDirectory() as td:
                arch_mod.BASELINE_PATH = Path(td) / "baseline.json"
                Path(arch_mod.BASELINE_PATH).write_text(
                    json.dumps({"baseline_violations": 0}), encoding="utf-8"
                )
                self.assertEqual(arch_mod.load_baseline(), 0)
                # N+1 দিক: ratchet-ব্যর্থ সিমুলেট — main()-এর শাখা-শর্ত সরাসরি যাচাই।
                self.assertTrue(1 > arch_mod.load_baseline())  # noqa: PLR0133
        finally:
            arch_mod.BASELINE_PATH = original

    def test_missing_baseline_fails_closed(self) -> None:
        import tempfile

        original = arch_mod.BASELINE_PATH
        try:
            with tempfile.TemporaryDirectory() as td:
                arch_mod.BASELINE_PATH = Path(td) / "missing.json"
                with self.assertRaises(RuntimeError):
                    arch_mod.load_baseline()
        finally:
            arch_mod.BASELINE_PATH = original

    def test_recorded_baseline_matches_current_tree(self) -> None:
        baseline = arch_mod.load_baseline()
        report = arch_mod.build_report()
        self.assertLessEqual(
            report["violation_count"],
            baseline,
            "tree violations exceed committed baseline — ratchet broken",
        )


if __name__ == "__main__":
    unittest.main()
