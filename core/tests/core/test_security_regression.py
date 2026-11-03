from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.config import Settings
from core.security.authentication.auth_middleware import AuthMiddleware


@pytest.mark.anyio
async def test_production_jwt_secret_required():
    """Verify that in production environment, a missing jwt_secret raises a RuntimeError."""

    with patch.dict(
        os.environ,
        {
            "ENV": "production",
            "ALLOW_TEST_AUTH_BYPASS": "false",
            "ALLOWED_HOSTS": "api.supremeai.com",
            "SUPREMEAI_JWT_SECRET": "",
            "JWT_SECRET": "",
        },
    ):
        # Patch where config_secrets BOUND the symbol (from .security.secret_vault
        # import get_secret_vault) — patching core.security.secret_vault directly
        # leaves config_secrets calling the real vault, whose BE-13 fail-closed
        # raise masks the property's JWT-specific error under test (main CI #733).
        with patch("core.config_secrets.get_secret_vault") as mock_get_secret_vault:
            mock_get_secret_vault.return_value.fetch_all_secrets.return_value = {}
            mock_get_secret_vault.return_value.fetch_secret.return_value = ""
            with pytest.raises(RuntimeError) as excinfo:
                _ = Settings().jwt_secret
    assert any(
        msg in str(excinfo.value)
        for msg in (
            "Production JWT secret must be set and >= 64 bytes",
            "SUPREMEAI_JWT_SECRET",
        )
    )

    # Explicitly test short secret triggers the length-validation RuntimeError
    with patch.dict(
        os.environ,
        {
            "ENV": "production",
            "ALLOW_TEST_AUTH_BYPASS": "false",
            "ALLOWED_HOSTS": "api.supremeai.com",
            "SUPREMEAI_JWT_SECRET": "too-short-secret",
        },
    ):
        with pytest.raises(RuntimeError) as excinfo_short:
            _ = Settings().jwt_secret
        assert "Production JWT secret must be set and >= 64 bytes" in str(excinfo_short.value)


def test_auth_middleware_rejects_invalid_api_token():
    """Verify that AuthMiddleware rejects invalid API tokens and 'test-token' if the expected token is different."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.responses import PlainTextResponse

    app = FastAPI()

    @app.get("/api/task/execute")
    def task():
        return PlainTextResponse("ok")

    app.add_middleware(AuthMiddleware)
    client = TestClient(app)

    # Setup expected API token env var and test that an invalid token (like 'test-token') gets 401
    with (
        patch.dict(
            os.environ,
            {
                "ALLOW_TEST_AUTH_BYPASS": "false",
                "SUPREMEAI_API_KEY": "super-secure-production-api-token",
            },
        ),
        patch("core.config.settings.allow_test_auth_bypass", False),
    ):
        resp = client.get("/api/task/execute", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"
