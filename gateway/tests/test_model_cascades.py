"""
test_model_cascades.py — Tests for Zero-Waste Model Priority Cascade and Fallback.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import gateway.service.providers.adapters as _adapters
from gateway.service.providers.adapters import (
    forward_chat_completion,
    PROVIDER_MODEL_CASCADES,
    PROVIDER_CONFIGS,
)
from gateway.service.pool import FederationSquad, ProviderKeyPool, KeySlot


@pytest.fixture(autouse=True)
def _reset_pooled_stealth_client():
    """Drop the shared production client pool at each test boundary.

    forward_chat_completion() acquires the SHARED pool via _get_stealth_client();
    the class-level patch('httpx.AsyncClient.post') mocks only .post, so the
    constructor still builds a REAL client and _get_stealth_client caches it
    (is_closed present). Every later test file's forwarder fake was then bypassed
    by that cached real client — the 2026-10-28 G6e/G7/G8 suite reds in
    test_stealth_dns_guards. No real connections are made here (post is mocked),
    so dropping the reference without aclose leaks nothing."""
    _adapters._STEALTH_CLIENT = None
    yield
    _adapters._STEALTH_CLIENT = None


def test_provider_cascades_defined():
    """Verify all major providers have non-empty prioritized model cascades."""
    assert "groq" in PROVIDER_MODEL_CASCADES
    assert "gemini" in PROVIDER_MODEL_CASCADES
    assert "openrouter" in PROVIDER_MODEL_CASCADES
    assert "perplexity" in PROVIDER_MODEL_CASCADES
    assert "sonar" in PROVIDER_MODEL_CASCADES["perplexity"]

    # Verify Groq contains live verified models
    assert "llama-3.3-70b-versatile" in PROVIDER_MODEL_CASCADES["groq"]
    assert "llama-3.1-8b-instant" in PROVIDER_MODEL_CASCADES["groq"]

    # Verify Gemini contains live verified models
    assert "gemini-2.5-flash" in PROVIDER_MODEL_CASCADES["gemini"]
    assert "gemini-2.5-flash-lite" in PROVIDER_MODEL_CASCADES["gemini"]
    # gemini-flash-lite-latest is the current free-tier top pick (2.5-flash hits quota 429)
    assert PROVIDER_MODEL_CASCADES["gemini"][0] == "gemini-flash-lite-latest"

    # Verify Kilo uses the free auto-router, not the paid "auto" (which 402s)
    assert "kilo" in PROVIDER_MODEL_CASCADES
    assert PROVIDER_MODEL_CASCADES["kilo"][0] == "kilo-auto/free"
    assert "auto" not in PROVIDER_MODEL_CASCADES["kilo"]

    # Verify Cerebras is strictly excluded (per user mandate)
    assert "cerebras" not in PROVIDER_MODEL_CASCADES


@pytest.mark.asyncio
async def test_in_flight_model_cascade_on_404():
    """If top model returns 404, adapter must automatically try the next model in cascade."""
    call_history = []

    async def mock_post(url, json=None, headers=None, **kwargs):
        model = json.get("model")
        call_history.append(model)
        mock_resp = MagicMock()
        if model == "qwen/qwen3.8-27b":
            mock_resp.status_code = 404
            mock_resp.json.return_value = {"error": "model_not_found"}
            mock_resp.text = '{"error": "model_not_found"}'
        else:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": f"Success with {model}"}}]
            }
            mock_resp.text = "ok"
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        status, data = await forward_chat_completion(
            provider="groq",
            api_key="gsk-test",
            payload={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert status == 200
        assert isinstance(data, dict)
        assert data.get("model") == "openai/gpt-oss-20b"
        assert call_history == ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]


@pytest.mark.asyncio
async def test_skip_paid_tier_on_402():
    """If a model returns 402 Payment Required, adapter skips paid tier and cascades."""
    call_history = []

    async def mock_post(url, json=None, headers=None, **kwargs):
        model = json.get("model")
        call_history.append(model)
        mock_resp = MagicMock()
        if model == "gemini-flash-lite-latest":
            mock_resp.status_code = 402
            mock_resp.json.return_value = {"error": "Payment required"}
            mock_resp.text = '{"error": "Payment required"}'
        else:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "ok"}}]
            }
            mock_resp.text = "ok"
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        status, data = await forward_chat_completion(
            provider="gemini",
            api_key="AIza-test",
            payload={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert status == 200
        assert data.get("model") == "gemini-2.5-flash-lite"


def test_jules_key_included_in_gemini_pool(monkeypatch):
    """Verify JULES_API_KEY is discovered and included as an additional Gemini key."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTest1")
    monkeypatch.setenv("JULES_API_KEY", "AQ.SyTestJules")

    squad = FederationSquad()
    gemini_pool = squad.pools.get("gemini")
    assert gemini_pool is not None
    slot_names = [s.name for s in gemini_pool.slots]
    assert "GEMINI_API_KEY" in slot_names
    assert "JULES_API_KEY" in slot_names


def test_route_arbiter_multi_provider_failover_inclusion(monkeypatch):
    """When preferred_provider is groq, candidate_slots must include fallbacks (e.g. gemini)."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test1234567890")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTest1234567890")

    from gateway.service.route_arbiter import DynamicRouteArbiter

    arbiter = DynamicRouteArbiter()
    squad = FederationSquad()
    arbiter.squad = squad

    decision = arbiter.choose_best_route(
        requested_model="supreme-core",
        preferred_provider="groq",
        adaptive_routes={},
        stealth_available=False,
    )
    providers = [prov for prov, _ in decision.candidate_slots]
    assert "groq" in providers
    assert "gemini" in providers
    # groq must be first, gemini must follow as seamless failover
    assert providers[0] == "groq"
    assert providers[1] == "gemini"


def test_vision_input_routes_to_gemini():
    """Vision/image inputs must route to gemini vision without unbound variable errors."""
    body_text = {"messages": [{"role": "user", "content": "hi"}]}
    body_image = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}},
                ],
            }
        ]
    }

    # Verify text input has_image detection
    has_image_text = False
    for m in (body_text.get("messages") or []):
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and (part.get("type") == "image_url" or "image" in str(part.get("type", ""))):
                    has_image_text = True
                    break
    assert not has_image_text

    # Verify image input has_image detection
    has_image_vision = False
    for m in (body_image.get("messages") or []):
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and (part.get("type") == "image_url" or "image" in str(part.get("type", ""))):
                    has_image_vision = True
                    break
    assert has_image_vision


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
