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
    def fake_client(*_args, **_kwargs):
        raise RuntimeError('db down')
    monkeypatch.setattr(store, '_provider', 'supabase')
    monkeypatch.setattr(store, '_get_supabase_client', fake_client)
    try:
        store.save_conversation('s1', [{'role': 'u', 'content': 'hi'}])
    except RuntimeError:
        pass
    else:
        raise AssertionError('Expected RuntimeError on supabase failure')
