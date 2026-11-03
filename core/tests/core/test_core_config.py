# tests/test_core_config.py
"""Tests for core configuration and settings management."""

import os
from unittest.mock import patch


def test_settings_gemini_api_key():
    """Test that Gemini API key is properly configured."""
    from core.config import Settings

    # Test with environment variable
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}):
        settings = Settings()
        assert settings.gemini_api_key == "test-gemini-key"


def test_settings_openrouter_api_key():
    """Test OpenRouter API key configuration."""
    from core.config import Settings

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-router-key"}):
        settings = Settings()
        assert settings.openrouter_api_key == "test-router-key"


def test_settings_supabase_configuration():
    """Test Supabase database configuration."""
    from core.config import Settings

    with patch.dict(
        os.environ,
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-supabase-key"},
    ):
        settings = Settings()
        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.supabase_key == "test-supabase-key"


def test_settings_debug_mode_validation():
    """Test debug mode validation logic."""
    from core.config import Settings

    with patch.dict(os.environ, {"DEBUG": "true"}, clear=False):
        settings = Settings()
        assert settings.debug is True


def test_settings_cors_origins_parsing():
    """Test CORS origins parsing from environment."""
    from core.config import Settings

    with patch.dict(
        os.environ, {"CORS_ORIGINS": "http://localhost:3000,http://localhost:5173"}
    ):  # is_local()
        settings = Settings()
        assert "http://localhost:3000" in settings.cors_origins  # is_local()
        assert "http://localhost:5173" in settings.cors_origins  # is_local()


def test_settings_jwt_secret_validation():
    """Test JWT secret strength validation."""
    from core.config import Settings

    # Strong JWT secret should pass
    with patch.dict(os.environ, {"JWT_SECRET": "this-is-a-very-strong-secret-key-with-32-chars"}):
        settings = Settings()
        assert len(settings.jwt_secret) >= 32


def test_settings_admin_emails_parsing():
    """Test admin emails parsing."""
    from core.config import Settings

    with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@test.com,super@test.com"}):
        settings = Settings()
        assert "admin@test.com" in settings.admin_emails
        assert "super@test.com" in settings.admin_emails
