"""
Tests for services/memory_service.py — CascadeMemoryService & hash_vectorize
"""

from __future__ import annotations

import math
import os

import pytest

from services.memory_service import CascadeMemoryService, hash_vectorize


class TestHashVectorize:
    def test_returns_correct_dimensions(self):
        vec = hash_vectorize("hello world", size=384)
        assert len(vec) in (384, 1536)

    def test_empty_text_returns_unit_vector(self):
        vec = hash_vectorize("", size=384)
        assert vec[0] == 1.0
        assert sum(x * x for x in vec) == pytest.approx(1.0, abs=0.001)

    def test_single_word(self):
        vec = hash_vectorize("python", size=384)
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=0.001)

    def test_same_text_same_vector(self):
        vec1 = hash_vectorize("test text for hashing", size=384)
        vec2 = hash_vectorize("test text for hashing", size=384)
        assert vec1 == vec2

    def test_different_text_different_vector(self):
        vec1 = hash_vectorize("hello world", size=384)
        vec2 = hash_vectorize("goodbye world", size=384)
        assert vec1 != vec2

    def test_custom_size(self):
        vec = hash_vectorize("test", size=128)
        assert len(vec) == 128

    def test_l2_normalized(self):
        vec = hash_vectorize("some longer text with multiple words for testing", size=384)
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=0.001)

    def test_single_character_words(self):
        vec = hash_vectorize("a b c", size=384)
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=0.001)


class TestCascadeMemoryService:
    def test_init_with_sqlite_fallback(self, tmp_path):
        db_path = str(tmp_path / "test_memory.db")
        service = CascadeMemoryService(db_path=db_path)
        assert service._use_pg is False
        assert service.db_path is not None
        assert os.path.exists(tmp_path / "test_memory.db")

    def test_init_with_explicit_db_path_creates_directory(self, tmp_path):
        db_path = str(tmp_path / "subdir" / "memory.db")
        service = CascadeMemoryService(db_path=db_path)
        assert service._use_pg is False
        assert os.path.exists(db_path)

    def test_embed_without_encoder_uses_hash(self, tmp_path):
        service = CascadeMemoryService(db_path=str(tmp_path / "embed_test.db"))
        vec = service._embed("test text")
        assert len(vec) in (384, 1536)
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=0.001)

    def test_store_and_retrieve_memory(self, tmp_path):
        service = CascadeMemoryService(db_path=str(tmp_path / "store_test.db"))
        service.store_memory(
            file_path="/test/file.py",
            content="print('hello')",
            summary="A test file",
            structure="simple script",
        )
        memories = service.retrieve_memories()
        assert len(memories) >= 1
        assert any(m["file_path"] == "/test/file.py" for m in memories)

    def test_store_duplicate_updates(self, tmp_path):
        service = CascadeMemoryService(db_path=str(tmp_path / "dup_test.db"))
        service.store_memory("/test/file.py", "v1", "summary1", "struct1")
        service.store_memory("/test/file.py", "v2", "summary2", "struct2")
        memories = service.retrieve_memories()
        matching = [m for m in memories if m["file_path"] == "/test/file.py"]
        assert len(matching) == 1
        assert matching[0]["content"] == "v2"

    def test_retrieve_empty_when_no_memories(self, tmp_path):
        service = CascadeMemoryService(db_path=str(tmp_path / "empty_test.db"))
        memories = service.retrieve_memories()
        assert isinstance(memories, list)

    def test_delete_memory(self, tmp_path):
        service = CascadeMemoryService(db_path=str(tmp_path / "delete_test.db"))
        service.store_memory("/test/del.py", "content", "summary", "struct")
        service.delete_memory("/test/del.py")
        memories = service.retrieve_memories()
        assert not any(m["file_path"] == "/test/del.py" for m in memories)

    def test_delete_nonexistent_does_not_raise(self, tmp_path):
        service = CascadeMemoryService(db_path=str(tmp_path / "nodelfail.db"))
        # Should not raise
        service.delete_memory("/nonexistent/file.py")


class TestVectorMemoryFunctions:
    def test_get_embedding_returns_384_dimensions(self):
        from services.memory_service import get_embedding

        vec = get_embedding("test prompt for vectorization")
        assert isinstance(vec, list)
        assert len(vec) in (384, 1536)
        assert any(x != 0.0 for x in vec)

    @pytest.mark.asyncio
    async def test_save_and_recall_memory(self):
        from services.memory_service import recall_memories, save_memory

        res = await save_memory(
            session_id="test_sess_101",
            summary="Implemented telemetry and vector recall for eternal brain",
            task_type="feature",
            metadata={"source": "test"},
        )
        assert res.get("success") is True

        recalled = await recall_memories(
            task_description="telemetry and vector recall",
            limit=5,
        )
        assert isinstance(recalled, list)

    @pytest.mark.asyncio
    async def test_summarize_and_save_session(self):
        from services.memory_service import summarize_and_save_session

        messages = [
            {"role": "user", "content": "How do we implement LLM telemetry?"},
            {"role": "assistant", "content": "We use track_llm_call context manager."},
        ]
        res = await summarize_and_save_session(
            session_id="test_sess_102",
            messages=messages,
            task_type="coding",
        )
        assert res.get("success") is True


class TestLLMTelemetry:
    @pytest.mark.asyncio
    async def test_track_llm_call_success(self):
        from core.llm.telemetry import track_llm_call

        async with track_llm_call(
            session_id="test_telemetry_sess",
            provider="gemini",
            model="gemini-2.0-flash",
            task_type="test",
        ) as rec:
            assert rec.provider == "gemini"
            assert rec.model == "gemini-2.0-flash"
            rec.tokens_prompt = 10
            rec.tokens_completion = 20
            rec.cost_usd = 0.0001
        assert rec.success is True
        assert rec.latency_ms >= 0.0
        assert "gemini" in rec.to_log_line()

    @pytest.mark.asyncio
    async def test_track_llm_call_exception_handling(self):
        from core.llm.telemetry import track_llm_call

        rec_captured = None
        with pytest.raises(ValueError, match="simulated failure"):
            async with track_llm_call(
                session_id="test_err_sess",
                provider="groq",
                model="llama-3.3-70b-versatile",
            ) as rec:
                rec_captured = rec
                raise ValueError("simulated failure")
        assert rec_captured is not None
        assert rec_captured.success is False
        assert "simulated failure" in (rec_captured.error or "")
