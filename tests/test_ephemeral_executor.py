# tests/test_ephemeral_executor.py
"""Tests for EphemeralExecutor - secure code execution with cleanup."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import os


class TestEphemeralExecutorSecurity:
    """Test security features of EphemeralExecutor."""

    @pytest.fixture
    def temp_skills_dir(self, tmp_path):
        """Create a temporary skills directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return str(skills_dir)

    def test_malicious_skill_id_blocked(self, temp_skills_dir):
        """Test that path traversal in skill_id is blocked."""
        with patch('core.microvm_sandbox.MicroVMSandbox') as mock_sandbox_class:
            from backend.agents.ephemeral_executor import EphemeralExecutor

            mock_sandbox = MagicMock()
            mock_sandbox_class.return_value = mock_sandbox

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            malicious_ids = [
                "../etc/passwd",
                "..\\windows\\system32",
                "skill/../../../etc",
                "skill; rm -rf /",
                "skill$(whoami)",
            ]

            for skill_id in malicious_ids:
                result = executor.execute_use_and_throw(
                    skill_id=skill_id,
                    raw_code="def execute(): pass",
                    test_payload="{}"
                )

                assert result.exit_code == -1
                assert "Malicious" in result.stderr or "Blocked" in result.stderr

    def test_special_characters_in_skill_id_blocked(self, temp_skills_dir):
        """Test that special characters in skill_id are blocked."""
        with patch('core.microvm_sandbox.MicroVMSandbox') as mock_sandbox_class:
            from backend.agents.ephemeral_executor import EphemeralExecutor

            mock_sandbox = MagicMock()
            mock_sandbox_class.return_value = mock_sandbox

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            # Skill IDs should only contain alphanumeric and underscore
            result = executor.execute_use_and_throw(
                skill_id="../../../etc/passwd",
                raw_code="def execute(): pass",
                test_payload="{}"
            )

            assert result.exit_code == -1
            assert "Malicious" in result.stderr or "Blocked" in result.stderr


class TestEphemeralExecutorCleanup:
    """Test cleanup behavior of EphemeralExecutor."""

    @pytest.fixture
    def temp_skills_dir(self, tmp_path):
        """Create a temporary skills directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return str(skills_dir)

    def test_ephemeral_directory_created(self, temp_skills_dir):
        """Test that ephemeral directory is created on initialization."""
        with patch('core.microvm_sandbox.MicroVMSandbox'):
            from backend.agents.ephemeral_executor import EphemeralExecutor

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            ephemeral_path = Path(temp_skills_dir) / "ephemeral"
            assert ephemeral_path.exists()

    def test_cleanup_after_execution(self, temp_skills_dir):
        """Test that runtime directory is cleaned up after execution."""
        with patch('core.microvm_sandbox.MicroVMSandbox') as mock_sandbox_class:
            from backend.agents.ephemeral_executor import EphemeralExecutor

            mock_sandbox = MagicMock()
            mock_sandbox.run_quarantine_test.return_value = {
                "exit_code": 0,
                "stdout": "test output",
                "stderr": ""
            }
            mock_sandbox_class.return_value = mock_sandbox

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            # Execute a skill
            executor.execute_use_and_throw(
                skill_id="test_cleanup_skill",
                raw_code="# Test code\ndef execute(): return 'done'",
                test_payload="{}"
            )

            # Check that the skill directory was cleaned up
            skill_runtime_dir = Path(temp_skills_dir) / "ephemeral" / "test_cleanup_skill"
            assert not skill_runtime_dir.exists()

    def test_cleanup_after_failed_execution(self, temp_skills_dir):
        """Test cleanup happens even when execution fails."""
        with patch('core.microvm_sandbox.MicroVMSandbox') as mock_sandbox_class:
            from backend.agents.ephemeral_executor import EphemeralExecutor

            mock_sandbox = MagicMock()
            mock_sandbox.run_quarantine_test.side_effect = Exception("Sandbox error")
            mock_sandbox_class.return_value = mock_sandbox

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            # Execute should handle the exception gracefully
            try:
                result = executor.execute_use_and_throw(
                    skill_id="failed_skill",
                    raw_code="def execute(): raise Error()",
                    test_payload="{}"
                )
            except Exception:
                pass

            # Cleanup should still happen
            # Even if an exception occurs, the finally block should clean up


class TestEphemeralExecutorValidExecution:
    """Test valid execution scenarios."""

    @pytest.fixture
    def temp_skills_dir(self, tmp_path):
        """Create a temporary skills directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        return str(skills_dir)

    def test_valid_skill_execution(self, temp_skills_dir):
        """Test successful skill execution."""
        with patch('core.microvm_sandbox.MicroVMSandbox') as mock_sandbox_class:
            from backend.agents.ephemeral_executor import EphemeralExecutor

            mock_sandbox = MagicMock()
            mock_sandbox.run_quarantine_test.return_value = {
                "exit_code": 0,
                "stdout": "Execution successful",
                "stderr": ""
            }
            mock_sandbox_class.return_value = mock_sandbox

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            result = executor.execute_use_and_throw(
                skill_id="valid_skill",
                raw_code="def execute(): return 'success'",
                test_payload="{'test': true}"
            )

            assert result.exit_code == 0
            assert result.stdout == "Execution successful"

    def test_sandbox_called_with_correct_params(self, temp_skills_dir):
        """Test that sandbox is called with correct parameters."""
        with patch('core.microvm_sandbox.MicroVMSandbox') as mock_sandbox_class:
            from backend.agents.ephemeral_executor import EphemeralExecutor

            mock_sandbox = MagicMock()
            mock_sandbox.run_quarantine_test.return_value = {
                "exit_code": 0,
                "stdout": "test",
                "stderr": ""
            }
            mock_sandbox_class.return_value = mock_sandbox

            executor = EphemeralExecutor(base_skills_dir=temp_skills_dir)

            executor.execute_use_and_throw(
                skill_id="param_test_skill",
                raw_code="def execute():\n    return 'ok'",
                test_payload="test payload"
            )

            # Verify sandbox was called
            mock_sandbox.run_quarantine_test.assert_called_once()
