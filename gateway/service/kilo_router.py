"""
gateway/service/kilo_router.py — Smart Dynamic Router for Kilo Free Models.

Features:
- Live Discovery: Detects 100% free models (pricing prompt == "0" and completion == "0")
- Safe Exclusion: Excludes noisy/unpredictable/slow router routes:
    * 'kilo-auto/free' (unpredictable routing, high traffic)
    * 'openrouter/free' (slow double-hop, external queueing)
- Key Rotation: Round-robin load balancing across all available KILO_API_KEY_1..N slots.
- Automatic Fallback: If any model fails/times out, immediately cascades to the next healthy model.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
import requests
from openai import OpenAI

from gateway.service.pool import squad

logger = logging.getLogger("supremeai.kilo_router")

# Routes to strictly avoid in production
EXCLUDED_MODELS = {
    "kilo-auto/free",
    "kilo-auto/efficient",
    "openrouter/free",
}


class KiloSmartFreeRouter:
    """Manages dedicated, verified zero-cost models on Kilo Gateway with multi-key rotation."""

    def __init__(self, cache_ttl_seconds: int = 1800, base_url: str = "https://ai-gateway.kilo.ai/api/v1"):
        self.base_url = base_url
        self.cache_ttl = cache_ttl_seconds
        self.last_fetch_time: float = 0.0
        self.cached_models: List[str] = []
        self._current_model_idx: int = 0

    def get_active_keys(self) -> List[str]:
        """Collects all healthy Kilo keys from the squad pool or environment."""
        keys: List[str] = []
        kilo_pool = squad.pools.get("kilo")
        if kilo_pool and kilo_pool.healthy_slots:
            keys = [slot.key for slot in kilo_pool.healthy_slots]

        if not keys:
            # Fallback to direct os.environ check
            for k, v in os.environ.items():
                if k.startswith("KILO_API_KEY_") or k.startswith("KILOCODE_API_KEY_"):
                    val = v.strip().strip("'\"")
                    if len(val) > 20 and val not in keys:
                        keys.append(val)

        return keys

    def refresh_free_models(self, force: bool = False) -> List[str]:
        """
        Queries Kilo Gateway for models with prompt==0 and completion==0,
        stripping blacklisted auto/openrouter routes.
        """
        now = time.time()
        if not force and self.cached_models and (now - self.last_fetch_time < self.cache_ttl):
            return self.cached_models

        active_keys = self.get_active_keys()
        if not active_keys:
            logger.warning("[KiloRouter] No active Kilo keys found to query models endpoint.")
            return self._fallback_models()

        token = active_keys[0]
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                reliable_free: List[str] = []

                for m in data:
                    model_id = m.get("id", "")
                    pricing = m.get("pricing", {})
                    is_zero_cost = (
                        str(pricing.get("prompt")) == "0" and
                        str(pricing.get("completion")) == "0"
                    )

                    # Only select zero-cost models and explicitly exclude auto / openrouter routing
                    if is_zero_cost:
                        if model_id in EXCLUDED_MODELS or model_id.startswith("openrouter/"):
                            continue
                        reliable_free.append(model_id)

                # Prioritize well-known high-performance coding/reasoning models
                priority_order = [
                    "reflection/beam-free",
                    "nvidia/nemotron-3.5-lightning:free",
                    "cohere/north-mini-code:free",
                    "nvidia/nemotron-3.5-super-vl:free",
                    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                    "nvidia/nemotron-3-ultra-550b-a55b:free",
                ]

                sorted_models: List[str] = []
                for p in priority_order:
                    if p in reliable_free:
                        sorted_models.append(p)
                        reliable_free.remove(p)
                sorted_models.extend(reliable_free)

                if sorted_models:
                    self.cached_models = sorted_models
                    self.last_fetch_time = now
                    logger.info(f"[KiloRouter] Discovered {len(self.cached_models)} dedicated free models.")
                    return self.cached_models
        except Exception as e:
            logger.error(f"[KiloRouter] Error fetching free models from gateway: {e}")

        return self._fallback_models()

    def _fallback_models(self) -> List[str]:
        if self.cached_models:
            return self.cached_models
        return [
            "reflection/beam-free",
            "nvidia/nemotron-3.5-lightning:free",
            "cohere/north-mini-code:free",
            "nvidia/nemotron-3.5-super-vl:free",
        ]

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Executes chat completion with round-robin key rotation and cross-model failover.
        """
        models = self.refresh_free_models()
        kilo_pool = squad.pools.get("kilo")

        last_error: Optional[Exception] = None

        # Try models in priority order
        for model in models:
            # Rotate key for this attempt
            key_slot = kilo_pool.get_next_key() if kilo_pool else None
            api_key = key_slot.key if key_slot else None

            if not api_key:
                active_keys = self.get_active_keys()
                api_key = active_keys[0] if active_keys else None

            if not api_key:
                raise RuntimeError("No active Kilo API keys available.")

            client = OpenAI(base_url=self.base_url, api_key=api_key)

            try:
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "timeout": timeout,
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens

                resp = client.chat.completions.create(**kwargs)
                return {
                    "content": resp.choices[0].message.content,
                    "model": model,
                    "key_slot": key_slot.name if key_slot else "direct",
                    "usage": getattr(resp, "usage", None),
                }
            except Exception as err:
                last_error = err
                logger.warning(f"[KiloRouter] Failed with model={model}: {err}. Trying next dedicated model...")
                if key_slot and hasattr(err, "status_code"):
                    kilo_pool.report_injury(key_slot, getattr(err, "status_code", 500))
                continue

        raise RuntimeError(f"All dedicated Kilo free models exhausted. Last error: {last_error}")


# Singleton instance for system-wide access
kilo_smart_router = KiloSmartFreeRouter()

