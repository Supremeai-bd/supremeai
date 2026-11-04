"""Regression coverage for production boot with optional secrets absent."""

import os
import sys
from unittest.mock import patch

from core.config import Settings


def test_production_settings_validation_does_not_require_optional_secret_mixins(monkeypatch):
    env = {
        "ENV": "production",
        "SUPREMEAI_ADMIN_SECRET": "test-only-admin-secret-0123456789",
        "SUPREMEAI_DOCS_PASSWORD": "test-only-docs-password-012345",
        "SUPREMEAI_JWT_SECRET": "test-only-jwt-secret-" + ("x" * 80),
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_KEY": "test-only-supabase-key",
        "REDIS_URL": "redis://localhost:6379",
        "ENCRYPTION_KEY": "test-only-encryption-key-for-tests",
        "ALLOWED_HOSTS": "api.example.test",
        "STRIPE_API_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "",
        "CI_WEBHOOK_SECRET": "",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = Settings()

    # Simulate a real runtime: validate_all deliberately skips under pytest
    # during construction, so exercise that production-only branch directly.
    monkeypatch.delitem(sys.modules, "pytest", raising=False)
    monkeypatch.delenv("CI", raising=False)
    settings.validate_all()
