"""Full-coverage tests for core.security.scanning.secret_scanner (SecretHunter).

All LLM interaction is mocked (AISecretAnalyzer.gateway is an AsyncMock);
filesystem scans use tmp_path. No network, no real gitleaks binary.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import core.security.scanning.secret_scanner as ss_module
from core.security.scanning.secret_scanner import (
    AISecretAnalyzer,
    GitleaksRunner,
    SecretFinding,
    SecretHunter,
    SecretReport,
)

pytestmark = pytest.mark.security

AWS_LINE = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n'
OPENAI_LINE = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w3X4" + "\n"
MOCK_AWS_KEY = "".join(["AK", "IA", "IOSFODNN7EXAMPLE"])
MOCK_PRIVATE_KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----\n"
MOCK_JWT_LINE = "jwt_" + 'secret = "myjwtsecretvalue"\n'
MOCK_PASS_LINE = "pass" + 'word = "hunter2ish"\n'


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    monkeypatch.setattr(
        ss_module, "settings", SimpleNamespace(gemini_model_name="gemini-test-model")
    )


def make_finding(**overrides):
    base = dict(
        rule_id="aws-access-key",
        file_path="/tmp/src/config.py",
        line_number=3,
        column_start=0,
        column_end=20,
        matched_text=MOCK_AWS_KEY,
        secret_type="AWS Access Key ID",
        severity="critical",
        remediation="Remove it",
        ai_confidence=0.0,
    )
    base.update(overrides)
    return SecretFinding(**base)


class TestSecretFinding:
    def test_fields(self):
        finding = make_finding()
        assert finding.severity == "critical"
        assert finding.ai_confidence == 0.0


class TestSecretReport:
    def test_to_dict_empty(self):
        report = SecretReport(scan_id="scan-1", scanned_at="2026-01-01T00:00:00+00:00")
        data = report.to_dict()
        assert data["scan_id"] == "scan-1"
        assert data["findings_count"] == 0
        assert data["findings"] == []
        assert data["summary"] == {}

    def test_to_dict_with_findings_and_truncation(self):
        long_text = "X" * 80
        report = SecretReport(
            scan_id="scan-2",
            scanned_at="2026-01-01T00:00:00+00:00",
            total_files=5,
            findings=[make_finding(matched_text=long_text), make_finding(matched_text="short")],
            summary={"critical_count": 2},
        )
        data = report.to_dict()
        assert data["total_files"] == 5
        assert data["findings_count"] == 2
        first = data["findings"][0]
        assert first["matched_text"] == "X" * 50 + "..."
        assert data["findings"][1]["matched_text"] == "short"
        assert data["summary"] == {"critical_count": 2}


class TestGitleaksRunner:
    def test_all_patterns_compile(self):
        runner = GitleaksRunner()
        assert set(runner.compiled_patterns) == set(runner.PATTERNS)

    def test_bad_pattern_is_skipped_with_warning(self, monkeypatch):
        monkeypatch.setitem(
            GitleaksRunner.PATTERNS,
            "intentionally-bad",
            {"regex": "([unclosed", "type": "Bad", "severity": "low"},
        )
        runner = GitleaksRunner()
        assert "intentionally-bad" not in runner.compiled_patterns
        assert "aws-access-key" in runner.compiled_patterns

    def test_scan_file_detects_multiple_secret_types(self, tmp_path):
        target = tmp_path / "config.py"
        target.write_text(
            MOCK_AWS_KEY
            + "\n"  # aws-access-key
            + AWS_LINE  # aws-secret-key
            + 'api_key = "abcdefghijklmnop"\n'  # generic-api-key
            + MOCK_JWT_LINE  # jwt-secret
            + MOCK_PASS_LINE  # password-in-code
            + MOCK_PRIVATE_KEY_HEADER,  # private-key
            encoding="utf-8",
        )
        findings = GitleaksRunner().scan_file(target)
        rule_ids = {f.rule_id for f in findings}
        assert {
            "aws-access-key",
            "aws-secret-key",
            "generic-api-key",
            "jwt-secret",
            "password-in-code",
            "private-key",
        } <= rule_ids
        aws = next(f for f in findings if f.rule_id == "aws-access-key")
        assert aws.line_number == 1
        assert aws.severity == "critical"
        assert aws.secret_type == "AWS Access Key ID"
        assert "environment variables" in aws.remediation

    def test_scan_file_unreadable_returns_empty(self, tmp_path):
        missing = tmp_path / "ghost.py"
        assert GitleaksRunner().scan_file(missing) == []

    def test_scan_file_directory_path_returns_empty(self, tmp_path):
        # IsADirectoryError is an OSError -> caught -> []
        assert GitleaksRunner().scan_file(tmp_path) == []

    def test_scan_file_clean_file_no_findings(self, tmp_path):
        target = tmp_path / "clean.py"
        target.write_text("value = compute(1)\n", encoding="utf-8")
        assert GitleaksRunner().scan_file(target) == []

    def test_scan_directory_finds_secrets(self, tmp_path):
        (tmp_path / "secret.py").write_text(AWS_LINE, encoding="utf-8")
        findings = GitleaksRunner().scan_directory(tmp_path)
        assert len(findings) == 1
        assert findings[0].file_path.endswith("secret.py")

    def test_scan_directory_skips_hidden_tests_and_tmp(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "secret.py").write_text(AWS_LINE, encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "secret.py").write_text(AWS_LINE, encoding="utf-8")
        (tmp_path / "tmp_scratch").mkdir()
        (tmp_path / "tmp_scratch" / "secret.py").write_text(AWS_LINE, encoding="utf-8")
        (tmp_path / "test_module.py").write_text(AWS_LINE, encoding="utf-8")
        (tmp_path / "keep.py").write_text(AWS_LINE, encoding="utf-8")
        findings = GitleaksRunner().scan_directory(tmp_path)
        assert [f.file_path for f in findings] == [str(tmp_path / "keep.py")]

    def test_scan_directory_default_extensions_filter(self, tmp_path):
        (tmp_path / "notes.txt").write_text(AWS_LINE, encoding="utf-8")
        (tmp_path / "data.json").write_text(json.dumps({"k": MOCK_AWS_KEY}), encoding="utf-8")
        findings = GitleaksRunner().scan_directory(tmp_path)
        assert len(findings) == 1
        assert findings[0].file_path.endswith(".json")

    def test_scan_directory_custom_extensions(self, tmp_path):
        (tmp_path / "app.dart").write_text(AWS_LINE, encoding="utf-8")
        (tmp_path / "app.py").write_text(AWS_LINE, encoding="utf-8")
        findings = GitleaksRunner().scan_directory(tmp_path, extensions={".dart"})
        assert [f.file_path for f in findings] == [str(tmp_path / "app.dart")]

    def test_scan_directory_value_error_falls_back_to_full_parts(self, tmp_path, monkeypatch):
        outside = tmp_path.parent / "outside_secret.py"
        outside.write_text(AWS_LINE, encoding="utf-8")
        original_rglob = type(tmp_path).rglob

        def fake_rglob(self, pattern):
            # Yield a path that is NOT under the scan directory -> relative_to ValueError
            yield outside
            yield from original_rglob(self, pattern)

        monkeypatch.setattr(type(tmp_path), "rglob", fake_rglob)
        findings = GitleaksRunner().scan_directory(tmp_path)
        paths = {f.file_path for f in findings}
        assert str(outside) in paths

    def test_scan_directory_nonexistent_returns_empty(self, tmp_path):
        missing = tmp_path / "no-such-dir"
        assert GitleaksRunner().scan_directory(missing) == []


class TestAISecretAnalyzer:
    def _analyzer(self, content: str | None):
        analyzer = AISecretAnalyzer()
        message = MagicMock()
        message.content = content
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        analyzer.gateway = MagicMock()
        analyzer.gateway.acompletion = AsyncMock(return_value=response)
        return analyzer

    async def test_true_positive_updates_finding(self):
        payload = {
            "is_true_positive": True,
            "secret_type": "AWS root key",
            "severity": "critical",
            "confidence": 0.95,
            "remediation": "Rotate immediately",
        }
        analyzer = self._analyzer("```json\n" + json.dumps(payload) + "\n```")
        finding = make_finding()
        result = await analyzer.analyze_finding(finding, "context code")
        assert result is finding
        assert result.severity == "critical"
        assert result.secret_type == "AWS root key"
        assert result.remediation == "Rotate immediately"
        assert result.ai_confidence == 0.95

    async def test_false_positive_marks_info(self):
        payload = {"is_true_positive": False}
        analyzer = self._analyzer(json.dumps(payload))
        finding = make_finding()
        result = await analyzer.analyze_finding(finding, "ctx")
        assert result.severity == "info"
        assert result.ai_confidence == 0.0

    async def test_plain_json_without_code_fence(self):
        payload = {
            "is_true_positive": True,
            "severity": "high",
            "secret_type": "generic",
            "confidence": 0.7,
            "remediation": "fix",
        }
        analyzer = self._analyzer(json.dumps(payload))
        result = await analyzer.analyze_finding(make_finding(), "ctx")
        assert result.severity == "high"
        assert result.ai_confidence == 0.7

    async def test_none_content_falls_back_to_empty_object(self):
        analyzer = self._analyzer(None)
        finding = make_finding()
        result = await analyzer.analyze_finding(finding, "ctx")
        # "{}" -> is_true_positive defaults True, severity unchanged
        assert result.severity == "critical"

    async def test_invalid_json_sets_medium_confidence(self):
        analyzer = self._analyzer("this is not json at all")
        result = await analyzer.analyze_finding(make_finding(), "ctx")
        assert result.ai_confidence == 0.5

    async def test_attributeerror_in_response_sets_medium_confidence(self):
        # JSON array parses fine but .get() on a list raises AttributeError -> caught -> 0.5
        analyzer = self._analyzer(json.dumps([1, 2, 3]))
        result = await analyzer.analyze_finding(make_finding(), "ctx")
        assert result.ai_confidence == 0.5

    async def test_prompt_contains_context(self):
        analyzer = self._analyzer(json.dumps({"is_true_positive": False}))
        finding = make_finding(line_number=42, matched_text="TOKEN123")
        await analyzer.analyze_finding(finding, "the-code-context")
        prompt = analyzer.gateway.acompletion.call_args.kwargs["messages"][0]["content"]
        assert "the-code-context" in prompt
        assert "TOKEN123" in prompt
        assert "aws-access-key" in prompt
        assert "/tmp/src/config.py" in prompt
        assert analyzer.gateway.acompletion.call_args.kwargs["model"] == "gemini-test-model"


class TestSecretHunterScanCodebase:
    def _hunter(self, findings):
        hunter = SecretHunter()
        hunter.gitleaks = MagicMock()
        hunter.gitleaks.scan_directory.return_value = list(findings)
        hunter.ai_analyzer = MagicMock()
        hunter.ai_analyzer.analyze_finding = AsyncMock(side_effect=lambda f, c: f)
        return hunter

    async def test_missing_directory_raises(self, tmp_path):
        hunter = SecretHunter()
        with pytest.raises(FileNotFoundError):
            await hunter.scan_codebase(tmp_path / "nope")

    async def test_no_ai_filter_and_summary(self, tmp_path):
        hunter = self._hunter([make_finding(severity="critical"), make_finding(severity="medium")])
        (tmp_path / "config.py").write_text(AWS_LINE, encoding="utf-8")
        report = await hunter.scan_codebase(tmp_path, use_ai=False)
        hunter.gitleaks.scan_directory.assert_called_once_with(tmp_path)
        assert report.total_files >= 1
        assert report.summary["ai_validated"] is False
        assert report.summary["critical_count"] == 1
        assert report.summary["severity_distribution"] == {"critical": 1, "medium": 1}
        assert report.summary["type_distribution"] == {"AWS Access Key ID": 2}
        assert report.scan_id.startswith("secret-hunt-")

    async def test_ai_path_keeps_true_positive(self, tmp_path):
        hunter = self._hunter([make_finding()])
        target_file = tmp_path / "config.py"
        target_file.write_text(AWS_LINE, encoding="utf-8")
        finding = make_finding(file_path=str(target_file), line_number=1)
        hunter.gitleaks.scan_directory.return_value = [finding]
        report = await hunter.scan_codebase(tmp_path, use_ai=True)
        hunter.ai_analyzer.analyze_finding.assert_awaited_once()
        assert len(report.findings) == 1

    async def test_ai_path_drops_false_positive(self, tmp_path):
        hunter = self._hunter([make_finding()])

        async def mark_info(finding, context):
            finding.severity = "info"
            return finding

        hunter.ai_analyzer.analyze_finding = AsyncMock(side_effect=mark_info)
        report = await hunter.scan_codebase(tmp_path, use_ai=True)
        assert report.findings == []

    async def test_ai_path_context_oserror_falls_back_to_matched_text(self, tmp_path):
        hunter = self._hunter([make_finding()])
        # file_path points at a nonexistent file -> OSError -> context = matched_text
        finding = make_finding(file_path=str(tmp_path / "ghost.py"))
        hunter.gitleaks.scan_directory.return_value = [finding]

        async def capture(f, context):
            capture.context = context
            return f

        hunter.ai_analyzer.analyze_finding = AsyncMock(side_effect=capture)
        await hunter.scan_codebase(tmp_path, use_ai=True)
        assert capture.context == finding.matched_text

    async def test_ai_path_analyzer_exception_is_swallowed(self, tmp_path):
        hunter = self._hunter([make_finding()])
        hunter.ai_analyzer.analyze_finding = AsyncMock(side_effect=TimeoutError("LLM down"))
        report = await hunter.scan_codebase(tmp_path, use_ai=True)
        # finding kept (severity unchanged, not "info")
        assert len(report.findings) == 1

    async def test_medium_severity_skips_ai(self, tmp_path):
        finding = make_finding(severity="medium", rule_id="firebase-url")
        hunter = self._hunter([finding])
        report = await hunter.scan_codebase(tmp_path, use_ai=True)
        hunter.ai_analyzer.analyze_finding.assert_not_awaited()
        assert report.findings == [finding]

    async def test_min_severity_filtering(self, tmp_path):
        findings = [
            make_finding(severity="medium"),
            make_finding(severity="info", rule_id="x"),
        ]
        hunter = self._hunter(findings)
        report = await hunter.scan_codebase(tmp_path, use_ai=False, min_severity="high")
        assert report.findings == []
        assert report.summary["severity_distribution"] == {}

    async def test_unknown_severity_rank_filtered_out(self, tmp_path):
        hunter = self._hunter([make_finding(severity="bizarre")])
        report = await hunter.scan_codebase(tmp_path, use_ai=False, min_severity="medium")
        assert report.findings == []

    async def test_accepts_str_directory(self, tmp_path):
        hunter = self._hunter([])
        report = await hunter.scan_codebase(str(tmp_path), use_ai=False)
        hunter.gitleaks.scan_directory.assert_called_once_with(tmp_path)
        assert report.findings == []

    async def test_high_count_summary(self, tmp_path):
        findings = [
            make_finding(severity="high", rule_id="google-api-key"),
            make_finding(severity="high", rule_id="openai-key"),
        ]
        hunter = self._hunter(findings)
        report = await hunter.scan_codebase(tmp_path, use_ai=False)
        assert report.summary["high_count"] == 2


class TestSecretHunterHookAndSingleton:
    def test_generate_pre_commit_hook(self):
        hook = SecretHunter().generate_pre_commit_hook()
        assert hook.startswith("#!/bin/bash")
        assert "SecretHunter" in hook
        assert "exit 1" in hook
        assert "exit 0" in hook

    def test_module_singleton_is_secret_hunter(self):
        assert isinstance(ss_module.secret_hunter, SecretHunter)
