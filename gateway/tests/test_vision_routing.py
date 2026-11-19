"""Tests for multimodal vision routing isolation and fallback safety.

Ensures that requests containing image attachments are strictly routed to
multimodal-capable providers (Gemini / OpenAI) and never silently fall back
to text-only models (Groq / OpenRouter / Mistral), which would refuse images
with hallucinations like "I don't have the ability to view or interpret images".
"""

from unittest.mock import MagicMock

from gateway.service.route_arbiter import DynamicRouteArbiter, KeySlot


def test_choose_best_route_with_image_excludes_text_only_providers():
    """Vision requests must never fall back to text-only providers (Groq, Mistral, etc.)."""
    squad = MagicMock()

    # Setup slots for both gemini and groq
    gemini_slot = KeySlot(
        name="gemini-main",
        key="sk-gemini-test",
        provider="gemini",
        ewma_latency_ms=200.0,
    )

    groq_slot = KeySlot(
        name="groq-fast",
        key="sk-groq-test",
        provider="groq",
        ewma_latency_ms=50.0,
    )

    def mock_get_candidate_slots(provider="auto", *, vision=False):
        if provider == "gemini":
            return [("gemini", gemini_slot)]
        if provider == "groq":
            return [("groq", groq_slot)]
        if provider == "auto":
            return [("groq", groq_slot), ("gemini", gemini_slot)]
        return []

    squad.get_candidate_slots.side_effect = mock_get_candidate_slots

    arbiter = DynamicRouteArbiter(squad=squad)

    # 1. Without image: Groq is allowed and preferred for low latency
    decision_text = arbiter.choose_best_route(
        requested_model="auto",
        preferred_provider=None,
        adaptive_routes={},
        stealth_available=False,
        has_image=False,
    )
    providers_text = [p for p, _ in decision_text.candidate_slots]
    assert "groq" in providers_text

    # 2. With image: Groq MUST be excluded; only vision providers allowed
    decision_vision = arbiter.choose_best_route(
        requested_model="gemini-flash-lite-latest",
        preferred_provider="gemini",
        adaptive_routes={},
        stealth_available=False,
        has_image=True,
    )
    providers_vision = [p for p, _ in decision_vision.candidate_slots]
    assert "groq" not in providers_vision
    assert all(p in ("gemini", "openai") for p in providers_vision)
