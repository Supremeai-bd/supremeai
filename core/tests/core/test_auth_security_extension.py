"""Extension tests for core.security.authentication.auth_middleware — AuthMiddleware edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from core.security.authentication.auth_middleware import (
    AuthMiddleware,
    _decode_jwt,
    _is_public_path,
    verify_admin_session_fail_closed,
)


class TestDecodeJwtEdgeCases:
    """Edge cases for _decode_jwt function."""

    def test_decode_jwt_missing_secret_returns_none(self):
        """Missing jwt_secret returns None (fail-closed)."""
        from core.config import settings

        with patch.object(settings, "_jwt_secret", SecretStr(""), create=True):
            result = _decode_jwt("some-token")
            assert result is None

    def test_decode_jwt_invalid_token_returns_none(self):
        """Invalid JWT returns None."""
        result = _decode_jwt("invalid-token")
        assert result is None

    def test_decode_jwt_empty_token_returns_none(self):
        """Empty string JWT returns None."""
        result = _decode_jwt("")
        assert result is None


class TestIsPublicPath:
    """Tests for _is_public_path function."""

    def test_public_path_exact_match(self):
        from core.config import settings

        old_paths = settings.supremeai_public_paths
        settings.supremeai_public_paths = ["/health", "/docs"]
        try:
            assert _is_public_path("/health") is True
        finally:
            settings.supremeai_public_paths = old_paths

    def test_public_path_prefix_match(self):
        from core.config import settings

        old_paths = settings.supremeai_public_paths
        settings.supremeai_public_paths = ["/api/v1"]
        try:
            assert _is_public_path("/api/v1/health") is True
        finally:
            settings.supremeai_public_paths = old_paths

    def test_non_public_path(self):
        from core.config import settings

        old_paths = settings.supremeai_public_paths
        settings.supremeai_public_paths = ["/health"]
        try:
            assert _is_public_path("/admin") is False
        finally:
            settings.supremeai_public_paths = old_paths

    def test_root_path(self):
        from core.config import settings

        old_paths = settings.supremeai_public_paths
        settings.supremeai_public_paths = ["/"]
        try:
            assert _is_public_path("/") is True
        finally:
            settings.supremeai_public_paths = old_paths

    def test_root_path_non_root(self):
        from core.config import settings

        old_paths = settings.supremeai_public_paths
        settings.supremeai_public_paths = ["/"]
        try:
            assert _is_public_path("/api") is False
        finally:
            settings.supremeai_public_paths = old_paths


class TestAuthMiddlewareAdvanced:
    """Advanced tests for AuthMiddleware class."""

    @pytest.mark.anyio
    async def test_middleware_skips_non_http(self):
        """Non-HTTP scopes pass through."""
        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)
        scope = {"type": "websocket"}
        await middleware(scope, MagicMock(), MagicMock())
        mock_app.assert_called_once()

    @pytest.mark.anyio
    @patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False)
    async def test_middleware_rejects_missing_token(self, mock_is_test):
        """Missing token returns 401."""
        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)
        send = AsyncMock()
        scope = {
            "type": "http",
            "path": "/api/protected",
            "headers": [],
        }
        await middleware(scope, MagicMock(), send)
        mock_app.assert_not_called()
        assert send.await_count >= 1

    @pytest.mark.anyio
    @patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False)
    async def test_middleware_rejects_invalid_token(self, mock_is_test):
        """Invalid JWT returns 401."""
        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)
        send = AsyncMock()
        scope = {
            "type": "http",
            "path": "/api/protected",
            "headers": [(b"authorization", b"Bearer invalid-jwt-token")],
        }
        await middleware(scope, MagicMock(), send)
        mock_app.assert_not_called()

    @pytest.mark.anyio
    @patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False)
    async def test_middleware_api_token_mismatch(self, mock_is_test):
        """Wrong API token returns 401."""
        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)
        send = AsyncMock()
        scope = {
            "type": "http",
            "path": "/api/protected",
            "headers": [(b"authorization", b"Bearer wrong-token")],
        }
        await middleware(scope, MagicMock(), send)
        mock_app.assert_not_called()


class TestVerifyAdminSessionAdvanced:
    """Advanced tests for verify_admin_session_fail_closed."""

    def test_missing_auth_header(self):
        """Missing Authorization header raises HTTPException 401."""
        from fastapi import HTTPException

        request = MagicMock()
        request.headers.get.return_value = None

        with pytest.raises(HTTPException) as exc:
            import asyncio

            asyncio.run(verify_admin_session_fail_closed(request))
        assert exc.value.status_code == 401

    def test_malformed_auth_header(self):
        """Non-Bearer header raises HTTPException 401."""
        from fastapi import HTTPException

        request = MagicMock()
        request.headers.get.return_value = "Basic token"

        with pytest.raises(HTTPException) as exc:
            import asyncio

            asyncio.run(verify_admin_session_fail_closed(request))
        assert exc.value.status_code == 401

    def test_expired_token(self):
        """Expired token raises 401."""
        from fastapi import HTTPException
        from jwt import ExpiredSignatureError

        request = MagicMock()
        request.headers.get.return_value = "Bearer expired"

        with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
            mock_decode.side_effect = ExpiredSignatureError("expired")
            with pytest.raises(HTTPException) as exc:
                import asyncio

                asyncio.run(verify_admin_session_fail_closed(request))
            assert exc.value.status_code == 401

    def test_non_admin_role(self):
        """Non-admin role raises 401."""
        from fastapi import HTTPException

        request = MagicMock()
        request.headers.get.return_value = "Bearer viewer-token"

        with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user-1", "role": "viewer"}
            with pytest.raises(HTTPException) as exc:
                import asyncio

                asyncio.run(verify_admin_session_fail_closed(request))
            assert exc.value.status_code == 401

    def test_admin_role_success(self):
        """Admin role passes."""
        request = MagicMock()
        request.headers.get.return_value = "Bearer admin-token"

        with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "admin-1", "role": "admin"}
            import asyncio

            result = asyncio.run(verify_admin_session_fail_closed(request))
            assert result["sub"] == "admin-1"

    def test_master_admin_role_allowed(self):
        """master_admin role passes."""
        request = MagicMock()
        request.headers.get.return_value = "Bearer master-token"

        with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "master-1", "role": "master_admin"}
            import asyncio

            result = asyncio.run(verify_admin_session_fail_closed(request))
            assert result["sub"] == "master-1"
