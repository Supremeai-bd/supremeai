# backend/tests/core/test_idempotency_lock_cache_response.py
"""Regression tests for the idempotency cache_response_and_release_lock contract.

Issue #897 (P1 SECURITY): Idempotency middleware পূর্বে permanently disabled ছিল
কারণ `api/middleware.py` যে ৪টি নাম `core.cache.redis_manager` থেকে import করত,
তার মধ্যে `cache_response_and_release_lock` defined-ই ছিল না → ImportError →
silent fail-open → প্রতিটি request-এ entire middleware no-op।

এই test suite ৩টি contract pin করে:
    1. চারটি import (`acquire_idempotency_lock`, `cache_response_and_release_lock`,
       `redis_manager`, `release_idempotency_lock`) — সব exist করে।
    2. `cache_response_and_release_lock` Redis cache + lock release atomic ভাবে করে।
    3. Redis client unavailable হলেও lock release best-effort হয় (non-blocking recovery)।

WIRE-FIRST: pins fixed behavior, adds no deletion. বাংলা মন্তব্য সহ।
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.cache.redis_manager import (
    acquire_idempotency_lock,
    cache_response_and_release_lock,
    redis_manager,
    release_idempotency_lock,
)


class TestIdempotencyImportsContract:
    """Issue #897: verify চারটি import exist — আগে এই import ImportError দিত।"""

    def test_all_four_imports_resolvable(self):
        """middleware.py যে ৪টি নাম import করে, সবগুলো defined আছে কিনা যাচাই।"""
        # Import সফল হলেই test pass — ImportError হলে test আগেই fail করবে।
        assert callable(acquire_idempotency_lock)
        assert callable(cache_response_and_release_lock)
        assert redis_manager is not None
        assert callable(release_idempotency_lock)

    def test_cache_response_and_release_lock_signature(self):
        """`cache_response_and_release_lock(key, data, ttl=600)` signature contract।"""
        import inspect

        sig = inspect.signature(cache_response_and_release_lock)
        params = list(sig.parameters)
        assert params == ["key", "data", "ttl"], f"unexpected params: {params}"
        assert sig.parameters["ttl"].default == 600, (
            "ttl default 600s (5×IDEMPOTENCY_TTL_SECONDS) — middleware-এর সাথে মিল রাখা"
        )


class TestCacheResponseAndReleaseLock:
    """cache_response_and_release_lock — happy path + edge cases।"""

    @pytest.mark.asyncio
    async def test_caches_response_and_releases_lock_atomically(self):
        """সফল path: response cache + lock delete — দুটোই ঘটে।"""
        mock_client = MagicMock()
        mock_client.set = AsyncMock(return_value=True)
        with (
            patch.object(
                redis_manager, "get_client_async", new_callable=AsyncMock
            ) as mock_get_client,
            patch.object(
                redis_manager, "delete", new_callable=AsyncMock, return_value=True
            ) as mock_delete,
        ):
            mock_get_client.return_value = mock_client

            payload = json.dumps({"status_code": 200, "body": {"ok": True}})
            result = await cache_response_and_release_lock("anon:abc-123", payload, ttl=600)

        assert result is True, "cache write success → True"
        # Response cached at idempotency:response:{key}
        mock_client.set.assert_awaited_once()
        called_key, called_data = (
            mock_client.set.await_args.args[0],
            mock_client.set.await_args.args[1],
        )
        assert called_key == "idempotency:response:anon:abc-123"
        assert called_data == payload
        assert mock_client.set.await_args.kwargs == {"ex": 600}
        # Lock released at idempotency:{key}
        mock_delete.assert_awaited_once_with("idempotency:anon:abc-123")

    @pytest.mark.asyncio
    async def test_redis_unavailable_releases_lock_only(self):
        """Redis client None হলেও lock release best-effort হয় (non-blocking recovery)।"""
        with (
            patch.object(
                redis_manager, "get_client_async", new_callable=AsyncMock, return_value=None
            ),
            patch.object(
                redis_manager, "delete", new_callable=AsyncMock, return_value=True
            ) as mock_delete,
        ):
            result = await cache_response_and_release_lock("user-1:k-1", "{}", ttl=300)

        assert result is False, "client None → False (cache miss) but lock still released"
        mock_delete.assert_awaited_once_with("idempotency:user-1:k-1")

    @pytest.mark.asyncio
    async def test_cache_write_failure_releases_lock_best_effort(self):
        """Cache write raise করলেও lock release করতে হবে (যাতে duplicate আটকে না থাকে)।"""
        mock_client = MagicMock()
        mock_client.set = AsyncMock(side_effect=RuntimeError("redis disconnected"))
        with (
            patch.object(
                redis_manager, "get_client_async", new_callable=AsyncMock
            ) as mock_get_client,
            patch.object(
                redis_manager, "delete", new_callable=AsyncMock, return_value=True
            ) as mock_delete,
            patch.object(redis_manager, "report_failure") as mock_report,
        ):
            mock_get_client.return_value = mock_client

            result = await cache_response_and_release_lock("p:k", "{}", ttl=60)

        assert result is False, "write failed → False"
        # report_failure called for telemetry
        mock_report.assert_called_once()
        # Best-effort lock release still attempted
        mock_delete.assert_awaited_once_with("idempotency:p:k")

    @pytest.mark.asyncio
    async def test_cache_key_namespace_is_response_prefixed(self):
        """Cache key অবশ্যই `idempotency:response:{scoped_key}` — lock-এর থেকে আলাদা।"""
        mock_client = MagicMock()
        mock_client.set = AsyncMock(return_value=True)
        captured_keys: list[str] = []

        async def fake_set(key, *args, **kwargs):
            captured_keys.append(key)
            return True

        mock_client.set = fake_set
        with (
            patch.object(
                redis_manager, "get_client_async", new_callable=AsyncMock
            ) as mock_get_client,
            patch.object(redis_manager, "delete", new_callable=AsyncMock),
        ):
            mock_get_client.return_value = mock_client
            await cache_response_and_release_lock("user42:uuid-9", "{}")

        assert captured_keys == ["idempotency:response:user42:uuid-9"], (
            "cache key response-prefixed; lock key not-prefixed (separate namespace)"
        )


class TestMiddlewareImportContract:
    """Issue #897 #3: middleware import এখন no longer fail-open — ImportError raise করবে।"""

    def test_middleware_imports_resolve_without_import_error(self):
        """api/middleware.py এর import গুলো import করলে no ImportError হবে।"""
        # এই import টি middleware.py dispatch method-এর ভেতরে রয়েছে; আমরা সরাসরি
        # source-এর সব ৪টি নাম import করে verify করছি যে কোনো missing name নেই।
        from core.cache.redis_manager import (  # noqa: F401 — verify import contract
            acquire_idempotency_lock,
            cache_response_and_release_lock,
            release_idempotency_lock,
        )
        from core.cache.redis_manager import (
            redis_manager as rm,
        )

        # এখানে পৌঁছালেই মানে no ImportError — Issue #897 fix সফল।
        assert rm is not None

    def test_middleware_module_does_not_swallow_import_error(self):
        """api/middleware.py dispatch method এখন `try/except ImportError` fail-open নেই।

        Source inspection — নিশ্চিত করি যে fail-open pattern (live try/except ImportError
        wrapping redis_manager import) আর নেই। comment-এ উল্লেখ থাকতে পারে তাই comment
        line বাদ দিয়ে verify করছি।
        """
        import inspect
        import re

        from api.middleware import IdempotencyMiddleware

        src = inspect.getsource(IdempotencyMiddleware.dispatch)
        # Strip Python comments (# ...) — comment-এ থাকা শব্দ code pattern হিসেবে
        # গণ্য হবে না।
        code_lines = [re.sub(r"#.*$", "", line) for line in src.splitlines()]
        code_only = "\n".join(code_lines)
        assert "except ImportError" not in code_only, (
            "Issue #897: ImportError fail-open pattern removed — security middleware "
            "must not silently no-op. Missing import should propagate as real error."
        )
