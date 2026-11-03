"""
Auto-RAG Memory Injection tests (old plan, Feature 2 / audit G-3).

টিয়ার: unit — কোনো নেটওয়ার্ক/DB লাগে না (mock vector store)।
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.memory.auto_rag_injector import AutoRAGInjector, auto_rag_injector

pytestmark = [pytest.mark.unit, pytest.mark.memory]


def _make_vector_store(memories: list[dict] | None = None, fail: bool = False):
    vs = MagicMock()
    if fail:
        vs.similarity_search = AsyncMock(side_effect=RuntimeError("supabase down"))
        vs.upsert_batch = AsyncMock(side_effect=RuntimeError("supabase down"))
    else:
        vs.similarity_search = AsyncMock(return_value=memories or [])
        vs.upsert_batch = AsyncMock(return_value=True)
    return vs


@pytest.fixture
def injector():
    return AutoRAGInjector(vector_store=None)


# ── enrich_system_prompt ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_prepends_memory_block(injector):
    vs = _make_vector_store(
        [
            {"id": "1", "content": "User prefers Python", "score": 0.91, "metadata": {}},
            {"id": "2", "content": "Deploy target is Render", "score": 0.77, "metadata": {}},
        ]
    )
    injector._vs = vs
    out = await injector.enrich_system_prompt(
        system_prompt="You are helpful.",
        user_query="what language do I like?",
        user_id="u1",
        tenant_id="t1",
    )
    assert out.startswith("\n\n--- 🧠 Past Context (Auto-Recalled) ---")
    assert "User prefers Python" in out
    assert "You are helpful." in out
    # memory block আগে, system prompt পরে
    assert out.index("User prefers Python") < out.index("You are helpful.")
    vs.similarity_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrich_no_memories_returns_original(injector):
    injector._vs = _make_vector_store([])
    original = "You are helpful."
    out = await injector.enrich_system_prompt(original, "hi", "u1", "t1")
    assert out == original


@pytest.mark.asyncio
async def test_enrich_low_score_filtered_out(injector):
    vs = _make_vector_store([{"id": "1", "content": "noise", "score": 0.10, "metadata": {}}])
    injector._vs = vs
    original = "SYS"
    out = await injector.enrich_system_prompt(original, "query", "u1", "t1")
    assert out == original  # MIN_RELEVANCE_SCORE=0.55 এর নিচে — বাদ


@pytest.mark.asyncio
async def test_enrich_graceful_degradation_on_error(injector):
    injector._vs = _make_vector_store(fail=True)
    original = "You are helpful."
    out = await injector.enrich_system_prompt(original, "query", "u1", "t1")
    assert out == original  # ব্যর্থ হলেও মূল prompt অক্ষত


@pytest.mark.asyncio
async def test_enrich_empty_query_noop(injector):
    vs = _make_vector_store([{"id": "1", "content": "x", "score": 0.9, "metadata": {}}])
    injector._vs = vs
    out = await injector.enrich_system_prompt("SYS", "   ", "u1", "t1")
    assert out == "SYS"
    vs.similarity_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_truncates_long_memory(injector):
    vs = _make_vector_store([{"id": "1", "content": "x" * 5000, "score": 0.9, "metadata": {}}])
    injector._vs = vs
    out = await injector.enrich_system_prompt("SYS", "q", "u1", "t1")
    # MAX_CHARS_PER_MEMORY=400 + হেডার/স্কোর প্রিফিক্স
    assert "x" * 401 not in out.replace("\n", "")[:1000] or len(out) < 1000


# ── store_session_memory ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_low_importance_skipped(injector):
    vs = _make_vector_store()
    injector._vs = vs
    ok = await injector.store_session_memory("trivial", "u1", "s1", importance=0.3)
    assert ok is False
    vs.upsert_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_success(injector):
    vs = _make_vector_store()
    injector._vs = vs
    with patch(
        "core.memory.auto_rag_injector.AutoRAGInjector._get_query_embedding",
        new=AsyncMock(return_value=[0.1] * 384),
    ):
        ok = await injector.store_session_memory("important exchange", "u1", "s1", 0.8)
    assert ok is True
    # upsert_batch kwargs দিয়ে ডাকা হয়
    kwargs = vs.upsert_batch.await_args.kwargs
    assert len(kwargs["embeddings"]) == 1
    assert kwargs["payloads"][0]["user_id"] == "u1"
    assert kwargs["payloads"][0]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_store_failure_returns_false(injector):
    injector._vs = _make_vector_store(fail=True)
    with patch(
        "core.memory.auto_rag_injector.AutoRAGInjector._get_query_embedding",
        new=AsyncMock(return_value=[0.1] * 384),
    ):
        ok = await injector.store_session_memory("content", "u1", "s1", 0.9)
    assert ok is False


# ── module singleton contract ────────────────────────────────────────────


def test_singleton_exists():
    assert isinstance(auto_rag_injector, AutoRAGInjector)
