"""Tests for core.security.audit_logger — log_security_event."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.security.audit_logger import log_security_event


class TestLogSecurityEvent:
    """Tests for log_security_event function."""

    @pytest.fixture(autouse=True)
    def reset_redis(self):
        """Reset redis_manager state to prevent 'Event loop is closed' errors across tests."""
        from core.cache.redis_manager import redis_manager

        old_client = getattr(redis_manager, "_client", None)
        old_init = getattr(redis_manager, "_initialized", False)

        redis_manager._client = None
        redis_manager._initialized = False

        yield

        redis_manager._client = old_client
        redis_manager._initialized = old_init

    @pytest.mark.anyio
    async def test_log_event_returns_event_id(self):
        event_id = await log_security_event(
            event_type="LOGIN_SUCCESS",
            user_id="user-123",
            details={"ip": "127.0.0.1"},  # is_local()
            severity="INFO",
        )
        assert isinstance(event_id, str)
        assert event_id.startswith("sec-")

    @pytest.mark.anyio
    async def test_log_event_without_redis(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "")
        from core.cache.redis_manager import redis_manager

        redis_manager._initialized = False
        redis_manager._client = None

        event_id = await log_security_event(
            event_type="TEST_EVENT",
            user_id="user-456",
            details={"action": "test"},
            severity="DEBUG",
        )
        assert event_id.startswith("sec-")

    @pytest.mark.anyio
    async def test_log_event_critical_severity(self):
        event_id = await log_security_event(
            event_type="SECURITY_BREACH",
            user_id="admin-1",
            details={"ip": "10.0.0.5"},
            severity="CRITICAL",
        )
        assert event_id.startswith("sec-")

    @pytest.mark.anyio
    async def test_log_event_with_none_user(self):
        event_id = await log_security_event(
            event_type="ANONYMOUS_ACCESS",
            user_id=None,
            details={"path": "/public"},
        )
        assert event_id.startswith("sec-")

    @pytest.mark.anyio
    async def test_log_event_high_severity(self):
        event_id = await log_security_event(
            event_type="RATE_LIMIT_EXCEEDED",
            user_id="user-789",
            details={"rate": "100/min"},
            severity="HIGH",
        )
        assert event_id.startswith("sec-")

    @pytest.mark.asyncio
    async def test_log_event_with_redis_mock(self):
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=True)
        mock_client = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_redis = MagicMock()
        mock_redis.client = mock_client

        with patch("core.security.audit_logger.redis_manager", mock_redis):
            event_id = await log_security_event(
                event_type="API_KEY_CREATED",
                user_id="admin-2",
                details={"key_name": "test-key"},
            )
            assert event_id.startswith("sec-")
            mock_pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_event_redis_failure_graceful(self):
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.side_effect = Exception("Redis connection failed")
        mock_client = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_redis.client = mock_client

        # বাংলা মন্তব্য: সিকিউরিটি গার্ড এখন সাইলেন্ট ফেলিয়ার প্রতিরোধে RuntimeError থ্রো করে, তাই টেস্টে pytest.raises যুক্ত করা হলো
        with patch("core.security.audit_logger.redis_manager", mock_redis):
            with pytest.raises(RuntimeError, match="Audit logger persistence failed"):
                await log_security_event(
                    event_type="TEST",
                    user_id="user",
                    details={},
                )
