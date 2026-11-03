"""Integration tests for JIT OTP authentication flow.

বাংলা: JIT (Just-In-Time) OTP প্রমাণীকরণ ফ্লো — Discord, Email, Telegram, WhatsApp চ্যানেল সহ।
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.otp_router import (
    CHANNEL_DISCORD,
    CHANNEL_EMAIL,
    CHANNEL_TELEGRAM,
    CHANNEL_WHATSAPP,
    _mask,
    _sanitize_error,
    get_active_channel,
    send_otp,
    set_active_channel,
)


class TestJITOTPFlow:
    """Tests for JIT OTP authentication flow."""

    def test_mask_short_string(self):
        """Test masking short strings."""
        result = _mask("abc")
        assert result == "***"

    def test_mask_long_string(self):
        """Test masking long strings."""
        result = _mask("abcdefghijklmnopqrstuvwxyz")
        assert "..." in result
        assert len(result) < 20

    def test_mask_none(self):
        """Test masking None value."""
        result = _mask(None)
        assert result == "***"

    def test_sanitize_url(self):
        """Test URL sanitization in error messages."""
        msg = "Failed to connect to https://api.example.com/endpoint"
        result = _sanitize_error(Exception(msg))
        assert "[REDACTED_URL]" in result
        assert "api.example.com" not in result

    def test_sanitize_bearer_token(self):
        """Test bearer token sanitization."""
        msg = "Auth failed: Bearer abc123secret"
        result = _sanitize_error(Exception(msg))
        assert "[REDACTED_TOKEN]" in result
        assert "abc123secret" not in result

    def test_sanitize_truncates(self):
        """Test that sanitization truncates long messages."""
        long_msg = "a" * 300
        result = _sanitize_error(Exception(long_msg))
        assert len(result) <= 200

    @pytest.mark.asyncio
    async def test_get_active_channel_default(self):
        """Test getting channel defaults to Discord."""
        with patch("core.otp_router.redis_manager", None):
            result = await get_active_channel("admin-123")
        assert result == CHANNEL_DISCORD

    @pytest.mark.asyncio
    async def test_get_active_channel_override(self):
        """Test getting channel from Redis override."""
        mock_redis = MagicMock()
        mock_redis.client = True
        mock_redis.get_cache = AsyncMock(return_value="email")
        with patch("core.otp_router.redis_manager", mock_redis):
            result = await get_active_channel("admin-123")
        assert result == "email"

    @pytest.mark.asyncio
    async def test_set_active_channel_valid(self):
        """Test setting a valid channel."""
        mock_redis = MagicMock()
        mock_redis.client = True
        mock_redis.set_cache = AsyncMock()
        with patch("core.otp_router.redis_manager", mock_redis):
            await set_active_channel("admin-123", CHANNEL_EMAIL, ttl_seconds=7200)
        mock_redis.set_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_active_channel_invalid(self):
        """Test setting an invalid channel raises error."""
        with pytest.raises(ValueError):
            await set_active_channel("admin-123", "invalid_channel")

    @pytest.mark.asyncio
    async def test_send_discord_no_webhook(self):
        """Test Discord delivery fails without webhook URL."""
        with patch("core.otp_router.settings") as mock_settings:
            mock_settings.discord_otp_webhook_url = None
            from core.otp_router import _send_discord

            result = await _send_discord("admin-123", "123456", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_discord_success(self):
        """Test successful Discord delivery."""
        with (
            patch("core.otp_router.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_settings.discord_otp_webhook_url = MagicMock(
                get_secret_value=MagicMock(return_value="https://discord.webhook")
            )
            mock_response = MagicMock()
            mock_response.status_code = 204

            client_instance = AsyncMock()
            client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            from core.otp_router import _send_discord

            result = await _send_discord("admin-123", "123456", {"ip": "127.0.0.1"})  # is_local()
        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_no_config(self):
        """Test email delivery fails without configuration."""
        with patch("core.otp_router.settings") as mock_settings:
            mock_settings.resend_api_key = None
            mock_settings.admin_notification_email = None
            from core.otp_router import _send_email

            result = await _send_email("admin-123", "123456", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Test successful email delivery."""
        with (
            patch("core.otp_router.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_api_key = MagicMock()
            mock_api_key.get_secret_value = MagicMock(return_value="test-key")
            mock_settings.resend_api_key = mock_api_key
            mock_settings.admin_notification_email = "admin@example.com"
            mock_response = MagicMock()
            mock_response.status_code = 200

            client_instance = AsyncMock()
            client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            from core.otp_router import _send_email

            result = await _send_email("admin-123", "123456", {})
        assert result is True

    @pytest.mark.asyncio
    async def test_telegram_fallback_to_discord(self):
        """Test Telegram/WA fallback to Discord."""
        mock_redis = MagicMock()
        mock_redis.client = True
        mock_redis.get_cache = AsyncMock(return_value=CHANNEL_TELEGRAM)

        with (
            patch("core.otp_router.settings") as mock_settings,
            patch(
                "core.otp_router._send_discord",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("core.otp_router.redis_manager", mock_redis),
        ):
            mock_settings.discord_otp_webhook_url = MagicMock(
                get_secret_value=MagicMock(return_value="https://discord.webhook")
            )
            result = await send_otp("admin-123", "123456", {})
        assert result is True

    @pytest.mark.asyncio
    async def test_discord_failure_fallback_to_email(self):
        """Test Discord failure triggers email fallback."""
        with (
            patch("core.otp_router.settings") as mock_settings,
            patch(
                "core.otp_router._send_discord",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("core.otp_router._send_email", new_callable=AsyncMock, return_value=True),
            patch("core.otp_router.redis_manager", None),
        ):
            mock_api_key = MagicMock()
            mock_api_key.get_secret_value = MagicMock(return_value="test-key")
            mock_settings.discord_otp_webhook_url = MagicMock(
                get_secret_value=MagicMock(return_value="https://discord.webhook")
            )
            mock_settings.resend_api_key = mock_api_key
            mock_settings.admin_notification_email = "admin@example.com"
            result = await send_otp("admin-123", "123456", {})
        assert result is True

    def test_channel_constants_exist(self):
        """Test that channel constants are defined."""
        assert CHANNEL_DISCORD == "discord"
        assert CHANNEL_EMAIL == "email"
        assert CHANNEL_TELEGRAM == "telegram"
        assert CHANNEL_WHATSAPP == "whatsapp"
