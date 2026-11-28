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
    monkeypatch.setenv("GROQ_API_KEY", "fallback-secret-fixture")
    for value in ("private-fixture-not-json", '["wrong-shape"]'):
        monkeypatch.setenv("LLM_PROVIDER_KEYS", value)
        assert verifier._get_api_providers() == []
        warning = capsys.readouterr().err
        assert "Invalid LLM provider pool" in warning
        assert "private-fixture" not in warning
        assert "wrong-shape" not in warning and "fallback-secret-fixture" not in warning
# ---------------------------------------------------------------------------
# API pool discovery — the pipeline AI provider must check every
# Infisical-exported key (base + numbered + alias + comma pool) until one
# returns a valid verdict.
# ---------------------------------------------------------------------------

_POOL_ENV_NAMES = ["LLM_PROVIDER_KEYS", "EVALUATOR_MAX_KEYS_PER_PROVIDER"]
for _fam in ("GEMINI", "GOOGLE", "GROQ", "OPENAI", "OPENROUTER", "DEEPSEEK", "MISTRAL"):
    _POOL_ENV_NAMES.append(f"{_fam}_API_KEY")
    _POOL_ENV_NAMES.extend(f"{_fam}_API_KEY_{i}" for i in range(2, 13))
    _POOL_ENV_NAMES.append(f"{_fam}_API_KEYS")


def _clean_pool_env(monkeypatch):
    for name in _POOL_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_api_pool_discovers_every_infisical_env_key(monkeypatch):
    from scripts.ci.ai_semantic_pr_verifier import _get_api_providers
    _clean_pool_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gem-base")
    monkeypatch.setenv("GEMINI_API_KEY_2", "gem-second")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-alias")
    monkeypatch.setenv("GROQ_API_KEY_3", "groq-third")
    monkeypatch.setenv("GROQ_API_KEYS", "groq-a,groq-b")
    providers = _get_api_providers()
    # Each key is emitted once per model in the family's fallback chain, so an
    # exhausted model on a healthy key is retried on the next model.
    assert [(p["name"], p["key"], p["slot"]) for p in providers] == [
        ("gemini", "gem-base", "GEMINI_API_KEY"),
        ("gemini", "gem-second", "GEMINI_API_KEY_2"),
        ("gemini", "google-alias", "GOOGLE_API_KEY"),
        ("gemini", "gem-base", "GEMINI_API_KEY"),
        ("gemini", "gem-second", "GEMINI_API_KEY_2"),
        ("gemini", "google-alias", "GOOGLE_API_KEY"),
        ("groq", "groq-third", "GROQ_API_KEY_3"),
        ("groq", "groq-a", "GROQ_API_KEYS"),
        ("groq", "groq-b", "GROQ_API_KEYS"),
        ("groq", "groq-third", "GROQ_API_KEY_3"),
        ("groq", "groq-a", "GROQ_API_KEYS"),
        ("groq", "groq-b", "GROQ_API_KEYS"),
    ]
    gemini_models = [p["model"] for p in providers if p["name"] == "gemini"]
    assert gemini_models[:3] == ["gemini-flash-lite-latest"] * 3
    assert gemini_models[3:] == ["gemini-2.5-flash"] * 3
    assert all(p["url"] and p["model"] for p in providers)


def test_api_pool_json_entries_come_first_and_dedup_env_keys(monkeypatch):
    import json

    from scripts.ci.ai_semantic_pr_verifier import _get_api_providers
    _clean_pool_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER_KEYS", json.dumps({"groq": ["pool-key-1"]}))
    monkeypatch.setenv("GROQ_API_KEY", "pool-key-1")  # same value as the pool JSON
    monkeypatch.setenv("GEMINI_API_KEY", "env-gem")
    providers = _get_api_providers()
    # JSON entries carry their own explicit model (no fallback chain); env
    # keys are retried on every model in the family chain.
    assert [(p["name"], p["key"]) for p in providers] == [
        ("groq", "pool-key-1"),
        ("gemini", "env-gem"),
        ("gemini", "env-gem"),
        # the shared value surfaces again as the groq env key's fallback-model retry
        ("groq", "pool-key-1"),
    ]
    assert providers[0]["slot"] == "LLM_PROVIDER_KEYS[groq]"


def test_evaluator_max_keys_per_provider_caps_each_family(monkeypatch):
    from scripts.ci.ai_semantic_pr_verifier import _get_api_providers
    _clean_pool_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "g2")
    monkeypatch.setenv("GEMINI_API_KEY_3", "g3")
    monkeypatch.setenv("GROQ_API_KEY", "q1")
    monkeypatch.setenv("EVALUATOR_MAX_KEYS_PER_PROVIDER", "2")
    providers = _get_api_providers()
    # The cap limits keys tried per provider per model pass, so both gemini
    # keys still appear once for each model in the family chain.
    assert [p["key"] for p in providers] == ["g1", "g2", "g1", "g2", "q1", "q1"]


def test_provider_pool_checks_keys_until_one_is_valid(monkeypatch, capsys):
    from scripts.ci import ai_semantic_pr_verifier as verifier
    monkeypatch.setenv("SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF", "true")
    valid = '{"approved": true, "security_verdict": "PASS", "anti_bloat_verdict": "PASS"}'
    responses = iter([None, valid])
    with patch.object(verifier, "_get_api_providers", return_value=[
            {"name": "groq", "key": "bad-key", "slot": "GROQ_API_KEY"},
            {"name": "gemini", "key": "good-key", "slot": "GEMINI_API_KEY"},
    ]), \
         patch.object(verifier, "call_llm_provider",
                      side_effect=lambda prov, prompt: next(responses)):
        verdict = run_semantic_verification(["core/security/auth.py"], "+change")
    assert verdict["approved"] is True
    assert verdict["confidence"] == "llm-verified (gemini)"
    out = capsys.readouterr().out
    assert "Checking key 1/2" in out and "Checking key 2/2" in out
    assert "Valid API key found on attempt 2/2" in out
    # Key material must never reach the logs.
    assert "bad-key" not in out and "good-key" not in out


def test_provider_pool_reports_total_when_no_key_is_valid(monkeypatch, capsys):
    from scripts.ci import ai_semantic_pr_verifier as verifier
    monkeypatch.setenv("SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF", "true")
    with patch.object(verifier, "_get_api_providers", return_value=[
            {"name": "groq", "key": "k1"}, {"name": "openai", "key": "k2"},
    ]), \
         patch.object(verifier, "call_llm_provider", return_value=None):
        verdict = run_semantic_verification(["core/security/auth.py"], "+change")
    assert verdict["approved"] is False and verdict["confidence"] == "unverified"
    out = capsys.readouterr().out
    assert "2 provider key(s) checked" in out


def test_evaluator_providers_cover_numbered_and_alias_keys(monkeypatch):
    from scripts.ci.ai_pr_evaluator import _llm_providers
    _clean_pool_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY_2", "groq-second")  # base unset — old code crashed here
    monkeypatch.setenv("GROQ_API_KEYS", "q-pool-1, q-pool-2")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-alias")
    providers = _llm_providers()
    assert [(p["name"], p["key"]) for p in providers] == [
        ("groq", "groq-second"),
        ("groq", "q-pool-1"),
        ("groq", "q-pool-2"),
        ("gemini", "google-alias"),
    ]


def test_large_diff_still_checks_secrets_without_disclosing_them(monkeypatch):
    from scripts.ci import ai_semantic_pr_verifier as verifier
    secret = "sk-" + "x" * 30
    diff = "+" + "padding" * verifier.DIFF_CHAR_LIMIT + "\n+" + secret
    monkeypatch.setenv("SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF", "true")
    with patch.object(verifier, "call_llm_provider") as external:
        verdict = verifier.run_semantic_verification(["core/security/auth.py"], diff)
    assert not verdict["approved"] and verdict["security_verdict"] == "FAIL"
    assert verdict["confidence"] == "deterministic-regex"
    assert secret not in str(verdict)
    external.assert_not_called()


def test_unverified_verdict_is_not_misreported_as_a_confirmed_violation(monkeypatch, capsys):
    from scripts.ci import ai_semantic_pr_verifier as verifier
    monkeypatch.setattr(verifier.shutil, "which", lambda _: "/bin/gh")
    monkeypatch.setattr(verifier, "get_pr_files", lambda _: ["core/security/auth.py"])
    monkeypatch.setattr(verifier, "get_diff_text", lambda *_a, **_k: "+" + "x" * verifier.DIFF_CHAR_LIMIT)
    monkeypatch.setattr("sys.argv", ["verifier", "--pr", "123"])
    assert verifier.main() == 1
    out = capsys.readouterr().out
    assert "semantic review incomplete" in out
    assert "high-risk PR remains unverified" in out
    assert "High-risk violations must be resolved" not in out
