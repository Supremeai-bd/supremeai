# backend/tests/core/test_pgbouncer_exhaustion.py
"""PgBouncer pool saturation টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-1 (Phase 1)।

পরিকল্পনার মূল প্রশ্ন: "pgbouncer_pool.py এবং Supabase কানেকশন এক্সহস্ট
হচ্ছে কি না মাপা" — আগে শুধু mock-only ইউনিট টেস্ট ছিল
(test_pgbouncer_pool.py)। এই ফাইলটি আসল asyncpg লাইব্রেরি ছাড়াই
(pure-asyncio) আসল saturation সিম্যান্টিক্স যাচাই করে:

- সীমিত স্লটে (max_size=2) ৬টি সমান্তরাল acquire → সর্বোচ্চ ২টি একসাথে
  ব্যবহৃত হয়, release হলে অপেক্ষমাণরা ঢোকে;
- context manager exception-এও slot ফিরে পায় (লিক নেই);
- get_db_pool_with_retry ব্যাক-অফ দিয়ে রিট্রাই করে।

আসল Supabase-বিরুদ্ধে রানের জন্য দেখুন tests/cloud_db_load_test.py
(আসল টার্গেট কনফিগার থাকলে আসল মাপ)। CI-safe: কোনো নেটওয়ার্ক নেই।
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

import database.pgbouncer_pool as pool_mod
from database.pgbouncer_pool import PgBouncerConnectionPool

pytestmark = pytest.mark.performance


class _FakeAsyncpgPool:
    """আসল asyncpg.Pool-এর সিম্যান্টিক নকল — bounded asyncio.Semaphore দিয়ে।

    বাংলা মন্তব্য: এটি mock নয় বরং contract-double — acquire/release-এর
    bounded-ness আসলেই asyncpg-এর মতো আচরণ করে (max_size-এর বাইরে
    acquire অপেক্ষা করে)।
    """

    def __init__(self, max_size: int = 2) -> None:
        self._sem = asyncio.Semaphore(max_size)
        self.max_size = max_size
        self.in_use = 0
        self.max_observed_in_use = 0
        self.closed = False

    async def acquire(self) -> SimpleNamespace:
        await self._sem.acquire()
        self.in_use += 1
        self.max_observed_in_use = max(self.max_observed_in_use, self.in_use)
        return SimpleNamespace(pool=self)

    async def release(self, _conn: SimpleNamespace) -> None:
        self.in_use -= 1
        self._sem.release()

    async def close(self) -> None:
        self.closed = True


def _make_pool(max_size: int = 2) -> tuple[PgBouncerConnectionPool, _FakeAsyncpgPool]:
    wrapper = PgBouncerConnectionPool("postgresql://fake:5432/fake")
    fake = _FakeAsyncpgPool(max_size=max_size)
    wrapper._pool = fake  # type: ignore[assignment] -- টেস্ট সিম
    return wrapper, fake


class TestPoolSaturation:
    async def test_concurrent_acquires_bounded_by_max_size(self):
        """Given: max_size=2 পুল এবং ৬টি সমান্তরাল acquire যেগুলো কিছুক্ষণ ধরে রাখে।
        When: একসাথে চালানো হলে।
        Then: কখনোই একসাথে ২টির বেশি কানেকশন ব্যবহৃত হয় না (saturation মানা হয়)।
        """
        wrapper, fake = _make_pool(max_size=2)

        async def _hold_then_release(delay: float) -> None:
            conn = await wrapper.acquire()
            await asyncio.sleep(delay)
            await wrapper.release(conn)

        await asyncio.gather(*(_hold_then_release(0.02) for _ in range(6)))

        assert fake.max_observed_in_use <= 2, f"pool limit ভাঙা হয়েছে: {fake.max_observed_in_use} > 2"
        assert fake.in_use == 0, "সব কানেকশন ফেরত পাওয়া যায়নি (লিক)"

    async def test_waiting_acquires_proceed_after_release(self):
        """Given: ২টি স্লট দখলে, ৩ম একটি acquire অপেক্ষমাণ।
        When: একটি স্লট release হলে।
        Then: অপেক্ষমাণ acquire প্রায় সাথে সাথে সফল হয়।
        """
        wrapper, _fake = _make_pool(max_size=2)
        conn1 = await wrapper.acquire()
        conn2 = await wrapper.acquire()

        async def _third() -> bool:
            conn3 = await wrapper.acquire()
            await wrapper.release(conn3)
            return True

        task = asyncio.create_task(_third())
        await asyncio.sleep(0.05)
        assert not task.done(), "৩য় acquire স্লট খালি হওয়ার আগেই সফল হয়েছে — সন্দেহজনক"
        await wrapper.release(conn1)
        assert await asyncio.wait_for(task, timeout=1.0), "release-এর পরেও ৩য় acquire আটকে আছে"
        await wrapper.release(conn2)

    async def test_connection_context_manager_releases_on_exception(self):
        """Given: connection() context manager-এর ভেতরে ব্যতিক্রম।
        When: exception ছড়ালে।
        Then: slot finally-তে ফিরে যায় — ব্যর্থ অপারেশনে কানেকশন লিক হয় না।
        """
        wrapper, fake = _make_pool(max_size=1)

        with pytest.raises(RuntimeError, match="boom"):
            async with wrapper.connection():
                raise RuntimeError("boom")

        assert fake.in_use == 0, "exception-পথে কানেকশন লিক হয়েছে"
        # পরের acquire আর অপেক্ষা করে না
        conn = await asyncio.wait_for(wrapper.acquire(), timeout=1.0)
        await wrapper.release(conn)


class TestPoolContractGuards:
    async def test_acquire_before_connect_raises_runtime_error(self):
        """Given: connect() ছাড়া তৈরি wrapper।
        When: acquire() ডাকা হলে।
        Then: স্পষ্ট RuntimeError — নীরবে None নয়।
        """
        wrapper = PgBouncerConnectionPool("postgresql://fake:5432/fake")
        with pytest.raises(RuntimeError, match="not initialized"):
            await wrapper.acquire()

    async def test_get_db_pool_with_retry_recovers_after_init(self, monkeypatch):
        """Given: singleton অজুহাতে অনুপস্থিত।
        When: get_db_pool_with_retry চলছে এবং মাঝপথে singleton সেট হয়।
        Then: ব্যাক-অফ রিট্রাই-এর পর পুল ফেরত পায় (initial_delay ছোট করা)।
        """
        monkeypatch.setattr(pool_mod, "_db_pool_instance", None)
        wrapper = PgBouncerConnectionPool("postgresql://fake:5432/fake")
        monkeypatch.setattr(pool_mod, "_pool_lock", asyncio.Lock())  # নতুন লুপে পুরনো লক বাঁধা থাকতে পারে

        async def _init_late() -> None:
            await asyncio.sleep(0.05)
            monkeypatch.setattr(pool_mod, "_db_pool_instance", wrapper)

        init_task = asyncio.create_task(_init_late())
        pool = await pool_mod.get_db_pool_with_retry(max_retries=5, initial_delay=0.02)
        await init_task
        assert pool is wrapper

    async def test_close_resets_pool_state(self):
        """Given: সংযুক্ত ফেক পুল।
        When: close() ডাকা হলে।
        Then: ভেতরের পুল বন্ধ হয় এবং রেফারেন্স খালি হয়।
        """
        wrapper, fake = _make_pool(max_size=1)
        await wrapper.close()
        assert fake.closed, "ভেতরের পুল বন্ধ হয়নি"
        assert wrapper._pool is None  # type: ignore[truthy-function]
