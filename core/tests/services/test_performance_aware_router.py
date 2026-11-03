import pytest

from brain.performance_aware_router import PROVIDER_HEALTH, PerformanceAwareRouter


@pytest.fixture
def router():
    return PerformanceAwareRouter()


def test_is_provider_healthy_ok(router):
    assert router._is_provider_healthy("groq") is True


def test_is_provider_healthy_down(router):
    assert router._is_provider_healthy("unknown") is False


def test_get_provider_latency(router):
    assert router._get_provider_latency("google") == 250
    assert router._get_provider_latency("missing") == 9999


def test_calculate_score_returns_inf_for_unhealthy(router):
    score = router._calculate_score({"name": "missing"}, 1000)
    assert score == float("inf")


def test_calculate_score_lower_is_better_for_healthy(router):
    provider = {"name": "groq", "cost_per_1k": 0.0001, "quality": 9}
    score = router._calculate_score(provider, 50)
    assert score < float("inf")
    assert 0 <= score <= 1.0


@pytest.mark.asyncio
async def test_route_selects_healthy_provider(router):
    result = await router.route("test prompt", "general")
    assert "provider" in result
    assert "score" in result
    assert result["provider"] in [p["name"] for p in router.providers]


@pytest.mark.asyncio
async def test_route_raises_when_all_providers_unhealthy(router):
    original = PROVIDER_HEALTH.copy()
    for key in list(PROVIDER_HEALTH.keys()):
        PROVIDER_HEALTH[key] = {"status": "down", "latency_ms": 9999}

    try:
        with pytest.raises(Exception, match="No healthy providers available"):
            await router.route("test prompt", "general")
    finally:
        PROVIDER_HEALTH.update(original)


@pytest.mark.asyncio
async def test_route_fallback_when_all_unhealthy_but_score_inf():
    router = PerformanceAwareRouter()
    router._is_provider_healthy = lambda name: False
    router._get_provider_latency = lambda name: 9999

    with pytest.raises(Exception, match="No healthy providers available"):
        await router.route("test", "general")
