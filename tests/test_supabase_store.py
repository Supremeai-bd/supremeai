import os
from unittest.mock import MagicMock, patch
from memory.supabase_store import SupabaseStore


def test_provider_sqlite_when_no_url():
    with patch.dict(os.environ, {}, clear=False):
        store = SupabaseStore(database_url='', local_path=':memory:')
        assert store.provider == 'sqlite'


def test_provider_supabase_when_url_set():
    store = SupabaseStore(database_url='postgres://localhost/test', local_path=':memory:')
    assert store.provider == 'supabase'


def test_supabase_connect_failure(monkeypatch):
    store = SupabaseStore(database_url='postgres://localhost/test', local_path=':memory:')
    monkeypatch.setattr(store, '_conn', None)
    with patch('psycopg.connect', side_effect=RuntimeError('db down')):
        try:
            store.connect()
        except RuntimeError:
            pass
