from unittest.mock import patch

import pytest

from engine.vector_db import VectorDatabaseClient


@pytest.mark.asyncio
async def test_vector_db_save_experience():
    """Verify VectorDatabaseClient delegates save_experience to CascadeMemoryService."""
    client = VectorDatabaseClient()

    with patch("services.memory_service.memory_service") as mock_memory_service:
        await client.save_experience(
            vector=[0.1, 0.2, 0.3], metadata={"request": "Fix bug", "patch_id": "patch_1"}
        )

        mock_memory_service.store_memory.assert_called_once()
        args, kwargs = mock_memory_service.store_memory.call_args
        assert kwargs["summary"] == "Fix bug"
        assert kwargs["file_path"] == "patch_1"


@pytest.mark.asyncio
async def test_vector_db_find_similar_experiences():
    """Verify VectorDatabaseClient transforms hits from CascadeMemoryService back to legacy Pinecone shape."""
    client = VectorDatabaseClient()

    with patch("services.memory_service.memory_service") as mock_memory_service:
        # Mock Cascade return format
        mock_memory_service.query_context.return_value = [
            {
                "id": "123",
                "score": 0.85,
                "metadata": {
                    "original": {"request": "Fix something"},
                    "action_taken": "Solution text",
                },
            }
        ]

        # In the original code, if vector is a string it gets passed to query_context.
        # The adapter logic does `query_text = vector if isinstance(vector, str) else ""`
        results = await client.find_similar_experiences(vector="Fix something", top_k=1)

        # বাংলা মন্তব্য: ইঞ্জিন কোডে ইতিমধ্যে BUGFIX করা হয়েছে যাতে সঠিক
        # query_context(prompt=, top_k=) সিগনেচার ব্যবহার হয় (আগে ভুল
        # query=/limit=/threshold= kwargs পাঠানো হতো, যা TypeError তৈরি করত এবং
        # except ব্লকে চুপচাপ গিলে ফেলা হতো — ফলাফল সবসময় খালি থাকত)। টেস্টটিও
        # এখন সেই সঠিক সিগনেচার অনুযায়ী আপডেট করা হলো।
        mock_memory_service.query_context.assert_called_once_with(prompt="Fix something", top_k=1)

        assert len(results) == 1
        assert results[0]["id"] == "123"
        assert results[0]["score"] == 0.85
        assert results[0]["solution"] == "Solution text"
        assert results[0]["metadata"]["request"] == "Fix something"
