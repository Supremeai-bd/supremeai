from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.cache.autocache_proxy import AutocacheProxy
from core.cache.multi_layer_cache import MultiLayerCache
from core.cache.redis_manager import (
    IdempotencyUnavailableError,
    acquire_idempotency_lock,
)
from core.cache.semantic_cache import SemanticCache

# বাংলা মন্তব্য: মডিউল ৩-এর নতুন অপ্টিমাইজেশনগুলো টেস্ট করার জন্য ইউনিট টেস্ট।


@pytest.mark.anyio
async def test_multi_layer_cache_prefix_batched_lookup():
    cache = MultiLayerCache()
    # Mock prefix cache to trace mget call
    mock_redis = AsyncMock()
    mock_redis.mget.return_value = [None, "response_val"]

    with patch.object(cache, "_get_prefix_cache", return_value=mock_redis):
        # We query a prompt with multiple words
        res = await cache.get("write python script to find first occurrence", "gpt-4o")
        assert res is not None
        assert res["response"] == "response_val"
        assert res["source"] == "L3_PREFIX_CACHE"
        mock_redis.mget.assert_called_once()


@pytest.mark.anyio
async def test_idempotency_lock_fail_closed():
    # Test Redis unavailable with fail_closed=True raises exception
    with patch(
        "core.cache.redis_manager.SecureRedisManager.get_client_async",
        new_callable=AsyncMock,
    ) as mock_get_client:
        mock_get_client.return_value = None
        with pytest.raises(IdempotencyUnavailableError) as exc_info:
            await acquire_idempotency_lock("payment:key", fail_closed=True)
        assert "Idempotency lock unavailable" in str(exc_info.value)

        # Test fail_closed=False passes through
        res = await acquire_idempotency_lock("noncritical:key", fail_closed=False)
        assert res is True


@pytest.mark.anyio
async def test_autocache_proxy_ttl_and_dynamic_costs():
    mock_semantic = MagicMock(spec=SemanticCache)
    proxy = AutocacheProxy(mock_semantic)

    # Test request_history is a TTLCache
    from cachetools import TTLCache  # type: ignore

    # Some environments can export TTLCache as a non-type symbol, so
    # guard the isinstance() assertion to prevent TypeError-based breakage.
    if isinstance(TTLCache, type):
        assert isinstance(proxy.request_history, TTLCache)
    else:
        # Best-effort validation based on cachetools TTLCache API shape.
        assert hasattr(proxy.request_history, "ttl")

    # Test dynamic cost lookup
    mock_config = MagicMock()
    mock_config.get.side_effect = lambda k: (
        0.02 if "input" in k else 0.04 if "output" in k else None
    )

    with patch("core.config_cache.config_cache", mock_config):
        # Calculation: 10 input * 0.02 + 5 output * 0.04 = 0.20 + 0.20 = 0.40
        cost = proxy._calculate_cost("openai/gpt-4o", 10, 5)
        assert abs(cost - 0.40) < 1e-5
