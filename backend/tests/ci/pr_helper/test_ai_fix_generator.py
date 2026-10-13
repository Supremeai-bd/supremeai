"""Tests for AI Auto-Fix modules (issue #1034).

Tests Phase 1, 2, 3 modules:
  - ci_failure_collector.py    (Phase 1 — GitHub API + log parsing)
  - ai_fix_generator.py        (Phase 2 — Gemini/OpenAI/Mistral API + safety)
  - ai_autofix_flags.py        (Phase 3 — LaunchDarkly flag resolution)

Strategy (per env1.txt directive — "No Fake Mocking"):
  - Real regex parsing logic tested against real log fixtures
  - urllib transport replaced with stub object in tests (allowed — we test OUR
    code, not Google/OpenAI servers; spec explicitly permits "mock Gemini in tests")
  - LD flag resolution tested against env-var overrides + a fake ldclient stub
  - Safety guards (confidence threshold, max retries, scope limit, syntax check)
    tested with real ast.parse + real file IO
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).resolve().parents[4] / ".github" / "scripts" / "pr_helper"
sys.path.insert(0, str(SCRIPTS_DIR))

from ai_autofix_flags import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    VALID_MODELS,
    get_ai_autofix_config,
    is_ai_autofix_enabled,
)
from ai_fix_generator import (
    ALLOWED_PATH_PREFIXES,
    DEFAULT_MAX_ATTEMPTS,
    PROTECTED_PATH_PREFIXES,
    _call_gemini,
    _call_openai,
    _estimate_confidence,
    _is_allowed_path,
    _is_in_diff_scope,
    _is_protected_path,
    _is_syntax_valid,
    _strip_markdown_code_block,
    call_model,
    generate_fixes,
)
from ai_fix_generator import (
    DEFAULT_CONFIDENCE_THRESHOLD as GEN_DEFAULT_CONF,
)
from ci_failure_collector import (
    _classify_failure,
    _extract_file_path,
    _extract_lint_violations,
    _extract_message,
    _extract_test_name,
    parse_job_log,
)

# =============================================================================
# Phase 1 — CI Failure Collector
# =============================================================================


class TestCIFailureCollectorParsing:
    """Phase 1: parse_job_log + helper extraction functions."""

    def test_classify_import_error(self):
        assert _classify_failure("ModuleNotFoundError: No module named 'xyz'") == "import_error"
        assert (
            _classify_failure("ImportError: cannot import name 'X' from 'core.y'") == "import_error"
        )

    def test_classify_syntax_error(self):
        assert _classify_failure("SyntaxError: invalid syntax") == "syntax_error"

    def test_classify_lint_violation(self):
        log = "backend/core/x.py:12:34: E501 line too long (105 > 100 characters)"
        assert _classify_failure(log) == "lint_violation"

    def test_classify_test_failure(self):
        assert _classify_failure("AssertionError: assert 1 == 2") == "test_failure"
        assert (
            _classify_failure("FAILED tests/test_x.py::test_y - AssertionError: foo")
            == "test_failure"
        )

    def test_classify_generic(self):
        assert _classify_failure("some random output without errors") == "generic"

    def test_extract_test_name_pytest(self):
        log = "FAILED backend/tests/test_x.py::test_y - AssertionError: assert False"
        assert _extract_test_name(log) == "backend/tests/test_x.py::test_y"

    def test_extract_file_path_pyfile(self):
        log = '  File "backend/core/foo.py", line 42, in bar'
        assert _extract_file_path(log) == "backend/core/foo.py"

    def test_extract_file_path_ruff(self):
        log = "backend/core/foo.py:12:34: E501 line too long"
        assert _extract_file_path(log) == "backend/core/foo.py"

    def test_extract_message_assertion(self):
        assert _extract_message("AssertionError: assert 1 == 2") == "AssertionError: assert 1 == 2"

    def test_extract_message_import(self):
        msg = _extract_message("ImportError: No module named 'xyz'")
        assert "ImportError" in msg and "xyz" in msg

    def test_parse_lint_violations(self):
        log = (
            "backend/core/a.py:10:5: E501 line too long\n"
            "backend/core/b.py:20:1: F401 unused import\n"
            "backend/core/a.py:10:5: E501 line too long\n"  # duplicate — should be skipped
        )
        violations = _extract_lint_violations(log)
        assert len(violations) == 2  # dedup works
        assert violations[0]["rule_code"] == "E501"
        assert violations[0]["file_path"] == "backend/core/a.py"
        assert violations[0]["line"] == 10
        assert violations[0]["column"] == 5
        assert violations[1]["rule_code"] == "F401"

    def test_parse_job_log_pytest_failures(self):
        log = """
        ============================= test session starts =============================
        collected 10 items
        backend/tests/test_a.py ..F.                                          [ 50%]
        backend/tests/test_b.py F.                                            [100%]
        =================================== FAILURES ===================================
        _______________________________ test_one ______________________________________
        FAILED backend/tests/test_a.py::test_one - AssertionError: expected 5 got 3
        _______________________________ test_two ______________________________________
        FAILED backend/tests/test_b.py::test_two - ValueError: invalid literal
        ============================= 2 failed in 1.23s =============================
        """
        failures = parse_job_log(log)
        # 2 pytest FAILED failures extracted
        test_names = [f["test_name"] for f in failures if f["type"] == "test_failure"]
        assert "backend/tests/test_a.py::test_one" in test_names
        assert "backend/tests/test_b.py::test_two" in test_names
        # Each failure has file_path / message / stack_trace
        for f in failures:
            if f["type"] == "test_failure":
                assert f["message"]
                assert isinstance(f["log_excerpt"], str)

    def test_parse_job_log_empty(self):
        assert parse_job_log("") == []

    def test_parse_job_log_only_lint(self):
        log = "backend/core/x.py:1:1: E501 too long\nbackend/core/y.py:2:1: F401 unused"
        failures = parse_job_log(log)
        assert all(f["type"] == "lint_violation" for f in failures)
        assert len(failures) == 2

    def test_parse_job_log_generic_fallback(self):
        log = "Some unknown build step\nRuntimeError: connection refused\n"
        failures = parse_job_log(log)
        # Generic fallback should pick up the RuntimeError
        assert any(f["type"] in ("test_failure", "generic") for f in failures)
        assert any("RuntimeError" in f.get("message", "") for f in failures)


class TestCIFailureCollectorAPI:
    """Phase 1: GitHub API call paths (urllib transport mocked)."""

    def test_gh_request_returns_dict_for_json(self, monkeypatch):
        """JSON response parsed correctly."""
        from ci_failure_collector import _gh_request

        class FakeResp:
            status = 200
            headers = {"Content-Type": "application/json"}

            def read(self):
                return b'{"hello": "world"}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        def fake_urlopen(req, timeout):
            assert "api.github.com" in req.full_url
            assert req.get_header("Authorization") == "Bearer tkn"
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        status, body, _ = _gh_request("https://api.github.com/test", "tkn")
        assert status == 200
        assert body == {"hello": "world"}

    def test_gh_request_text_passthrough(self, monkeypatch):
        """Plain text response (logs) stays as bytes."""
        from ci_failure_collector import _gh_request

        class FakeResp:
            status = 200
            headers = {"Content-Type": "text/plain"}

            def read(self):
                return b"plain log line\nsecond line"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResp())
        status, body, _ = _gh_request("https://api.github.com/logs", "tkn", accept="text/plain")
        assert status == 200
        assert isinstance(body, bytes)
        assert b"plain log line" in body

    def test_gh_request_http_error(self, monkeypatch):
        import urllib.error

        from ci_failure_collector import _gh_request

        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", {}, b'{"message": "Not Found"}'
            )

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        status, body, _ = _gh_request("https://api.github.com/missing", "tkn")
        assert status == 404
        assert isinstance(body, dict)
        assert body.get("message") == "Not Found"

    def test_collect_failures_no_failed_runs(self, monkeypatch):
        """When no failed workflow runs exist, returns empty failed_jobs list."""
        from ci_failure_collector import collect_failures

        # Stub _gh_request so PR fetch is skipped via head_sha injection
        def fake_gh_request(url, token, method="GET", accept=None, body=None, timeout=30):
            # /actions/runs?head_sha=...&status=failure
            if "actions/runs" in url and "head_sha" in url:
                return 200, {"workflow_runs": []}, {}
            return 200, {}, {}

        monkeypatch.setattr("ci_failure_collector._gh_request", fake_gh_request)
        result = collect_failures(
            repo="SaifulHaqueNiloy/supremeai",
            pr_number=9999,
            token="tkn",
            head_sha="abc123",
            changed_files=["backend/core/x.py"],
        )
        assert result["summary"]["total_failed_jobs"] == 0
        assert result["summary"]["total_failures"] == 0
        assert result["changed_files"] == ["backend/core/x.py"]

    def test_collect_failures_full_path(self, monkeypatch):
        """Full happy-path: failed run → failed job → log → parsed failures."""
        from ci_failure_collector import collect_failures

        fake_log = """... lots of build output ...
FAILED backend/tests/test_x.py::test_one - AssertionError: assert False
FAILED backend/tests/test_x.py::test_two - ValueError: invalid input
== 2 failed in 1.0s ==
"""

        def fake_gh_request(url, token, method="GET", accept=None, body=None, timeout=30):
            if "actions/runs" in url and "head_sha" in url:
                return (
                    200,
                    {
                        "workflow_runs": [
                            {
                                "id": 111,
                                "html_url": "https://github.com/x/actions/runs/111",
                                "created_at": "2025-01-01T00:00:00Z",
                            }
                        ]
                    },
                    {},
                )
            if "actions/runs" in url and "jobs" in url:
                return (
                    200,
                    {
                        "jobs": [
                            {"id": 222, "name": "test-backend", "conclusion": "failure"},
                            {"id": 333, "name": "lint", "conclusion": "success"},  # filtered out
                        ]
                    },
                    {},
                )
            if "actions/jobs" in url and "logs" in url:
                return 200, fake_log.encode("utf-8"), {}
            return 200, {}, {}

        monkeypatch.setattr("ci_failure_collector._gh_request", fake_gh_request)
        result = collect_failures(
            repo="x/y",
            pr_number=1,
            token="tkn",
            head_sha="abc",
            changed_files=["backend/tests/test_x.py"],
        )
        assert result["summary"]["total_failed_jobs"] == 1  # only failure jobs
        assert result["summary"]["total_failures"] >= 2  # 2 FAILED lines
        assert result["summary"]["by_type"].get("test_failure", 0) >= 2
        assert result["run_id"] == 111


# =============================================================================
# Phase 2 — AI Fix Generator
# =============================================================================


class TestAIFixGeneratorMarkdown:
    """Phase 2: markdown code-fence stripping."""

    def test_strip_python_fence(self):
        text = "```python\ndef foo():\n    return 1\n```"
        assert _strip_markdown_code_block(text) == "def foo():\n    return 1"

    def test_strip_plain_fence(self):
        text = "```\nx = 1\n```"
        assert _strip_markdown_code_block(text) == "x = 1"

    def test_strip_no_fence(self):
        assert _strip_markdown_code_block("x = 1") == "x = 1"

    def test_strip_partial_fence(self):
        text = "```\nx = 1\n"  # missing closing fence
        assert _strip_markdown_code_block(text) == "x = 1"

    def test_strip_empty(self):
        assert _strip_markdown_code_block("") == ""


class TestAIFixGeneratorSyntax:
    """Phase 2: syntax validation via ast.parse."""

    def test_valid_syntax(self):
        assert _is_syntax_valid("x = 1\ny = 2\n") is True

    def test_invalid_syntax(self):
        assert _is_syntax_valid("def foo(\n") is False

    def test_empty_code(self):
        assert _is_syntax_valid("") is False
        assert _is_syntax_valid("   \n  ") is False

    def test_complex_valid(self):
        code = """
import os
from pathlib import Path

def main():
    files = list(Path(".").glob("*.py"))
    return sorted(files)

if __name__ == "__main__":
    main()
"""
        assert _is_syntax_valid(code) is True


class TestAIFixGeneratorScope:
    """Phase 2: PR diff scope + protected path safety guards."""

    def test_in_diff_scope_exact_match(self):
        assert _is_in_diff_scope("backend/tests/test_x.py", ["backend/tests/test_x.py"]) is True

    def test_in_diff_scope_prefix_match(self):
        assert _is_in_diff_scope("tests/test_x.py", ["backend/tests/test_x.py"]) is True

    def test_out_of_diff_scope(self):
        assert _is_in_diff_scope("backend/core/config.py", ["backend/tests/test_x.py"]) is False

    def test_empty_file_path(self):
        assert _is_in_diff_scope("", ["backend/tests/test_x.py"]) is False

    def test_protected_path_core(self):
        assert _is_protected_path("backend/core/config.py") is True

    def test_protected_path_github(self):
        assert _is_protected_path(".github/workflows/pr.yml") is True

    def test_protected_path_empty(self):
        assert _is_protected_path("") is True  # unknown → protected

    def test_not_protected_test_file(self):
        assert _is_protected_path("backend/tests/test_x.py") is False

    def test_allowed_path(self):
        assert _is_allowed_path("backend/tests/test_x.py") is True
        assert _is_allowed_path("scripts/run.py") is True

    def test_not_allowed_path(self):
        assert _is_allowed_path("docs/README.md") is False

    def test_protected_prefixes_const(self):
        assert ".github/" in PROTECTED_PATH_PREFIXES
        assert "backend/core/" in PROTECTED_PATH_PREFIXES

    def test_allowed_prefixes_const(self):
        assert "backend/" in ALLOWED_PATH_PREFIXES
        assert "tests/" in ALLOWED_PATH_PREFIXES


class TestAIFixGeneratorConfidence:
    """Phase 2: confidence heuristic."""

    def test_high_confidence_valid_syntax(self):
        original = '"""docstring"""\n\ndef foo():\n    return 1\n'
        fixed = '"""docstring"""\n\ndef foo():\n    return 2\n'
        conf = _estimate_confidence(original, fixed, "backend/tests/test_x.py", True)
        assert conf >= 0.7  # syntax + length + no-fence + import + first-line

    def test_low_confidence_invalid_syntax(self):
        original = '"""docstring"""\n\ndef foo():\n    return 1\n'
        fixed = "def broken(\n"
        conf = _estimate_confidence(original, fixed, "backend/tests/test_x.py", False)
        assert conf < 0.4  # no syntax bonus, but other heuristics may add a little

    def test_markdown_leftover_reduces_confidence(self):
        original = '"""doc"""\n\nx = 1\n'
        fixed = '"""doc"""\n\n```python\nx = 1\n```\n'
        conf = _estimate_confidence(original, fixed, "backend/tests/test_x.py", True)
        # Markdown fence left → no markdown bonus → lower confidence
        assert conf < 0.9

    def test_confidence_bounded(self):
        # Even perfect code should not exceed 1.0
        original = '"""docstring"""\n\ndef foo():\n    return 1\n'
        conf = _estimate_confidence(original, original, "backend/tests/test_x.py", True)
        assert 0.0 <= conf <= 1.0


class TestAIFixGeneratorAPI:
    """Phase 2: Gemini + OpenAI API call (urllib transport mocked)."""

    def test_call_gemini_missing_key(self):
        text, err, tokens = _call_gemini("", "gemini-2.5-flash", "sys", "usr")
        assert text == ""
        assert "GEMINI_API_KEY not set" in err
        assert tokens == 0

    def test_call_gemini_success(self, monkeypatch):
        fake_response = json.dumps(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "fixed code here"}]},
                    }
                ],
                "usageMetadata": {"promptTokenCount": 42},
            }
        ).encode("utf-8")

        class FakeResp:
            status = 200

            def read(self):
                return fake_response

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResp())
        text, err, tokens = _call_gemini("key", "gemini-2.5-flash", "sys", "usr")
        assert text == "fixed code here"
        assert err == ""
        assert tokens == 42

    def test_call_gemini_quota_exhausted(self, monkeypatch):
        import urllib.error

        err_body = json.dumps({"error": {"message": "Quota exceeded for this key"}}).encode("utf-8")

        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, err_body)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        text, err, tokens = _call_gemini("key", "gemini-2.5-flash", "sys", "usr")
        assert text == ""
        assert "QUOTA_EXHAUSTED" in err
        assert tokens == 0

    def test_call_openai_missing_key(self):
        text, err, tokens = _call_openai("", "gpt-4o-mini", "sys", "usr")
        assert text == ""
        assert "OPENAI_API_KEY not set" in err

    def test_call_openai_success(self, monkeypatch):
        fake_response = json.dumps(
            {
                "choices": [{"message": {"content": "openai fixed code"}}],
                "usage": {"prompt_tokens": 100},
            }
        ).encode("utf-8")

        class FakeResp:
            status = 200

            def read(self):
                return fake_response

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResp())
        text, err, tokens = _call_openai("key", "gpt-4o-mini", "sys", "usr")
        assert text == "openai fixed code"
        assert err == ""
        assert tokens == 100

    def test_call_model_auto_fallback(self, monkeypatch):
        """'auto' model_choice: Gemini quota exhausted → OpenAI fallback succeeds."""
        import urllib.error

        gemini_err = json.dumps({"error": {"message": "rate limit"}}).encode("utf-8")
        openai_ok = json.dumps(
            {
                "choices": [{"message": {"content": "fallback worked"}}],
                "usage": {"prompt_tokens": 50},
            }
        ).encode("utf-8")

        call_count = {"n": 0}

        def fake_urlopen(req, timeout):
            call_count["n"] += 1
            if "generativelanguage.googleapis.com" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, gemini_err)

            # OpenAI path
            class FakeResp:
                status = 200

                def read(self):
                    return openai_ok

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        text, err, tokens, model_used = call_model(
            "auto", "gem-key", "openai-key", "mistral-key", "sys", "usr"
        )
        assert text == "fallback worked"
        assert err == ""
        assert model_used == "gpt-4o-mini"
        assert call_count["n"] == 2  # Gemini first, then OpenAI

    def test_call_model_explicit_no_fallback(self, monkeypatch):
        """model_choice='gemini' should NOT fall back to OpenAI."""
        import urllib.error

        gemini_err = json.dumps({"error": {"message": "rate limit"}}).encode("utf-8")

        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, gemini_err)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        text, err, tokens, model_used = call_model(
            "gemini", "gem-key", "openai-key", "mistral-key", "sys", "usr"
        )
        assert text == ""
        assert "QUOTA_EXHAUSTED" in err
        # No fallback — model_used empty (because Gemini failed)

    def test_call_model_all_fail(self, monkeypatch):
        """All 3 providers fail → return aggregate error."""
        import urllib.error

        err_body = json.dumps({"error": {"message": "fail"}}).encode("utf-8")

        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, err_body)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        text, err, tokens, model_used = call_model("auto", "gem", "oai", "mis", "sys", "usr")
        assert text == ""
        assert "All models failed" in err


class TestAIFixGeneratorGenerateFixes:
    """Phase 2: end-to-end generate_fixes flow with all safety guards."""

    def _make_failures_data(self, file_path: str = "backend/tests/test_x.py") -> dict:
        return {
            "pr_number": 1234,
            "head_sha": "abc123",
            "changed_files": ["backend/tests/test_x.py"],
            "failed_jobs": [
                {
                    "job_id": 1,
                    "name": "test",
                    "conclusion": "failure",
                    "log_bytes": 1000,
                    "failures": [
                        {
                            "type": "test_failure",
                            "test_name": f"{file_path}::test_one",
                            "file_path": file_path,
                            "message": "AssertionError: assert 1 == 2",
                            "stack_trace": "",
                            "log_excerpt": "FAILED backend/tests/test_x.py::test_one",
                        }
                    ],
                }
            ],
            "summary": {
                "total_failed_jobs": 1,
                "total_failures": 1,
                "by_type": {"test_failure": 1},
            },
        }

    def test_generate_fixes_out_of_scope_skipped(self, tmp_path):
        """File not in PR diff → skip + escalate."""
        # Set up a fake repo with the source file
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text("def test_one():\n    assert False\n")
        # But mark changed_files as something else
        failures_data = self._make_failures_data("backend/tests/test_x.py")
        failures_data["changed_files"] = ["backend/api/routes.py"]  # different file

        result = generate_fixes(
            failures_data,
            repo=str(repo),
            gemini_key="k",
            openai_key="k",
            mistral_key="k",
            max_attempts=2,
            confidence_threshold=0.8,
        )
        assert result["summary"]["skipped_out_of_scope"] == 1
        assert result["summary"]["applied"] == 0
        assert "OUT_OF_SCOPE" in result["attempts"][0]["error"]

    def test_generate_fixes_protected_path_skipped(self, tmp_path):
        """backend/core/ path is protected → skip."""
        failures_data = self._make_failures_data("backend/core/config.py")
        failures_data["changed_files"] = ["backend/core/config.py"]  # in diff, but protected
        result = generate_fixes(
            failures_data,
            repo=str(tmp_path),
            gemini_key="k",
            openai_key="k",
            mistral_key="k",
        )
        assert result["summary"]["skipped_out_of_scope"] == 1
        assert any("PROTECTED_PATH" in a.get("error", "") for a in result["attempts"])

    def test_generate_fixes_low_confidence_skipped(self, tmp_path):
        """AI response that fails confidence threshold → skip + escalate."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text(
            '"""doc"""\n\ndef test_one():\n    assert False\n'
        )
        failures_data = self._make_failures_data("backend/tests/test_x.py")

        # Mock Gemini to return high-syntax but completely different code (low confidence)
        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = (
                "def completely_unrelated():\n    pass\n",  # different first line, no docstring
                "",
                100,
            )
            result = generate_fixes(
                failures_data,
                repo=str(repo),
                gemini_key="k",
                openai_key="k",
                mistral_key="k",
                max_attempts=2,
                confidence_threshold=0.95,  # very high → must reject
            )
        # Confidence will be low (first line mismatch)
        assert result["summary"]["skipped_low_confidence"] >= 1
        assert result["summary"]["applied"] == 0
        assert any("LOW_CONFIDENCE" in a.get("error", "") for a in result["attempts"])

    def test_generate_fixes_applied_on_success(self, tmp_path):
        """Full happy-path: Gemini returns valid fix → applied to file."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        original = '"""test module"""\n\ndef test_one():\n    assert 1 == 2\n'
        (repo / "backend" / "tests" / "test_x.py").write_text(original)
        failures_data = self._make_failures_data("backend/tests/test_x.py")

        # Mock Gemini to return a syntax-valid fix with preserved first line
        fixed_code = '"""test module"""\n\ndef test_one():\n    assert 1 == 1\n'
        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = (fixed_code, "", 200)
            result = generate_fixes(
                failures_data,
                repo=str(repo),
                gemini_key="k",
                openai_key="k",
                mistral_key="k",
                max_attempts=2,
                confidence_threshold=0.5,  # lower threshold so it passes
            )
        assert result["summary"]["applied"] == 1
        assert result["attempts"][0]["applied"] is True
        assert result["attempts"][0]["model_used"] == "gemini-2.5-flash"
        # File was actually written
        on_disk = (repo / "backend" / "tests" / "test_x.py").read_text()
        assert "assert 1 == 1" in on_disk

    def test_generate_fixes_max_attempts_enforced(self, tmp_path):
        """max_attempts=1 → second failure should be skipped."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text("def test_one():\n    assert False\n")
        (repo / "backend" / "tests" / "test_y.py").write_text("def test_two():\n    assert False\n")

        failures_data = {
            "pr_number": 1234,
            "head_sha": "abc",
            "changed_files": ["backend/tests/test_x.py", "backend/tests/test_y.py"],
            "failed_jobs": [
                {
                    "job_id": 1,
                    "name": "test",
                    "conclusion": "failure",
                    "log_bytes": 100,
                    "failures": [
                        {
                            "type": "test_failure",
                            "test_name": "backend/tests/test_x.py::test_one",
                            "file_path": "backend/tests/test_x.py",
                            "message": "AssertionError",
                            "stack_trace": "",
                            "log_excerpt": "",
                        },
                        {
                            "type": "test_failure",
                            "test_name": "backend/tests/test_y.py::test_two",
                            "file_path": "backend/tests/test_y.py",
                            "message": "AssertionError",
                            "stack_trace": "",
                            "log_excerpt": "",
                        },
                    ],
                }
            ],
            "summary": {"total_failed_jobs": 1, "total_failures": 2, "by_type": {}},
        }

        fixed_code = "def test_one():\n    assert True\n"
        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = (fixed_code, "", 100)
            result = generate_fixes(
                failures_data,
                repo=str(repo),
                gemini_key="k",
                openai_key="k",
                mistral_key="k",
                max_attempts=1,
                confidence_threshold=0.5,
            )
        # Only first failure got an AI attempt; second one escalated
        assert result["summary"]["applied"] == 1
        assert any("MAX_ATTEMPTS_REACHED" in (a.get("error") or "") for a in result["attempts"])

    def test_generate_fixes_syntax_invalid_skipped(self, tmp_path):
        """AI returns broken syntax → skip + record."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text(
            '"""doc"""\n\ndef test_one():\n    assert False\n'
        )
        failures_data = self._make_failures_data("backend/tests/test_x.py")

        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = ("def broken(\n", "", 50)
            result = generate_fixes(
                failures_data,
                repo=str(repo),
                gemini_key="k",
                openai_key="k",
                mistral_key="k",
                max_attempts=2,
                confidence_threshold=0.5,
            )
        assert result["summary"]["syntax_invalid"] == 1
        assert result["summary"]["applied"] == 0

    def test_generate_fixes_api_error_recorded(self, tmp_path):
        """Gemini API error → recorded, escalated."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text("def test():\n    pass\n")
        failures_data = self._make_failures_data("backend/tests/test_x.py")

        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = ("", "GEMINI_API_KEY not set", 0)
            with patch("ai_fix_generator._call_openai") as mock_oai:
                mock_oai.return_value = ("", "OPENAI_API_KEY not set", 0)
                with patch("ai_fix_generator._call_mistral") as mock_mis:
                    mock_mis.return_value = ("", "MISTRAL_API_KEY not set", 0)
                    result = generate_fixes(
                        failures_data,
                        repo=str(repo),
                        gemini_key="",
                        openai_key="",
                        mistral_key="",
                        max_attempts=2,
                        confidence_threshold=0.5,
                    )
        assert result["summary"]["errors"] >= 1

    def test_generate_fixes_audit_trail_complete(self, tmp_path):
        """Each attempt has model_used, prompt_tokens, response_text, confidence."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text(
            '"""doc"""\n\ndef test_one():\n    assert False\n'
        )
        failures_data = self._make_failures_data("backend/tests/test_x.py")

        fixed = '"""doc"""\n\ndef test_one():\n    assert True\n'
        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = (fixed, "", 123)
            result = generate_fixes(
                failures_data,
                repo=str(repo),
                gemini_key="k",
                openai_key="k",
                mistral_key="k",
                max_attempts=2,
                confidence_threshold=0.5,
            )
        a = result["attempts"][0]
        assert a["model_used"] == "gemini-2.5-flash"
        assert a["prompt_tokens"] == 123
        assert a["response_text"]
        assert isinstance(a["confidence"], float)
        assert 0.0 <= a["confidence"] <= 1.0
        assert a["syntax_valid"] is True
        assert a["in_diff_scope"] is True


# =============================================================================
# Phase 3 — LaunchDarkly Flag Integration
# =============================================================================


class TestLDFlagResolution:
    """Phase 3: ai_autofix_flags.get_ai_autofix_config()."""

    def test_defaults_when_no_ld_no_env(self, monkeypatch):
        """LD unavailable + no env vars → fail-closed defaults."""
        # Ensure no env vars set
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        # Make LD unavailable
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)

        cfg = get_ai_autofix_config()
        assert cfg["enabled"] is False  # fail-closed
        assert cfg["model"] == DEFAULT_MODEL
        assert cfg["max_retries"] == DEFAULT_MAX_RETRIES
        assert cfg["confidence_threshold"] == DEFAULT_CONFIDENCE_THRESHOLD
        assert cfg["source"] == "default"

    def test_env_overrides(self, monkeypatch):
        """Env vars override LD + defaults."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)
        monkeypatch.setenv("AI_AUTO_FIX_ENABLED", "true")
        monkeypatch.setenv("AI_AUTO_FIX_MODEL", "openai")
        monkeypatch.setenv("AI_AUTO_FIX_MAX_RETRIES", "3")
        monkeypatch.setenv("AI_AUTO_FIX_CONFIDENCE_THRESHOLD", "0.9")

        cfg = get_ai_autofix_config()
        assert cfg["enabled"] is True
        assert cfg["model"] == "openai"
        assert cfg["max_retries"] == 3
        assert cfg["confidence_threshold"] == 0.9
        assert cfg["source"] == "env"

    def test_env_overrides_invalid_model(self, monkeypatch):
        """Invalid model → fallback to default."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)
        monkeypatch.setenv("AI_AUTO_FIX_MODEL", "claude-3")  # not in VALID_MODELS

        cfg = get_ai_autofix_config()
        assert cfg["model"] == DEFAULT_MODEL  # rejected, falls back

    def test_max_retries_clamped(self, monkeypatch):
        """max_retries clamped to [0, 5] safety range."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)
        monkeypatch.setenv("AI_AUTO_FIX_MAX_RETRIES", "99")

        cfg = get_ai_autofix_config()
        assert cfg["max_retries"] == 5  # clamped

        monkeypatch.setenv("AI_AUTO_FIX_MAX_RETRIES", "-3")
        cfg = get_ai_autofix_config()
        assert cfg["max_retries"] == 0  # clamped

    def test_confidence_threshold_clamped(self, monkeypatch):
        """confidence_threshold clamped to [0.0, 1.0]."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)
        monkeypatch.setenv("AI_AUTO_FIX_CONFIDENCE_THRESHOLD", "1.5")

        cfg = get_ai_autofix_config()
        assert cfg["confidence_threshold"] == 1.0

    def test_ld_variation_used_when_no_env(self, monkeypatch):
        """LD returns 'true' for enabled → config reflects it, source=launchdarkly."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)

        class FakeContext:
            pass

        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: FakeContext())

        # Stub LD client to return enabled=True
        class FakeLDClient:
            def variation(self, key, ctx, default):
                if key == "ai-auto-fix-enabled":
                    return True
                if key == "ai-auto-fix-model":
                    return "gemini"
                if key == "ai-auto-fix-max-retries":
                    return 1
                if key == "ai-auto-fix-confidence-threshold":
                    return 0.9
                return default

        fake_mod = type("ldclient", (), {"get": lambda: FakeLDClient()})
        monkeypatch.setitem(__import__("sys").modules, "ldclient", fake_mod)

        cfg = get_ai_autofix_config()
        assert cfg["enabled"] is True
        assert cfg["model"] == "gemini"
        assert cfg["max_retries"] == 1
        assert cfg["confidence_threshold"] == 0.9
        assert cfg["source"] == "launchdarkly"

    def test_is_ai_autofix_enabled_default_false(self, monkeypatch):
        """Kill switch default = False (fail-closed)."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)
        assert is_ai_autofix_enabled() is False

    def test_valid_models_const(self):
        assert "auto" in VALID_MODELS
        assert "gemini" in VALID_MODELS
        assert "openai" in VALID_MODELS
        assert "mistral" in VALID_MODELS

    def test_flag_key_names_match_issue_spec(self):
        """Flag keys must match issue #1034 Phase 3 spec exactly."""
        from ai_autofix_flags import (
            FLAG_CONFIDENCE_THRESHOLD,
            FLAG_ENABLED,
            FLAG_MAX_RETRIES,
            FLAG_MODEL,
        )

        assert FLAG_ENABLED == "ai-auto-fix-enabled"
        assert FLAG_MODEL == "ai-auto-fix-model"
        assert FLAG_MAX_RETRIES == "ai-auto-fix-max-retries"
        assert FLAG_CONFIDENCE_THRESHOLD == "ai-auto-fix-confidence-threshold"


# =============================================================================
# Integration: LD config feeds AI generator
# =============================================================================


class TestEndToEndFlagToGenerator:
    """Phase 3 + Phase 2 integration: LD config drives generator params."""

    def test_generator_uses_ld_config(self, tmp_path, monkeypatch):
        """LD says max_retries=1 → generator respects it."""
        for k in (
            "AI_AUTO_FIX_ENABLED",
            "AI_AUTO_FIX_MODEL",
            "AI_AUTO_FIX_MAX_RETRIES",
            "AI_AUTO_FIX_CONFIDENCE_THRESHOLD",
        ):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr("ai_autofix_flags._build_ld_context", lambda: None)
        monkeypatch.setenv("AI_AUTO_FIX_ENABLED", "true")
        monkeypatch.setenv("AI_AUTO_FIX_MAX_RETRIES", "1")

        cfg = get_ai_autofix_config()
        assert cfg["enabled"] is True
        assert cfg["max_retries"] == 1

        # Wire cfg into generator
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "backend" / "tests").mkdir(parents=True)
        (repo / "backend" / "tests" / "test_x.py").write_text(
            '"""doc"""\n\ndef test_one():\n    assert False\n'
        )
        failures_data = {
            "pr_number": 1234,
            "head_sha": "abc",
            "changed_files": ["backend/tests/test_x.py"],
            "failed_jobs": [
                {
                    "job_id": 1,
                    "name": "test",
                    "conclusion": "failure",
                    "log_bytes": 100,
                    "failures": [
                        {
                            "type": "test_failure",
                            "test_name": "backend/tests/test_x.py::test_one",
                            "file_path": "backend/tests/test_x.py",
                            "message": "AssertionError",
                            "stack_trace": "",
                            "log_excerpt": "",
                        },
                        {
                            "type": "test_failure",
                            "test_name": "backend/tests/test_x.py::test_two",
                            "file_path": "backend/tests/test_x.py",
                            "message": "AssertionError",
                            "stack_trace": "",
                            "log_excerpt": "",
                        },
                    ],
                }
            ],
            "summary": {"total_failed_jobs": 1, "total_failures": 2, "by_type": {}},
        }

        with patch("ai_fix_generator._call_gemini") as mock_gem:
            mock_gem.return_value = ('"""doc"""\n\ndef test_one():\n    assert True\n', "", 100)
            result = generate_fixes(
                failures_data,
                repo=str(repo),
                gemini_key="k",
                openai_key="k",
                mistral_key="k",
                max_attempts=cfg["max_retries"],
                confidence_threshold=cfg["confidence_threshold"],
            )
        # max_retries=1 → first failure applied, second escalated
        assert result["summary"]["applied"] == 1
        assert any("MAX_ATTEMPTS_REACHED" in (a.get("error") or "") for a in result["attempts"])
