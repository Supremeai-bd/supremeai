"""
service/pool.py — Dynamic Load-Balanced Key Pool & Provider Orchestrator.

Core Doctrine:
- Zero hardcoding of key counts (handles 1, 12, 35, or 0 keys dynamically).
- Concurrent round-robin distribution over all currently healthy keys.
- Automatic injury/cooldown on HTTP 429/5xx, auto-healing when cooldown expires.
- Cross-provider failover: if all keys of a provider are on cooldown, automatically
  switches to the next available healthy provider.
- Model-aware tracking per slot so verified working models are prioritized.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("supremeai.pool")

# Cooldown durations in seconds
COOLDOWN_RATE_LIMIT = 60       # 429 Too Many Requests
COOLDOWN_SERVER_ERROR = 30     # 5xx Provider Outage
COOLDOWN_AUTH_ERROR = 600      # 401/403 Invalid or quota-exhausted key


@dataclass
class KeySlot:
    name: str                  # e.g., "GEMINI_API_KEY_3"
    key: str                   # actual secret token
    provider: str              # e.g., "gemini"
    cooldown_until: float = 0.0
    total_calls: int = 0
    total_errors: int = 0
    verified_model: Optional[str] = None
    ewma_latency_ms: float = 0.0

    @property
    def is_healthy(self) -> bool:
        return time.time() >= self.cooldown_until


def _is_valid_secret(val: str) -> bool:
    """Filter out dummy/placeholder values commonly populated in unconfigured vaults."""
    if not val or len(val) < 8:
        return False
    low = val.lower()
    if low in ("dummy", "unset", "none", "placeholder", "changeme", "undefined", "null"):
        return False
    if set(low) == {"x"} or low.startswith("x*"):
        return False
    return True


class ProviderKeyPool:
    """Manages the pool of keys for a single provider."""

    def __init__(self, provider: str, prefixes: List[str] | str):
        self.provider = provider
        if isinstance(prefixes, str):
            self.prefixes = [prefixes]
        else:
            self.prefixes = prefixes
        self.slots: List[KeySlot] = []
        self._index: int = 0
        self.discover_keys()

    def discover_keys(self) -> int:
        """Scan os.environ for keys matching ^PREFIX(_\\d+)?$ across all assigned prefixes."""
        found: List[Tuple[str, str]] = []

        for prefix in self.prefixes:
            pattern = re.compile(rf"^{prefix}(?:_.*)?$", re.IGNORECASE)
            for env_name, env_val in os.environ.items():
                val = env_val.strip().strip("'\"")
                if pattern.match(env_name) and _is_valid_secret(val):
                    # Exclude config vars like _MODEL, _BASE_URL, _URL
                    if not any(env_name.upper().endswith(s) for s in ["_MODEL", "_BASE_URL", "_URL"]):
                        if (env_name, val) not in found:
                            found.append((env_name, val))

        # Check comma-separated pools (e.g., GROQ_API_KEYS, OPENROUTER_API_KEYS)
        for prefix in self.prefixes:
            pool_env = f"{prefix}S"
            pool_val = os.environ.get(pool_env, "").strip().strip("'\"")
            if pool_val and "," in pool_val:
                for idx, token in enumerate(pool_val.split(",")):
                    t = token.strip().strip("'\"")
                    if _is_valid_secret(t):
                        entry_name = f"{pool_env}_POOL_{idx+1}"
                        if not any(f[1] == t for f in found):
                            found.append((entry_name, t))

        # Sort so ordering is deterministic
        found.sort(key=lambda x: x[0])
        self.slots = [
            KeySlot(name=name, key=val, provider=self.provider)
            for name, val in found
        ]
        self._index = 0
        logger.info(f"[{self.provider}] Discovered {len(self.slots)} key(s)")
        return len(self.slots)

    @property
    def total_count(self) -> int:
        return len(self.slots)

    @property
    def healthy_slots(self) -> List[KeySlot]:
        now = time.time()
        return [s for s in self.slots if s.cooldown_until <= now]

    def get_next_key(self) -> Optional[KeySlot]:
        """Latency-aware round-robin selection across currently healthy keys."""
        healthy = self.healthy_slots
        if not healthy:
            return None

        # Prefer untested healthy keys first via round-robin; for tested keys, prioritize lowest EWMA latency
        untested = [s for s in healthy if s.ewma_latency_ms <= 0]
        if untested:
            self._index = (self._index + 1) % len(untested)
            slot = untested[self._index]
        else:
            sorted_healthy = sorted(healthy, key=lambda s: s.ewma_latency_ms)
            slot = sorted_healthy[0]

        slot.total_calls += 1
        return slot

    def report_success(self, slot: KeySlot, latency_ms: float = 0.0):
        """Record successful call latency using Exponential Moving Average."""
        if latency_ms > 0:
            if slot.ewma_latency_ms <= 0:
                slot.ewma_latency_ms = float(latency_ms)
            else:
                slot.ewma_latency_ms = (slot.ewma_latency_ms * 0.7) + (float(latency_ms) * 0.3)

    def report_injury(self, slot: KeySlot, status_code: int):
        """Mark a key injured and put it on the cooldown bench."""
        slot.total_errors += 1
        if status_code == 429:
            duration = COOLDOWN_RATE_LIMIT
            reason = "rate_limit"
        elif status_code in (401, 403):
            duration = COOLDOWN_AUTH_ERROR
            reason = "auth_exhausted"
        elif status_code == 402:
            duration = COOLDOWN_AUTH_ERROR * 2
            reason = "payment_required"
        else:
            duration = COOLDOWN_SERVER_ERROR
            reason = "server_error"

        slot.cooldown_until = time.time() + duration
        logger.warning(
            f"[{self.provider}] Key {slot.name} injured ({reason}, HTTP {status_code}). "
            f"Benched for {duration}s."
        )


class FederationSquad:
    """The master team orchestrator managing all provider pools."""

    # Prioritized provider order: Groq, Gemini, and Perplexity lead for lowest response times
    DEFAULT_PROVIDER_ORDER = [
        "groq",
        "gemini",
        "sambanova",
        "perplexity",
        "openrouter",
        "openai",
        "mistral",
        "v0",
        "huggingface",
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
        """Discovers/reloads all keys across all configured providers."""
        for provider, prefixes in self.PREFIX_MAP.items():
            self.pools[provider] = ProviderKeyPool(provider, prefixes)

    def stats(self) -> dict:
        """Returns operational telemetry for MCP Control Tower and /health endpoint."""
        now = time.time()
        summary = {
            "total_providers": len(self.pools),
            "providers": {},
            "total_keys": 0,
            "total_healthy_keys": 0,
        }
        for name, pool in self.pools.items():
            healthy = pool.healthy_slots
            cooldown_count = len(pool.slots) - len(healthy)
            tested = [s.ewma_latency_ms for s in healthy if s.ewma_latency_ms > 0]
            avg_lat = round(sum(tested) / len(tested), 2) if tested else 0.0
            summary["providers"][name] = {
                "total": len(pool.slots),
                "healthy": len(healthy),
                "cooling_down": cooldown_count,
                "avg_latency_ms": avg_lat,
            }
            summary["total_keys"] += len(pool.slots)
            summary["total_healthy_keys"] += len(healthy)
        return summary

    def get_candidate_slots(self, preferred_provider: Optional[str] = None) -> List[Tuple[str, KeySlot]]:
        """
        Yields (provider, KeySlot) candidates to try.
        Starts with preferred_provider if healthy, then falls back to others in priority order.
        """
        order = list(self.DEFAULT_PROVIDER_ORDER)
        if preferred_provider and preferred_provider in order:
            order.remove(preferred_provider)
            order.insert(0, preferred_provider)

        candidates = []
        for p in order:
            pool = self.pools.get(p)
            if pool:
                slot = pool.get_next_key()
                if slot:
                    candidates.append((p, slot))
        return candidates

    def report_success(self, provider: str, slot: KeySlot, latency_ms: float = 0.0):
        """Record successful completion latency for the given slot."""
        pool = self.pools.get(provider)
        if pool:
            pool.report_success(slot, latency_ms)


# Singleton squad instance
squad = FederationSquad()
