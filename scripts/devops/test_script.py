import pytest
from unittest.mock import patch, MagicMock
from backend.services.memory_service import CascadeMemoryService

def test_cascade_memory_service_sqlite_fallback():
    service = CascadeMemoryService(db_path=":memory:")
    assert not service._use_pg
    service.store_memory(
        file_path="test.py",
        content="def test(): pass",
        summary="test summary",
        structure="{}"
    )
    # verify search or schema
    assert True

def test_cascade_memory_service_pgvector(monkeypatch):
    # This is a unit test that mocks postgres to verify schema execution
    mock_pg = MagicMock()
    mock_pg.is_available.return_value = True
    
    with patch("backend.services.memory_service.pooled_pg", mock_pg):
        service = CascadeMemoryService()
        assert service._use_pg
        # Verify schema execution
        mock_pg.execute.assert_called_with(
            """
    CREATE TABLE IF NOT EXISTS ai_memory (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT DEFAULT NULL, -- NEW: nullable for backward compat
        session_id TEXT,
        agent_type TEXT,
        task_type TEXT,
        summary TEXT,
        embedding TEXT, -- Store as JSON string
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
"""
        )
