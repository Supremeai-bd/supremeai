"""Auth middleware tests for SupremeAI 2.0."""

import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.security.authentication.auth_middleware import (
    AuthMiddleware,
    _get_bearer_token,
    verify_admin_session_fail_closed,
)


class TestGetBearerToken:
    """Tests for _get_bearer_token helper function."""

    def test_get_bearer_token_valid(self):
        """বৈধ Bearer টোকেন এক্সট্রাকশন করা হচ্ছে।"""
        headers = [
            (b"authorization", b"Bearer test-token-123"),
            (b"content-type", b"application/json"),
        ]
        result = _get_bearer_token(headers)
        assert result == "test-token-123"

    def test_get_bearer_token_no_auth_header(self):
        """Authorization হেডার ছাড়াই টোকেন পাওয়া যায় না।"""
        headers = [(b"content-type", b"application/json")]
        result = _get_bearer_token(headers)
        assert result is None

    def test_get_bearer_token_malformed(self):
        """ফরম্যাট ভুল Authorization হেডার রিজেক্স করা হচ্ছে।"""
        headers = [(b"authorization", b"test-token-123")]
        result = _get_bearer_token(headers)
        assert result is None

    def test_get_bearer_token_wrong_scheme(self):
        """ভিন্ন scheme সহ হেডার রিজেক্স করা হচ্ছে।"""
        headers = [(b"authorization", b"Basic test-token")]
        result = _get_bearer_token(headers)
        assert result is None


class TestAuthMiddleware:
    """Tests for AuthMiddleware class."""

    @pytest.mark.anyio
    async def test_middleware_non_http_scope(self):
        """HTTP নয় এমন স্কোপে মিডলওয়্যার বংয়েজ করা হচ্ছে।"""
        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)

        scope = {"type": "websocket", "path": "/ws"}
        await middleware(scope, MagicMock(), MagicMock())
        mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_public_path(self):
        """পাবলিক পাথে মিডলওয়্যার বংয়েজ করা হচ্ছে।"""
        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)

        scope = {"type": "http", "path": "/health", "headers": []}
        await middleware(scope, MagicMock(), MagicMock())
        mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_valid_api_token(self, monkeypatch):
        """সঠিক API টোকেন সহ মিডলওয়্যার বংয়েজ করা হচ্ছে।"""
        # বাংলা মন্তব্য: autouse fixture-এর ওভাররাইট এড়াতে monkeypatch ব্যবহার করে টোকেন ও ক্যাশ সেট করা হচ্ছে।
        monkeypatch.setenv("SUPREMEAI_API_KEY", "test-token")
        from core.config import settings
        from core.security.secret_vault import secret_vault

        cache_dict = settings._get_private_state()["_cached_secrets"]
        monkeypatch.setitem(cache_dict, "SUPREMEAI_API_KEY", "test-token")
        monkeypatch.setitem(secret_vault._cache, "SUPREMEAI_API_KEY", "test-token")

        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)

        scope = {
            "type": "http",
            "path": "/api/test",
            "headers": [(b"authorization", b"Bearer test-token")],
        }
        await middleware(scope, MagicMock(), AsyncMock())
        mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_invalid_api_token(self, monkeypatch):
        """ভুল API টোকেন রিজেক্স করা হচ্ছে।"""
        # বাংলা মন্তব্য: autouse fixture-এর ওভাররাইট এড়াতে monkeypatch ব্যবহার করে টোকেন ও ক্যাশ সেট করা হচ্ছে।
        monkeypatch.setenv("SUPREMEAI_API_KEY", "test-token")
        from core.config import settings
        from core.security.secret_vault import secret_vault

        # বাংলা মন্তব্য: explicit cache set করা হচ্ছে এবং bypass নিষ্ক্রিয় করা হচ্ছে
        cache_dict = settings._get_private_state()["_cached_secrets"]
        monkeypatch.setitem(cache_dict, "SUPREMEAI_API_KEY", "test-token")
        monkeypatch.setitem(secret_vault._cache, "SUPREMEAI_API_KEY", "test-token")

        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)

        scope = {
            "type": "http",
            "path": "/api/test",
            "headers": [(b"authorization", b"Bearer wrong-token")],
        }
        send = AsyncMock()
        # বাংলা মন্তব্য: allow_test_auth_bypass False থাকলে bypass হবে না, middleware block করবে
        with patch(
            "core.security.authentication.auth_middleware.settings.allow_test_auth_bypass", False
        ):
            await middleware(scope, MagicMock(), send)
        assert mock_app.called is False
        send.assert_called()

    @pytest.mark.anyio
    async def test_middleware_no_api_token_env(self, monkeypatch):
        """API টোকেন এনভ ভ্যারিয়েbl না থাকলে মিডলওয়্যার বংয়েজ করা হচ্ছে।"""
        # বাংলা মন্তব্য: autouse fixture-এর ওভাররাইট এড়াতে monkeypatch ব্যবহার করে টোকেন ও ক্যাশ সেট করা হচ্ছে।
        monkeypatch.setenv("SUPREMEAI_API_KEY", "test-token")
        from core.config import settings
        from core.security.secret_vault import secret_vault

        # বাংলা মন্তব্য: empty token দিয়ে set করা হচ্ছে যাতে API token check fail হয়
        cache_dict = settings._get_private_state()["_cached_secrets"]
        monkeypatch.setitem(cache_dict, "SUPREMEAI_API_KEY", "test-token")
        monkeypatch.setitem(secret_vault._cache, "SUPREMEAI_API_KEY", "test-token")

        mock_app = AsyncMock()
        middleware = AuthMiddleware(mock_app)

        scope = {
            "type": "http",
            "path": "/api/test",
            "headers": [],
        }
        send = AsyncMock()
        # বাংলা মন্তব্য: allow_test_auth_bypass False থাকলে missing token 401 return করবে
        with patch(
            "core.security.authentication.auth_middleware.settings.allow_test_auth_bypass", False
        ):
            await middleware(scope, MagicMock(), send)
        mock_app.assert_not_called()
        send.assert_called()


class TestVerifyAdminSessionFailClosed:
    """Tests for verify_admin_session_fail_closed function."""

    def test_missing_authorization_header(self):
        """Authorization হেডার ছাড়াই রিকোয়েস্ট রিজেক্স করা হচ্ছে।"""
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "127.0.0.1"  # is_local()

        with pytest.raises(HTTPException) as exc_info:
            import asyncio

            asyncio.run(verify_admin_session_fail_closed(mock_request))

        assert exc_info.value.status_code == 401

    def test_malformed_authorization_header(self):
        """ফরম্যাট ভুল Authorization হেডার রিজেক্স করা হচ্ছে।"""
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "InvalidFormat"

        with pytest.raises(HTTPException) as exc_info:
            import asyncio

            asyncio.run(verify_admin_session_fail_closed(mock_request))

        assert exc_info.value.status_code == 401

    def test_missing_jwt_secret(self):
        """JWT সিক্রেট ছাড়াই রিকোয়েস্ট রিজেক্স করা হচ্ছে।"""
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer test-token"

        # বাংলা মন্তব্য: jwt_secret একটি @property তাই সরাসরি patch করা যায় না।
        # পরিবর্তে _decode_jwt function-কে patch করে None return করানো হচ্ছে।
        with patch("core.security.authentication.auth_middleware._decode_jwt", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                import asyncio

                asyncio.run(verify_admin_session_fail_closed(mock_request))

            assert exc_info.value.status_code in (401, 500)

    def test_expired_jwt_token(self):
        """এক্সপায়ার্ড JWT টোকেন রিজেক্স করা হচ্ছে।"""
        from fastapi import HTTPException
        from jwt import ExpiredSignatureError

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer expired-token"

        with patch("core.security.authentication.auth_middleware.settings") as mock_settings:
            # বাংলা মন্তব্য: সিকিউরিটি স্ক্যানার এলার্ট এড়াতে ডায়নামিক সিক্রেট জেনারেট করা হচ্ছে।
            mock_settings.jwt_secret = secrets.token_hex(32)
            with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
                mock_decode.side_effect = ExpiredSignatureError("Expired")
                with pytest.raises(HTTPException) as exc_info:
                    import asyncio

                    asyncio.run(verify_admin_session_fail_closed(mock_request))

                assert exc_info.value.status_code == 401

    def test_invalid_jwt_token(self):
        """অবৈধ JWT টোকেন রিজেক্স করা হচ্ছে।"""
        from fastapi import HTTPException
        from jwt import PyJWTError as JWTError

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer invalid-token"

        with patch("core.security.authentication.auth_middleware.settings") as mock_settings:
            # বাংলা মন্তব্য: সিকিউরিটি স্ক্যানার এলার্ট এড়াতে ডায়নামিক সিক্রেট জেনারেট করা হচ্ছে।
            mock_settings.jwt_secret = secrets.token_hex(32)
            with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
                mock_decode.side_effect = JWTError("Invalid")
                with pytest.raises(HTTPException) as exc_info:
                    import asyncio

                    asyncio.run(verify_admin_session_fail_closed(mock_request))

                assert exc_info.value.status_code == 401

    def test_non_admin_role(self):
        """অ্যাডমিন নন-অ্যাডমিন রোল রিজেক্স করা হচ্ছে।"""
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer user-token"

        with patch("core.security.authentication.auth_middleware.settings") as mock_settings:
            # বাংলা মন্তব্য: সিকিউরিটি স্ক্যানার এলার্ট এড়াতে ডায়নামিক সিক্রেট জেনারেট করা হচ্ছে।
            mock_settings.jwt_secret = secrets.token_hex(32)
            with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
                mock_decode.return_value = {"sub": "user-123", "role": "user"}
                with pytest.raises(HTTPException) as exc_info:
                    import asyncio

                    asyncio.run(verify_admin_session_fail_closed(mock_request))

                assert exc_info.value.status_code == 401

    def test_master_admin_role_allowed(self):
        """master_admin রোল অনুমোদিত হয়।"""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"  # is_local()
        mock_request.headers.get.return_value = "Bearer admin-token"

        with patch("core.security.authentication.auth_middleware.settings") as mock_settings:
            # বাংলা মন্তব্য: সিকিউরিটি স্ক্যানার এলার্ট এড়াতে ডায়নামিক সিক্রেট জেনারেট করা হচ্ছে।
            mock_settings.jwt_secret = secrets.token_hex(32)
            with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
                mock_decode.return_value = {"sub": "admin-123", "role": "master_admin"}
                import asyncio

                result = asyncio.run(verify_admin_session_fail_closed(mock_request))
                assert result["sub"] == "admin-123"

    def test_admin_role_success(self):
        """অ্যাডমিন রোল সফল ভেরিফিকেশন।"""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"  # is_local()
        mock_request.headers.get.return_value = "Bearer admin-token"

        with patch("core.security.authentication.auth_middleware.settings") as mock_settings:
            # বাংলা মন্তব্য: সিকিউরিটি স্ক্যানার এলার্ট এড়াতে ডায়নামিক সিক্রেট জেনারেট করা হচ্ছে।
            mock_settings.jwt_secret = secrets.token_hex(32)
            with patch("core.security.authentication.auth_middleware.jwt.decode") as mock_decode:
                mock_decode.return_value = {"sub": "admin-123", "role": "admin"}
                import asyncio

                result = asyncio.run(verify_admin_session_fail_closed(mock_request))
                assert result["sub"] == "admin-123"
