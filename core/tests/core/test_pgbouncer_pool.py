from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from database.pgbouncer_pool import PgBouncerConnectionPool


@pytest.mark.asyncio
async def test_singleton_pattern():
    from database.pgbouncer_pool import PgBouncerConnectionPool, get_db_pool, init_db_pool

    with patch.object(PgBouncerConnectionPool, "connect", new_callable=AsyncMock):
        await init_db_pool("test_dsn")
        pool1 = await get_db_pool()
        pool2 = await get_db_pool()
        assert pool1 is pool2


@pytest.mark.asyncio
async def test_connect():
    pool = PgBouncerConnectionPool("test_dsn")
    with patch(
        "database.pgbouncer_pool.asyncpg.create_pool", new_callable=AsyncMock
    ) as mock_create_pool:
        mock_pool = MagicMock()
        mock_create_pool.return_value = mock_pool
        await pool.connect()
        mock_create_pool.assert_called_once_with(
            dsn="test_dsn",
            min_size=1,
            max_size=5,
            max_inactive_connection_lifetime=300,
            ssl=ANY,
            statement_cache_size=0,
            command_timeout=30,
            connection_class=ANY,
        )
        assert pool._pool is mock_pool


@pytest.mark.asyncio
async def test_acquire_without_initialization():
    pool = PgBouncerConnectionPool("test_dsn")
    with pytest.raises(RuntimeError, match="Connection pool not initialized"):
        await pool.acquire()


@pytest.mark.asyncio
async def test_acquire_and_release():
    pool = PgBouncerConnectionPool("test_dsn")
    mock_pool = MagicMock()
    mock_pool.acquire = AsyncMock(return_value="mock_connection")
    mock_pool.release = AsyncMock()
    pool._pool = mock_pool

    conn = await pool.acquire()
    assert conn == "mock_connection"
    mock_pool.acquire.assert_called_once()

    await pool.release(conn)
    mock_pool.release.assert_called_once_with("mock_connection")


@pytest.mark.asyncio
async def test_close_resets_pool():
    pool = PgBouncerConnectionPool("test_dsn")
    mock_pool = MagicMock()
    mock_pool.close = AsyncMock()
    pool._pool = mock_pool

    await pool.close()
    assert pool._pool is None
    mock_pool.close.assert_called_once()
