"""Tests for AutonoGuard Engine - Autonomous governance layer.

This module tests:
- JIT OTP verification and requests
- IP churn detection
- AST security scanning
- Error remediation
- Operation enforcement
- Circuit breaker integration
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.autonoguard_engine import (
    SENSITIVE_OPS,
    AutonoGuardEngine,
    ChurnDetection,
    OperationContext,
    autonoguard_engine,
)

# --- OperationContext Tests ---


class TestOperationContext:
    """Tests for OperationContext model."""

    def test_context_creation(self):
        """Test creating OperationContext."""
        context = OperationContext(
            admin_id="admin-123",
            ip_address="192.168.1.1",
            path="/api/v1/admin/users",
            method="POST",
            headers={"Content-Type": "application/json"},
            correlation_id="corr-456",
        )

        assert context.admin_id == "admin-123"
        assert context.ip_address == "192.168.1.1"
        assert context.correlation_id == "corr-456"

    def test_context_defaults(self):
        """Test OperationContext default values."""
        context = OperationContext(
            admin_id="admin",
            ip_address="127.0.0.1",  # is_local()
            path="/test",
            method="GET",
            headers={},
        )

        assert context.correlation_id is None


# --- ChurnDetection Tests ---


class TestChurnDetection:
    """Tests for ChurnDetection model."""

    def test_churn_detection_creation(self):
        """Test creating ChurnDetection."""
        detection = ChurnDetection(
            is_churn=True,
            previous_ips=["192.168.1.1", "10.0.0.1"],
            first_seen=time.time(),
            churn_count=6,
        )

        assert detection.is_churn is True
        assert len(detection.previous_ips) == 2
        assert detection.churn_count == 6


# --- AutonoGuardEngine Tests ---


class TestAutonoGuardEngine:
    """Tests for AutonoGuardEngine class."""

    def test_init(self):
        """Test engine initialization."""
        engine = AutonoGuardEngine()

        assert engine._initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test engine async initialization."""
        engine = AutonoGuardEngine()

        with patch("core.autonoguard_engine.redis_manager") as mock_redis:
            mock_redis.client = MagicMock()
            mock_redis.set_cache = AsyncMock()

            await engine.initialize()

            assert engine._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that initialize is idempotent."""
        engine = AutonoGuardEngine()

        with patch("core.autonoguard_engine.redis_manager") as mock_redis:
            mock_redis.client = MagicMock()
            mock_redis.set_cache = AsyncMock()

            await engine.initialize()
            await engine.initialize()  # Should not re-initialize

            mock_redis.set_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_ip_churn_no_redis(self):
        """Test IP churn detection when Redis unavailable."""
        engine = AutonoGuardEngine()

        with patch("core.autonoguard_engine.redis_manager", None):
            result = await engine.detect_ip_churn("admin-123", "192.168.1.1")

            assert result.is_churn is False
            assert result.churn_count == 0

    @pytest.mark.asyncio
    async def test_detect_ip_churn_with_history(self):
        """Test IP churn detection with IP history."""
        engine = AutonoGuardEngine()

        mock_redis = MagicMock()
        mock_redis.client = MagicMock()
        mock_redis.hgetall = AsyncMock(
            return_value={
                "192.168.1.1": "1234567890",
                "10.0.0.1": "1234567891",
                "first_seen": "1234567800",
            }
        )
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch("core.autonoguard_engine.redis_manager", mock_redis):
            result = await engine.detect_ip_churn("admin-123", "172.16.0.1")

            assert isinstance(result, ChurnDetection)

    @pytest.mark.asyncio
    async def test_verify_jit_otp_no_redis(self):
        """Test OTP verification when Redis unavailable."""
        engine = AutonoGuardEngine()

        with patch("core.autonoguard_engine.redis_manager", None):
            result = await engine.verify_jit_otp("admin-123", "123456")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_jit_otp_valid(self):
        """Test OTP verification with valid code."""
        import hashlib

        engine = AutonoGuardEngine()
        code = "123456"
        expected_hash = hashlib.sha256(code.encode()).hexdigest()

        mock_redis = MagicMock()
        mock_redis.get_cache = AsyncMock(return_value=expected_hash)
        mock_redis.client = MagicMock()
        mock_redis.client.delete = AsyncMock()

        with patch("core.autonoguard_engine.redis_manager", mock_redis):
            result = await engine.verify_jit_otp("admin-123", code)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_jit_otp_invalid(self):
        """Test OTP verification with invalid code."""
        engine = AutonoGuardEngine()

        mock_redis = MagicMock()
        mock_redis.get_cache = AsyncMock(return_value="wrong_hash")

        with patch("core.autonoguard_engine.redis_manager", mock_redis):
            result = await engine.verify_jit_otp("admin-123", "123456")

            assert result is False

    @pytest.mark.asyncio
    async def test_request_jit_otp_cooldown(self):
        """Test OTP request respects cooldown."""
        engine = AutonoGuardEngine()

        mock_redis = MagicMock()
        mock_redis.get_cache = AsyncMock(return_value="1")  # Cooldown active

        with patch("core.autonoguard_engine.redis_manager", mock_redis):
            result = await engine.request_jit_otp("admin-123", {})

            assert result is False

    @pytest.mark.asyncio
    async def test_can_bypass_otp_disabled(self):
        """Test OTP bypass when anti-hacking disabled."""
        engine = AutonoGuardEngine()

        with patch("core.autonoguard_engine.ANTI_HACKING_ENABLED", False):
            result = await engine.can_bypass_otp("admin-123", "192.168.1.1")

            assert result is True

    @pytest.mark.asyncio
    async def test_enforce_operation_no_anti_hacking(self):
        """Test operation enforcement when anti-hacking disabled."""
        engine = AutonoGuardEngine()

        with (
            patch("core.autonoguard_engine.ANTI_HACKING_ENABLED", False),
            patch.object(engine, "scan_for_threats", return_value={"safe": True}),
        ):
            allowed, error = await engine.enforce_operation(
                admin_id="admin-123",
                ip="192.168.1.1",
                otp_code=None,
                path="/api/v1/admin/users",
                method="POST",
            )

            assert allowed is True
            assert error is None

    @pytest.mark.asyncio
    async def test_enforce_operation_blocked_code(self):
        """Test operation enforcement with unsafe code."""
        engine = AutonoGuardEngine()

        with (
            patch("core.autonoguard_engine.ANTI_HACKING_ENABLED", False),
            patch.object(
                engine,
                "scan_for_threats",
                return_value={"safe": False, "error": "malicious code"},
            ),
        ):
            allowed, error = await engine.enforce_operation(
                admin_id="admin-123",
                ip="192.168.1.1",
                otp_code=None,
                path="/api/v1/admin/users",
                method="POST",
                code_to_scan="import os; os.system('echo test')",
            )

            assert allowed is False
            assert "Security validation failed" in error

    @pytest.mark.asyncio
    async def test_heal_error_circuit_breaker_open(self):
        """Test heal error skips when circuit breaker open."""
        engine = AutonoGuardEngine()

        from unittest.mock import MagicMock

        engine._circuit_breaker = MagicMock()
        engine._circuit_breaker.allow_request.return_value = False

        result = await engine.heal_error(
            Exception("test"),
            OperationContext(
                admin_id="admin",
                ip_address="127.0.0.1",  # is_local()
                path="/test",
                method="GET",
                headers={},
            ),
        )

        assert result is None


class TestSensitiveOps:
    """Tests for SENSITIVE_OPS configuration."""

    def test_sensitive_ops_defined(self):
        """Test that sensitive operations are defined."""
        assert len(SENSITIVE_OPS) > 0
        assert "/api/v1/admin/" in SENSITIVE_OPS
        assert "/api/v1/billing/" in SENSITIVE_OPS

    def test_sensitive_ops_contains_orchestrate(self):
        """Test that orchestrate endpoint is sensitive."""
        assert "/api/v1/orchestrate/" in SENSITIVE_OPS


class TestSingleton:
    """Tests for autonoguard_engine singleton."""

    def test_singleton_exists(self):
        """Test that autonoguard_engine singleton exists."""
        assert autonoguard_engine is not None
        assert isinstance(autonoguard_engine, AutonoGuardEngine)
