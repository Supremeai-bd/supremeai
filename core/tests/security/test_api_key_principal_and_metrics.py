"""Tests for API Key & Principal Unification, Rate-Limiting, Immediate Cache Invalidation,
and Observability Route Normalization (Phase 1 SSOT Implementation).
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.observability.metrics_registry import normalize_route_path
from core.security import generate_api_key, hash_api_key
from core.security.api_key_middleware import APIKeyAuthMiddleware
from core.security.authentication.auth_middleware import AuthMiddleware


def _build_request(path: str = "/api/v1/protected", headers: dict | None = None) -> Request:
    header_list = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": header_list,
        "client": ("127.0.0.1", 1234),
        "query_string": b"",
        "state": {},
    }
    return Request(scope)


class TestMetricsRouteNormalization:
    """Test path normalization for Prometheus cardinality and PII protection."""

    def test_normalize_uuid(self):
        raw = "/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000/status"
        expected = "/api/v1/tasks/{id}/status"
        assert normalize_route_path(raw) == expected

    def test_normalize_numeric_id(self):
        raw = "/api/v1/users/42/details"
        expected = "/api/v1/users/{id}/details"
        assert normalize_route_path(raw) == expected

    def test_normalize_resource_id(self):
        raw = "/api/v1/keys/key_90c9c0e53bc39659/revoke"
        expected = "/api/v1/keys/{id}/revoke"
        assert normalize_route_path(raw) == expected

    def test_normalize_hex_hash(self):
        raw = "/reports/6f996212beeb262f62a8499ede74fddd"
        expected = "/reports/{hash}"
        assert normalize_route_path(raw) == expected

    def test_static_path_untouched(self):
        assert normalize_route_path("/v1/chat/completions") == "/v1/chat/completions"
        assert normalize_route_path("/health") == "/health"
        assert normalize_route_path("/metrics") == "/metrics"

    def test_strips_query_string(self):
        raw = "/api/search?q=test&page=2"
        assert normalize_route_path(raw) == "/api/search"


class TestApiKeyMiddlewarePrincipalAndLimiter:
    """Test APIKeyAuthMiddleware rate limit key format and principal attachment."""

    @pytest.mark.asyncio
    async def test_bearer_header_extraction_and_principal_unification(self):
        plain_key = generate_api_key()
        key_hash = hash_api_key(plain_key)
        fake_row = {
            "id": 42,
            "user_id": "usr_tenant_alpha",
            "key_hash": key_hash,
            "revoked": False,
            "expires_at": None,
            "rate_limit_rps": 10,
            "rate_limit_window": 60,
            "scopes": ["chat", "read"],
        }

        mock_limiter = AsyncMock()
        mock_limiter.acquire = AsyncMock(return_value=True)

        mw = APIKeyAuthMiddleware(app=MagicMock())
        mw.limiter = mock_limiter

        with (
            patch.object(mw, "_get_cached_api_key", new_callable=AsyncMock) as mock_get_cache,
            patch("core.security.api_key_middleware.record_api_key_usage", new_callable=AsyncMock) as mock_record_usage,
            patch("core.security.api_key_middleware.is_test_environment", return_value=False),
        ):
            mock_get_cache.return_value = fake_row

            # Pass key as Authorization: Bearer <key>
            req = _build_request("/api/v1/chat/completions", headers={"authorization": f"Bearer {plain_key}"})

            async def dummy_call_next(request: Request):
                # Verify request.state and scope have unified user principal
                assert request.state.api_key["id"] == 42
                assert request.state.api_key["user_id"] == "usr_tenant_alpha"
                assert request.state.user["sub"] == "usr_tenant_alpha"
                assert request.state.user["role"] == "api_key_user"
                assert request.state.user["auth_type"] == "api_key"
                assert request.state.user["key_id"] == 42
                assert request.scope["user"]["sub"] == "usr_tenant_alpha"
                return JSONResponse(status_code=201, content={"success": True})

            resp = await mw.dispatch(req, dummy_call_next)
            assert resp.status_code == 201

            # Verify rate limiter was invoked with stable ID f"apikey:{row['id']}" NOT header prefix
            from unittest.mock import call
            assert mock_limiter.acquire.call_args_list[-1] == call("apikey:42", limit=10, window=60)

            # Verify usage was recorded with real status_code 201 and latency > 0
            mock_record_usage.assert_called_once()
            call_kwargs = mock_record_usage.call_args[1]
            assert call_kwargs["key_id"] == 42
            assert call_kwargs["status_code"] == 201
            assert call_kwargs["latency_ms"] >= 0.0


class TestAuthMiddlewarePrincipalBypass:
    """Test AuthMiddleware recognizes API key principal and does not 401."""

    @pytest.mark.asyncio
    async def test_auth_middleware_allows_api_key_principal_without_jwt(self):
        called = {"reached": False}

        async def inner_app(scope, receive, send):
            called["reached"] = True
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b'{"ok": true}'})

        auth_mw = AuthMiddleware(inner_app)

        # Scope where APIKeyAuthMiddleware already authenticated
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/protected/resource",
            "headers": [],
            "state": {
                "api_key": {"id": 101, "masked": "sk-supreme-****"},
                "user": {"sub": "usr_tenant_alpha", "role": "api_key_user", "auth_type": "api_key"},
            },
            "user": {"sub": "usr_tenant_alpha", "role": "api_key_user", "auth_type": "api_key"},
        }

        sent_messages = []

        async def send(msg):
            sent_messages.append(msg)

        async def receive():
            return {"type": "http.request"}

        with patch("core.security.authentication.auth_middleware.is_test_environment", return_value=False):
            await auth_mw(scope, receive, send)

        assert called["reached"] is True
        assert sent_messages[0]["status"] == 200


class TestApiKeyCacheInvalidation:
    """Test that revoking, rotating, and deleting an API key immediately invalidates Redis cache."""

    @pytest.mark.asyncio
    async def test_revoke_invalidates_cache(self):
        from core.models.api_key import revoke_api_key

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {
            "id": 10,
            "name": "dev_key",
            "key_masked": "sk-****-1234",
            "key_hash": "hash_abc_123",
            "revoked": True,
            "updated_at": 1700000000,
        }

        with (
            patch("core.models.api_key.get_db_pool", return_value=mock_pool),
            patch("core.cache.redis_manager.redis_manager.delete", new_callable=AsyncMock) as mock_del_cache,
        ):
            res = await revoke_api_key(10)
            assert res["revoked"] is True
            mock_del_cache.assert_called_once_with("apikey:hash_abc_123")

    @pytest.mark.asyncio
    async def test_delete_invalidates_cache(self):
        from core.models.api_key import delete_api_key

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"key_hash": "hash_xyz_789"}

        with (
            patch("core.models.api_key.get_db_pool", return_value=mock_pool),
            patch("core.cache.redis_manager.redis_manager.delete", new_callable=AsyncMock) as mock_del_cache,
        ):
            deleted = await delete_api_key(25)
            assert deleted is True
            mock_del_cache.assert_called_once_with("apikey:hash_xyz_789")

    @pytest.mark.asyncio
    async def test_rotate_invalidates_old_cache(self):
        from core.models.api_key import rotate_api_key

        mock_pool = AsyncMock()
        # First query fetches old key_hash
        mock_pool.fetchrow.side_effect = [
            {"key_hash": "old_hash_999"},
            {
                "id": 30,
                "name": "rotated_key",
                "key_masked": "sk-****-9999",
                "key_prefix": "sk-supreme-r",
                "revoked": False,
                "created_at": 1700000000,
                "updated_at": 1700000005,
            },
        ]

        with (
            patch("core.models.api_key.get_db_pool", return_value=mock_pool),
            patch("core.cache.redis_manager.redis_manager.delete", new_callable=AsyncMock) as mock_del_cache,
        ):
            res = await rotate_api_key(30, "new_hash_111", "sk-****-9999", "sk-supreme-r")
            assert res["id"] == 30
            mock_del_cache.assert_called_once_with("apikey:old_hash_999")
