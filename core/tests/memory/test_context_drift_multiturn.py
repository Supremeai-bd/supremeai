# backend/tests/memory/test_context_drift_multiturn.py
"""১২+ টার্নের কনটেক্সট-ড্রিফট টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-2 (Phase 2)।

পরিকল্পনার প্রশ্ন: "১০+ টার্ন চ্যাটের পর মূল টাস্ক ভুলে যাওয়া বা ফেক
আউটপুট রোধ" — আগে রিপোর দীর্ঘতম কথোপকথন-ফ্লো টেস্ট ছিল ৩ মেসেজ।

যাচাইকৃত আচরণ:
- ১২ টার্নের পরেও টার্ন-১-এর মূল টাস্ক recall-এ অক্ষত (ভুলে যায়নি);
- recall-এ ঠিক ১২টি এন্ট্রিই — কোনো ফেক/বানানো এন্ট্রি নেই;
- ৫৫ টার্ন (compaction threshold ৫০ পেরিয়ে) — hierarchical compaction
  মূল টাস্ককে compact summary-তে বাঁচিয়ে রাখে;
- long-term facade ১২ টার্ন জুড়ে প্রতিটি টার্ন backend-এ পাঠায়।

CI-safe: tmp sqlite ফাইল + ফেক long-term backend — কোনো LLM/নেটওয়ার্ক নেই।
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from core.unified_memory import UnifiedMemoryInterface
from core.memory.sliding_window import SlidingWindowMemory

pytestmark = [pytest.mark.memory, pytest.mark.important]

CORE_TASK = "CORE TASK: book a round-trip flight to Dhaka departing Friday morning, window seat"


class _FakeLongTermMemory:
    """কল-রেকর্ডিং ফেক long-term backend।"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.store_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []

    def store_memory(self, **kwargs: Any) -> bool:
        with self._lock:
            self.store_calls.append(kwargs)
        return True

    def query_context(self, **kwargs: Any) -> list[dict[str, Any]]:
        with self._lock:
            self.query_calls.append(kwargs)
        return [{"text": "dhaka flight", "score": 0.9}]


def _make_facade(tmp_path) -> tuple[UnifiedMemoryInterface, _FakeLongTermMemory]:
    facade = UnifiedMemoryInterface()
    fake = _FakeLongTermMemory()
    facade.long_term_memory = fake
    facade.short_term_memory = SlidingWindowMemory(db_path=str(tmp_path / "drift.db"))
    return facade, fake


def _filler_turns(count: int, start: int = 2) -> list[str]:
    """টার্ন-১-এর পরের ফিলার টার্নগুলো — মূল টাস্ক থেকে মনোযোগ সরানো।"""
    return [
        f"turn {i}: unrelated discussion about topic-{i}, "
        f"weather, lunch plans, and a long digression number {i}"
        for i in range(start, start + count)
    ]


class TestTwelveTurnNoDrift:
    def test_core_task_survives_12_turns(self, tmp_path):
        """Given: টার্ন-১-এ মূল টাস্ক, তারপর ১১টি ফিলার টার্ন।
        When: ১২ টার্ন শেষে recall(20) করা হলে।
        Then: মূল টাস্ক অক্ষত উপস্থিত — ১২ টার্নে ভুলে যায়নি।
        """
        facade, _ = _make_facade(tmp_path)
        session = "drift-12"
        all_turns = [CORE_TASK] + _filler_turns(11)
        for turn in all_turns:
            assert facade.store_short_term_memory(session, turn) is True

        recalled = facade.get_short_term_memory(session, limit=20)
        assert len(recalled) == 12, f"১২ এন্ট্রির কথা, পাওয়া গেল {len(recalled)}"
        assert any(CORE_TASK in entry.get("text", "") for entry in recalled), (
            "মূল টাস্ক ১২ টার্নে হারিয়ে গেছে — context drift!"
        )

    def test_no_fabricated_entries_after_12_turns(self, tmp_path):
        """Given: ঠিক ১২টি নির্দিষ্ট টার্ন সংরক্ষিত।
        When: recall করা হলে।
        Then: প্রতিটি recalled টেক্সট সংরক্ষিত টার্নগুলোর একটির অংশ —
        কোনো বানানো/হ্যালুসিনেটেড এন্ট্রি নেই।
        """
        facade, _ = _make_facade(tmp_path)
        session = "drift-fabrication"
        all_turns = [CORE_TASK] + _filler_turns(11)
        for turn in all_turns:
            facade.store_short_term_memory(session, turn)

        recalled = facade.get_short_term_memory(session, limit=20)
        for entry in recalled:
            text = entry.get("text", "")
            assert any(text in turn or turn in text for turn in all_turns), (
                f"সংরক্ষিত কোনো টার্নের সাথে মেলে না (ফেক এন্ট্রি?): {text[:80]!r}"
            )

    def test_recall_is_newest_first(self, tmp_path):
        """Given: ক্রমানুসারে ১২ টার্ন।
        When: recall করা হলে।
        Then: নতুন টার্ন আগে আসে (created_at DESC) — ক্রম-চুক্তি অক্ষত।
        """
        facade, _ = _make_facade(tmp_path)
        session = "drift-order"
        all_turns = [CORE_TASK] + _filler_turns(11)
        for turn in all_turns:
            facade.store_short_term_memory(session, turn)
            # created_at আলাদা করতে সামান্য বিরতি নিশ্চিত করা কঠিন —
            # তাই শেষ টার্ন প্রথম এন্ট্রিতে থাকা যাচাই (নতুনতম-প্রথম অন্তত)
        recalled = facade.get_short_term_memory(session, limit=20)
        last_turn = all_turns[-1]
        assert last_turn in recalled[0].get("text", ""), (
            f"নতুনতম টার্ন প্রথমে নেই: {recalled[0].get('text', '')[:80]!r}"
        )

    def test_long_term_backend_receives_every_turn(self, tmp_path):
        """Given: প্রতিটি টার্ন short-term + long-term উভয়ে যাচ্ছে।
        When: ১২ টার্ন + শেষে একটি query।
        Then: ১২টি long-term store + ১টি query — facade প্লাম্বিং পূর্ণ।
        """
        facade, fake = _make_facade(tmp_path)
        session_id = "drift-plumbing"
        all_turns = [CORE_TASK] + _filler_turns(11)
        for i, turn in enumerate(all_turns):
            facade.store_long_term_memory(session_id, "drift_test", "conversation", turn)
        result = facade.query_long_term_memory("dhaka flight", top_k=5, session_id=session_id)

        assert len(fake.store_calls) == 12
        assert len(fake.query_calls) == 1
        assert result == [{"text": "dhaka flight", "score": 0.9}]


class TestCompactionPreservesCoreTask:
    def test_55_turns_compact_summary_keeps_core_task(self, tmp_path):
        """Given: ৫৫টি টার্ন (compaction threshold ৫০-এর উপরে), টার্ন-১-এ মূল টাস্ক।
        When: hierarchical compaction চালু হলে।
        Then: compact summary-তে মূল টাস্কের মূল শব্দ বাঁচে —
        দীর্ঘ কথোপকথনেও ভুলে যাওয়া রোধ।
        """
        facade, _ = _make_facade(tmp_path)
        session = "drift-55"
        all_turns = [CORE_TASK] + _filler_turns(54)
        for turn in all_turns:
            facade.store_short_term_memory(session, turn)

        summaries = facade.short_term_memory.get_compact_summaries(session)
        assert summaries, "৫০+ উইন্ডো পেরিয়েও compaction হয়নি — কনফিগ ভাঙছে"
        combined = " ".join(s.get("summary", "") for s in summaries)
        assert "dhaka" in combined.lower() or "flight" in combined.lower(), (
            f"compact summary-তে মূল টাস্ক নেই: {combined[:200]!r}"
        )

    def test_compaction_happens_only_after_threshold(self, tmp_path):
        """Given: threshold (৫০)-এর নিচে ১২টি টার্ন।
        When: compaction পরীক্ষা করলে।
        Then: অকাল compaction নেই — ছোট সেশন অকারণে summary করে না।
        """
        facade, _ = _make_facade(tmp_path)
        session = "drift-small"
        for turn in [CORE_TASK] + _filler_turns(11):
            facade.store_short_term_memory(session, turn)

        summaries = facade.short_term_memory.get_compact_summaries(session)
        assert summaries == [], f"১২ টার্নেই অকাল compaction: {summaries}"
