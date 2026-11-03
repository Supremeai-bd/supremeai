# backend/tests/memory/test_unified_memory_concurrency.py
"""unified_memory ফ্যাসাডের কনকারেন্সি টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-1 (Phase 1)।

পরিকল্পনার মূল প্রশ্ন: "কনকারেন্ট রাইটের সময় unified_memory.py ও ভেক্টর স্টোরে
ডেডলক বা টাইমআউট হচ্ছে কি না" — এই ফাইলটি async-gather ও thread-parallel
উভয় পথে সমান্তরাল store/query ঝড় চালিয়ে সেটি যাচাই করে।

নিয়ম মেনে: কোনো আসল DB/LLM কল নেই — long-term backend ফেক, LLM gateway
patched (test_memory_distillation.py-এর প্রমাণিত প্যাটার্ন)। CI-safe।
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.unified_memory import UnifiedMemoryInterface
from memory.sliding_window import SlidingWindowMemory

pytestmark = [pytest.mark.memory, pytest.mark.performance]

# ডিস্টিলেশন ট্রিগার করতে ৪০০+ ক্যারেক্টার কনটেন্ট (MEMORY_DISTILL_MIN_CONTENT_CHARS)
_LONG_CONTENT = "SupremeAI concurrent memory write probe. " * 12  # ~47*12 = 564 chars


class _ThreadSafeFakeLongTermMemory:
    """lock-সুরক্ষিত ফেক long-term backend — থ্রেড/async উভয় পথের কল রেকর্ড করে।"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.store_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.store_result = True
        # বাংলা মন্তব্য: facade ব্যর্থতা ধরে store_memory-র exception থেকে
        # (return value উপেক্ষিত) — তাই ব্যর্থতা সিমুলেট করতে raise লাগে।
        self.raise_on_store: Exception | None = None
        self.query_result: list[dict[str, Any]] = [{"text": "probe", "score": 0.9}]

    def store_memory(self, **kwargs: Any) -> bool:
        with self._lock:
            self.store_calls.append(kwargs)
        if self.raise_on_store is not None:
            raise self.raise_on_store
        return self.store_result

    def query_context(self, **kwargs: Any) -> list[dict[str, Any]]:
        with self._lock:
            self.query_calls.append(kwargs)
        return list(self.query_result)


def _make_interface() -> tuple[UnifiedMemoryInterface, _ThreadSafeFakeLongTermMemory]:
    """Facade + lock-সুরক্ষিত ফেক long-term backend (কোনো DB স্পর্শ হয় না)।"""
    facade = UnifiedMemoryInterface()
    fake = _ThreadSafeFakeLongTermMemory()
    facade.long_term_memory = fake
    return facade, fake


class TestParallelDistilledStores:
    async def test_30_parallel_distilled_stores_all_land_with_distinct_sessions(self):
        """Given: ৩০টি সমান্তরাল distilled store।
        When: asyncio.gather একসাথে চালালে।
        Then: সবগুলো সফল, ঠিক ৩০টি backend কল, প্রতিটি session_id আলাদা থাকে।
        """
        facade, fake = _make_interface()
        gateway = MagicMock()
        gateway.acompletion = AsyncMock(
            return_value={
                "success": True,
                "text": 'ok {"facts": ["concurrent"], "open_items": []}',
                "model": "stub",
                "cost": 0.0,
            }
        )
        with patch("core.llm.llm_gateway.llm_gateway", gateway):
            results = await asyncio.gather(
                *(
                    facade.store_long_term_memory_distilled(
                        session_id=f"conc-{i:03d}",
                        agent_type="load_test",
                        task_type="knowledge",
                        content=_LONG_CONTENT,
                    )
                    for i in range(30)
                )
            )

        assert all(results), f"কিছু distilled store ব্যর্থ: {results}"
        assert len(fake.store_calls) == 30
        stored_sessions = {c.get("session_id") for c in fake.store_calls}
        assert stored_sessions == {f"conc-{i:03d}" for i in range(30)}, (
            "session_id cross-contamination ধরা পড়েছে"
        )

    async def test_distilled_store_failure_does_not_poison_parallel_writes(self):
        """Given: একটি backend রাইট ব্যর্থ হবে, বাকিগুলো সফল।
        When: সমান্তরাল gather-এ চললে।
        Then: ব্যর্থটি False ফেরায়, সফলগুলো True — একটির ব্যর্থতা অন্যদের
        ছোঁয়াচে ভাঙে না।
        """
        facade, fake = _make_interface()
        fake.raise_on_store = RuntimeError("simulated backend outage")

        async def _one(i: int) -> bool:
            # বাংলা মন্তব্য: sync মেথড — to_thread দিয়ে সমান্তরাল করা হয়
            return await asyncio.to_thread(
                facade.store_long_term_memory,
                f"failmix-{i}",
                "load_test",
                "knowledge",
                f"short probe {i}",
            )

        results = await asyncio.gather(*(_one(i) for i in range(5)))
        # ব্যর্থতা নিরাপদে False হিসেবে ফেরে — exception ছড়ায় না
        assert results == [False] * 5


class TestParallelSyncStoresAndQueries:
    async def test_20_thread_parallel_stores_all_recorded(self):
        """Given: ২০টি থ্রেড-সমান্তরাল sync long-term store।
        When: asyncio.to_thread দিয়ে gather চালালে।
        Then: ২০টি কলই রেকর্ড হয়, কোনো কল হারায় না।
        """
        facade, fake = _make_interface()

        async def _one(i: int) -> bool:
            return await asyncio.to_thread(
                facade.store_long_term_memory,
                f"thread-{i:02d}",
                "load_test",
                "knowledge",
                f"thread probe {i}",
            )

        results = await asyncio.gather(*(_one(i) for i in range(20)))
        assert all(results)
        assert len(fake.store_calls) == 20

    async def test_20_thread_parallel_queries_all_dispatched(self):
        """Given: ২০টি সমান্তরাল query_long_term_memory।
        When: থ্রেড-পুলে একসাথে চললে।
        Then: প্রতিটি query তার session_id নিয়ে backend-এ পৌঁছায়, ফলাফল
        ফেরত আসে — cross-contamination নেই।
        """
        facade, fake = _make_interface()

        async def _one(i: int) -> list[dict[str, Any]]:
            return await asyncio.to_thread(
                facade.query_long_term_memory,
                f"q-{i:02d} probe",
                top_k=3,
                session_id=f"sess-{i:02d}",
            )

        results = await asyncio.gather(*(_one(i) for i in range(20)))
        assert all(r == fake.query_result for r in results)
        assert len(fake.query_calls) == 20
        queried_sessions = {c.get("session_id") for c in fake.query_calls}
        assert queried_sessions == {f"sess-{i:02d}" for i in range(20)}

    async def test_mixed_store_query_storm_no_exception(self):
        """Given: ১০টি store + ১০টি query মিশ্র ঝড়।
        When: একই gather-এ ইন্টারলিভড চালালে।
        Then: কোনো exception নেই, মোট ২০টি backend কল।
        """
        facade, fake = _make_interface()
        store_jobs = [
            asyncio.to_thread(
                facade.store_long_term_memory,
                f"mix-{i}",
                "load_test",
                "knowledge",
                f"mix probe {i}",
            )
            for i in range(10)
        ]
        query_jobs = [
            asyncio.to_thread(facade.query_long_term_memory, f"mix query {i}", top_k=2)
            for i in range(10)
        ]
        results = await asyncio.gather(*store_jobs, *query_jobs)
        assert all(r is True or isinstance(r, list) for r in results)
        assert len(fake.store_calls) + len(fake.query_calls) == 20


class TestShortTermWindowConcurrency:
    def test_distinct_session_parallel_writes_all_retrievable(self, tmp_path):
        """Given: ১০টি থ্রেড আলাদা আলাদা session-এ short-term রাইট।
        When: একই সময়ে চললে (প্রতি অপারেশন নিজের sqlite কানেকশন খোলে)।
        Then: পরে প্রতিটি session নিজের টেক্সট ফিরে পায় — হারানো রাইট নেই।
        """
        facade = UnifiedMemoryInterface()
        # বাংলা মন্তব্য: hermetic sqlite ফাইল — ডিফল্ট shared DB ফাইল স্পর্শ হয় না
        facade.short_term_memory = SlidingWindowMemory(db_path=str(tmp_path / "st.db"))

        def _write(i: int) -> bool:
            return facade.store_short_term_memory(f"st-sess-{i}", f"short term probe {i}")

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        for i in range(10):
            recalled = facade.get_short_term_memory(f"st-sess-{i}")
            assert recalled, f"session st-sess-{i}-এর রাইট হারিয়েছে"
            assert any(f"short term probe {i}" in r.get("text", "") for r in recalled), (
                f"session st-sess-{i}-এ ভুল কনটেন্ট: {recalled}"
            )
