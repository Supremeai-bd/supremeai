"""Regression tests for passing Pydantic SecretStr settings to runtime clients."""

from types import SimpleNamespace

from pydantic import SecretStr

import core.database.supabase_client as supabase_client_module
import core.db as db_module
import core.persistence.pooled_pg as pooled_pg_module
from core.database.session import get_async_url
from core.database.supabase_client import SupabaseDB


def test_database_url_is_unwrapped_before_scheme_normalization(monkeypatch):
    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(
            supabase_database_url=SecretStr("postgres://user:pass@db.example.test/app")
        ),
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert db_module._get_database_url() == (
        "postgresql+asyncpg://user:pass@db.example.test/app"
    )


def test_session_and_pooled_dsn_accept_secretstr(monkeypatch):
    assert get_async_url(SecretStr("postgres://user:pass@db.example.test/app")) == (
        "postgresql+asyncpg://user:pass@db.example.test/app"
    )

    monkeypatch.setattr(
        pooled_pg_module,
        "settings",
        SimpleNamespace(
            supabase_database_url=SecretStr("postgres://user:pass@db.example.test/app")
        ),
    )
    assert pooled_pg_module._resolve_dsn() == (
        "postgres://user:pass@db.example.test/app"
    )


def test_supabase_clients_receive_plain_secret_strings(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_create_client(url: str, key: str) -> object:
        calls.append((url, key))
        return object()

    monkeypatch.setattr(
        supabase_client_module,
        "settings",
        SimpleNamespace(
            supabase_url="https://project.example.test",
            supabase_key=SecretStr("anon-test-key"),
            supabase_service_key=SecretStr("service-test-key"),
        ),
    )
    monkeypatch.setattr(supabase_client_module, "create_client", fake_create_client)

    db = SupabaseDB()

    assert calls == [
        ("https://project.example.test", "anon-test-key"),
        ("https://project.example.test", "service-test-key"),
    ]
    assert db.client is not None
    assert db.service_client is not None
