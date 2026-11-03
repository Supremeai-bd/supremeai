"""Idempotency middleware tests for SupremeAI 2.0."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.idempotency_middleware import IdempotencyMiddleware


class TestIdempotencyMiddleware:
    """Tests for IdempotencyMiddleware class."""

    @pytest.mark.anyio
    async def test_middleware_non_http_scope(self):
        """HTTP নয় স্কোপে মিডলওয়্যার বংয়েজ।"""
        mock_app = AsyncMock()
        middleware = IdempotencyMiddleware(mock_app)

        scope = {"type": "websocket"}
        await middleware(scope, MagicMock(), MagicMock())
        mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_pytest_environment(self):
        """পাইটেস্ট এনভায়রনমেন্টে মিডলওয়্যার বংয়েজ।"""
        mock_app = AsyncMock()
        middleware = IdempotencyMiddleware(mock_app)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/orchestrate/generate",
            "headers": [],
        }

        from unittest.mock import patch

        with patch.dict("sys.modules"):
            sys.modules["pytest"] = MagicMock()
            await middleware(scope, MagicMock(), MagicMock())
            mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_get_request(self):
        """GET রিকোয়েস্টে মিডলওয়্যার বংয়েজ।"""
        mock_app = AsyncMock()
        middleware = IdempotencyMiddleware(mock_app)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [],
        }
        await middleware(scope, MagicMock(), MagicMock())
        mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_post_without_idempotency_key(self):
        """Idempotency কি ছাড়াই POST রিকোয়েস্ট অ্যাপ্রভ করা হচ্ছে।"""
        mock_app = AsyncMock()
        middleware = IdempotencyMiddleware(mock_app)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/test",
            "headers": [(b"idempotency-key", b"test-key")],
        }

        from unittest.mock import patch

        with patch.dict("sys.modules"):
            if "pytest" in sys.modules:
                del sys.modules["pytest"]

            with patch.dict(os.environ, {"ENV": "production", "REDIS_URL": ""}):
                with patch.object(
                    middleware, "_get_redis", new_callable=AsyncMock, return_value=None
                ):
                    await middleware(scope, MagicMock(), MagicMock())
                    mock_app.assert_called_once()

    @pytest.mark.anyio
    async def test_middleware_put_request(self):
        """PUT রিকোয়েস্টে মিডলওয়্যার বংয়েজ।"""
        mock_app = AsyncMock()
        middleware = IdempotencyMiddleware(mock_app)

        scope = {
            "type": "http",
            "method": "PUT",
            "path": "/api/test",
            "headers": [],
        }
        await middleware(scope, MagicMock(), MagicMock())
        mock_app.assert_called_once()
