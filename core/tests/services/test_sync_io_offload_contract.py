"""Sync-I/O event-loop offload contract tests (Issue #2716).

বাংলা সারসংক্ষেপ:
------------------
Render free-tier single-worker — ইভেন্ট-লুপ ব্লক মানে পুরো সার্ভিস স্তব্ধ।
এই চুক্তি-টেস্ট প্রমাণ করে: embedding recall/save ও arXiv research search-এর
sync নেটওয়ার্ক কল worker-thread-এ অফলোড হয় — provider hang অবস্থাতেও
অন্য রিকোয়েস্ট সাড়া দেয়। (to_thread ছাড়া এই টেস্ট নিশ্চিতভাবে ব্যর্থ হবে।)
"""

import asyncio
import threading

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


class _Gate:
    """বাংলা মন্তব্য: thread-safe গেট — fake sync-কল শুরু/ছাড় নিয়ন্ত্রণ।"""

    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.loop_thread = threading.get_ident()
        self.started = asyncio.Event()
        self.release = threading.Event()

    def block_until_released(self) -> None:
        assert threading.get_ident() != self.loop_thread, "sync provider ran on the event loop"
        self.loop.call_soon_threadsafe(self.started.set)
        assert self.release.wait(timeout=5.0), "test gate never released (timeout)"

    async def release_when_blocked(self, task: asyncio.Task) -> None:
        # বাংলা: worker আটকে থাকা অবস্থাতেই লুপ notification পায়; sleep লাগে না।
        try:
            await asyncio.wait_for(self.started.wait(), timeout=3.0)
            assert not task.done()
        finally:
            self.release.set()


# ── 1. recall_memories — embedding offload ────────────────────────────────────


@pytest.mark.asyncio
async def test_recall_memories_offloads_blocking_embedding(monkeypatch):
    """বাংলা মন্তব্য: embedding provider hang করলেও লুপ সাড়া দেয় (to_thread চুক্তি)।"""
    import services.memory_service as ms

    gate = _Gate()

    def blocking_embed(text: str) -> list[float]:
        gate.block_until_released()
        return [0.0] * 384

    class EmptyVectorStore:
        def rpc(self, _name, _params):
            return self

        def execute(self):
            from types import SimpleNamespace

            return SimpleNamespace(data=[])

    monkeypatch.setattr(ms, "get_embedding", blocking_embed)
    monkeypatch.setattr(ms, "_get_supabase", EmptyVectorStore)

    task = asyncio.create_task(
        ms.recall_memories(task_description="loop-liveness probe", limit=1, user_id="fixture-user")
    )
    await gate.release_when_blocked(task)
    result = await asyncio.wait_for(task, timeout=3.0)
    assert isinstance(result, list)  # বাংলা: fallback পথ সৎ []/ম্যাচ ফেরত দেয়


@pytest.mark.asyncio
async def test_save_memory_offloads_blocking_embedding(monkeypatch):
    """বাংলা মন্তব্য: save-চেইনের legacy Supabase path-ও thread-অফলোড মানে।"""
    import services.memory_service as ms

    gate = _Gate()

    def blocking_embed(text: str) -> list[float]:
        gate.block_until_released()
        return [0.0] * 384

    monkeypatch.setattr(ms, "get_embedding", blocking_embed)
    # বাংলা মন্তব্য: supabase-অনুপস্থিতিতে পথ সৎভাবে শেষ হয় — শুধু embedding-গেট যাচাই
    monkeypatch.setattr(ms, "_get_supabase", lambda: None)

    task = asyncio.create_task(
        ms.save_memory(session_id="s-offload", summary="offload probe", user_id="u1")
    )
    await gate.release_when_blocked(task)
    result = await asyncio.wait_for(task, timeout=3.0)
    assert isinstance(result, dict)


# ── 2. research_search — arXiv urlopen offload ────────────────────────────────


@pytest.mark.asyncio
async def test_research_search_offloads_blocking_urlopen(monkeypatch):
    """বাংলা মন্তব্য: arXiv urlopen (15s timeout) hang করলেও লুপ সাড়া দেয়।"""
    from core.agents.research_assistant import ResearchAssistant
    from core.api.routes.agents import ResearchRequest, research_search

    gate = _Gate()

    def blocking_search(self, query: str, source: str = "arxiv", max_results: int = 5):
        gate.block_until_released()
        return []

    monkeypatch.setattr(ResearchAssistant, "search", blocking_search)

    task = asyncio.create_task(research_search(ResearchRequest(query="quantum decoherence")))
    await gate.release_when_blocked(task)
    result = await asyncio.wait_for(task, timeout=3.0)
    # বাংলা মন্তব্য: রুট সৎ প্রতিক্রিয়া-শেপ {count, results, source} — ব্লক-মুক্ত সম্পন্নই চুক্তি
    assert isinstance(result, dict)
    assert result["count"] == 0
    assert result["source"] == "arxiv"


@pytest.mark.asyncio
async def test_research_search_error_contracts_preserved(monkeypatch):
    """বাংলা মন্তব্য: to_thread thread-exception re-raise করে — 400/502 চুক্তি অক্ষত।"""
    from core.agents.research_assistant import ResearchAssistant, ResearchSourceError
    from core.api.routes.agents import ResearchRequest, research_search

    def bad_query(self, query: str, source: str = "arxiv", max_results: int = 5):
        raise ValueError("query must not be empty")

    def upstream_down(self, query: str, source: str = "arxiv", max_results: int = 5):
        raise ResearchSourceError("arXiv API request failed: connection refused")

    from fastapi import HTTPException

    monkeypatch.setattr(ResearchAssistant, "search", bad_query)
    with pytest.raises(HTTPException) as err400:
        await research_search(ResearchRequest(query="   "))
    assert err400.value.status_code == 400

    monkeypatch.setattr(ResearchAssistant, "search", upstream_down)
    with pytest.raises(HTTPException) as err502:
        await research_search(ResearchRequest(query="valid query"))
    assert err502.value.status_code == 502
    assert "connection refused" in err502.value.detail
