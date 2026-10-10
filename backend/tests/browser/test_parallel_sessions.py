# backend/tests/browser/test_parallel_sessions.py
"""ব্রাউজার সেশন সমান্তরালতা টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-3 (Phase 3)।

পরিকল্পনার প্রশ্ন: "একাধিক ইউজার একই সময়ে ব্রাউজার অটোমেশন চালালে
সার্ভারের রিসোর্স ম্যানেজমেন্ট" — আগে কোনো parallel multi-session টেস্ট
ছিল না (শুধু single-session মক টেস্ট)।

দুই স্তর:
- CI-safe (এই ফাইল, `performance` marker): আসল BrowserSessionManager +
  আসল asyncio.Semaphore, ফেক browser factory — PR/nightly ফুল-স্যুইটে চলে;
- আসল chromium (e2e marker): test_session_rss_guard.py ও
  test_vision_cascade_e2e.py — nightly e2e job-এ চলে।
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.browser_session_manager import BrowserSessionManager

pytestmark = pytest.mark.performance


class _FakeBrowserFactory:
    """আসল browser প্রতিস্থাপনকারী ফ্যাক্টরি — সমান্তরালতা গণনা করে।"""

    def __init__(self) -> None:
        self.active_contexts = 0
        self.max_observed_contexts = 0
        self.total_created = 0
        self.fail_new_page = False

    def make_get_global_browser(self) -> Any:
        factory = self

        async def _get_global_browser() -> Any:
            browser = MagicMock()

            async def _new_context(**_kwargs: Any) -> Any:
                factory.active_contexts += 1
                factory.max_observed_contexts = max(
                    factory.max_observed_contexts, factory.active_contexts
                )
                factory.total_created += 1
                context = MagicMock()

                async def _new_page() -> Any:
                    if factory.fail_new_page:
                        raise RuntimeError("simulated page launch failure")
                    return MagicMock()

                context.new_page = AsyncMock(side_effect=_new_page)

                async def _close() -> None:
                    factory.active_contexts -= 1

                context.close = AsyncMock(side_effect=_close)
                return context

            browser.new_context = AsyncMock(side_effect=_new_context)
            return browser

        return _get_global_browser


@pytest.fixture()
def wired_manager(monkeypatch):
    """ফেক browser factory-তে সংযুক্ত manager (max_sessions=2)।"""
    factory = _FakeBrowserFactory()
    monkeypatch.setattr(
        "core.browser_session_manager.get_global_browser",
        factory.make_get_global_browser(),
    )
    manager = BrowserSessionManager(max_sessions=2, idle_timeout_seconds=60)
    return manager, factory


class TestSessionSlotSaturation:
    async def test_concurrent_creates_bounded_by_max_sessions(self, wired_manager):
        """Given: max_sessions=2 এবং ৫টি সমান্তরাল create।
        When: সবাই একসাথে সেশন চাইলে।
        Then: কখনোই একসাথে ২টির বেশি browser context চালু হয় না —
        Render free-tier RAM-এ অসীম ব্রাউজার স্পন রোধ।
        """
        manager, factory = wired_manager

        async def _create_and_hold(owner: str, hold: float) -> None:
            session = await manager.create(owner_id=owner)
            await asyncio.sleep(hold)
            await manager.close(session.id, owner)

        await asyncio.gather(*(_create_and_hold(f"owner-{i}", 0.05) for i in range(5)))

        assert factory.max_observed_contexts <= 2, (
            f"সেশন-স্লট সীমা ভাঙা হয়েছে: {factory.max_observed_contexts} > 2"
        )
        assert factory.active_contexts == 0, "সব context বন্ধ হয়নি (লিক)"
        assert factory.total_created == 5

    async def test_waiting_session_proceeds_after_close(self, wired_manager):
        """Given: ২টি স্লট দখলে, ৩ম ব্যবহারকারী অপেক্ষমাণ।
        When: একটি সেশন বন্ধ হলে।
        Then: অপেক্ষমাণ ব্যবহারকারীর সেশন তৈরি হয় — deadlock নেই।
        """
        manager, _ = wired_manager
        s1 = await manager.create(owner_id="u1")
        s2 = await manager.create(owner_id="u2")

        async def _third() -> Any:
            return await manager.create(owner_id="u3")

        task = asyncio.create_task(_third())
        await asyncio.sleep(0.05)
        assert not task.done(), "স্লট খালি হওয়ার আগেই ৩য় সেশন — সন্দেহজনক"

        await manager.close(s1.id, "u1")
        s3 = await asyncio.wait_for(task, timeout=2.0)
        await manager.close(s2.id, "u2")
        await manager.close(s3.id, "u3")

    async def test_failed_context_creation_releases_slot(self, wired_manager, monkeypatch):
        """Given: new_page ব্যর্থ হচ্ছে (ব্রাউজার রিসোর্স চাপ)।
        When: create() exception দিলে।
        Then: স্লট ফিরে যায় — ব্যর্থতায় স্লট-লিক নেই, পরের ব্যবহারকারী ঢোকে।
        """
        manager, factory = wired_manager
        factory.fail_new_page = True

        with pytest.raises(RuntimeError, match="page launch failure"):
            await manager.create(owner_id="victim")

        # ব্যর্থতার পরে স্লট খালি — নতুন চেষ্টা সফল
        factory.fail_new_page = False
        session = await asyncio.wait_for(manager.create(owner_id="next"), timeout=2.0)
        await manager.close(session.id, "next")

    async def test_shutdown_closes_all_sessions(self, wired_manager):
        """Given: ২টি সক্রিয় সেশন।
        When: shutdown() ডাকা হলে।
        Then: সব context বন্ধ + সব স্লট মুক্ত — জম্বি সেশন নেই।
        """
        manager, factory = wired_manager
        await manager.create(owner_id="a")
        await manager.create(owner_id="b")

        await manager.shutdown()

        assert factory.active_contexts == 0
        # shutdown-এর পরেও নতুন সেশন নেওয়া যায় (fresh slots)
        session = await asyncio.wait_for(manager.create(owner_id="c"), timeout=2.0)
        await manager.close(session.id, "c")

    async def test_paused_owner_rejected_before_slot_consumed(self, wired_manager):
        """Given: paused মালিক।
        When: সেশন চাইলে।
        Then: PermissionError — এবং স্লট খরচ হয় না।
        """
        manager, factory = wired_manager
        manager.pause_owner("banned-user")

        with pytest.raises(PermissionError, match="paused"):
            await manager.create(owner_id="banned-user")

        assert factory.total_created == 0, "paused মালিকের জন্য context তৈরি হয়েছে!"
