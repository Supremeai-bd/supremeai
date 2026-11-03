"""Tests for core.cache.redis_manager — SecureRedisManager & IdempotencyLock."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.cache.redis_manager import (
    IdempotencyUnavailableError,
    SecureRedisManager,
    _AcquireIdempotencyLockContext,
    acquire_idempotency_lock,
    redis_manager,
)


@pytest.fixture
def manager():
    """Create a fresh SecureRedisManager for each test."""
    m = SecureRedisManager()
    m.url = ""
    m._client = None
    m._initialized = True
    return m


class TestSecureRedisManagerInitialization:
    """SecureRedisManager init & connection tests."""

    @pytest.mark.asyncio
    async def test_init_no_url(self):
        """No redis_url → _client remains None, _initialized False."""
        with patch("core.cache.redis_manager.os.getenv", return_value=""):
            with patch("core.security.secret_vault.secret_vault.fetch_secret", return_value=""):
                mgr = SecureRedisManager()
                mgr.url = ""
                assert mgr._client is None
                assert mgr._initialized is False

    @pytest.mark.asyncio
    async def test_ensure_connected_no_url(self):
        """No URL → _ensure_connected logs critical, _initialized True."""
        with patch("core.cache.redis_manager.os.getenv", return_value=""):
            with patch("core.security.secret_vault.secret_vault.fetch_secret", return_value=""):
                mgr = SecureRedisManager()
                mgr.url = ""
                await mgr._ensure_connected()
                assert mgr._initialized is True
                assert mgr._client is None

    @pytest.mark.asyncio
    async def test_get_client_async_returns_none_when_no_url(self):
        """get_client_async returns None when no Redis URL configured."""
        with patch("core.cache.redis_manager.os.getenv", return_value=""):
            with patch("core.security.secret_vault.secret_vault.fetch_secret", return_value=""):
                mgr = SecureRedisManager()
                mgr.url = ""
                client = await mgr.get_client_async()
                assert client is None

    @pytest.mark.asyncio
    async def test_init_lock_prevents_race(self):
        """_init_lock prevents double initialization."""
        mgr = SecureRedisManager()
        await mgr._ensure_connected()
        await mgr._ensure_connected()
        assert mgr._initialized is True

    @pytest.mark.asyncio
    async def test_client_property_sync_fallback(self):
        """client property returns _client directly without sync blocking."""
        mgr = SecureRedisManager()
        mgr._client = "mock_client"
        assert mgr.client == "mock_client"


class TestSecureRedisManagerOperations:
    """SecureRedisManager SET/GET/DELETE operations."""

    @pytest.mark.asyncio
    async def test_set_no_client(self, manager):
        result = await manager.set("key", "value")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_no_client(self, manager):
        result = await manager.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_no_client(self, manager):
        result = await manager.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_cache_alias(self, manager):
        result = await manager.set_cache("k", "v", ex_seconds=60)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_cache_alias(self, manager):
        result = await manager.get_cache("k")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_json_no_client(self, manager):
        result = await manager.set_json("k", {"a": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_get_json_no_client(self, manager):
        result = await manager.get_json("k")
        assert result is None


class TestRedisManagerClose:
    """SecureRedisManager.close() behavior."""

    @pytest.mark.asyncio
    async def test_close_without_client(self, manager):
        await manager.close()
        assert manager._client is None


class TestModuleLevelSingleton:
    """Module-level redis_manager singleton."""

    def test_redis_manager_is_instance(self):
        assert isinstance(redis_manager, SecureRedisManager)


class TestIdempotencyLock:
    """_AcquireIdempotencyLockContext & acquire_idempotency_lock."""

    @pytest.mark.asyncio
    async def test_acquire_no_client_fail_closed(self):
        redis_manager.url = ""
        redis_manager._initialized = True
        redis_manager._client = None
        with pytest.raises(IdempotencyUnavailableError):
            async with acquire_idempotency_lock("test-key", fail_closed=True):
                pass

    @pytest.mark.asyncio
    async def test_acquire_no_client_fail_open(self):
        redis_manager._initialized = False
        redis_manager._client = None
        async with acquire_idempotency_lock("test-key", fail_closed=False):
            pass

    @pytest.mark.asyncio
    async def test_lock_context_manager(self):
        ctx = _AcquireIdempotencyLockContext("test", ttl=30, fail_closed=False)
        async with ctx as lock:
            assert lock is ctx
            assert ctx.acquired is False

    def test_lock_context_key_format(self):
        ctx = _AcquireIdempotencyLockContext("my-key")
        assert ctx.key == "idempotency:my-key"

    @pytest.mark.asyncio
    async def test_lock_acquire_release_exit(self):
        redis_manager._initialized = False
        redis_manager._client = None
        ctx = _AcquireIdempotencyLockContext("test", fail_closed=False)
        async with ctx:
            pass


class TestMultiLevelCache:
    """Tests for MultiLevelCache system."""

    @pytest.mark.asyncio
    async def test_multilevel_cache_l1_l2(self):
        from core.cache.redis_manager import MultiLevelCache

        mock_redis = MagicMock()
        mock_redis.get_cache = AsyncMock(return_value="redis-value")
        mock_redis.set_cache = AsyncMock()

        ml_cache = MultiLevelCache(redis_mgr=mock_redis)

        # L2 Hit & L1 Warmup
        val = await ml_cache.get("key1")
        assert val == "redis-value"
        assert ml_cache.local_cache["key1"] == "redis-value"

        # L1 Hit
        mock_redis.get_cache.reset_mock()
        l1_val = await ml_cache.get("key1")
        assert l1_val == "redis-value"
        mock_redis.get_cache.assert_not_called()

        # Set
        await ml_cache.set("key2", "val2", ttl=600)
        assert ml_cache.local_cache["key2"] == "val2"
        mock_redis.set_cache.assert_awaited_once_with("key2", "val2", ex_seconds=600)

        # Invalidate Local
        ml_cache.invalidate_local("key1")
        assert "key1" not in ml_cache.local_cache
