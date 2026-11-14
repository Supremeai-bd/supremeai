"""Unit tests for SupremeAI Tiny Brain PR Guard."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import tiny_brain_pr_guard as guard  # noqa: E402


class TestTinyBrainGuard(unittest.TestCase):
    def test_forbidden_path(self) -> None:
        self.assertTrue(guard.is_forbidden_path("gateway/middleware/auth.py"))
        self.assertTrue(guard.is_forbidden_path(".github/workflows/unified-pipeline.yml"))
        self.assertTrue(guard.is_forbidden_path("scripts/ci/ai_pr_evaluator.py"))
        self.assertFalse(guard.is_forbidden_path("README.md"))

    def test_tier1_violations(self) -> None:
        v = guard.tier1_violations(["README.md", "gateway/middleware/x.py"], {"additions": 5})
        self.assertIn("gateway/middleware/x.py", v)

    def test_diff_size_floor(self) -> None:
        v = guard.tier1_violations(["README.md"], {"additions": 600})
        self.assertTrue(any("diff_size_floor" in x for x in v))

    def test_evaluate_low_risk_auto_approve(self) -> None:
        class FakeApi:
            def __init__(self):
                self.calls = []
            def __call__(self, endpoint, method="GET", payload=None):
                self.calls.append((endpoint, method))
                if endpoint.endswith("/pulls/1"):
                    return {"number": 1, "head": {"sha": "abc"}, "additions": 5, "deletions": 1, "files": [{"path": "README.md"}]}
                if endpoint.endswith("/pulls/1/files?per_page=100"):
                    return [{"path": "README.md"}]
                if "check-runs" in endpoint:
                    return {"check_runs": [{"name": "t", "status": "completed", "conclusion": "success"}]}
                if endpoint.endswith("/environments"):
                    return {"environments": [{"name": "production", "id": 7}]}
                if "pending_deployments" in endpoint:
                    return {"ok": True}
                if "comments" in endpoint:
                    return {"ok": True}
                return {}

        api = FakeApi()

        def fake_brain(pr_number, files, diff_stats, ci_status, url, token, timeout=8):
            return {"verdict": "AUTO_MERGE", "confidence": 0.98, "reasoning": "ok"}

        orig = guard.call_tiny_brain
        guard.call_tiny_brain = fake_brain
        try:
            r = guard.evaluate(1, run_id=9, api=api, dry_run=False)
        finally:
            guard.call_tiny_brain = orig
        self.assertEqual(r["verdict"], "AUTO_MERGE")

    def test_evaluate_brain_unreachable_fail_closed(self) -> None:
        class FakeApi:
            def __call__(self, endpoint, method="GET", payload=None):
                if endpoint.endswith("/pulls/2"):
                    return {"number": 2, "head": {"sha": "abc"}, "additions": 5, "deletions": 1, "files": [{"path": "README.md"}]}
                if endpoint.endswith("/pulls/2/files?per_page=100"):
                    return [{"path": "README.md"}]
                if "check-runs" in endpoint:
                    return {"check_runs": [{"name": "t", "status": "completed", "conclusion": "success"}]}
                if "comments" in endpoint:
                    return {"ok": True}
                return {}

        api = FakeApi()

        def fake_brain(*a, **k):
            return None

        orig = guard.call_tiny_brain
        guard.call_tiny_brain = fake_brain
        try:
            r = guard.evaluate(2, run_id=9, api=api, dry_run=False)
        finally:
            guard.call_tiny_brain = orig
        self.assertEqual(r["verdict"], "HUMAN_REVIEW")
        self.assertEqual(r["reason"], "brain_unreachable")


if __name__ == "__main__":
    unittest.main()
