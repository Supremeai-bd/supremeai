"""Tests for pass^k reliability benchmarking (ROADMAP Sprint 4 / promotion gates).

বাংলা: SelfBenchmarkEngine-এর নতুন RELIABILITY ক্যাটাগরি যাচাই করে —
C(s,k)/C(n,k) unbiased estimator এবং ai_system-driven রান শেডিউলিং।
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from core.self_benchmark import BenchmarkCategory, SelfBenchmarkEngine


class TestPassHatKEstimator(unittest.TestCase):
    def test_perfect_reliability_is_one(self):
        # বাংলা: n=5 রানে 5 সফল, k=3 → C(5,3)/C(5,3) = 1.0
        self.assertEqual(SelfBenchmarkEngine._pass_hat_k_estimator(5, 5, 3), 1.0)

    def test_partial_success_is_fraction(self):
        # C(4,3)/C(5,3) = 4/10 = 0.4
        self.assertAlmostEqual(SelfBenchmarkEngine._pass_hat_k_estimator(4, 5, 3), 0.4)

    def test_below_k_successes_is_zero(self):
        self.assertEqual(SelfBenchmarkEngine._pass_hat_k_estimator(2, 5, 3), 0.0)

    def test_fewer_samples_than_k_is_zero(self):
        self.assertEqual(SelfBenchmarkEngine._pass_hat_k_estimator(3, 2, 3), 0.0)

    def test_exact_n_equals_k_all_or_nothing(self):
        self.assertEqual(SelfBenchmarkEngine._pass_hat_k_estimator(3, 3, 3), 1.0)
        self.assertEqual(SelfBenchmarkEngine._pass_hat_k_estimator(2, 3, 3), 0.0)


class TestReliabilityBenchmark(unittest.TestCase):
    def test_reliability_category_runs_and_gates(self):
        # বাংলা: সবসময় সফল AI → pass^k = 1.0 → passed=True
        engine = SelfBenchmarkEngine(
            ai_system=SimpleNamespace(process=_async_ok),
            config={"reliability_k": 2, "reliability_samples": 3, "test_duration_ms": 1000},
        )
        results = asyncio.run(engine._benchmark_reliability())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, BenchmarkCategory.RELIABILITY)
        self.assertEqual(results[0].score, 1.0)
        self.assertTrue(results[0].passed)

    def test_unreliable_system_fails_gate(self):
        # বাংলা: সবসময় ব্যর্থ AI → pass^k = 0.0 → gate fail
        engine = SelfBenchmarkEngine(
            ai_system=SimpleNamespace(process=_async_fail),
            config={"reliability_k": 2, "reliability_samples": 3, "test_duration_ms": 1000},
        )
        results = asyncio.run(engine._benchmark_reliability())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score, 0.0)
        self.assertFalse(results[0].passed)

    def test_no_ai_system_returns_empty(self):
        engine = SelfBenchmarkEngine(ai_system=None)
        self.assertEqual(asyncio.run(engine._benchmark_reliability()), [])


async def _async_ok(q=None):
    return SimpleNamespace(success=True)


async def _async_fail(q=None):
    return SimpleNamespace(success=False)


if __name__ == "__main__":
    unittest.main()
