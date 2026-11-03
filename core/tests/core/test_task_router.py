"""MESH-6 (issue #926) — TaskRouter core unit tests.

বাংলা সারসংক্ষেপ:
------------------
Tower-native Task Queue-র core contract যাচাই:
CAS atomic claim, lease/heartbeat renewal, Zero Zombie reap (failover),
retry/failed lifecycle, role/capability matching, queue visibility।

কোনো fake/mock নেই — আসল TaskRouter (in-memory mode, Redis ছাড়া) দিয়ে।
asyncio_mode = "auto" (pyproject) — async test সরাসরি চলে।
"""

from __future__ import annotations

import asyncio
import unittest

from core.task_router import (
    TaskRouter,
    reset_task_router_for_tests,
)


class TaskRouterCoreTest(unittest.TestCase):
    """TaskRouter-এর ব্যাপক behavior contract।"""

    def setUp(self) -> None:
        self.router = TaskRouter(lease_seconds=600, max_active_per_node=2)

    def tearDown(self) -> None:
        reset_task_router_for_tests()

    # ── submit ───────────────────────────────────────────────────────────────
    async def test_submit_creates_pending_task(self) -> None:
        rec = await self.router.submit_task(
            task_type="pytest",
            title="run core tests",
            payload={"test_path": "tests/core"},
            required_capabilities=["pytest"],
        )
        self.assertTrue(rec.task_id.startswith("task-"))
        self.assertEqual(rec.status, "pending")
        self.assertEqual(rec.attempts, 0)
        got = await self.router.get_task(rec.task_id)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got.title, "run core tests")

    async def test_submit_invalid_task_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await self.router.submit_task(task_type="dance", title="x")

    async def test_submit_invalid_target_role_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await self.router.submit_task(task_type="bash", title="x", target_role="chef")

    # ── claim: matching + ordering ──────────────────────────────────────────
    async def test_claim_returns_best_match(self) -> None:
        await self.router.submit_task(task_type="bash", title="t1")
        got = await self.router.claim_task(node_id="pc-1", role="coder", capabilities=["bash"])
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got.task_type, "bash")

    async def test_claim_respects_priority_then_fifo(self) -> None:
        low = await self.router.submit_task(task_type="bash", title="low", priority=9)
        high = await self.router.submit_task(task_type="bash", title="high", priority=0)
        got = await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        assert got is not None
        self.assertEqual(got.task_id, high.task_id, "priority 0 আগে claim হওয়া উচিত")
        got2 = await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        assert got2 is not None
        self.assertEqual(got2.task_id, low.task_id)

    async def test_claim_capability_mismatch_returns_none(self) -> None:
        await self.router.submit_task(
            task_type="ollama", title="needs-gpu", required_capabilities=["ollama", "gpu"]
        )
        got = await self.router.claim_task(node_id="pc-2", capabilities=["ollama"])
        self.assertIsNone(got, "capability মিল না হলে claim হবে না")

    async def test_claim_target_role_mismatch_returns_none(self) -> None:
        await self.router.submit_task(task_type="bash", title="for-tester", target_role="tester")
        got = await self.router.claim_task(node_id="pc-1", role="coder", capabilities=["bash"])
        self.assertIsNone(got)
        got2 = await self.router.claim_task(node_id="pc-2", role="tester", capabilities=["bash"])
        self.assertIsNotNone(got2)

    # ── claim: CAS / limits ─────────────────────────────────────────────────
    async def test_cas_two_nodes_cannot_claim_same_task(self) -> None:
        """CAS guarantee — একটিমাত্র pending task, দুই node একসাথে claim করতে চাইলে
        ঠিক একজনই পাবে (asyncio.Lock দিয়ে atomic)।"""
        await self.router.submit_task(task_type="bash", title="only-one")
        results = await asyncio.gather(
            self.router.claim_task(node_id="pc-1", capabilities=["bash"]),
            self.router.claim_task(node_id="pc-2", capabilities=["bash"]),
        )
        winners = [r for r in results if r is not None]
        self.assertEqual(len(winners), 1, "ঠিক একটি node task পাবে")

    async def test_max_active_per_node_limit(self) -> None:
        for i in range(3):
            await self.router.submit_task(task_type="bash", title=f"t{i}")
        first = await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        self.assertIsNotNone(first)
        second = await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        self.assertIsNotNone(second)
        third = await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        self.assertIsNone(third, "max_active_per_node=2 — তৃতীয়টি পাবে না")
        self.assertEqual(await self.router.active_task_count("pc-1"), 2)

    # ── lease renewal + ownership ───────────────────────────────────────────
    async def test_renew_lease_by_owner_ok_wrong_node_forbidden(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="t")
        got = await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        assert got is not None
        renewed = await self.router.renew_lease(rec.task_id, node_id="pc-1", lease_seconds=120)
        self.assertEqual(renewed.status, "leased")
        with self.assertRaises(PermissionError):
            await self.router.renew_lease(rec.task_id, node_id="pc-2")
        with self.assertRaises(ValueError):
            await self.router.renew_lease(rec.task_id, node_id="pc-1", lease_seconds=0)

    async def test_complete_by_owner_only(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="t")
        await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        with self.assertRaises(PermissionError):
            await self.router.complete_task(rec.task_id, node_id="pc-2", result={})
        done = await self.router.complete_task(rec.task_id, node_id="pc-1", result={"exit_code": 0})
        self.assertEqual(done.status, "done")
        self.assertEqual(done.result, {"exit_code": 0})
        self.assertIsNone(done.lease_node_id)

    # ── failure → retry → failed ────────────────────────────────────────────
    async def test_fail_then_retry_then_permanent(self) -> None:
        rec = await self.router.submit_task(task_type="pytest", title="flaky", max_attempts=2)
        # attempt 1: claim + fail → back to pending
        await self.router.claim_task(node_id="pc-1", capabilities=["pytest"])
        failed1 = await self.router.fail_task(rec.task_id, node_id="pc-1", error="boom-1")
        self.assertEqual(failed1.status, "pending")
        # attempt 2: claim + fail → max_attempts ছুঁয়েছে → failed
        await self.router.claim_task(node_id="pc-2", capabilities=["pytest"])
        failed2 = await self.router.fail_task(rec.task_id, node_id="pc-2", error="boom-2")
        self.assertEqual(failed2.status, "failed")
        self.assertEqual(failed2.attempts, 2)

    async def test_fail_by_wrong_node_forbidden(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="t")
        await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        with self.assertRaises(PermissionError):
            await self.router.fail_task(rec.task_id, node_id="ghost", error="x")

    # ── reap: Zero Zombie Tasks ─────────────────────────────────────────────
    async def test_reap_expired_lease_requeues_for_failover(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="zombie")
        # 1 সেকেন্ডের lease — মেয়াদ শেষ করে reap যাচাই।
        await self.router.claim_task(node_id="pc-dead", capabilities=["bash"], lease_seconds=1)
        leased = await self.router.get_task(rec.task_id)
        assert leased is not None
        self.assertEqual(leased.status, "leased")
        await asyncio.sleep(1.1)
        reaped = await self.router.reap_expired_leases()
        self.assertIn(rec.task_id, reaped)
        after = await self.router.get_task(rec.task_id)
        assert after is not None
        self.assertEqual(after.status, "pending", "expired lease → requeue (failover)")
        self.assertIsNone(after.lease_node_id)

    async def test_reap_after_max_attempts_fails_permanently(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="zombie-max", max_attempts=1)
        await self.router.claim_task(node_id="pc-dead", capabilities=["bash"], lease_seconds=1)
        await asyncio.sleep(1.1)
        await self.router.reap_expired_leases()
        after = await self.router.get_task(rec.task_id)
        assert after is not None
        self.assertEqual(after.status, "failed")

    # ── cancel ───────────────────────────────────────────────────────────────
    async def test_cancel_pending_and_terminal_guard(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="t")
        cancelled = await self.router.cancel_task(rec.task_id)
        self.assertEqual(cancelled.status, "cancelled")
        with self.assertRaises(ValueError):
            await self.router.cancel_task(
                rec.task_id,
            )
        with self.assertRaises(KeyError):
            await self.router.cancel_task("task-does-not-exist")

    # ── visibility ───────────────────────────────────────────────────────────
    async def test_list_and_stats(self) -> None:
        a = await self.router.submit_task(task_type="bash", title="a")
        b = await self.router.submit_task(task_type="bash", title="b")
        await self.router.claim_task(node_id="pc-1", capabilities=["bash"])
        all_tasks = await self.router.list_tasks()
        self.assertEqual(len(all_tasks), 2)
        leased_list = await self.router.list_tasks(status="leased")
        self.assertEqual([t.task_id for t in leased_list], [a.task_id])
        pending_list = await self.router.list_tasks(status="pending")
        self.assertEqual([t.task_id for t in pending_list], [b.task_id])
        with self.assertRaises(ValueError):
            await self.router.list_tasks(status="bogus")
        stats = await self.router.queue_stats()
        self.assertEqual(stats["leased"], 1)
        self.assertEqual(stats["pending"], 1)

    # ── specific claim ───────────────────────────────────────────────────────
    async def test_claim_specific(self) -> None:
        rec = await self.router.submit_task(task_type="bash", title="t")
        got = await self.router._claim_specific(rec.task_id, node_id="pc-1")
        self.assertIsNotNone(got)
        # আবার claim করতে চাইলে None ( leased)
        again = await self.router._claim_specific(rec.task_id, node_id="pc-2")
        self.assertIsNone(again)
        with self.assertRaises(KeyError):
            await self.router._claim_specific("task-missing", node_id="pc-1")


if __name__ == "__main__":
    unittest.main()
