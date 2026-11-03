"""#1827 — usage metrics aggregation last-mile tests.

বাংলা: collector + CostGuard aggregates → usage_metrics row (delta semantics,
honest zeros, upsert via existing db helper) — manual POST আর দরকার নেই।
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


class FakeCollector:
    def __init__(self) -> None:
        self._metrics: dict[str, float] = {"ai_tokens_total:{'model': 'gpt'}": 120}
        self._health: dict[str, Any] = {
            "total_requests": 40,
            "total_errors": 5,
            "ai_costs": {"gpt": 0.12},
        }

    async def get_overall_health(self) -> dict[str, Any]:
        return self._health


class FakeStore:
    def __init__(self) -> None:
        self.upserted: list[dict[str, Any]] = []

    def upsert_usage_metric(self, data: dict[str, Any]) -> dict[str, Any] | None:
        self.upserted.append(data)
        return data


@pytest.fixture()
def aggregator():
    for mod_name in [m for m in list(sys.modules) if m.endswith("usage_metrics_aggregator")]:
        del sys.modules[mod_name]
    from core.startup import usage_metrics_aggregator as mod

    mod._LAST_TOTALS.clear()
    return mod


class TestCollectSnapshot:
    @pytest.mark.asyncio
    async def test_row_shape_and_math(self, aggregator):
        snap = await aggregator.collect_usage_snapshot(
            "tenant-supremeai", FakeCollector(), redis=None, last_totals={}
        )
        assert set(aggregator.USAGE_METRICS_DIMENSIONS) <= set(snap.keys())
        assert snap["total_requests"] == 40
        assert snap["total_tokens"] == 120
        assert snap["total_cost"] == pytest.approx(0.12)
        assert snap["error_rate"] == pytest.approx(0.125)
        assert snap["tenant_id"] == "tenant-supremeai"

    @pytest.mark.asyncio
    async def test_delta_semantics_only_growth_written(self, aggregator):
        collector = FakeCollector()
        baseline: dict[str, float] = {}
        first = await aggregator.collect_usage_snapshot("t1", collector, None, baseline)
        assert first["total_requests"] == 40
        collector._health["total_requests"] = 55
        second = await aggregator.collect_usage_snapshot("t1", collector, None, baseline)
        assert second["total_requests"] == 15, "second row is the delta, not cumulative"

    @pytest.mark.asyncio
    async def test_honest_zeros_without_sources(self, aggregator):
        snap = await aggregator.collect_usage_snapshot(
            "t1", FakeCollector(), redis=None, last_totals={}
        )
        assert snap["unique_users"] == 0
        assert snap["avg_latency_ms"] == 0

    @pytest.mark.asyncio
    async def test_cost_guard_redis_spend_added(self, aggregator):
        class FakeRedisClient:
            async def keys(self, pattern: str):
                return ["cost_guard:t1:pro:spent"] if pattern == "cost_guard:*:spent" else []

            async def get(self, key: str):
                return "1.5"

        class FakeRedis:
            async def get_client_async(self):
                return FakeRedisClient()

        snap = await aggregator.collect_usage_snapshot(
            "t1", FakeCollector(), redis=FakeRedis(), last_totals={}
        )
        assert snap["total_cost"] == pytest.approx(1.62)  # 0.12 model cost + 1.5 spend


class TestAggregationCycle:
    @pytest.mark.asyncio
    async def test_cycle_upserts_via_store(self, aggregator):
        store = FakeStore()
        snap = await aggregator.run_aggregation_cycle(
            tenant_id="t1", collector=FakeCollector(), store=store, redis=None, last_totals={}
        )
        assert snap is not None
        assert len(store.upserted) == 1
        assert store.upserted[0]["tenant_id"] == "t1"

    @pytest.mark.asyncio
    async def test_cycle_never_raises_on_store_failure(self, aggregator):
        class BrokenStore:
            def upsert_usage_metric(self, data):
                raise RuntimeError("db down")

        snap = await aggregator.run_aggregation_cycle(
            tenant_id="t1",
            collector=FakeCollector(),
            store=BrokenStore(),
            redis=None,
            last_totals={},
        )
        assert snap is None, "failed cycle is logged and swallowed (never kills the loop)"


class TestStartupWiring:
    def test_supervisor_agent_registered(self):
        source = (Path(__file__).resolve().parents[2] / "core" / "startup" / "agents.py").read_text(
            encoding="utf-8"
        )
        assert "usage-metrics-aggregator" in source
        assert "ENABLE_USAGE_METRICS_AGGREGATOR" in source
        assert "USAGE_METRICS_INTERVAL_HOURS" in source
