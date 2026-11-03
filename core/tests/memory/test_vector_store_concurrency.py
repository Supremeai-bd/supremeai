# backend/tests/memory/test_vector_store_concurrency.py
"""ChromaDBStore fallback-মোড কনকারেন্সি টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-1।

পরিকল্পনার প্রশ্ন: "ভেক্টর স্টোরে (ChromaDB) প্যারালাল অ্যাক্সেস" — এই টেস্ট
fallback TF-IDF মোডে (chromadb ক্লায়েন্ট ছাড়া) সমান্তরাল add/query/delete
চালিয়ে _fallback_lock (Tier-1 race-fix) কাজ করছে কি না যাচাই করে।

রেস-ফিক্সের প্রমাণ: লক না থাকলে query()-র iteration চলাকালীন অন্য থ্রেডের
add/delete "dictionary changed size during iteration" ক্র্যাশ করত।
CI-safe: কোনো chromadb/নেটওয়ার্ক নেই — _CHROMA_AVAILABLE জোর করে False।
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

import memory.chromadb_store as cs
from core.memory.chromadb_store import ChromaDBStore

pytestmark = [pytest.mark.memory, pytest.mark.performance]


@pytest.fixture()
def fallback_store(tmp_path, monkeypatch) -> ChromaDBStore:
    """Fallback-মোডে forced store — chromadb ক্লায়েন্ট সচেতনভাবে বন্ধ।"""
    monkeypatch.setattr(cs, "_CHROMA_AVAILABLE", False)
    return ChromaDBStore(db_path=str(tmp_path / "vecstore"))


class TestFallbackConcurrentAccess:
    def test_parallel_adds_all_lands(self, fallback_store: ChromaDBStore):
        """Given: ২০টি থ্রেড একসাথে আলাদা doc যোগ করছে।
        When: সব থ্রেড শেষ হলে।
        Then: ২০টি doc-ই স্টোরে আছে — কোনো রাইট হারায়নি।
        """

        def _add(i: int) -> None:
            fallback_store.add_document(
                doc_id=f"doc-{i:02d}",
                text=f"vector probe document number {i} unique tokens alpha{i}",
                metadata={"seq": i},
            )

        threads = [threading.Thread(target=_add, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert fallback_store.count() == 20, f"রাইট হারিয়েছে: ২০টির বদলে {fallback_store.count()}টি"

    def test_query_during_concurrent_adds_never_crashes(self, fallback_store: ChromaDBStore):
        """Given: এক থ্রেড টানা query করছে, আর ১৫টি থ্রেড টানা doc যোগ করছে।
        When: একই সময়ে চললে (আগে এখানে iteration-race ক্র্যাশ হতো)।
        Then: কোনো exception নেই — _fallback_lock snapshot-iteration কাজ করছে।
        """
        errors: list[Exception] = []

        def _writer(i: int) -> None:
            try:
                for j in range(5):
                    fallback_store.add_document(
                        doc_id=f"race-{i}-{j}",
                        text=f"race doc {i} {j} tokens beta{i}{j}",
                    )
            except Exception as e:  # pragma: no cover - ব্যর্থতা রেকর্ড
                errors.append(e)

        def _reader(stop: threading.Event) -> None:
            try:
                while not stop.is_set():
                    fallback_store.query("race doc tokens", n_results=3)
            except Exception as e:  # pragma: no cover - ব্যর্থতা রেকর্ড
                errors.append(e)

        stop = threading.Event()
        reader = threading.Thread(target=_reader, args=(stop,))
        reader.start()
        writers = [threading.Thread(target=_writer, args=(i,)) for i in range(15)]
        for t in writers:
            t.start()
        for t in writers:
            t.join(timeout=10)
        stop.set()
        reader.join(timeout=10)

        assert not errors, f"কনকারেন্ট অ্যাক্সেসে ক্র্যাশ: {errors[:3]}"
        assert fallback_store.count() == 75, f"কিছু রাইট হারিয়েছে: {fallback_store.count()}"

    def test_concurrent_delete_and_query_never_crashes(self, fallback_store: ChromaDBStore):
        """Given: পুরনো docs আছে; এক থ্রেড delete করছে, আরেকটি query করছে।
        When: একই সময়ে চললে।
        Then: কোনো exception নেই — delete-ও লক-সুরক্ষিত।
        """
        for i in range(30):
            fallback_store.add_document(doc_id=f"del-{i:02d}", text=f"deletable doc {i} gamma{i}")
        errors: list[Exception] = []

        def _deleter() -> None:
            try:
                for i in range(30):
                    fallback_store.delete(f"del-{i:02d}")
            except Exception as e:  # pragma: no cover
                errors.append(e)

        def _querier(stop: threading.Event) -> None:
            try:
                while not stop.is_set():
                    fallback_store.query("deletable doc", n_results=3)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        stop = threading.Event()
        querier = threading.Thread(target=_querier, args=(stop,))
        querier.start()
        deleter = threading.Thread(target=_deleter)
        deleter.start()
        deleter.join(timeout=10)
        stop.set()
        querier.join(timeout=10)

        assert not errors, f"delete/query রেস ক্র্যাশ: {errors[:3]}"
        assert fallback_store.count() == 0

    def test_query_returns_relevant_docs_under_contention(self, fallback_store: ChromaDBStore):
        """Given: মিশ্র docs এবং সমান্তরাল রাইটাররা।
        When: query করলে।
        Then: ফলাফল এখনও অর্থবহ — সবচেয়ে মিলযুক্ত doc শীর্ষে থাকে।
        """
        fallback_store.add_document(doc_id="target", text="kubernetes pod eviction policy details")
        fallback_store.add_document(doc_id="noise", text="cooking pasta recipes olive oil")

        def _add_noise(i: int) -> None:
            fallback_store.add_document(doc_id=f"noise-{i}", text=f"unrelated noise {i}")

        threads = [threading.Thread(target=_add_noise, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        results = fallback_store.query("kubernetes pod eviction", n_results=3)
        assert results, "ফলাফল ফাঁকা"
        assert results[0][0] == "target", f"শীর্ষ ফলাফল ভুল: {results[0][0]}"

    def test_parallel_distinct_doc_ids_no_lost_writes(self, fallback_store: ChromaDBStore):
        """Given: ৫০টি সমান্তরাল add_documents ব্যাচ-কল।
        When: সবাই শেষ হলে।
        Then: ৫০টি ডকুমেন্টই গণনায় আসে।
        """
        errors: list[Any] = []

        def _batch(i: int) -> None:
            try:
                fallback_store.add_documents(
                    [{"id": f"batch-{i:02d}", "text": f"batch content {i} delta{i}"}]
                )
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=_batch, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors
        assert fallback_store.count() == 50
