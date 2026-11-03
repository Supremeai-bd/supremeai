from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.rate_limiter import AsyncRateLimiter


@pytest.mark.asyncio
async def test_async_rate_limiter_lua_path(monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    fake_client = MagicMock()
    fake_client.eval = AsyncMock(return_value=[1, 5])

    with patch.object(AsyncRateLimiter, "_get_redis", AsyncMock(return_value=fake_client)):
        limiter = AsyncRateLimiter()
        limiter._rate_limit_enabled = True
        allowed = await limiter.acquire("test-key", limit=10, window=60)
        assert allowed is True
        fake_client.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_rate_limiter_lua_rejection(monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    fake_client = MagicMock()
    fake_client.eval = AsyncMock(return_value=[0, 11])

    with patch.object(AsyncRateLimiter, "_get_redis", AsyncMock(return_value=fake_client)):
        limiter = AsyncRateLimiter()
        limiter._rate_limit_enabled = True
        allowed = await limiter.acquire("test-key", limit=10, window=60)
        assert allowed is False
        fake_client.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_rate_limiter_pipeline_fallback(monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    fake_pipe = MagicMock()
    fake_pipe.execute = AsyncMock(return_value=[1, 0, 3, True])
    fake_client = MagicMock()
    fake_client.eval = AsyncMock(side_effect=TypeError("Mock no eval"))
    fake_client.pipeline = MagicMock(return_value=fake_pipe)

    with patch.object(AsyncRateLimiter, "_get_redis", AsyncMock(return_value=fake_client)):
        limiter = AsyncRateLimiter()
        limiter._rate_limit_enabled = True
        allowed = await limiter.acquire("test-key", limit=10, window=60)
        assert allowed is True
        fake_pipe.execute.assert_awaited_once()
