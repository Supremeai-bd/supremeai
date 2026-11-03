"""
Tests for services/email/email_service.py — EmailService
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.email.email_service import EmailService


@pytest.fixture
def email_service():
    return EmailService()


class TestEmailService:
    def test_init(self, email_service):
        assert email_service._settings is None

    def test_get_settings_returns_settings(self, email_service):
        with patch("services.email.email_service.settings") as mock_settings:
            result = email_service._get_settings()
            assert result is mock_settings

    def test_get_settings_fallback(self, email_service):
        with patch("services.email.email_service.settings", side_effect=Exception("No settings")):
            result = email_service._get_settings()
            assert hasattr(result, "resend_api_url")
            assert hasattr(result, "frontend_url")

    def test_api_key_from_env(self, email_service):
        with patch.dict(os.environ, {"RESEND_API_KEY": "test-key-123"}, clear=False):
            key = email_service.api_key
            assert key == "test-key-123"

    def test_api_key_empty_when_not_set(self, email_service):
        with patch.dict(os.environ, {}, clear=True):
            key = email_service.api_key
            assert key == ""

    def test_from_email_default(self, email_service):
        with patch.dict(os.environ, {}, clear=True):
            email = email_service.from_email
            assert email == "noreply@supremeai.dev"

    def test_from_email_from_env(self, email_service):
        with patch.dict(os.environ, {"RESEND_FROM_EMAIL": "test@example.com"}, clear=False):
            email = email_service.from_email
            assert email == "test@example.com"

    @pytest.mark.asyncio
    async def test_send_welcome_email(self, email_service):
        with patch.object(email_service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "sent", "id": "email-123"}
            result = await email_service.send_welcome_email(
                to_email="user@example.com",
                user_name="Test User",
            )
            assert result["status"] == "sent"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_password_reset(self, email_service):
        with patch.object(email_service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "sent"}
            result = await email_service.send_password_reset(
                to_email="user@example.com",
                reset_link="https://supremeai.dev/reset/token-123",
            )
            assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_billing_notification(self, email_service):
        with patch.object(email_service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "sent"}
            result = await email_service.send_billing_notification(
                to_email="user@example.com",
                invoice_amount=29.99,
                due_date="2025-01-15",
            )
            assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_email_failure_emits_error(self, email_service):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("services.email.email_service.error_event_bus") as mock_event_bus:
                result = await email_service._send_email(
                    to_email="user@example.com",
                    subject="Test",
                    body="<p>Test</p>",
                )
                assert result is False
                mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_success(self, email_service):
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.json.return_value = {"id": "email-123"}

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await email_service._send_email(
                to_email="user@example.com",
                subject="Test",
                body="<p>Test</p>",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_network_error(self, email_service):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("services.email.email_service.error_event_bus") as mock_event_bus:
                result = await email_service._send_email(
                    to_email="user@example.com",
                    subject="Test",
                    body="<p>Test</p>",
                )
                assert result is False
                mock_event_bus.emit.assert_called_once()
