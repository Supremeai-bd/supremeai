import os
from unittest.mock import AsyncMock, patch

import pytest

from core.cache.multi_layer_cache import MultiLayerCache, is_simple_cache_mode
from core.middleware.security import RequestValidationMiddleware


def test_simple_cache_mode_flag():
    with patch.dict(os.environ, {"CACHE_SIMPLE_MODE": "true"}):
        assert is_simple_cache_mode() is True

    with patch.dict(os.environ, {"CACHE_SIMPLE_MODE": "false"}):
        assert is_simple_cache_mode() is False


@pytest.mark.asyncio
async def test_multi_layer_cache_simple_mode_bypasses_l2_l3():
    with patch.dict(os.environ, {"CACHE_SIMPLE_MODE": "true"}):
        cache = MultiLayerCache()
        exact_mock = AsyncMock(get=AsyncMock(return_value=None), setex=AsyncMock())
        cache._get_exact_cache = lambda: exact_mock
        cache._get_semantic_cache = lambda: AsyncMock(
            query_similar=AsyncMock(side_effect=RuntimeError("L2 should not be called"))
        )
        cache._get_prefix_cache = lambda: AsyncMock(
            mget=AsyncMock(side_effect=RuntimeError("L3 should not be called"))
        )

        # In simple mode, get() should check L1 and skip L2/L3 without calling them
        result = await cache.get("test prompt", "test-model")
        assert result is None

        # In simple mode, set() should write L1 and skip L2/L3 without calling them
        await cache.set("test prompt", "test response", "test-model")
        assert exact_mock.setex.called


def test_exempt_rate_limit_prefixes():
    middleware = RequestValidationMiddleware(app=None)
    for path in ["/health", "/api/v1/health", "/api/health", "/metrics", "/docs", "/redoc"]:
        assert path.startswith(middleware.EXEMPT_RATE_LIMIT_PREFIXES)
