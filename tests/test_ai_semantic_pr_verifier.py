"""Unit tests for SupremeAI AI Semantic PR Verifier Gate."""

from __future__ import annotations

import unittest
from unittest.mock import patch

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
        with patch("scripts.ci.ai_semantic_pr_verifier._get_api_providers", return_value=[]):
            verdict = run_semantic_verification(files, diff)
        self.assertFalse(verdict["approved"])
        self.assertEqual(verdict["security_verdict"], "UNKNOWN")

    def test_missing_diff_never_approves(self) -> None:
        verdict = run_semantic_verification(["core/security/auth.py"], "")
        self.assertFalse(verdict["approved"])
        self.assertEqual(verdict["confidence"], "unverified")

    def test_inconsistent_llm_verdict_does_not_approve(self) -> None:
        with patch.dict("os.environ", {"SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF": "true"}), \
             patch("scripts.ci.ai_semantic_pr_verifier._get_api_providers", return_value=[{"name": "fixture", "model": "m"}]), \
             patch("scripts.ci.ai_semantic_pr_verifier.call_llm_provider", return_value='{"approved": true, "security_verdict": "FAIL", "anti_bloat_verdict": "PASS"}'):
            verdict = run_semantic_verification(["core/security/auth.py"], "+change")
        self.assertFalse(verdict["approved"])

    def test_invalid_boolean_does_not_approve(self) -> None:
        with patch.dict("os.environ", {"SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF": "true"}), \
             patch("scripts.ci.ai_semantic_pr_verifier._get_api_providers", return_value=[{"name": "fixture", "model": "m"}]), \
             patch("scripts.ci.ai_semantic_pr_verifier.call_llm_provider", return_value='{"approved": "false", "security_verdict": "PASS", "anti_bloat_verdict": "PASS"}'):
            verdict = run_semantic_verification(["core/security/auth.py"], "+change")
        self.assertFalse(verdict["approved"])


if __name__ == "__main__":
    unittest.main()


def test_oversized_diff_is_unverified():
    from scripts.ci.ai_semantic_pr_verifier import DIFF_CHAR_LIMIT
    verdict = run_semantic_verification(["core/security/auth.py"], "+x" * DIFF_CHAR_LIMIT)
    assert verdict["approved"] is False and verdict["confidence"] == "unverified"


def test_pr_diff_failure_never_uses_unrelated_local_diff():
    from subprocess import CompletedProcess
    from scripts.ci import ai_semantic_pr_verifier as verifier
    with patch.object(verifier, "run_cmd", return_value=CompletedProcess([], 1, "", "unavailable")) as cmd:
        assert verifier.get_diff_text(["core/security/auth.py"], pr_number="123") == ""
    assert cmd.call_args.args[0] == ["gh", "pr", "diff", "123"]


def test_failed_pr_file_lookup_does_not_fall_back_to_base_checkout(monkeypatch):
    from subprocess import CompletedProcess
    from scripts.ci import ai_semantic_pr_verifier as verifier
    monkeypatch.setattr(verifier.shutil, "which", lambda _: "/bin/gh")
    monkeypatch.setattr(verifier, "run_cmd", lambda _: CompletedProcess([], 1, "", "error"))
    monkeypatch.setattr(verifier, "get_changed_files_from_git", lambda: ["README.md"])
    monkeypatch.setattr("sys.argv", ["verifier", "--pr", "123"])
    assert verifier.main() == 1


def test_pr_file_count_and_renamed_sensitive_path(monkeypatch):
    from subprocess import CompletedProcess
    from scripts.ci import ai_semantic_pr_verifier as verifier
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    commands = iter([
        CompletedProcess([], 0, "1\n", ""),
        CompletedProcess([], 0, '{"filename":"docs/new.md","previous_filename":"core/security/auth.py"}\n', ""),
    ])
    monkeypatch.setattr(verifier, "run_cmd", lambda _: next(commands))
    assert verifier.classify_pr_risk(verifier.get_pr_files("123"))[0] == "HIGH"
    commands = iter([CompletedProcess([], 0, "2\n", ""), CompletedProcess([], 0, '{"filename":"docs/new.md"}\n', "")])
    assert verifier.get_pr_files("123") == []


def test_no_external_diff_or_paid_calls_by_default(monkeypatch):
    monkeypatch.delenv("SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF", raising=False)
    with patch("scripts.ci.ai_semantic_pr_verifier.call_llm_provider") as call:
        verdict = run_semantic_verification(["core/security/auth.py"], "+safe change")
    assert not verdict["approved"]
    call.assert_not_called()


def test_secret_pattern_does_not_echo_secret():
    secret = "sk-" + "x" * 30
    assert secret not in str(scan_regex_secrets('+token = "' + secret + '"'))


def test_invalid_pool_fails_closed_without_disclosing_configuration(monkeypatch, capsys):
    from scripts.ci import ai_semantic_pr_verifier as verifier
    monkeypatch.setenv("LLM_PROVIDER_KEYS", "private-fixture-not-json")
    assert verifier._get_api_providers() == []
    warning = capsys.readouterr().err
    assert "Invalid LLM provider pool" in warning
    assert "private-fixture" not in warning
