import os
import json
import pytest
from unittest.mock import patch, MagicMock
from memory.supabase_store import SupabaseStore

def test_supabase_store_sqlite_fallback():
    # If no URL, defaults to SQLite
    store = SupabaseStore(database_url=None, local_path=":memory:")
    assert store.provider == "sqlite"
    
    # Save/get conversation
    messages = [{"role": "user", "content": "hi"}]
    store.save_conversation("session_123", messages)
    
    # Retrive
    history = store.get_conversation("session_123")
    assert len(history) == 1
    assert history[0]["content"] == "hi"

def test_supabase_store_cloud_upsert():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_upsert = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.upsert.return_value = mock_upsert
    
    mock_supabase_mod = MagicMock()
    mock_supabase_mod.create_client.return_value = mock_client
    
    with patch.dict("sys.modules", {"supabase": mock_supabase_mod}), \
         patch.dict(os.environ, {"SUPABASE_KEY": "my-key"}):
        
        store = SupabaseStore(database_url="postgresql://db.supabase.co:5432/postgres", local_path=":memory:")
        assert store.provider == "supabase"
        
        messages = [{"role": "system", "content": "hello"}]
        store.save_conversation("session_abc", messages)
        
        mock_client.table.assert_called_with("conversations")
        mock_table.upsert.assert_called_once()
        mock_upsert.execute.assert_called_once()
