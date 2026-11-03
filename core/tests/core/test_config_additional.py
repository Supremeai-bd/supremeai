from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from core.config import Settings


@patch.dict(
    os.environ,
    {"CORS_ORIGINS": "https://a.example.com, https://b.example.com"},
    clear=False,
)
def test_parse_cors_origins_comma_separated():
    settings = Settings()
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_settings_raises_when_production_secret_missing(monkeypatch):
    mock_vault = MagicMock()
    mock_vault.fetch_secret.return_value = None
    mock_vault.fetch_all_secrets.return_value = {}
    mock_vault.fetch_json_secret.return_value = {}
    with (
        patch.dict(
            os.environ,
            {
                "ENV": "production",
                "ALLOW_TEST_AUTH_BYPASS": "false",
                "OPENROUTER_API_KEY": "sk-open",
                "GEMINI_API_KEY": "sk-gemini",
            },
            clear=True,
        ),
        # secret access moved to a get_secret_vault() accessor; patch it at
        # the config_secrets boundary.
        patch("core.config_secrets.get_secret_vault", return_value=mock_vault),
    ):
        # Reset the module-level secret cache so the mocked vault is actually
        # consulted (earlier tests in the session already populated it).
        Settings._cached_secrets = {}
        Settings._secrets_batch_loaded = False
        # validate_all() short-circuits whenever pytest is importable (CI
        # fail-open). Temporarily hide it so the REAL production fail-fast
        # branch is exercised; monkeypatch restores sys.modules afterwards.
        monkeypatch.delitem(sys.modules, "pytest", raising=False)
        with pytest.raises((ValueError, RuntimeError)):
            Settings()
