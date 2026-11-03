"""Coverage tests for core/db.py (engine setup, sessions, health-check, slow-query)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import core.db as core_db


@pytest.fixture(autouse=True)
def _reset_db():
    core_db.get_engine.cache_clear()
    core_db._engine = None
    core_db._async_session_factory = None
    yield
    core_db.get_engine.cache_clear()
    core_db._engine = None
    core_db._async_session_factory = None


def test_get_database_url_empty(monkeypatch):
    # Audit fix (patch v3): canonical field is supabase_database_url; the old
    # settings.database_url attribute never existed. DATABASE_URL env must be
    # cleared for the fallback assertion to be hermetic.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(core_db, "settings", SimpleNamespace(supabase_database_url=""))
    with pytest.raises(RuntimeError, match="SQLite fallback is disabled"):
        core_db._get_database_url()


@pytest.mark.parametrize(
    "in_url,out_url",
    [
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("mysql://u@h/db", "mysql://u@h/db"),
    ],
)
def test_get_database_url_conversions(monkeypatch, in_url, out_url):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(core_db, "settings", SimpleNamespace(supabase_database_url=in_url))
    assert core_db._get_database_url() == out_url


def test_get_engine_sqlite_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        core_db, "settings", SimpleNamespace(supabase_database_url="sqlite+aiosqlite:///:memory:")
    )
    engine = core_db.get_engine()
    assert "sqlite" in engine.url.drivername
    assert core_db.get_engine() is engine  # cached


def test_get_session_factory_returns_and_reuses(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        core_db, "settings", SimpleNamespace(supabase_database_url="sqlite+aiosqlite:///:memory:")
    )
    f1 = core_db.get_session_factory()
    f2 = core_db.get_session_factory()
    assert f1 is f2


async def test_get_db_commit_path(monkeypatch):
    monkeypatch.setattr(
        core_db, "settings", SimpleNamespace(supabase_database_url="sqlite+aiosqlite:///:memory:")
    )
    core_db.get_engine.cache_clear()
    gen = core_db.get_db()
    session = await anext(gen)
    assert session is not None
    with pytest.raises(StopAsyncIteration):
        await anext(gen)  # resume -> commit -> close


async def test_get_db_rollback_on_error(monkeypatch):
    fake_session = MagicMock()
    fake_session.commit = AsyncMock(side_effect=RuntimeError("boom"))
    fake_session.rollback = AsyncMock()
    fake_session.close = AsyncMock()
    fake_factory = MagicMock()
    fake_factory.return_value.__aenter__ = AsyncMock(return_value=fake_session)
    fake_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(core_db, "get_session_factory", lambda: fake_factory)
    gen = core_db.get_db()
    await anext(gen)
    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("boom"))
    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()


async def test_db_session_context(monkeypatch):
    monkeypatch.setattr(
        core_db, "settings", SimpleNamespace(supabase_database_url="sqlite+aiosqlite:///:memory:")
    )
    core_db.get_engine.cache_clear()
    async with core_db.db_session() as session:
        assert session is not None


async def test_check_db_health_unhealthy(monkeypatch):
    monkeypatch.setattr(core_db, "engine", None)
    monkeypatch.setattr(core_db, "get_engine", lambda: None)
    result = await core_db.check_db_health()
    assert result["healthy"] is False
    assert "error" in result


async def test_check_db_health_healthy_and_slow_query(monkeypatch):
    monkeypatch.setattr(
        core_db, "settings", SimpleNamespace(supabase_database_url="sqlite+aiosqlite:///:memory:")
    )
    core_db.get_engine.cache_clear()
    engine = core_db.get_engine()
    monkeypatch.setattr(core_db, "engine", engine)
    monkeypatch.setattr(core_db, "SLOW_QUERY_THRESHOLD_MS", -1)  # force slow-path logging
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    result = await core_db.check_db_health()
    assert result["healthy"] is True
    assert "latency_ms" in result
    assert result["pool_size"] == core_db.POOL_SIZE
