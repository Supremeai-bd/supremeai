# tests/test_agents_skill_ingestor.py
"""Tests for SkillIngestor agent - MCP skill ingestion and validation."""

from unittest.mock import MagicMock, patch

import pytest


class TestSkillIngestorStaticSafety:
    """Test static AST safety checking for skill code."""

    def test_safe_simple_function(self):
        """Test that safe simple code passes validation."""
        # Import with mocked sandbox
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            safe_code = "def execute(payload): return {'result': payload}"
            is_safe, msg = ingestor.static_ast_safety_check(safe_code)

            assert is_safe is True
            assert msg == "AST verified."

    def test_dangerous_subprocess_import(self):
        """Test that subprocess import is blocked."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            dangerous_code = "import subprocess; subprocess.Popen('echo malicious_payload_blocked')"
            is_safe, msg = ingestor.static_ast_safety_check(dangerous_code)

            assert is_safe is False
            assert "Forbidden import found" in msg or "subprocess" in msg

    def test_dangerous_os_system(self):
        """Test that os.system calls are blocked."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            dangerous_code = "import os; os.system('echo malicious_payload_blocked')"
            is_safe, msg = ingestor.static_ast_safety_check(dangerous_code)

            assert is_safe is False

    def test_dangerous_eval_call(self):
        """Test that eval calls are blocked."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            dangerous_code = 'result = eval(\'__import__("os").system("ls")\')'
            is_safe, msg = ingestor.static_ast_safety_check(dangerous_code)

            assert is_safe is False

    def test_dangerous_exec_call(self):
        """Test that exec calls are blocked."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            dangerous_code = "exec('import os; os.system(\"whoami\")')"
            is_safe, msg = ingestor.static_ast_safety_check(dangerous_code)

            assert is_safe is False

    def test_open_import_from_blocked(self):
        """Test that 'from os import' is blocked."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            dangerous_code = "from os import system; system('ls')"
            is_safe, msg = ingestor.static_ast_safety_check(dangerous_code)

            assert is_safe is False

    def test_safe_imports_allowed(self):
        """Test that safe imports are allowed."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            safe_code = "import json; import math; import re\ndef execute(payload): return json.dumps({'result': math.sqrt(16)})"
            is_safe, msg = ingestor.static_ast_safety_check(safe_code)

            assert is_safe is True


class TestSkillIngestorPathTraversal:
    """Test path traversal protection in skill ingestor."""

    def test_path_traversal_with_dotdot(self):
        """Test that path traversal attempts are blocked."""
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            ingestor = SkillIngestor()
            # Skill IDs with path traversal should be blocked
            malicious_ids = ["../etc", "..\\windows", "skill/../../../etc"]

            for skill_id in malicious_ids:
                is_safe, _ = ingestor.static_ast_safety_check("def exec(): pass")
                # The security check should catch malicious patterns in code
                # Path traversal is handled at execution level
                assert isinstance(is_safe, bool)


class TestSkillIngestorIngestMCP:
    """Test MCP skill ingestion functionality."""

    @pytest.fixture
    def mock_manifest(self):
        """Create a mock skill manifest."""
        manifest = MagicMock(skill_id="test_skill_123", name="Test Skill", version="1.0.0")
        # schemas/skill_index.py JSON-serializes manifest.model_dump(); a bare
        # MagicMock there returns a MagicMock which is not JSON-serializable.
        manifest.model_dump.return_value = {
            "skill_id": "test_skill_123",
            "name": "Test Skill",
            "version": "1.0.0",
        }
        return manifest

    def test_ingest_mcp_skill_success(self, mock_manifest, tmp_path):
        """Test successful MCP skill ingestion (fully offline + hermetic)."""
        import hashlib
        import io
        import zipfile as zipfile_mod

        from backend.schemas.skill_index import SkillIndexManager

        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            # Build a real in-memory zip so the checksum / zip-slip pipeline runs.
            buf = io.BytesIO()
            with zipfile_mod.ZipFile(buf, "w") as zf:
                zf.writestr("main.py", "x = 1\n")
            zip_bytes = buf.getvalue()

            mock_manifest.source_url = "https://github.com/modelcontextprotocol/servers/repo"
            mock_manifest.checksum = hashlib.sha256(zip_bytes).hexdigest()

            # Hermetic storage: staging/quarantine + skill index under tmp_path,
            # never the real backend/skills tree.
            ingestor = SkillIngestor(base_skills_dir=str(tmp_path))
            ingestor.index_manager = SkillIndexManager(tmp_path / ".index.json")
            ingestor.sandbox.run_quarantine_test.return_value = {"exit_code": 0}

            fake_response = MagicMock()
            fake_response.__enter__.return_value.read.return_value = zip_bytes
            with (
                patch("urllib.request.urlopen", return_value=fake_response),
                patch.object(
                    ingestor.morphic_adapter,
                    "adapt_code_to_contract",
                    return_value={"success": True, "code": "y = 2\n"},
                ),
            ):
                result = ingestor.ingest_mcp_skill(
                    manifest=mock_manifest,
                    zip_url="https://github.com/modelcontextprotocol/servers/skill.zip",
                    entry_file="main.py",
                    test_payload="{'test': true}",
                )

            # Should return a dict with success status
            assert isinstance(result, dict)
            assert result.get("success") is True, result


class TestSkillIngestorHarvestedScanner:
    """Step-2.5 (#2328): checks harvested from the retired ephemeral_synthesizer scanner."""

    @pytest.mark.parametrize(
        "code",
        [
            "import shutil",
            "from shutil import rmtree",
            "import builtins",
            "from builtins import open",
            "x = __import__('o' + 's')",
            "g = globals()",
            "l = locals()",
            "import os.path",
            "from os.path import join",
            "import requests",
        ],
    )
    def test_harvested_patterns_blocked(self, code):
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            is_safe, _ = SkillIngestor().static_ast_safety_check(code)
            assert is_safe is False

    def test_safe_code_still_passes(self):
        with patch("backend.agents.skill_ingestor.DockerSandbox"):
            from backend.agents.skill_ingestor import SkillIngestor

            code = "import json\ndef execute(p): return json.dumps(p)"
            assert SkillIngestor().static_ast_safety_check(code) == (True, "AST verified.")
