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
from .pool import KeySlot, FederationSquad

logger = logging.getLogger("supremeai.arbiter")

# Per-model latency thresholds from architectural plan
MODEL_LATENCY_THRESHOLDS_MS: Dict[str, float] = {
    "supreme-spark": 1500.0,
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
    ) -> RoutingDecision:
        model_clean = (requested_model or "auto").strip().lower()
        target_latency = MODEL_LATENCY_THRESHOLDS_MS.get(model_clean, 1800.0)

        # 1. Enforce strict model boundary contracts
        if model_clean in ("supremeai-web", "supremeai/web", "supremeai-webhook", "supremeai/webhook"):
            return RoutingDecision(
                route_type="stealth-webhook",
                target_latency_ms=target_latency,
                allow_stealth_fallback=True,
                candidate_slots=[],
            )

        if model_clean in ("supremeai-api", "supremeai/api"):
            candidates = self.squad.get_candidate_slots(preferred_provider) if self.squad else []
            if not candidates:
                candidates = self.squad.get_candidate_slots("auto") if self.squad else []
            return RoutingDecision(
                route_type="api-pool",
                target_latency_ms=target_latency,
                allow_stealth_fallback=False,  # API pool strictly disallows stealth relay
                candidate_slots=candidates,
            )

        # 2. Per-model ordered candidate slots
        allowed_providers = MODEL_PROVIDER_CASCADES.get(model_clean)
        candidates: List[Tuple[str, KeySlot]] = []

        if self.squad:
            if preferred_provider and preferred_provider not in ("auto", "stealth"):
                candidates = self.squad.get_candidate_slots(preferred_provider)
            elif allowed_providers:
                # Rank allowed providers according to adaptive route_score
                for prov in allowed_providers:
                    candidates.extend(self.squad.get_candidate_slots(prov))
            else:
                candidates = self.squad.get_candidate_slots("auto")

        # Re-sort all candidate slots by route_score using model's latency threshold
        if candidates:
            candidates = sorted(
                candidates,
                key=lambda item: route_score(
                    RouteSnapshot(
                        name=item[1].name,
                        latency_ms=item[1].ewma_latency_ms,
                        remaining=item[1].remaining_free,
                        limit=item[1].free_limit,
                        failures=item[1].consecutive_failures,
                    ),
                    latency_target_ms=target_latency,
                ),
                reverse=True,
            )

        # 3. Dynamic route competition between Stealth Webhook and API Key Pool
        stealth_route = adaptive_routes.get("stealth-webhook")
        api_route = adaptive_routes.get("api-pool")

        stealth_snap = stealth_route.snapshot(available=stealth_available) if stealth_route else RouteSnapshot("stealth-webhook", available=False)
        api_snap = api_route.snapshot(available=bool(candidates)) if api_route else RouteSnapshot("api-pool", available=False)

        # Determine winner
        score_stealth = route_score(stealth_snap, latency_target_ms=target_latency)
        score_api = route_score(api_snap, latency_target_ms=target_latency)

        # If spark or latency-sensitive, prioritize lower latency
        allow_stealth = model_clean in ("supreme-spark", "supreme-core", "supreme-reason", "supreme-deep", "auto")
        if preferred_provider in ("stealth", "ghost_gemini", "web_session"):
            route_type = "stealth-webhook"
        elif not stealth_available:
            route_type = "api-pool"
        elif not candidates:
            route_type = "stealth-webhook"
        elif score_api >= score_stealth:
            route_type = "api-pool"
        else:
            route_type = "stealth-webhook"

        return RoutingDecision(
            route_type=route_type,
            target_latency_ms=target_latency,
            allow_stealth_fallback=allow_stealth,
            candidate_slots=candidates,
        )


route_arbiter = DynamicRouteArbiter()
