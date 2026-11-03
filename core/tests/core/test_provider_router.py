import asyncio
from unittest.mock import patch

import pytest

from core.llm.provider_router import LatencyAwareWeightedRouter, ProviderStats


def test_provider_stats_record_and_rates():
    stats = ProviderStats(name="test", base_weight=2.0)

    assert stats.avg_latency_ms == 0.0
    assert stats.success_rate == 1.0

    stats.record(100.0, True)
    stats.record(300.0, False)

    assert stats.avg_latency_ms == 200.0
    assert stats.success_rate == 0.5
    assert stats.successes == 1
    assert stats.failures == 1


def test_provider_stats_circuit_trip_and_expiry():
    stats = ProviderStats(name="test", base_weight=1.0)

    with patch("core.llm.provider_router.time.monotonic", side_effect=[100.0, 100.0, 111.0]):
        stats.trip_circuit(10.0)
        assert stats.is_circuit_open() is True
        assert stats.is_circuit_open() is False


def test_effective_weight_penalizes_latency_and_preserves_minimum():
    router = LatencyAwareWeightedRouter({"fast": 5.0})
    stats = router.stats["fast"]

    with (
        patch.object(stats, "is_circuit_open", return_value=False),
        patch("core.llm.provider_router.settings.LATENCY_NORMALIZATION_MS", 100.0),
        patch("core.llm.provider_router.settings.MIN_PROVIDER_WEIGHT", 0.1),
    ):
        stats.record(100.0, True)
        assert router._effective_weight(stats) == 2.5

        stats.record(100000.0, False)
        assert router._effective_weight(stats) >= 0.1


@pytest.mark.asyncio
async def test_select_provider_uses_only_closed_candidates():
    router = LatencyAwareWeightedRouter({"open": 5.0, "closed": 1.0})
    router.stats["open"].trip_circuit(60.0)

    with patch("core.llm.provider_router.random.choices", return_value=["closed"]) as choices:
        selected = await router.select_provider()

    assert selected == "closed"
    choices.assert_called_once()
    assert choices.call_args.args[0] == ("closed",)


@pytest.mark.asyncio
async def test_select_provider_falls_back_when_all_circuits_are_open():
    router = LatencyAwareWeightedRouter({"a": 1.0, "b": 2.0})
    router.stats["a"].circuit_open_until = 200.0
    router.stats["b"].circuit_open_until = 150.0

    with patch("core.llm.provider_router.time.monotonic", return_value=100.0):
        assert await router.select_provider() == "b"


@pytest.mark.asyncio
async def test_record_result_creates_unknown_provider():
    router = LatencyAwareWeightedRouter({"known": 1.0})

    await router.record_result("new-provider", 42.0, True)

    assert "new-provider" in router.stats
    assert router.stats["new-provider"].successes == 1
    assert router.stats["new-provider"].avg_latency_ms == 42.0


@pytest.mark.asyncio
async def test_record_result_trips_circuit_after_failure_threshold():
    router = LatencyAwareWeightedRouter({"provider": 1.0})
    stats = router.stats["provider"]

    with (
        patch("core.llm.provider_router.settings.CIRCUIT_FAILURE_THRESHOLD", 3),
        patch("core.llm.provider_router.settings.CIRCUIT_SUCCESS_RATE_FLOOR", 0.5),
        patch("core.llm.provider_router.settings.CIRCUIT_COOLDOWN_SECONDS", 30.0),
        patch.object(stats, "trip_circuit") as trip,
    ):
        await router.record_result("provider", 10.0, False)
        await router.record_result("provider", 10.0, False)
        await router.record_result("provider", 10.0, False)

    trip.assert_called_once_with(30.0)
    assert stats.failures == 3
    assert stats.success_rate == 0.0


def test_provider_stats_empty_latency_defaults_to_zero():
    stats = ProviderStats(name="test", base_weight=1.0)
    assert stats.avg_latency_ms == 0.0
