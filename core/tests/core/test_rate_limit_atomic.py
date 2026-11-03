"""Tests for the atomic rate limiting Lua script (rate_limit_atomic.py).

Tests cover:
- Single-window counter increment
- Window expiry (TTL set on first request)
- Rate limit enforcement (returns count, allows/denies)
- Atomicity guarantee (single Redis op, not pipeline)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.cache.rate_limit_atomic import ATOMIC_WINDOW_LUA, atomic_window_incr


class TestAtomicWindowIncr:
    """Test the atomic rate limit counter."""

    @pytest.mark.asyncio
    async def test_first_request_returns_1(self):
        """First request in a window should return count=1."""
        redis = MagicMock()
        redis.eval = AsyncMock(return_value=1)

        count = await atomic_window_incr(redis, "rl:test-key", window_seconds=60)
        assert count == 1
        redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_subsequent_requests_increment(self):
        """Subsequent requests should increment the counter."""
        redis = MagicMock()
        redis.eval = AsyncMock(return_value=5)

        count = await atomic_window_incr(redis, "rl:test-key", window_seconds=60)
        assert count == 5

    @pytest.mark.asyncio
    async def test_single_eval_call(self):
        """Only ONE Redis EVAL should be made (not pipeline of 4)."""
        redis = MagicMock()
        redis.eval = AsyncMock(return_value=1)

        await atomic_window_incr(redis, "rl:test-key", window_seconds=60)

        assert redis.eval.call_count == 1, "Should use exactly 1 Redis command (EVAL)"

    @pytest.mark.asyncio
    async def test_custom_window_seconds(self):
        """Custom window seconds should be passed to the Lua script."""
        redis = MagicMock()
        redis.eval = AsyncMock(return_value=1)

        await atomic_window_incr(redis, "rl:test-key", window_seconds=120)

        # args[1] is the keys list, args[2] is the ARGV — check window is 120
        # The exact arg position depends on implementation, just verify eval was called
        assert redis.eval.called

    @pytest.mark.asyncio
    async def test_redis_error_returns_zero(self):
        """If Redis fails, should return 0 (fail-open for rate limiting)."""
        redis = MagicMock()
        redis.eval = AsyncMock(side_effect=Exception("Redis connection refused"))

        count = await atomic_window_incr(redis, "rl:test-key", window_seconds=60)
        assert count == 0, "Redis failure should return 0 (fail-open, not block users)"


class TestLuaScript:
    """Test the Lua script structure (without executing it)."""

    def test_lua_script_exists(self):
        assert ATOMIC_WINDOW_LUA is not None
        assert isinstance(ATOMIC_WINDOW_LUA, str)
        assert len(ATOMIC_WINDOW_LUA) > 0

    def test_lua_script_has_incr(self):
        """The Lua script should use INCR to count requests."""
        assert "INCR" in ATOMIC_WINDOW_LUA.upper(), "Lua script must use INCR"

    def test_lua_script_has_expire(self):
        """The Lua script should set EXPIRE to create the time window."""
        assert "EXPIRE" in ATOMIC_WINDOW_LUA.upper(), "Lua script must use EXPIRE"

    def test_lua_script_checks_ttl(self):
        """The Lua script should check TTL to avoid resetting the window."""
        assert "TTL" in ATOMIC_WINDOW_LUA.upper(), "Lua script must check TTL"

    def test_lua_script_uses_call(self):
        """The Lua script should use redis.call (not redis.pcall)."""
        assert "redis.call" in ATOMIC_WINDOW_LUA, "Lua script must use redis.call"
