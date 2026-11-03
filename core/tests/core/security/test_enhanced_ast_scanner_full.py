"""Full-coverage tests for core.security.enhanced_ast_scanner.

Covers EnhancedASTScanner (AST visitor + regex pattern scans), SecurityScanner
(orchestrator) and the CLI main() entry point. File-based tests use tmp_path;
CLI tests patch SecurityScanner to avoid scanning the real tree.
"""

from __future__ import annotations

import ast
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import core.security.enhanced_ast_scanner as eas_module
from core.security.enhanced_ast_scanner import (
    EnhancedASTScanner,
    SecurityIssue,
    SecurityScanner,
)

pytestmark = pytest.mark.security


SQLI_CODE = 'cursor.execute("SELECT * FROM users WHERE id=" + user_id)\n'
DANGEROUS_CODE = (
    "import pickle\nimport os\nos.system('rm -rf /')\n" + "pass" + "word = 'supersecretvalue123'\n"
)


class TestEnhancedASTScanner:
    def test_init_splits_lines(self):
        scanner = EnhancedASTScanner("f.py", "a\nb\nc")
        assert scanner.file_path == "f.py"
        assert scanner.lines == ["a", "b", "c"]
        assert scanner.issues == []

    def test_scan_detects_command_injection_call(self):
        scanner = EnhancedASTScanner("f.py", "os.system('ls')\n")
        issues = scanner.scan()
        assert any(i.category == "command_injection" and i.severity == "critical" for i in issues)
        cmd_issue = next(i for i in issues if i.category == "command_injection")
        assert cmd_issue.line_number == 1
        assert "os.system" in cmd_issue.description

    def test_scan_detects_subprocess_call(self):
        scanner = EnhancedASTScanner("f.py", "import subprocess\nsubprocess.run('ls')\n")
        issues = scanner.scan()
        assert any(
            i.category == "command_injection" and "subprocess" in i.description for i in issues
        )

    def test_scan_detects_sql_injection_pattern(self):
        scanner = EnhancedASTScanner("f.py", SQLI_CODE)
        issues = scanner.scan()
        assert any(i.category == "sql_injection" and i.severity == "critical" for i in issues)

    def test_scan_detects_hardcoded_secret_pattern(self):
        scanner = EnhancedASTScanner("f.py", "api_key = 'abcdefghijklmnopqrstuvwxyz'\n")
        issues = scanner.scan()
        assert any(i.category == "hardcoded_secrets" for i in issues)

    def test_scan_detects_insecure_deserialization_pattern(self):
        scanner = EnhancedASTScanner("f.py", "data = pickle.loads(blob)\n")
        issues = scanner.scan()
        assert any(
            i.category == "insecure_deserialization" and i.severity == "high" for i in issues
        )

    def test_scan_detects_path_traversal_pattern(self):
        scanner = EnhancedASTScanner("f.py", "handle = open(base_path + name)\n")
        issues = scanner.scan()
        assert any(i.category == "path_traversal" and i.severity == "high" for i in issues)

    def test_pattern_line_number_and_snippet(self):
        code = "x = 1\ny = 2\ndata = pickle.loads(blob)\n"
        scanner = EnhancedASTScanner("f.py", code)
        issues = scanner.scan()
        deser = next(i for i in issues if i.category == "insecure_deserialization")
        assert deser.line_number == 3
        assert "pickle.loads" in deser.code_snippet

    def test_syntax_error_creates_code_quality_issue(self):
        scanner = EnhancedASTScanner("f.py", "def broken(:\n")
        issues = scanner.scan()
        assert len(issues) == 1
        issue = issues[0]
        assert issue.category == "code_quality"
        assert issue.severity == "medium"
        assert issue.line_number == 0
        assert "Syntax error" in issue.description

    def test_visit_import_flags_pickle(self):
        scanner = EnhancedASTScanner("f.py", "import pickle\n")
        issues = scanner.scan()
        assert any(
            i.category == "insecure_deserialization" and "pickle" in i.description for i in issues
        )

    def test_visit_import_ignores_safe_modules(self):
        scanner = EnhancedASTScanner("f.py", "import json\nfrom os.path import join\n")
        issues = scanner.scan()
        # os.path is not in the dangerous set for plain imports
        assert not any("json" in i.description for i in issues)

    def test_visit_import_from_flags_cgi(self):
        scanner = EnhancedASTScanner("f.py", "from cgi import parse_qs\n")
        issues = scanner.scan()
        assert any("cgi" in i.description for i in issues)

    def test_visit_import_from_relative_is_ignored(self):
        scanner = EnhancedASTScanner("f.py", "from . import sibling\n")
        issues = scanner.scan()
        assert not any("insecure_deserialization" in i.category for i in issues)

    def test_visit_call_nested_attribute_does_not_crash(self):
        # node.func.value is an Attribute (no .id) -> AttributeError swallowed
        scanner = EnhancedASTScanner("f.py", "obj.sub.system('x')\n")
        issues = scanner.scan()
        assert not any(
            i.category == "command_injection" and "obj.sub" in i.description for i in issues
        )

    def test_visit_call_non_name_value_ignored(self):
        scanner = EnhancedASTScanner("f.py", "handlers['run']('x')\n")
        issues = scanner.scan()
        assert not any("unsafe" in i.description for i in issues)

    def test_visit_call_name_not_os_or_subprocess_ignored(self):
        # func.value is a Name but not os/subprocess -> no issue (branch 110->121)
        scanner = EnhancedASTScanner("f.py", "obj.system('x')\nrunner.call('y')\n")
        issues = scanner.scan()
        assert not any(i.category == "command_injection" for i in issues)

    def test_visit_call_exception_swallowed(self, monkeypatch):
        # An unexpected error inside visit_Call is logged at debug and swallowed
        scanner = EnhancedASTScanner("f.py", "os.system('x')\n")

        def boom(*args, **kwargs):
            raise RuntimeError("injected failure")

        monkeypatch.setattr(scanner, "_add_issue", boom)
        # Should not raise — the AST-based issue is swallowed by the handler
        scanner.scan()
        # The regex pattern-scan still runs afterwards and reports os.system
        assert not any("Potentially unsafe" in i.description for i in scanner.issues)

    def test_add_issue_line_out_of_bounds_snippet_empty(self):
        scanner = EnhancedASTScanner("f.py", "os.system('x')\n")
        # Fabricate a node without a valid lineno
        node = ast.parse("pass").body[0]
        node.lineno = 99  # beyond len(lines)
        scanner._add_issue("high", "test", "desc", node, "fix it")
        issue = scanner.issues[0]
        assert issue.code_snippet == ""
        assert issue.line_number == 99

    def test_add_issue_zero_lineno(self):
        scanner = EnhancedASTScanner("f.py", "x = 1\n")
        node = ast.parse("pass").body[0]
        node.lineno = 0
        scanner._add_issue("low", "test", "desc", node, "fix")
        assert scanner.issues[0].code_snippet == ""
        assert scanner.issues[0].line_number == 0

    def test_scan_returns_same_list_instance(self):
        scanner = EnhancedASTScanner("f.py", "x = 1\n")
        issues = scanner.scan()
        assert issues is scanner.issues

    def test_clean_code_no_issues(self):
        scanner = EnhancedASTScanner("f.py", "value = compute(1, 2)\nprint(value)\n")
        assert scanner.scan() == []


class TestSecurityScanner:
    def test_default_scan_paths(self):
        scanner = SecurityScanner()
        assert scanner.scan_paths == ["backend"]

    def test_custom_scan_paths(self):
        scanner = SecurityScanner(scan_paths=["/tmp/a", "/tmp/b"])
        assert scanner.scan_paths == ["/tmp/a", "/tmp/b"]

    def test_scan_file_clean_file(self, tmp_path):
        target = tmp_path / "clean.py"
        target.write_text("value = 1\n", encoding="utf-8")
        issues = SecurityScanner().scan_file(str(target))
        assert issues == []

    def test_scan_file_with_issues(self, tmp_path):
        target = tmp_path / "dirty.py"
        target.write_text("os.system('x')\n", encoding="utf-8")
        issues = SecurityScanner().scan_file(str(target))
        assert any(i.category == "command_injection" for i in issues)

    def test_scan_file_empty_returns_empty(self, tmp_path):
        target = tmp_path / "empty.py"
        target.write_text("   \n", encoding="utf-8")
        assert SecurityScanner().scan_file(str(target)) == []

    def test_scan_file_missing_file_returns_empty(self, tmp_path):
        missing = tmp_path / "nope.py"
        assert SecurityScanner().scan_file(str(missing)) == []

    def test_scan_file_directory_path_returns_empty(self, tmp_path):
        # open() on a directory raises IsADirectoryError -> caught -> []
        assert SecurityScanner().scan_file(str(tmp_path)) == []

    def test_scan_directory_missing_returns_empty(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        assert SecurityScanner().scan_directory(str(missing)) == []

    def test_scan_directory_skips_ignored_paths(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "dirty.py").write_text("os.system('x')\n", encoding="utf-8")
        scanner = SecurityScanner()
        # The directory itself contains "tests" in path when rooted there —
        # use a scan root whose own path is free of ignore patterns.
        assert scanner.scan_directory(str(tmp_path)) == []

    def test_scan_directory_scans_py_files_only(self, tmp_path):
        (tmp_path / "dirty.py").write_text("os.system('x')\n", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("os.system('x')\n", encoding="utf-8")
        issues = SecurityScanner().scan_directory(str(tmp_path))
        assert len(issues) >= 1
        assert all(i.file_path.endswith(".py") for i in issues)

    def test_scan_directory_handles_rglob_error(self, tmp_path):
        scanner = SecurityScanner()
        with patch("pathlib.Path.rglob", side_effect=OSError("boom")):
            assert scanner.scan_directory(str(tmp_path)) == []

    def test_scan_all_with_file_path(self, tmp_path):
        target = tmp_path / "single.py"
        target.write_text("os.system('x')\n", encoding="utf-8")
        scanner = SecurityScanner(scan_paths=[str(target)])
        assert any(i.category == "command_injection" for i in scanner.scan_all())

    def test_scan_all_with_dir_path(self, tmp_path):
        (tmp_path / "dirty.py").write_text("os.system('x')\n", encoding="utf-8")
        scanner = SecurityScanner(scan_paths=[str(tmp_path)])
        assert scanner.scan_all()

    def test_scan_all_skips_nonexistent_path(self, tmp_path):
        scanner = SecurityScanner(scan_paths=[str(tmp_path / "ghost")])
        assert scanner.scan_all() == []

    def test_generate_report_with_issues(self):
        issues = [
            SecurityIssue(
                severity="critical",
                category="command_injection",
                description="d1",
                file_path="a.py",
                line_number=1,
                code_snippet="os.system('x')",
                recommendation="r1",
            ),
            SecurityIssue(
                severity="high",
                category="insecure_deserialization",
                description="d2",
                file_path="b.py",
                line_number=2,
                code_snippet="pickle.loads(x)",
                recommendation="r2",
            ),
            SecurityIssue(
                severity="critical",
                category="command_injection",
                description="d3",
                file_path="c.py",
                line_number=3,
                code_snippet="eval(x)",
                recommendation="r3",
            ),
        ]
        report = SecurityScanner().generate_report(issues)
        assert report["total_issues"] == 3
        assert report["by_severity"]["critical"] == 2
        assert report["by_severity"]["high"] == 1
        assert report["by_severity"]["info"] == 0
        assert report["by_category"] == {"command_injection": 2, "insecure_deserialization": 1}
        assert report["issues"][0]["file"] == "a.py"
        assert report["issues"][0]["code"] == "os.system('x')"
        assert isinstance(report["timestamp"], float)

    def test_generate_report_triggers_scan_when_issues_none(self, tmp_path):
        target = tmp_path / "dirty.py"
        target.write_text("os.system('x')\n", encoding="utf-8")
        scanner = SecurityScanner(scan_paths=[str(target)])
        report = scanner.generate_report(None)
        assert report["total_issues"] >= 1


class TestMainEntryPoint:
    def _run_main(self, monkeypatch, issues):
        fake_scanner = MagicMock()
        fake_scanner.scan_all.return_value = issues
        fake_scanner.generate_report.return_value = {"by_severity": {"critical": 1, "high": 0}}
        monkeypatch.setattr(eas_module, "SecurityScanner", lambda: fake_scanner)
        monkeypatch.setattr(eas_module.logger, "info", MagicMock())
        return fake_scanner

    def test_main_exits_nonzero_on_critical(self, monkeypatch):
        issue = SecurityIssue(
            severity="critical",
            category="command_injection",
            description="d",
            file_path="a.py",
            line_number=1,
            code_snippet="",
            recommendation="r",
        )
        self._run_main(monkeypatch, [issue])
        with pytest.raises(SystemExit) as excinfo:
            eas_module.main()
        assert excinfo.value.code == 1

    def test_main_exits_nonzero_on_high(self, monkeypatch):
        fake_scanner = MagicMock()
        fake_scanner.scan_all.return_value = []
        fake_scanner.generate_report.return_value = {"by_severity": {"critical": 0, "high": 3}}
        monkeypatch.setattr(eas_module, "SecurityScanner", lambda: fake_scanner)
        with pytest.raises(SystemExit):
            eas_module.main()

    def test_main_returns_clean_when_no_critical_or_high(self, monkeypatch):
        fake_scanner = MagicMock()
        fake_scanner.scan_all.return_value = []
        fake_scanner.generate_report.return_value = {
            "by_severity": {"critical": 0, "high": 0, "medium": 1}
        }
        monkeypatch.setattr(eas_module, "SecurityScanner", lambda: fake_scanner)
        # Should not raise SystemExit
        eas_module.main()


class TestSecurityIssueDataclass:
    def test_fields_round_trip(self):
        issue = SecurityIssue(
            severity="low",
            category="info",
            description="note",
            file_path="x.py",
            line_number=7,
            code_snippet="pass",
            recommendation="ok",
        )
        assert (issue.severity, issue.line_number, issue.file_path) == ("low", 7, "x.py")


def _simple_namespace(**kwargs):
    return SimpleNamespace(**kwargs)
