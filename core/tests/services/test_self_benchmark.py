# backend/tests/services/test_self_benchmark.py
"""Tests for SelfBenchmarkEngine and AdaptiveOptimizer."""

import pytest

from core.adaptive_optimizer import get_optimizer
from core.integration_layer import get_integrator
from core.self_benchmark import BenchmarkCategory, SelfBenchmarkEngine


@pytest.mark.asyncio
async def test_self_benchmark_engine_run():
    integrator = await get_integrator()
    benchmarker = SelfBenchmarkEngine(ai_system=integrator)
    report = await benchmarker.run_full_benchmark(
        categories=[BenchmarkCategory.PERFORMANCE, BenchmarkCategory.ACCURACY]
    )

    assert report.overall_score >= 0.0
    assert report.grade in ["A+", "A", "B+", "B", "C+", "C", "D", "F"]
    assert len(report.results) > 0


@pytest.mark.asyncio
async def test_adaptive_optimizer_cycle():
    integrator = await get_integrator()
    benchmarker = SelfBenchmarkEngine(ai_system=integrator)
    report = await benchmarker.run_full_benchmark(categories=[BenchmarkCategory.PERFORMANCE])

    optimizer = get_optimizer(benchmarker=benchmarker, ai_system=integrator)
    cycle = await optimizer.optimize_based_on_benchmark(report)

    assert cycle.cycle_id.startswith("opt_")
    assert cycle.overall_improvement >= 0
    assert len(optimizer.optimization_history) > 0
