"""Regression tests for production DB degraded boot path in database/session.py.

Guarantees:
1. production + missing DB + degradation=true  -> no engine (_engine_instance is None, no SQLite)
2. production + DB failure + degradation=true -> no SQLite (_engine_instance is None)
3. production + degradation=false + missing DB -> raises RuntimeError (fail closed)
4. production + degradation=false + DB failure -> raises RuntimeError (fail closed)
5. dev/test + missing DB                       -> SQLite allowed
"""

from unittest.mock import patch

import pytest

import database.session as session_mod


@pytest.fixture(autouse=True)
def reset_session_module_state():
    """Ensure engine and sessionmaker singletons are reset before and after each test."""
    session_mod._engine_instance = None
    session_mod._session_maker_instance = None
    yield
    session_mod._engine_instance = None
    session_mod._session_maker_instance = None


def test_production_missing_db_degradation_true_creates_no_engine(monkeypatch):
    """Production + missing pooler URL + SUPABASE_ALLOW_DB_DEGRADATION=true:
    init_engine() must immediately return without creating ANY engine (no SQLite).
    """
    monkeypatch.setattr(session_mod.settings, "env", "production")
    monkeypatch.setattr(
        type(session_mod.settings), "supabase_database_url", property(lambda self: "")
    )
    monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")

    session_mod.init_engine()

    assert session_mod._engine_instance is None
    assert session_mod._session_maker_instance is None

    # Accessing session maker in degraded mode raises RuntimeError
    with pytest.raises(RuntimeError, match="running in degraded REST-only mode"):
        session_mod._get_session_maker()


def test_production_db_failure_degradation_true_creates_no_sqlite(monkeypatch):
    """Production + DB connection failure + SUPABASE_ALLOW_DB_DEGRADATION=true:
    init_engine() must immediately return on failure without creating an in-memory SQLite engine.
    """
    monkeypatch.setattr(session_mod.settings, "env", "production")
    monkeypatch.setattr(
        type(session_mod.settings),
        "supabase_database_url",
        property(lambda self: "postgresql+asyncpg://invalid:url@localhost:5432/db"),
    )
    monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "true")

    with patch(
        "database.session.create_async_engine",
        side_effect=Exception("Simulated connection timeout"),
    ):
        session_mod.init_engine()

    # Engine MUST NOT be created, and definitely NOT SQLite
    assert session_mod._engine_instance is None
    assert session_mod._session_maker_instance is None


def test_production_missing_db_degradation_false_fails_closed(monkeypatch):
    """Production + missing DB + degradation=false:
    Must raise RuntimeError (fail-closed) to protect against booting without strict DB.
    """
    monkeypatch.setattr(session_mod.settings, "env", "production")
    monkeypatch.setattr(
        type(session_mod.settings), "supabase_database_url", property(lambda self: "")
    )
    monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "false")

    with pytest.raises(
        RuntimeError, match="Production environment requires SUPABASE_DATABASE_URL_POOLER"
    ):
        session_mod.init_engine()


def test_production_db_failure_degradation_false_fails_closed(monkeypatch):
    """Production + DB failure + degradation=false:
    Must raise RuntimeError (fail-closed).
    """
    monkeypatch.setattr(session_mod.settings, "env", "production")
    monkeypatch.setattr(
        type(session_mod.settings),
        "supabase_database_url",
        property(lambda self: "postgresql+asyncpg://user:pass@localhost:5432/db"),
    )
    monkeypatch.setenv("SUPABASE_ALLOW_DB_DEGRADATION", "false")

    with patch("database.session.create_async_engine", side_effect=Exception("Connection refused")):
        with pytest.raises(RuntimeError, match="Production DB engine creation failed"):
            session_mod.init_engine()


def test_dev_environment_missing_db_allows_sqlite_fallback(monkeypatch):
    """Development / test environment + missing DB:
    SQLite in-memory fallback is allowed.
    """
    monkeypatch.setattr(session_mod.settings, "env", "development")
    monkeypatch.setattr(
        type(session_mod.settings), "supabase_database_url", property(lambda self: "")
    )
    monkeypatch.delenv("SUPABASE_ALLOW_DB_DEGRADATION", raising=False)

    session_mod.init_engine()

    assert session_mod._engine_instance is not None
    assert session_mod._engine_instance.dialect.name == "sqlite"
