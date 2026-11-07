"""Unit tests for SupremeAI AI Semantic PR Verifier Gate."""

from __future__ import annotations

import unittest
from scripts.ci.ai_semantic_pr_verifier import (
    classify_pr_risk,
    is_high_risk_file,
    parse_llm_verdict,
    run_semantic_verification,
    scan_regex_secrets,
)


class TestAiSemanticPrVerifier(unittest.TestCase):
    def test_high_risk_detection(self) -> None:
        high_risk_paths = [
            "core/security/auth.py",
            "core/security/secret_vault.py",
            "core/api/routes/auth.py",
            "core/api/routes/keys.py",
            "infrastructure/supabase/migrations/20261101_init.sql",
            "migrations/001_initial.py",
            "core/db.py",
            "core/config.py",
            ".github/workflows/unified-pipeline.yml",
        ]
        for path in high_risk_paths:
            self.assertTrue(is_high_risk_file(path), f"Expected {path} to be HIGH RISK")

    def test_low_risk_detection(self) -> None:
        low_risk_paths = [
            "README.md",
            "docs/PR_TO_PRODUCTION_LIFECYCLE.md",
            "studio/src/App.tsx",
            "browser/src/index.ts",
            "tests/test_basic.py",
            "package.json",
        ]
        for path in low_risk_paths:
            self.assertFalse(is_high_risk_file(path), f"Expected {path} to be LOW RISK")

    def test_classify_pr_risk_mixed(self) -> None:
        files = ["README.md", "core/security/jwt.py", "docs/index.md"]
        risk, risky = classify_pr_risk(files)
        self.assertEqual(risk, "HIGH")
        self.assertEqual(risky, ["core/security/jwt.py"])

    def test_classify_pr_risk_all_low(self) -> None:
        files = ["README.md", "studio/components/Button.tsx"]
        risk, risky = classify_pr_risk(files)
        self.assertEqual(risk, "LOW")
        self.assertEqual(risky, [])

    def test_scan_regex_secrets(self) -> None:
        safe_diff = "+# Just a comment\n+def foo(): return 42"
        self.assertEqual(scan_regex_secrets(safe_diff), [])

        dirty_diff = '+service_role_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token_value_here"'
        hits = scan_regex_secrets(dirty_diff)
        self.assertTrue(len(hits) > 0, "Expected secret pattern hit")

    def test_parse_llm_verdict(self) -> None:
        raw_valid = 'Here is the review:\n{"approved": true, "security_verdict": "PASS", "anti_bloat_verdict": "PASS"}\nThanks'
        parsed = parse_llm_verdict(raw_valid)
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.get("approved"))
        self.assertEqual(parsed.get("security_verdict"), "PASS")

        raw_invalid = "Sorry, I cannot answer."
        self.assertIsNone(parse_llm_verdict(raw_invalid))

    def test_run_semantic_verification_fallback(self) -> None:
        files = ["core/security/auth.py"]
        diff = "+# clean security patch\n+def verify_token(): pass"
        verdict = run_semantic_verification(files, diff)
        self.assertIn("approved", verdict)
        self.assertTrue(verdict["approved"])
        self.assertEqual(verdict["security_verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
