import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.security.rate_limiter as rl_module
from core.security.rate_limiter import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
)


@pytest.mark.asyncio
async def test_is_allowed_no_client_non_production_allows():
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=None)
    with (
        patch.object(rl_module, "redis_manager", manager),
        patch.object(rl_module.settings, "env", "local"),
    ):
        limiter = SlidingWindowRateLimiter()
        allowed, count, remaining = await limiter.is_allowed("ip1", 10, 60)
    assert allowed is True
    assert count == 0
    assert remaining == 10


@pytest.mark.asyncio
async def test_is_allowed_no_client_production_denies():
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=None)
    with (
        patch.object(rl_module, "redis_manager", manager),
        patch.object(rl_module.settings, "env", "production"),
    ):
        limiter = SlidingWindowRateLimiter()
        allowed, count, remaining = await limiter.is_allowed("ip1", 10, 60)
    assert allowed is False
    assert count == 0
    assert remaining == 0


@pytest.mark.asyncio
async def test_is_allowed_with_client_uses_evalsha():
    client = MagicMock()
    client.evalsha = AsyncMock(return_value=[1, 3])
    client.eval = AsyncMock(return_value=[1, 3])
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=client)
    with (
        patch.object(rl_module, "redis_manager", manager),
        patch.object(rl_module.settings, "env", "local"),
    ):
        limiter = SlidingWindowRateLimiter()
        limiter.script_sha = "cached-sha"
        allowed, count, remaining = await limiter.is_allowed("ip1", 10, 60)
    assert allowed is True
    assert count == 3
    assert remaining == 7
    client.evalsha.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_allowed_with_client_falls_back_to_eval():
    client = MagicMock()
    client.evalsha = AsyncMock(return_value=[0, 10])
    client.eval = AsyncMock(return_value=[0, 10])
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=client)
    with (
        patch.object(rl_module, "redis_manager", manager),
        patch.object(rl_module.settings, "env", "local"),
    ):
        limiter = SlidingWindowRateLimiter()
        limiter.script_sha = None
        allowed, count, remaining = await limiter.is_allowed("ip1", 10, 60)
    assert allowed is False
    assert count == 10
    client.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_allowed_error_in_non_production_allows():
    client = MagicMock()
    client.evalsha = AsyncMock(side_effect=Exception("redis error"))
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=client)
    with (
        patch.object(rl_module, "redis_manager", manager),
        patch.object(rl_module.settings, "env", "development"),
    ):
        limiter = SlidingWindowRateLimiter()
        limiter.script_sha = "cached-sha"
        allowed, count, remaining = await limiter.is_allowed("ip1", 10, 60)
    assert allowed is True
    assert remaining == 10


@pytest.mark.asyncio
async def test_get_reset_time_no_client():
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=None)
    with patch.object(rl_module, "redis_manager", manager):
        limiter = SlidingWindowRateLimiter()
        reset = await limiter.get_reset_time("ip1", 60)
    assert reset == int(time.time()) + 60


@pytest.mark.asyncio
async def test_get_reset_time_with_client():
    client = MagicMock()
    client.zrange = AsyncMock(return_value=[("1740000000_12345", "1740000000_12345")])
    manager = MagicMock()
    manager.get_client_async = AsyncMock(return_value=client)
    with patch.object(rl_module, "redis_manager", manager):
        limiter = SlidingWindowRateLimiter()
        reset = await limiter.get_reset_time("ip1", 60)
    assert reset == 1740000000 + 60


def test_rate_limit_exceeded_error_is_exception():
    assert issubclass(RateLimitExceededError, Exception)
