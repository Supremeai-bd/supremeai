"""
gateway/service/route_arbiter.py — Dynamic Route Arbiter & Multi-Provider Decision Engine.

Enforces:
1. Dynamic provider ranking based on real-time latency, error rates, and remaining free quota.
2. Per-model routing policies:
   - supreme-spark: Ultra-low latency (<1.5s). Groq first, fall back to SambaNova/Gemini Flash, then stealth webhook if needed.
   - supreme-reason: High reasoning. Gemini 2.5 Pro / Flash-thinking first, OpenRouter reasoning fallbacks, stealth session fallback.
   - supreme-deep: Deep research / wide context (<2.0s target). Large context OpenRouter / Gemini Flash 1.5/2.5.
   - supreme-core: Balanced sovereign engine. Adaptive squad rotation.
   - supremeai-web: Dedicated to stealth webhook / web sessions.
   - supremeai-api: Dedicated to sovereign multi-key API pool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .adaptive_routing import RouteSnapshot, route_score
from .free_route_policy import VISION_PROVIDERS
from .pool import FederationSquad, KeySlot

logger = logging.getLogger("supremeai.arbiter")

RELAY_ONLY_MODELS = frozenset({
    "supremeai-web", "supremeai/web", "supremeai-webhook", "supremeai/webhook",
    "supremeai/stealth", "supremeai/ghost_gemini", "supremeai/web_session",
})
API_ONLY_MODELS = frozenset({"supremeai-api", "supremeai/api"})

# Per-model latency thresholds from architectural plan
MODEL_LATENCY_THRESHOLDS_MS: Dict[str, float] = {
    "supreme-spark": 1500.0,
    "supremeai-spark": 1500.0,
    "supremeai-fast": 1500.0,
    "supreme-core": 1800.0,
    "supreme-reason": 2000.0,
    "supremeai-reasoning": 2000.0,
    "supreme-deep": 2500.0,
    "supremeai-deep-research": 2500.0,
    "supremeai-web": 2000.0,
    "supremeai-api": 1800.0,
}

# Per-model preferred provider cascades
MODEL_PROVIDER_CASCADES: Dict[str, List[str]] = {
    "supreme-spark": ["groq", "kilo", "sambanova", "gemini", "openrouter"],
    "supremeai-spark": ["groq", "kilo", "sambanova", "gemini", "openrouter"],
    "supreme-reason": ["gemini", "kilo", "openrouter", "groq", "mistral"],
    "supreme-deep": ["openrouter", "kilo", "gemini", "groq", "mistral"],
    "supreme-core": ["groq", "kilo", "gemini", "openrouter", "sambanova", "mistral"],
    "supremeai-web": ["ghost_gemini", "web_session", "stealth"],
    "supremeai-api": ["groq", "kilo", "gemini", "openrouter", "sambanova", "mistral", "openai"],
}


@dataclass
class RoutingDecision:
    """Actionable decision returned by the arbiter."""
    route_type: str  # "stealth-webhook" or "api-pool"
    provider: Optional[str] = None
    slot: Optional[KeySlot] = None
    candidate_slots: List[Tuple[str, KeySlot]] = None
    target_latency_ms: float = 1800.0
    allow_stealth_fallback: bool = True


class DynamicRouteArbiter:
    """Intelligent multi-tier arbiter selecting best provider and route without static bias."""

    def __init__(self, squad: Optional[FederationSquad] = None):
        self.squad = squad

    def choose_best_route(
        self,
        requested_model: str,
        preferred_provider: Optional[str],
        adaptive_routes: Dict[str, Any],
        stealth_available: bool,
        has_image: bool = False,
    ) -> RoutingDecision:
        model_clean = (requested_model or "auto").strip().lower()
        target_latency = MODEL_LATENCY_THRESHOLDS_MS.get(model_clean, 1800.0)

        # 1. Enforce strict model boundary contracts
        if model_clean in RELAY_ONLY_MODELS:
            return RoutingDecision(
                route_type="stealth-webhook",
                target_latency_ms=target_latency,
                allow_stealth_fallback=True,
                candidate_slots=[],
            )

        if model_clean in API_ONLY_MODELS:
            candidates: List[Tuple[str, KeySlot]] = []
            seen_slot_names = set()
            if self.squad and preferred_provider and preferred_provider not in ("auto", "stealth"):
                for p, s in self.squad.get_candidate_slots(preferred_provider, vision=has_image):
                    if (not has_image or p in VISION_PROVIDERS) and s.name not in seen_slot_names:
                        candidates.append((p, s))
                        seen_slot_names.add(s.name)
            if self.squad:
                for p, s in self.squad.get_candidate_slots("auto", vision=has_image):
                    if (not has_image or p in VISION_PROVIDERS) and s.name not in seen_slot_names:
                        candidates.append((p, s))
                        seen_slot_names.add(s.name)
            return RoutingDecision(
                route_type="api-pool",
                target_latency_ms=target_latency,
                allow_stealth_fallback=False,  # API pool strictly disallows stealth relay
                candidate_slots=candidates,
            )

        # 2. Per-model ordered candidate slots with multi-provider failover
        allowed_providers = MODEL_PROVIDER_CASCADES.get(model_clean)
        candidates: List[Tuple[str, KeySlot]] = []

        if self.squad:
            seen_slot_names = set()
            primary_candidates: List[Tuple[str, KeySlot]] = []
            fallback_candidates: List[Tuple[str, KeySlot]] = []

            # Primary: if preferred_provider specified, queue its candidate slots first
            if preferred_provider and preferred_provider not in ("auto", "stealth"):
                for prov, slot in self.squad.get_candidate_slots(preferred_provider, vision=has_image):
                    if (not has_image or prov in VISION_PROVIDERS) and slot.name not in seen_slot_names:
                        primary_candidates.append((prov, slot))
                        seen_slot_names.add(slot.name)

            # Secondary / Fallbacks: cascade across allowed_providers and full federation squad
            provider_sequence = list(allowed_providers or ["groq", "gemini", "openrouter", "sambanova", "mistral", "kilo"])
            if has_image:
                # Strictly isolate vision tasks to multimodal providers (never text-only models like Groq/Mistral/Kilo)
                provider_sequence = [p for p in provider_sequence if p in VISION_PROVIDERS]
            for prov in provider_sequence:
                if prov == preferred_provider:
                    continue
                for prov_item, slot in self.squad.get_candidate_slots(prov, vision=has_image):
                    if slot.name not in seen_slot_names:
                        fallback_candidates.append((prov_item, slot))
                        seen_slot_names.add(slot.name)

            # Tertiary: add any other healthy squad auto slots
            for prov_item, slot in self.squad.get_candidate_slots("auto", vision=has_image):
                if has_image and prov_item not in VISION_PROVIDERS:
                    continue
                if slot.name not in seen_slot_names:
                    fallback_candidates.append((prov_item, slot))
                    seen_slot_names.add(slot.name)

            # Score and rank primary and fallback groups independently
            sort_key = lambda item: route_score(
                RouteSnapshot(
                    name=item[1].name,
                    latency_ms=item[1].rank_latency_ms,
                    remaining=item[1].remaining_free,
                    limit=item[1].free_limit,
                    failures=item[1].consecutive_failures,
                ),
                latency_target_ms=target_latency,
            )
            primary_candidates = sorted(primary_candidates, key=sort_key, reverse=True)
            fallback_candidates = sorted(fallback_candidates, key=sort_key, reverse=True)

            candidates = primary_candidates + fallback_candidates

        # Keep the relay as the text fallback when no approved API route exists.
        # An explicitly selected API lane or image request never switches lanes.
        allow_stealth = bool(stealth_available and not has_image)
        route_type = "stealth-webhook" if allow_stealth and not candidates else "api-pool"

        return RoutingDecision(
            route_type=route_type,
            target_latency_ms=target_latency,
            allow_stealth_fallback=allow_stealth,
            candidate_slots=candidates,
        )


route_arbiter = DynamicRouteArbiter()
