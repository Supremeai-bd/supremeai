"""
service/pool.py — Dynamic Load-Balanced Key Pool & Provider Orchestrator.

Selection is adaptive: healthy keys compete using observed latency, remaining
configured free-tier budget, and recent failures. Provider order is retained
only as a discovery set for compatibility; it is not a routing priority.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .adaptive_routing import RouteSnapshot, is_valid_secret, route_score

logger = logging.getLogger("supremeai.pool")

COOLDOWN_RATE_LIMIT = 60
COOLDOWN_SERVER_ERROR = 30
COOLDOWN_AUTH_ERROR = 600


@dataclass
class KeySlot:
    name: str
    key: str
    provider: str
    cooldown_until: float = 0.0
    total_calls: int = 0
    total_errors: int = 0
    verified_model: Optional[str] = None
    ewma_latency_ms: float = 0.0
    free_limit: Optional[int] = None
    remaining_free: Optional[int] = None
    consecutive_failures: int = 0

    @property
    def is_healthy(self) -> bool:
        return (
            time.time() >= self.cooldown_until
            and (self.remaining_free is None or self.remaining_free > 0)
        )


class ProviderKeyPool:
    """Manages keys for one provider and their adaptive free-tier state."""

    def __init__(self, provider: str, prefixes: List[str] | str):
        self.provider = provider
        self.prefixes = [prefixes] if isinstance(prefixes, str) else prefixes
        self.slots: List[KeySlot] = []
        self._index = 0
        self.discover_keys()

    def _configured_free_limit(self) -> Optional[int]:
        for env_name in (
            f"SUPREMEAI_FREE_LIMIT_{self.provider.upper()}",
            f"FREE_TIER_LIMIT_{self.provider.upper()}",
        ):
            raw = os.getenv(env_name, "").strip()
            if raw:
                try:
                    return max(0, int(raw))
                except ValueError:
                    logger.warning("Ignoring invalid free-tier limit %s", env_name)
        return None

    def discover_keys(self) -> int:
        found: List[Tuple[str, str]] = []
        for prefix in self.prefixes:
            pattern = re.compile(rf"^{prefix}(?:_.*)?$", re.IGNORECASE)
            for env_name, env_val in os.environ.items():
                val = env_val.strip().strip("'\"")
                if pattern.match(env_name) and is_valid_secret(val):
                    if not any(env_name.upper().endswith(s) for s in ("_MODEL", "_BASE_URL", "_URL")):
                        if (env_name, val) not in found:
                            found.append((env_name, val))

        for prefix in self.prefixes:
            pool_env = f"{prefix}S"
            pool_val = os.environ.get(pool_env, "").strip().strip("'\"")
            if pool_val and "," in pool_val:
                for idx, token in enumerate(pool_val.split(",")):
                    token = token.strip().strip("'\"")
                    if is_valid_secret(token) and not any(item[1] == token for item in found):
                        found.append((f"{pool_env}_POOL_{idx + 1}", token))

        found.sort(key=lambda item: item[0])
        limit = self._configured_free_limit()
        self.slots = [
            KeySlot(name=name, key=value, provider=self.provider, free_limit=limit, remaining_free=limit)
            for name, value in found
        ]
        self._index = 0
        logger.info("[%s] Discovered %s key(s)", self.provider, len(self.slots))
        return len(self.slots)

    @property
    def total_count(self) -> int:
        return len(self.slots)

    @property
    def healthy_slots(self) -> List[KeySlot]:
        return [slot for slot in self.slots if slot.is_healthy]

    def get_next_key(self) -> Optional[KeySlot]:
        """Compatibility helper returning the best currently healthy key."""
        healthy = self.healthy_slots
        if not healthy:
            return None
        return max(
            healthy,
            key=lambda slot: route_score(RouteSnapshot(
                name=slot.name,
                latency_ms=slot.ewma_latency_ms,
                remaining=slot.remaining_free,
                limit=slot.free_limit,
                failures=slot.consecutive_failures,
            )),
        )

    def report_success(self, slot: KeySlot, latency_ms: float = 0.0):
        if latency_ms > 0:
            if slot.ewma_latency_ms <= 0:
                slot.ewma_latency_ms = float(latency_ms)
            else:
                slot.ewma_latency_ms = (slot.ewma_latency_ms * 0.7) + (float(latency_ms) * 0.3)
        slot.consecutive_failures = 0
        if slot.remaining_free is not None:
            slot.remaining_free = max(0, slot.remaining_free - 1)

    def report_injury(self, slot: KeySlot, status_code: int):
        slot.total_errors += 1
        slot.consecutive_failures += 1
        if status_code == 429:
            duration, reason = COOLDOWN_RATE_LIMIT, "rate_limit"
        elif status_code in (401, 403):
            duration, reason = COOLDOWN_AUTH_ERROR, "auth_exhausted"
        elif status_code == 402:
            duration, reason = COOLDOWN_AUTH_ERROR * 2, "payment_required"
        else:
            duration, reason = COOLDOWN_SERVER_ERROR, "server_error"
        slot.cooldown_until = time.time() + duration
        if status_code == 429 and slot.remaining_free is not None:
            slot.remaining_free = 0
        logger.warning(
            "[%s] Key %s injured (%s, HTTP %s). Benched for %ss.",
            self.provider, slot.name, reason, status_code, duration,
        )


class FederationSquad:
    """Master orchestrator for all discovered provider key pools."""

    # Discovery set only. get_candidate_slots ranks all healthy keys by score.
    DEFAULT_PROVIDER_ORDER = [
        "groq", "gemini", "sambanova", "perplexity", "openrouter", "openai",
        "mistral", "v0", "huggingface",
    ]

    PREFIX_MAP: Dict[str, List[str]] = {
        "groq": ["GROQ_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "JULES_API_KEY"],
        "sambanova": ["SAMBANOVA_API_KEY"],
        "kilo": ["KILO_API_KEY", "KILOCODE_API_KEY", "KILO_API_KEYS"],
        "perplexity": ["PERPLEXITY_API_KEY", "PPLX_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "manus": ["MANUS_API_KEY", "MANUS_API_KEYS"],
        "v0": ["V0_API_KEY"],
        "huggingface": ["HF_API_KEY", "HUGGINGFACE_API_KEY"],
    }

    def __init__(self):
        self.pools: Dict[str, ProviderKeyPool] = {}
        self.reload_squad()

    def reload_squad(self):
        for provider, prefixes in self.PREFIX_MAP.items():
            self.pools[provider] = ProviderKeyPool(provider, prefixes)

    def stats(self) -> dict:
        summary = {"total_providers": len(self.pools), "providers": {}, "total_keys": 0, "total_healthy_keys": 0}
        for name, pool in self.pools.items():
            healthy = pool.healthy_slots
            tested = [slot.ewma_latency_ms for slot in healthy if slot.ewma_latency_ms > 0]
            summary["providers"][name] = {
                "total": len(pool.slots),
                "healthy": len(healthy),
                "cooling_down": len(pool.slots) - len(healthy),
                "avg_latency_ms": round(sum(tested) / len(tested), 2) if tested else 0.0,
                "remaining_free": (
                    sum(slot.remaining_free for slot in healthy if slot.remaining_free is not None)
                    if any(slot.remaining_free is not None for slot in healthy)
                    else None
                ),
            }
            summary["total_keys"] += len(pool.slots)
            summary["total_healthy_keys"] += len(healthy)
        return summary

    def get_candidate_slots(self, preferred_provider: Optional[str] = None) -> List[Tuple[str, KeySlot]]:
        """Return healthy keys ranked by latency, free quota and failures."""
        candidates: List[Tuple[str, KeySlot]] = []
        for provider in self.DEFAULT_PROVIDER_ORDER:
            pool = self.pools.get(provider)
            if pool:
                candidates.extend((provider, slot) for slot in pool.healthy_slots)
        if preferred_provider and preferred_provider not in ("auto", ""):
            candidates = [item for item in candidates if item[0] == preferred_provider]
        ranked = sorted(
            candidates,
            key=lambda item: route_score(RouteSnapshot(
                name=item[1].name,
                latency_ms=item[1].ewma_latency_ms,
                remaining=item[1].remaining_free,
                limit=item[1].free_limit,
                failures=item[1].consecutive_failures,
            )),
            reverse=True,
        )
        return ranked

    def report_success(self, provider: str, slot: KeySlot, latency_ms: float = 0.0):
        pool = self.pools.get(provider)
        if pool:
            pool.report_success(slot, latency_ms)


squad = FederationSquad()
