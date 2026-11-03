"""Issue #1689 (CRITICAL) — vector store cross-tenant isolation tests.

`FreeTierOptimizedVectorStore.similarity_search` used to accept
``user_id: str | None = None`` and silently omit ``p_user_id`` from the
``match_memories`` RPC when the value was falsy — the database then returned
EVERY user's memories (cross-tenant data leak). These tests lock the new
fail-closed contract:

1. ``user_id`` is a required argument (TypeError when omitted)
2. blank/whitespace user_id → ValueError, no RPC call
3. ``p_user_id`` is ALWAYS present in RPC params
"""

from unittest.mock import MagicMock

import pytest

from core.ai_memory.vector_store import FreeTierOptimizedVectorStore


def _store() -> FreeTierOptimizedVectorStore:
    """Store instance with a mocked supabase client (no network)."""
    s = FreeTierOptimizedVectorStore("https://example.supabase.co", "test-key")
    s.client = MagicMock()
    return s


def _successful_rpc(store: FreeTierOptimizedVectorStore) -> None:
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value.data = [
        {"id": "mem-1", "similarity": 0.92, "metadata": {"content": "hello"}}
    ]
    store.client.rpc = MagicMock(return_value=mock_rpc)


class TestSimilaritySearchTenantIsolation:
    async def test_user_id_is_required(self):
        store = _store()
        with pytest.raises(TypeError):
            await store.similarity_search(query_embedding=[0.1] * 384)  # type: ignore[call-arg]

    @pytest.mark.parametrize("bad_user_id", ["", "   ", None])
    async def test_blank_user_id_fails_closed_without_rpc(self, bad_user_id):
        store = _store()
        _successful_rpc(store)
        with pytest.raises(ValueError, match="non-empty user_id"):
            await store.similarity_search(
                query_embedding=[0.1] * 384,
                user_id=bad_user_id,  # type: ignore[arg-type]
            )
        store.client.rpc.assert_not_called()  # no DB access without tenant scope

    async def test_p_user_id_always_sent(self):
        store = _store()
        _successful_rpc(store)
        results = await store.similarity_search(
            query_embedding=[0.1] * 384, user_id="u-tenant1", limit=5
        )
        assert len(results) == 1
        store.client.rpc.assert_called_once_with(
            "match_memories",
            {
                "query_embedding": [0.1] * 384,
                "match_threshold": 0.7,
                "match_count": 5,
                "p_user_id": "u-tenant1",
            },
        )

    async def test_whitespace_user_id_is_rejected(self):
        store = _store()
        with pytest.raises(ValueError):
            await store.similarity_search(query_embedding=[0.1] * 384, user_id="\t \n")
