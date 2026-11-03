"""
Tests for LLM Gateway consolidation improvements.
These tests verify the enhancements made to unify multiple gateways.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm.llm_gateway import LLMGateway, get_llm_gateway
from core.resilience.circuit_breaker_manager import get_circuit_breaker_manager


@pytest.fixture
def llm_gateway():
    """Create a test LLMGateway instance."""
    return LLMGateway()


# NOTE (Phase-2.1, issue #2249): the legacy services/llm LLMRouter fixture and
# its shared-circuit-breaker test were retired together with the module —
# the canonical stack (core/llm/llm_gateway + brain/model_router) is covered
# by the gateway tests below.


@pytest.mark.asyncio
async def test_shared_circuit_breaker_manager():
    """Test that circuit breakers are shared between gateways."""
    cb_manager = get_circuit_breaker_manager()

    # Get circuit breakers for same model from different gateways
    cb1 = cb_manager.get_circuit_breaker("test-model")
    cb2 = cb_manager.get_circuit_breaker("test-model")

    # They should be the same instance
    assert cb1 is cb2, "Circuit breakers should be shared between gateways"

    # Test state sharing
    cb1.force_open()
    assert cb2.is_open, "Circuit breaker state should be shared"


@pytest.mark.asyncio
async def test_gateway_has_rate_limit_handling(llm_gateway):
    """Test that the enhanced gateway has rate limit handling."""
    # Check that the rate limit handler method exists
    assert hasattr(llm_gateway, "_handle_rate_limit_error"), (
        "LLMGateway should have rate limit handling method"
    )

    # Check that the method is async
    import inspect

    assert inspect.iscoroutinefunction(llm_gateway._handle_rate_limit_error), (
        "Rate limit handler should be async"
    )


# RETIRED with services/llm/llm_router.py (issue #2249):
#   test_router_uses_shared_circuit_breaker — asserted the legacy router's
#   breaker wiring; the gateway/shared-manager behaviour remains covered by
#   test_gateway_429_handling_simulation + test_circuit_breaker_state_sharing.


@pytest.mark.asyncio
async def test_gateway_429_handling_simulation(llm_gateway):
    """Test 429 handling logic without making actual HTTP requests."""
    import httpx

    # Create a mock HTTPStatusError for 429
    mock_response = Mock()
    mock_response.status_code = 429

    # Test 1: Fast fallback (OmniRoute logic) if pause is too long
    mock_response.headers = {"Retry-After": "30"}  # 30 second delay
    mock_exc = httpx.HTTPStatusError("Too Many Requests", response=mock_response, request=Mock())

    # Mock the sleep function to avoid actual sleep
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Call the rate limit handler
        result = await llm_gateway._handle_rate_limit_error("test-model", mock_exc)

        # Verify it returned False (fail-fast fallback)
        assert result is False, "Rate limit handler should return False to trigger fast fallback"
        assert not mock_sleep.called, "Should not sleep when triggering fast fallback"

    # Test 2: Retry if pause is short
    mock_response.headers = {"Retry-After": "2"}  # 2 second delay
    mock_exc = httpx.HTTPStatusError("Too Many Requests", response=mock_response, request=Mock())

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await llm_gateway._handle_rate_limit_error("test-model", mock_exc)

        # Verify it returned True
        assert result is True, "Rate limit handler should return True to retry when pause is short"
        assert mock_sleep.called, "Should sleep for short backoff"


@pytest.mark.asyncio
async def test_provider_taxonomy_consistency():
    """Test that provider taxonomies are more consistent between gateways."""
    get_llm_gateway()

    # The provider → settings-key map moved to module level during the
    # gateway registry refactor; the instance no longer carries it.
    from core.llm.llm_gateway.registry import _MODEL_KEY_MAP

    # Verify that the gateway registry has expanded provider mapping
    expected_providers = [
        "groq",
        "gemini",
        "gpt",
        "openai",
        "deepseek",
        "openrouter",
        "hf",
        "huggingface",
        "nvidia",
        "moonshot",
        "together",
        "ollama",
        "hf_space",
    ]

    for provider in expected_providers:
        assert provider in _MODEL_KEY_MAP, f"Gateway should support {provider} provider"


@pytest.mark.asyncio
async def test_circuit_breaker_state_sharing():
    """Test that circuit breaker states are shared across different gateway instances."""
    # Create multiple gateway instances
    gw1 = LLMGateway()
    gw2 = LLMGateway()

    # Get circuit breakers for the same model from both gateways
    cb1 = gw1._get_or_create_circuit_breaker("shared-model-test")
    cb2 = gw2._get_or_create_circuit_breaker("shared-model-test")

    # They should be the same instance due to shared manager
    assert cb1 is cb2, "Circuit breakers should be shared across gateway instances"

    # Test state change in one affects the other
    cb1.force_open()
    assert cb2.is_open, "Opening circuit breaker in one should affect shared instance"


def test_gateway_health_endpoint_simulation():
    """Test the health endpoint functionality.

    NOTE: must stay a SYNC test — TestClient.get() is a blocking portal call;
    inside an async test it deadlocks the running event loop.

    ROOT-CAUSE FIX (issue #1068): uses a fresh FastAPI() app with ONLY the
    llm-gateway router mounted and the auth dependency overridden. The previous
    version mounted the router on the full main app (core.app); its middleware
    stack performs async work inside TestClient's portal loop, which can hang
    depending on tests that ran earlier (order-dependent state) and tripped the
    core-unit suite timeout in CI. The handler + dependency are synchronous, so
    a fresh app yields a deterministic response — and this now asserts the real
    200 payload contract instead of accepting 401/403 as a pass.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user_token
    from api.routes.llm_gateway_routes import router

    probe = FastAPI()
    probe.include_router(router)
    probe.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "test_admin@supremeai.com",
        "role": "admin",
        "tenant_id": "test-tenant",
    }
    client = TestClient(probe)

    response = client.get("/llm-gateway/health")
    assert response.status_code == 200, f"Health endpoint should exist: {response.status_code}"
    body = response.json()
    assert body["status"] == "healthy"
    assert body["gateway_initialized"] is True


@pytest.mark.asyncio
async def test_enhanced_gateway_features():
    """Test that the enhanced gateway has all the expected features."""
    gateway = get_llm_gateway()

    # Verify enhanced features exist
    assert hasattr(gateway, "_handle_rate_limit_error"), (
        "Enhanced gateway should have rate limit handler"
    )

    assert hasattr(gateway, "_get_or_create_circuit_breaker"), (
        "Enhanced gateway should have circuit breaker management"
    )

    # Verify it's using the centralized circuit breaker manager
    original_method = gateway._get_or_create_circuit_breaker
    cb = original_method("test-model")
    shared_cb = get_circuit_breaker_manager().get_circuit_breaker("test-model")

    assert cb is shared_cb, "Gateway should use shared circuit breaker"


def test_provider_mapping_completeness():
    """Test that provider mapping covers all expected providers."""
    # The provider → settings-key map moved to module level during the
    # gateway registry refactor; the instance no longer carries it.
    from core.llm.llm_gateway.registry import _MODEL_KEY_MAP

    # Check that the expanded provider map includes all expected providers
    expected_providers = {
        "groq",
        "gemini",
        "gpt",
        "openai",
        "deepseek",
        "openrouter",
        "hf",
        "huggingface",
        "nvidia",
        "moonshot",
        "together",
        "ollama",
        "hf_space",
    }

    actual_providers = set(_MODEL_KEY_MAP.keys())

    missing_providers = expected_providers - actual_providers
    assert not missing_providers, f"Missing providers in mapping: {missing_providers}"

    extra_providers = actual_providers - expected_providers
    print(f"Additional providers in mapping: {extra_providers}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
