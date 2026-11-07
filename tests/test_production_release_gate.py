#!/usr/bin/env python3
"""Unit tests for scripts/ci/production_release_gate.py (Phase 5)."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ci.production_release_gate import (
    REQUIRED_FIELDS,
    evaluate_all,
    main,
    render_markdown_report,
    self_test,
)


class TestProductionReleaseGate(unittest.TestCase):
    def test_self_test_passes(self) -> None:
        self.assertEqual(self_test(), 0)

    def test_evaluate_all_passes_on_live_repo(self) -> None:
        report = evaluate_all()
        self.assertTrue(report["all_passed"], f"Failed capabilities: {report['capabilities']}")
        self.assertEqual(report["passed"], report["total"])
        for cap in report["capabilities"]:
            for field in REQUIRED_FIELDS:
                self.assertIn(field, cap)
                self.assertTrue(cap[field], f"Field {field} empty on {cap['capability_id']}")

    def test_render_markdown_contains_bangla_summary_and_table(self) -> None:
        report = evaluate_all()
        md = render_markdown_report(report)
        self.assertIn("সকাল ১০:০০টার হেলথ", md)
        self.assertIn("upstash-redis-pool", md)
        self.assertIn("autonomy-brain-loop", md)

    def test_cli_check_returns_zero(self) -> None:
        self.assertEqual(main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
