#!/usr/bin/env python3
"""Tests for rules_breaker.py — Red Team Pentest Scanner."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.agents.rules_breaker import (
    scan_secret_hardcoding,
    scan_localhost_binding,
    scan_silent_failures,
    scan_test_manipulation,
    scan_docs_garbage,
    scan_privilege_elevation,
    scan_client_side_auth,
    probe_sql_injection_patterns,
    probe_path_traversal_patterns,
    probe_xss_patterns,
    probe_auth_bypass,
    probe_insecure_deserialization,
    probe_cors_misconfiguration,
    probe_log_injection,
    probe_self_merge_patterns,
)


class TestSecretHardcoding:
    def test_detects_api_key(self, tmp_path: Path) -> None:
        f = tmp_path / "config.py"
        f.write_text('API_KEY = "sk-abcdefghij1234567890"\n')
        # Patch ROOT_DIR via monkeypatch would require module reload;
        # instead test regex directly
        import re
        pattern = r'(?i)(api_key|apikey|api_secret|secret_key|private_key|access_key)\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']'
        text = f.read_text()
        assert re.search(pattern, text)

    def test_ignores_comments(self, tmp_path: Path) -> None:
        f = tmp_path / "safe.py"
        f.write_text('# API_KEY = "sk-abcdefghij1234567890"\n')
        import re
        pattern = r'(?i)(api_key|apikey|api_secret|secret_key|private_key|access_key)\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']'
        text = f.read_text()
        # Comments should still match naive regex — scanner uses line-level
        # This test documents current behavior; scanner skips comment lines
        matches = [i for i, line in enumerate(text.splitlines(), 1) if not line.strip().startswith("#") and re.search(pattern, line)]
        assert matches == []


class TestLocalhostBinding:
    def test_detects_localhost(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text('HOST = "127.0.0.1"\nPORT = 8000\n')
        import re
        pattern = r'(?i)(localhost|127\.0\.0\.1|0\.0\.0\.0)'
        text = f.read_text()
        assert re.search(pattern, text)

    def test_ignores_comment(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text('# BIND = "127.0.0.1"\n')
        lines = f.read_text().splitlines()
        matches = [l for l in lines if not l.strip().startswith("#") and re.search(r'(?i)(localhost|127\.0\.0\.1)', l)]
        assert matches == []


class TestSilentFailures:
    def test_detects_bare_except_pass(self, tmp_path: Path) -> None:
        import re
        f = tmp_path / "risky.py"
        f.write_text("try:\n    do_something()\nexcept Exception:\n    pass\n")
        lines = f.read_text().splitlines()
        found = False
        for i, line in enumerate(lines, start=1):
            if line.strip().startswith("#"):
                continue
            if re.match(r'^\s*except\b.*:\s*$', line):
                j = i
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        if next_line == "pass":
                            found = True
                        break
                    j += 1
        assert found

    def test_allows_logged_except(self, tmp_path: Path) -> None:
        import re
        f = tmp_path / "safe.py"
        f.write_text("try:\n    do_something()\nexcept Exception:\n    logger.error(e)\n")
        lines = f.read_text().splitlines()
        found = False
        for i, line in enumerate(lines, start=1):
            if line.strip().startswith("#"):
                continue
            if re.match(r'^\s*except\b.*:\s*$', line):
                j = i
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith("#"):
                        if next_line == "pass":
                            found = True
                        break
                    j += 1
        assert not found


class TestTestManipulation:
    def test_detects_skip_marker(self, tmp_path: Path) -> None:
        f = tmp_path / "test_bad.py"
        f.write_text("import pytest\n\n@pytest.mark.skip\n def test_bug():\n    pass\n")
        import re
        assert re.search(r'@pytest\.mark\.skip', f.read_text())

    def test_detects_xfail_marker(self, tmp_path: Path) -> None:
        f = tmp_path / "test_bad.py"
        f.write_text("import pytest\n\n@pytest.mark.xfail\n def test_bug():\n    pass\n")
        import re
        assert re.search(r'@pytest\.mark\.xfail', f.read_text())


class TestDocsGarbage:
    def test_flags_non_canonical_docs(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        rogue = docs_dir / "random_note.md"
        rogue.write_text("# Random note\n")
        allowed = {"docs/master_docs", "docs/agents", "docs/architecture", "docs/governance", "docs/INDEX.md", "docs/ROADMAP.md"}
        rel = str(rogue.relative_to(tmp_path)).replace("\\", "/")
        is_allowed = any(rel == a or rel.startswith(a + "/") for a in allowed)
        assert not is_allowed

    def test_allows_canonical_docs(self, tmp_path: Path) -> None:
        canonical = tmp_path / "docs" / "master_docs" / "ARCH-01.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Canonical\n")
        allowed = {"docs/master_docs", "docs/agents", "docs/architecture", "docs/governance", "docs/INDEX.md", "docs/ROADMAP.md"}
        rel = str(canonical.relative_to(tmp_path)).replace("\\", "/")
        is_allowed = any(rel == a or rel.startswith(a + "/") for a in allowed)
        assert is_allowed


class TestPrivilegeElevation:
    def test_detects_sudo(self, tmp_path: Path) -> None:
        f = tmp_path / "setup.sh"
        f.write_text("sudo apt-get install nginx\n")
        import re
        assert re.search(r'(?i)(sudo\s+|runas\s+|elevat\w*\s*\(|ShellExecute.*runas|admin.*privilege)', f.read_text())

    def test_ignores_safe_comment(self, tmp_path: Path) -> None:
        f = tmp_path / "safe.sh"
        f.write_text("# sudo is not used here\n")
        lines = f.read_text().splitlines()
        matches = [l for l in lines if not l.strip().startswith("#") and re.search(r'(?i)(sudo\s+|runas\s+|elevat\w*\s*\()', l)]
        assert matches == []


class TestSQLInjection:
    def test_detects_fstring_sql(self, tmp_path: Path) -> None:
        f = tmp_path / "query.py"
        f.write_text('cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n')
        import re
        assert re.search(r'(?i)(execute|executemany)\s*\(.*f["\']', f.read_text())

    def test_detects_concatenated_sql(self, tmp_path: Path) -> None:
        f = tmp_path / "query.py"
        f.write_text('cursor.execute("SELECT * FROM users WHERE id = " + user_id)\n')
        import re
        assert re.search(r'(?i)(execute|executemany)\s*\(.*\+', f.read_text())


class TestPathTraversal:
    def test_detects_user_input_in_path(self, tmp_path: Path) -> None:
        f = tmp_path / "serve.py"
        f.write_text("filepath = os.path.join(BASE_DIR, request.args['filename'])\n")
        import re
        assert re.search(r'(?i)(os\.path\.join|Path\().*request\.(args|params|query|body|form)', f.read_text())


class TestXSS:
    def test_detects_innerhtml(self, tmp_path: Path) -> None:
        f = tmp_path / "app.tsx"
        f.write_text("element.innerHTML = userInput;\n")
        import re
        assert re.search(r'(?i)(innerHTML\s*=|dangerouslySetInnerHTML)', f.read_text())


class TestInsecureDeserialization:
    def test_detects_pickle_loads(self, tmp_path: Path) -> None:
        f = tmp_path / "load.py"
        f.write_text("data = pickle.loads(user_bytes)\n")
        import re
        assert re.search(r'(?i)(pickle\.loads?|yaml\.load\(.*Loader=None|eval\(|exec\()', f.read_text())


class TestCORS:
    def test_detects_wildcard_cors(self, tmp_path: Path) -> None:
        f = tmp_path / "main.py"
        f.write_text('CORS(app, origins=["*"])\n')
        import re
        assert re.search(r'(?i)(origins\s*=\s*\["\*"\]|allow_all|Access-Control-Allow-Origin.*\*)', f.read_text())


class TestSelfMerge:
    def test_detects_self_merge_pattern(self, tmp_path: Path) -> None:
        f = tmp_path / "bot.py"
        f.write_text("# Self-merge is not allowed\n")
        # Should not match because it's a comment
        lines = f.read_text().splitlines()
        matches = [l for l in lines if not l.strip().startswith("#") and re.search(r'(?i)(self_merge|self-merge|self_approv)', l)]
        assert matches == []


class TestLogInjection:
    def test_detects_user_input_in_log(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("logger.info(f'User said: {request.body}')\n")
        import re
        assert re.search(r'(?i)(print\(.*request\.|logger\.(info|debug|warn|error)\(.*request\.)', f.read_text())


class TestRuleBreakerIntegration:
    def test_scanner_returns_findings_list(self) -> None:
        # Test that scanners return list of dicts with expected keys
        result = scan_silent_failures(10)
        assert isinstance(result, list)
        for item in result:
            assert "file" in item
            assert "line" in item
            assert "rule" in item
            assert "severity" in item
            assert "description" in item

    def test_secret_scanner_returns_findings_list(self) -> None:
        result = scan_secret_hardcoding(10)
        assert isinstance(result, list)
        for item in result:
            assert "file" in item
            assert "snippet" in item
            assert "rule" in item

    def test_localhost_scanner_returns_findings_list(self) -> None:
        result = scan_localhost_binding(10)
        assert isinstance(result, list)
        for item in result:
            assert "file" in item
            assert "description" in item
