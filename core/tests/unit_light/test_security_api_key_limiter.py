from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.security.api_key_limiter import (
    API_KEY_LIMIT_PREFIX,
    DEFAULT_MAX_REQUESTS_PER_MINUTE,
    enforce_api_key_rate_limit,
)


@pytest.mark.asyncio
async def test_fail_open_when_redis_unavailable():
    manager = MagicMock()
    manager.client = None
    with patch("core.cache.redis_manager.redis_manager", manager):
        # Should not raise even though Redis is down.
        await enforce_api_key_rate_limit("abc123hash")


@pytest.mark.asyncio
async def test_under_limit_passes():
    # Issue #460 contract: ONE billable atomic EVAL per evaluation.
    client = MagicMock()
    client.eval = AsyncMock(return_value=5)
    manager = MagicMock()
    manager.client = client
    with patch("core.cache.redis_manager.redis_manager", manager):
        await enforce_api_key_rate_limit("abc123hash", max_requests=10)
    client.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_over_limit_raises_429():
    client = MagicMock()
    client.eval = AsyncMock(return_value=11)
    manager = MagicMock()
    manager.client = client
    with patch("core.cache.redis_manager.redis_manager", manager):
        with pytest.raises(HTTPException) as exc_info:
            await enforce_api_key_rate_limit("abc123hash", max_requests=10)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_unexpected_redis_error_fails_open():
    client = MagicMock()
    client.eval = AsyncMock(side_effect=Exception("redis boom"))
    manager = MagicMock()
    manager.client = client
    with patch("core.cache.redis_manager.redis_manager", manager):
        await enforce_api_key_rate_limit("abc123hash")


def test_constants_are_sane():
    assert API_KEY_LIMIT_PREFIX.startswith("apikey:rate:")
    assert DEFAULT_MAX_REQUESTS_PER_MINUTE > 0
