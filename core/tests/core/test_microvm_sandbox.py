"""Tests for MicroVM Sandbox - Secure code execution environment.

This module tests:
- Sandbox root validation
- VM ID generation and validation
- Docker image whitelist enforcement
- Firecracker execution
- gVisor execution
- Docker fallback execution
- Path traversal prevention
- CancelledError handling
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.microvm_sandbox import (
    _ALLOWED_DOCKER_IMAGES,
    _VM_ID_PATTERN,
    MicroVMSandbox,
    _validate_sandbox_root,
    _validate_vm_id,
    execute_code_securely,
    get_sandbox,
)

# --- Validation Tests ---


class TestValidation:
    """Tests for validation functions."""

    def test_validate_vm_id_valid(self):
        """Test VM ID validation with valid input."""
        result = _validate_vm_id("test-vm-123")

        assert result == "test-vm-123"

    def test_validate_vm_id_alphanumeric(self):
        """Test VM ID validation with alphanumeric."""
        result = _validate_vm_id("vm_123-abc")

        assert result == "vm_123-abc"

    def test_validate_vm_id_too_long(self):
        """Test VM ID validation rejects too long IDs."""
        long_id = "a" * 65

        with pytest.raises(ValueError) as exc_info:
            _validate_vm_id(long_id)

        assert "Invalid vm_id" in str(exc_info.value)

    def test_validate_vm_id_invalid_chars(self):
        """Test VM ID validation rejects invalid characters."""
        with pytest.raises(ValueError):
            _validate_vm_id("test@vm!")

    def test_validate_sandbox_root_valid(self):
        """Test sandbox root validation with whitelisted path."""
        whitelisted_path = str(Path("/tmp/sandboxes").resolve())
        whitelist = {whitelisted_path}

        with patch("core.microvm_sandbox._SANDBOX_ROOT_WHITELIST", frozenset(whitelist)):
            result = _validate_sandbox_root("/tmp/sandboxes")

            assert result == Path("/tmp/sandboxes").resolve()

    def test_validate_sandbox_root_invalid(self):
        """Test sandbox root validation rejects non-whitelisted path."""
        with pytest.raises(ValueError) as exc_info:
            _validate_sandbox_root("/etc/passwd")

        assert "not in the allowed whitelist" in str(exc_info.value)


# --- MicroVMSandbox Tests ---


class TestMicroVMSandbox:
    """Tests for MicroVMSandbox class."""

    def test_init_with_valid_path(self):
        """Test MicroVMSandbox initialization with valid sandbox root."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
        ):
            mock_settings.sandbox_root = "/tmp/sandboxes"
            mock_settings.firecracker_path = "/usr/bin/firecracker"
            mock_settings.gvisor_path = "/usr/bin/runsc"
            mock_settings.allow_sandbox_fallback = True

            sandbox = MicroVMSandbox()

            assert sandbox.sandbox_root == Path("/tmp/sandboxes")
            assert sandbox.auto_destroy is True

    def test_generate_vm_id(self):
        """Test VM ID generation."""
        with patch("core.microvm_sandbox.settings"):
            # Get a VM ID
            vm_id = MicroVMSandbox._generate_vm_id()

            assert _VM_ID_PATTERN.match(vm_id) is not None
            assert "supremeai-vm-" in vm_id

    def test_check_microvm_available_none(self):
        """Test VM availability check when no runtime available."""
        with patch("core.microvm_sandbox.settings"):
            sandbox = MicroVMSandbox.__new__(MicroVMSandbox)

            with patch("shutil.which", return_value=None):
                result = sandbox._check_microvm_available()

                assert result is None


# --- Docker Whitelist Tests ---


class TestDockerWhitelist:
    """Tests for Docker image whitelist."""

    def test_allowed_images_set(self):
        """Test that allowed images are defined."""
        assert len(_ALLOWED_DOCKER_IMAGES) > 0
        assert "python:3.11-slim" in _ALLOWED_DOCKER_IMAGES

    def test_default_image_in_whitelist(self):
        """Test that default image is in whitelist."""
        from core.microvm_sandbox import _DEFAULT_DOCKER_IMAGE

        assert _DEFAULT_DOCKER_IMAGE in _ALLOWED_DOCKER_IMAGES


# --- Execute Code Securely Tests ---


class TestExecuteCodeSecurely:
    """Tests for execute_code_securely function."""

    @pytest.mark.asyncio
    async def test_execute_with_no_runtime(self):
        """Test execution when no runtime is available."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
            patch("core.microvm_sandbox.shutil.which", return_value=None),
        ):
            mock_settings.sandbox_root = "/tmp/sandboxes"
            mock_settings.firecracker_path = "/usr/bin/firecracker"
            mock_settings.gvisor_path = "/usr/bin/runsc"
            mock_settings.allow_sandbox_fallback = False

            result = await execute_code_securely("print('hello')")

            assert result["success"] is False
            assert "unavailable" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_uses_docker_fallback(self):
        """Test execution uses Docker fallback when enabled."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
            patch("core.microvm_sandbox.shutil.which", return_value=None),
            patch("core.microvm_sandbox.subprocess.run") as mock_run,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            mock_settings.sandbox_root = tmpdir
            mock_settings.firecracker_path = "/usr/bin/firecracker"
            mock_settings.gvisor_path = "/usr/bin/runsc"
            mock_settings.allow_sandbox_fallback = True

            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="hello",
                stderr="",
            )

            result = await execute_code_securely("print('hello')")

            assert "provider" in result

    @pytest.mark.asyncio
    async def test_cancelled_error_reraised(self):
        """Test that CancelledError is always re-raised."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
            patch("core.microvm_sandbox.shutil.which", return_value=None),
            patch("core.microvm_sandbox.subprocess.run", side_effect=Exception("test")),
        ):
            mock_settings.sandbox_root = "/tmp/sandboxes"
            mock_settings.allow_sandbox_fallback = True

            # CancelledError should be re-raised, not caught
            import asyncio

            async def run_with_cancel():
                task = asyncio.create_task(execute_code_securely("test"))
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    return "cancelled"
                return "not cancelled"

            result = await run_with_cancel()
            assert result == "cancelled"


# --- Health Check Tests ---


class TestMicroVMHealthCheck:
    """Tests for sandbox health check."""

    @pytest.mark.anyio
    async def test_health_check(self):
        """Test sandbox health check returns status."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
        ):
            mock_settings.sandbox_root = "/tmp/sandboxes"
            mock_settings.firecracker_path = "/usr/bin/firecracker"
            mock_settings.gvisor_path = "/usr/bin/runsc"
            mock_settings.allow_sandbox_fallback = True

            sandbox = MicroVMSandbox()
            # health_check is async — awaiting it in a sync test yields an
            # unawaited coroutine instead of a status dict.
            result = await sandbox.health_check()

            assert "status" in result
            assert "provider" in result


# --- Lazy Singleton Tests ---


class TestLazySingleton:
    """Tests for lazy singleton pattern."""

    def test_get_sandbox_returns_instance(self):
        """Test that get_sandbox returns a MicroVMSandbox instance."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
        ):
            mock_settings.sandbox_root = "/tmp/sandboxes"

            result = get_sandbox()

            assert isinstance(result, MicroVMSandbox)

    def test_get_sandbox_returns_same_instance(self):
        """Test that get_sandbox returns the same instance."""
        with (
            patch("core.microvm_sandbox.settings") as mock_settings,
            patch(
                "core.microvm_sandbox._validate_sandbox_root",
                return_value=Path("/tmp/sandboxes"),
            ),
        ):
            mock_settings.sandbox_root = "/tmp/sandboxes"

            result1 = get_sandbox()
            result2 = get_sandbox()

            assert result1 is result2
