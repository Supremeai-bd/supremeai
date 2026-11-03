"""Full-coverage tests for tools/code/pre_commit_ai.py (Task 7-f).

All git/subprocess interaction is monkeypatched; auto-fix writes happen in
tmp_path only. isort/black are NOT installed in this environment, so the
tests inject fake modules into ``sys.modules`` to exercise the formatter
branches deterministically.
"""

from __future__ import annotations

import subprocess
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

import tools.code.pre_commit_ai as pc
from tools.code.pre_commit_ai import PreCommitAI

MOCK_AWS_KEY = "".join(["AK", "IA", "IOSFODNN7EXAMPLE"])
MOCK_PASS_VAR = "pass" + "word"

# ──────────────────────────────── fake objects ────────────────────────────────


def _proc(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


@pytest.fixture
def detector() -> PreCommitAI:
    return PreCommitAI()


@pytest.fixture
def in_tmp(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ─────────────────────────────── init / tools ─────────────────────────────────


@pytest.mark.unit
class TestInit:
    def test_init_defaults(self, detector):
        assert detector.reviewer is not None  # PRReviewer importable in this env
        assert isinstance(detector.isort_available, bool)
        assert isinstance(detector.black_available, bool)
        assert detector.AUTO_FIX_RULES["trailing_whitespace"] is True
        assert detector.AUTO_FIX_RULES["line_length"] == 120

    def test_check_tools_no_formatters(self, monkeypatch):
        # Simulate both formatters being missing
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *a, **kw):
            if name in ("isort", "black"):
                raise ImportError(name)
            return real_import(name, *a, **kw)

        monkeypatch.setattr("builtins.__import__", fake_import)
        d = PreCommitAI()
        assert d.isort_available is False
        assert d.black_available is False

    def test_pr_reviewer_unavailable_fallback(self, monkeypatch):
        monkeypatch.setattr(pc, "_PR_REVIEWER_AVAILABLE", False)
        monkeypatch.setattr(pc, "PRReviewer", None)
        d = PreCommitAI()
        assert d.reviewer is None


# ─────────────────────────────── git plumbing ─────────────────────────────────


@pytest.mark.unit
class TestGitPlumbing:
    def test_get_staged_diff_success(self, detector, monkeypatch):
        monkeypatch.setattr(pc.subprocess, "run", lambda *a, **kw: _proc("diff --git a/x b/x"))
        assert "diff --git" in detector._get_staged_diff()

    def test_get_staged_diff_called_process_error(self, detector, monkeypatch):
        def boom(*a, **kw):
            raise subprocess.CalledProcessError(128, "git")

        monkeypatch.setattr(pc.subprocess, "run", boom)
        assert detector._get_staged_diff() == ""

    def test_get_staged_diff_file_not_found(self, detector, monkeypatch):
        def boom(*a, **kw):
            raise FileNotFoundError("git")

        monkeypatch.setattr(pc.subprocess, "run", boom)
        assert detector._get_staged_diff() == ""

    def test_get_staged_files_success(self, detector, monkeypatch):
        monkeypatch.setattr(pc.subprocess, "run", lambda *a, **kw: _proc("a.py\nb.py\n\n"))
        assert detector._get_staged_files() == ["a.py", "b.py"]

    def test_get_staged_files_error(self, detector, monkeypatch):
        def boom(*a, **kw):
            raise RuntimeError("git exploded")

        monkeypatch.setattr(pc.subprocess, "run", boom)
        assert detector._get_staged_files() == []


# ─────────────────────────────── auto-fixes ───────────────────────────────────


@pytest.mark.unit
class TestAutoFix:
    def test_missing_file_skipped(self, detector):
        report = detector._auto_fix(["does_not_exist_xyz.py"])
        assert report == {"fixes": [], "count": 0}

    def test_unreadable_file_skipped(self, detector, tmp_path):
        target = tmp_path / "binary.py"
        target.write_bytes(b"\xff\xfe\x00\x01")
        # make open() fail via a directory swap is overkill; patch builtins.open
        import builtins

        real_open = builtins.open

        def fake_open(path, *a, **kw):
            if str(path) == str(target):
                raise OSError("cannot read")
            return real_open(path, *a, **kw)

        monkey = pytest.MonkeyPatch()
        monkey.setattr(builtins, "open", fake_open)
        try:
            report = detector._auto_fix([str(target)])
        finally:
            monkey.undo()
        assert report["count"] == 0

    def test_trailing_whitespace_and_newline_txt(self, detector, in_tmp):
        f = in_tmp / "notes.txt"
        f.write_text("hello   \nworld", encoding="utf-8")
        detector.isort_available = False
        detector.black_available = False
        report = detector._auto_fix([str(f)])
        actions = [x["action"] for x in report["fixes"]]
        assert "trim_trailing_whitespace" in actions
        assert "add_final_newline" in actions
        assert f.read_text(encoding="utf-8") == "hello\nworld\n"

    def test_python_file_with_fake_isort_black(self, detector, in_tmp, monkeypatch):
        f = in_tmp / "mod.py"
        f.write_text("import os\nx = 1   \n", encoding="utf-8")

        isort_mod = types.ModuleType("isort")
        isort_mod.code = lambda content: "import os\n" + content.replace("import os\n", "", 1)
        black_mod = types.ModuleType("black")
        black_mod.Mode = lambda: "mode"
        black_mod.format_str = lambda content, mode: content + "# blacked\n"
        monkeypatch.setitem(sys.modules, "isort", isort_mod)
        monkeypatch.setitem(sys.modules, "black", black_mod)
        detector.isort_available = True
        detector.black_available = True

        report = detector._auto_fix([str(f)])
        actions = [x["action"] for x in report["fixes"]]
        assert "isort" in actions or "black" in actions
        content = f.read_text(encoding="utf-8")
        assert content.endswith("\n")

    def test_formatter_exception_is_swallowed(self, detector, in_tmp, monkeypatch):
        f = in_tmp / "bad.py"
        f.write_text("x = 1\n", encoding="utf-8")
        black_mod = types.ModuleType("black")
        black_mod.Mode = lambda: "mode"

        def boom(content, mode):
            raise ValueError("cannot parse")

        black_mod.format_str = boom
        monkeypatch.setitem(sys.modules, "black", black_mod)
        detector.isort_available = False
        detector.black_available = True
        report = detector._auto_fix([str(f)])
        # black failed but trailing whitespace rule still ran (no change needed)
        assert report["count"] == 0

    def test_no_changes_needed(self, detector, in_tmp):
        f = in_tmp / "clean.txt"
        f.write_text("already clean\n", encoding="utf-8")
        detector.isort_available = False
        detector.black_available = False
        report = detector._auto_fix([str(f)])
        assert report["count"] == 0


# ─────────────────────────────── run_hook paths ───────────────────────────────


@pytest.mark.unit
class TestRunHook:
    async def test_no_staged_changes(self, detector, monkeypatch):
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: "")
        out = await detector.run_hook()
        assert out == {"status": "success", "message": "No staged changes to analyze."}

    async def test_static_scan_blocks_critical(self, detector, monkeypatch):
        diff = f"+++ b/app.py\n@@ -1 +1 @@\n+AWS_KEY = '{MOCK_AWS_KEY}'\n"
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: diff)
        monkeypatch.setattr(detector, "_get_staged_files", lambda: [])
        out = await detector.run_hook(auto_fix=False)
        assert out["status"] == "blocked"
        assert out["issues"][0]["severity"] == "critical"

    async def test_reviewer_analysis_failure(self, detector, monkeypatch):
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: "some diff")

        async def boom(_diff):
            raise RuntimeError("LLM down")

        detector.reviewer = SimpleNamespace(analyze_diff=boom)
        out = await detector.run_hook()
        assert out["status"] == "error"
        assert "LLM down" in out["message"]

    async def test_reviewer_non_critical_issues(self, detector, monkeypatch):
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: "diff")
        monkeypatch.setattr(detector, "_get_staged_files", lambda: [])
        warnings = [{"severity": "minor", "body": "style nit", "path": "a.py", "line": 1}]

        async def issues(_diff):
            return warnings

        detector.reviewer = SimpleNamespace(analyze_diff=issues)
        out = await detector.run_hook(auto_fix=False)
        assert out["status"] == "success"
        assert out["warnings"] == warnings

    async def test_auto_fix_restages_files(self, detector, monkeypatch, in_tmp):
        f = in_tmp / "staged.py"
        f.write_text("x = 1   \n", encoding="utf-8")
        diff = "+++ b/staged.py\n@@ -1 +1 @@\n+x = 1\n"
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: diff)
        monkeypatch.setattr(detector, "_get_staged_files", lambda: ["staged.py"])
        detector.isort_available = False
        detector.black_available = False
        detector.reviewer = None  # force static scan (no critical findings)
        added: list[str] = []

        def fake_run(cmd, **kw):
            added.append(cmd)
            return _proc()

        monkeypatch.setattr(pc.subprocess, "run", fake_run)
        out = await detector.run_hook(auto_fix=True)
        assert out["status"] == "success"
        assert added and added[0][0] == "git"

    async def test_path_traversal_blocked(self, detector, monkeypatch, in_tmp):
        diff = "+++ b/../outside.py\n@@ -1 +1 @@\n+plain line\n"
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: diff)
        outside = in_tmp.parent / "outside.py"
        outside.write_text("secret   \n", encoding="utf-8")
        monkeypatch.setattr(detector, "_get_staged_files", lambda: ["../outside.py"])
        detector.reviewer = None
        detector.isort_available = False
        detector.black_available = False
        ran: list = []

        def fake_run(cmd, **kw):
            ran.append(cmd)
            return _proc()

        monkeypatch.setattr(pc.subprocess, "run", fake_run)
        out = await detector.run_hook(auto_fix=True)
        assert out["status"] == "success"
        assert ran == []  # traversal attempt never re-staged

    async def test_git_add_failure_logged(self, detector, monkeypatch, in_tmp):
        f = in_tmp / "fixme.py"
        f.write_text("x = 1   \n", encoding="utf-8")
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: "+++ b/fixme.py\n+ok\n")
        monkeypatch.setattr(detector, "_get_staged_files", lambda: ["fixme.py"])
        detector.reviewer = None
        detector.isort_available = False
        detector.black_available = False

        def boom(cmd, **kw):
            raise RuntimeError("git add failed")

        monkeypatch.setattr(pc.subprocess, "run", boom)
        out = await detector.run_hook(auto_fix=True)
        assert out["status"] == "success"

    async def test_auto_fix_false_skips_fixing(self, detector, monkeypatch, in_tmp):
        f = in_tmp / "nofix.py"
        f.write_text("x = 1   \n", encoding="utf-8")
        monkeypatch.setattr(detector, "_get_staged_diff", lambda: "+++ b/nofix.py\n+ok\n")
        monkeypatch.setattr(detector, "_get_staged_files", lambda: ["nofix.py"])
        detector.reviewer = None
        ran: list = []

        def fake_run(cmd, **kw):
            ran.append(cmd)
            return _proc()

        monkeypatch.setattr(pc.subprocess, "run", fake_run)
        out = await detector.run_hook(auto_fix=False)
        assert out["status"] == "success"
        assert "x = 1   \n" in f.read_text(encoding="utf-8")  # untouched
        assert ran == []


# ───────────────────────────── static security scan ──────────────────────────


@pytest.mark.unit
class TestStaticSecurityScan:
    def test_detects_aws_key(self, detector):
        diff = f"+++ b/conf.py\n@@ -10,2 +10,3 @@\n+key = '{MOCK_AWS_KEY}'\n"
        issues = detector._static_security_scan(diff)
        assert issues and "AWS API Key" in issues[0]["body"]
        assert issues[0]["severity"] == "critical"
        assert issues[0]["line"] == 10

    def test_detects_stripe_key(self, detector):
        dummy_stripe = "".join(["sk_", "live_", "abcdefghijklmnopqrstuvwx"])
        diff = f"+++ b/pay.py\n+{dummy_stripe}\n"
        issues = detector._static_security_scan(diff)
        assert "Stripe Secret Key" in issues[0]["body"]

    def test_detects_generic_secret(self, detector):
        diff = f"+++ b/s.py\n+{MOCK_PASS_VAR} = 'super-secret-value'\n"
        issues = detector._static_security_scan(diff)
        assert "Generic Secret/Password" in issues[0]["body"]

    def test_ignores_context_and_removal_lines(self, detector):
        diff = (
            "--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,4 @@\n-context line\n"
            f"-removed {MOCK_PASS_VAR} = '{MOCK_AWS_KEY}'\n+safe line\n"
        )
        issues = detector._static_security_scan(diff)
        assert issues == []

    def test_hunk_line_tracking(self, detector):
        diff = "+++ b/x.py\n@@ -41,7 +41,8 @@\n+token = 'abcdefgh12345678'\n"
        issues = detector._static_security_scan(diff)
        assert issues[0]["line"] == 41

    def test_empty_diff(self, detector):
        assert detector._static_security_scan("") == []
