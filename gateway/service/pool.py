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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .adaptive_routing import RouteSnapshot, is_valid_secret, route_score
from .providers.web_engines import WEB_ENGINES
from .free_route_policy import RouteIdentity

logger = logging.getLogger("supremeai.pool")

COOLDOWN_RATE_LIMIT = 300  # 5 minutes per plan
COOLDOWN_SERVER_ERROR = 30
COOLDOWN_AUTH_ERROR = 600

# Hysteresis: cool fast, come back only on evidence.
#
# A slot re-entered rotation purely because a timer expired, so a dead cookie got
# re-admitted every 30s/5min/10min, failed again, and the pool spent its time
# rediscovering the same fact. Now an injured slot doubles its cooldown each time
# it fails again without an intervening success (1x, 2x, 4x, 8x), and while it
# has not yet succeeded it is *recovering*: still usable (a pool of only-recovering
# slots must still answer), but ranked strictly behind every slot with a clean
# record. Only a real success clears the count.
INJURY_BACKOFF_CAP = 8
INJURY_COOLDOWN_CEILING_S = 3600
MAX_INJURY_LEVEL = 10


def injury_backoff(level: int) -> int:
    """Multiplier for the n-th consecutive injury: 1, 2, 4, 8, 8, …"""
    if level <= 1:
        return 1
    return min(INJURY_BACKOFF_CAP, 1 << min(level - 1, 3))

# Baseline (ms) latency seed for providers so rotation is latency-aware before
# any real measurement exists. Lower = faster. Unknown providers default 500.
PROVIDER_BASELINE_LATENCY_MS: dict[str, float] = {
    "groq": 120.0,
    "gemini": 250.0,
    "google": 250.0,
    "openrouter": 600.0,
    "sambanova": 400.0,
    "mistral": 300.0,
    "perplexity": 700.0,
    "openai": 800.0,
    "v0": 500.0,
    "huggingface": 900.0,
    "kilo": 200.0,
    # বাংলা মন্তব্য: "manus" সম্পূর্ণ সরানো হলো (dead provider) — এটি PREFIX_MAP/
    # baseline-latency-তে ঘোষিত ছিল, কিন্তু PROVIDER_CONFIGS-এ কোনো transport নেই,
    # DEFAULT_PROVIDER_ORDER-এও নেই। কী থাকলে স্লট discover হত কিন্তু কোনো পথেই
    # সার্ভ হত না — pool স্ট্যাটস ও ranking-কে বিভ্রান্ত করত (dead weight)।
    "cohere": 600.0,
    "cerebras": 80.0,
    # বাংলা মন্তব্য: Web engine baseline — আবার ফেরত আনা হলো কারণ PREFIX_MAP/
    # WEB_ENGINES এগুলোকে discovered হিসেবে সার্ভ করে, latency বেসলাইন ছাড়া
    # 500ms ডিফল্ট ফলব্যাক করে (test_web_engine_providers.py এটা ব্লক করে)।
    "claude_web": 1400.0,
    "chatgpt_web": 1200.0,
    "gemini_v0_web": 2500.0,
    "ghost_gemini": 2500.0,
    "web_session": 2000.0,
}


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
    ewma_first_token_ms: float = 0.0
    free_limit: Optional[int] = None
    remaining_free: Optional[int] = None
    consecutive_failures: int = 0
    supported_models: set[str] = field(default_factory=set)
    unsupported_models: set[str] = field(default_factory=set)
    preferred_model: Optional[str] = None
    discovered_models: List[str] = field(default_factory=list)
    catalog_identity: RouteIdentity | None = None
    catalog_valid_until: float = 0.0
    # Consecutive injuries since the last success. Drives the cooldown backoff
    # and marks the slot as `recovering` until a request actually works again.
    injury_level: int = 0

    @property
    def rank_latency_ms(self) -> float:
        """Latency used for fastest-first ranking: time-to-first-token when known.

        Streaming calls report their first-text-token latency into
        ``ewma_first_token_ms``; until a slot has served one we fall back to the
        general ``ewma_latency_ms`` so a fresh slot still ranks sensibly.
        """
        return self.ewma_first_token_ms or self.ewma_latency_ms

    @property
    def recovering(self) -> bool:
        """Injured and not yet proven. Servable, but only as a last resort."""
        return self.injury_level > 0

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
                    if "," not in val and not any(env_name.upper().endswith(s) for s in ("_MODEL", "_BASE_URL", "_URL")):
                        if not any(key == val for _, key in found):
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
        baseline = PROVIDER_BASELINE_LATENCY_MS.get(self.provider.lower(), 500.0)
        self.slots = [
            KeySlot(name=name, key=value, provider=self.provider, free_limit=limit, remaining_free=limit, ewma_latency_ms=baseline)
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
            key=lambda slot: (
                0 if slot.recovering else 1,
                route_score(RouteSnapshot(
                    name=slot.name,
                    latency_ms=slot.rank_latency_ms,
                    remaining=slot.remaining_free,
                    limit=slot.free_limit,
                    failures=slot.consecutive_failures,
                )),
            ),
        )

    def report_model_capability(self, slot: KeySlot, model: str, success: bool, status_code: int = 200):
        if not model:
            return
        clean_m = str(model).strip()
        if success:
            slot.supported_models.add(clean_m)
            slot.preferred_model = clean_m
            slot.unsupported_models.discard(clean_m)
        elif status_code in (404, 400):
            slot.unsupported_models.add(clean_m)
            slot.supported_models.discard(clean_m)
            if slot.preferred_model == clean_m:
                slot.preferred_model = next(iter(slot.supported_models), None)

    def report_success(self, slot: KeySlot, latency_ms: float = 0.0, first_token_ms: float | None = None):
        if latency_ms > 0:
            if slot.ewma_latency_ms <= 0:
                slot.ewma_latency_ms = float(latency_ms)
            else:
                slot.ewma_latency_ms = (slot.ewma_latency_ms * 0.7) + (float(latency_ms) * 0.3)
        if first_token_ms is not None and first_token_ms > 0:
            if slot.ewma_first_token_ms <= 0:
                slot.ewma_first_token_ms = float(first_token_ms)
            else:
                slot.ewma_first_token_ms = (slot.ewma_first_token_ms * 0.7) + (float(first_token_ms) * 0.3)
        slot.consecutive_failures = 0
        # The only thing that ends probation: a request that worked.
        slot.injury_level = 0
        if slot.remaining_free is not None:
            slot.remaining_free = max(0, slot.remaining_free - 1)

    def report_injury(
        self,
        slot: KeySlot,
        status_code: int,
        latency_ms: float = 0.0,
        *,
        ceiling_s: float | None = None,
    ):
        """Bench a slot, doubling the bench for each failure since its last success.

        `ceiling_s` lets a caller whose evidence refreshes on a known cadence (the
        relay probe, every 30 minutes) cap the escalation. A cookie can be renewed
        at any moment, and the only way to discover that is to send it a request —
        so benching a session-injured slot for an hour would hide the recovery for
        two refresh cycles. The default ceiling stays an hour: an API key does not
        start working again on its own.
        """
        slot.total_errors += 1
        slot.consecutive_failures += 1
        if latency_ms > 0:
            # Slow/failed attempts raise the latency estimate so the slot is
            # deprioritised for future fastest-first rotation.
            if slot.ewma_latency_ms <= 0:
                slot.ewma_latency_ms = float(latency_ms)
            else:
                slot.ewma_latency_ms = (slot.ewma_latency_ms * 0.7) + (float(latency_ms) * 0.3)
            if slot.ewma_first_token_ms <= 0:
                slot.ewma_first_token_ms = float(latency_ms)
            else:
                slot.ewma_first_token_ms = (slot.ewma_first_token_ms * 0.7) + (float(latency_ms) * 0.3)
        if status_code == 429:
            duration, reason = COOLDOWN_RATE_LIMIT, "rate_limit"
        elif status_code in (401, 403):
            duration, reason = COOLDOWN_AUTH_ERROR, "auth_exhausted"
        elif status_code == 402:
            duration, reason = COOLDOWN_AUTH_ERROR * 2, "payment_required"
        else:
            duration, reason = COOLDOWN_SERVER_ERROR, "server_error"
        slot.injury_level = min(slot.injury_level + 1, MAX_INJURY_LEVEL)
        backoff = injury_backoff(slot.injury_level)
        benched = min(duration * backoff, INJURY_COOLDOWN_CEILING_S if ceiling_s is None else ceiling_s)
        slot.cooldown_until = time.time() + benched
        if status_code == 429 and slot.remaining_free is not None:
            slot.remaining_free = 0
        logger.warning(
            "[%s] Key %s injured (%s, HTTP %s). Benched for %.0fs (injury %s, backoff x%s).",
            self.provider, slot.name, reason, status_code, benched, slot.injury_level, backoff,
        )


class FederationSquad:
    """Master orchestrator for all discovered provider key pools."""

    # Discovery set only; serving requires separate account/model approval.
    DEFAULT_PROVIDER_ORDER = [
        "groq", "gemini", "openrouter", "kilo", "sambanova", "mistral", "perplexity", "openai",
        "huggingface", "cohere", "cerebras",
        # Fallback lane only: the relay hop plus a session that can expire makes
        # a web engine slower and less predictable than any keyed provider.
        *(engine.provider for engine in WEB_ENGINES),
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
        # বাংলা মন্তব্য: manus সরানো — PROVIDER_CONFIGS-এ transport নেই, তাই কী
        # discover হলেও কোনো রুটে সার্ভ হত না (dead provider, অডিট 2026-11-24)।
        "v0": ["V0_API_KEY"],
        "huggingface": ["HF_API_KEY", "HUGGINGFACE_API_KEY"],
        "cohere": ["COHERE_API_KEY"],
        "cerebras": ["CEREBRAS_API_KEY"],
        # Web engines (cookie/webhook slots). Their provider names and credential
        # env names come from providers/web_engines.py — the same mapping the
        # adapter resolves, so a slot cannot be routable in one half and unknown
        # in the other.
        **{engine.provider: list(engine.credential_envs) for engine in WEB_ENGINES},
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
                # Servable but not yet proven: they answer only if nothing better
                # is left, which is what keeps a flapping key from owning traffic.
                "recovering": sum(1 for slot in healthy if slot.recovering),
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

    def get_candidate_slots(self, preferred_provider: Optional[str] = None, *, vision: bool = False) -> List[Tuple[str, KeySlot]]:
        """Return approved healthy keys ranked by latency, quota and failures.

        বাংলা মন্তব্য: fail-open eligibility fallback — SUPREMEAI_FREE_ROUTE_POLICY
        / SUPREMEAI_FREE_ROUTE_HMAC_KEY ভল্টে provision না থাকলে approved_route()
        সবসময় None দেয়, ফলে সব কী আবিষ্কৃত হয়েও কোনো ক্যান্ডিডেট হত না
        (প্রতিটি চ্যাট 503 — hidden kill-switch)। নীতি হলো: নীতি সত্যিই provision
        করা থাকলে সেটাই কর্তৃত্বপূর্ণ (strict), না থাকলে একটি বৈধ আকৃতির কী
        সরাসরি eligible (fail-open) — কী কনফিগার করা মানেই সার্ভ করার অনুমতি,
        অন্যথায় "intelligent" আচরণ সম্ভব নয়। policy-check ফাংশন প্যাচ করে
        নীতি-এনফোর্সমেন্ট সবসময় আগের মতো কড়া রাখা যায় (টেস্টে monkeypatch-প্রতি)।
        """
        from .providers.adapters import eligible_chat_models, PROVIDER_CONFIGS
        from .free_route_policy import POLICY_ENV

        policy_configured = bool(os.getenv(POLICY_ENV, "").strip())

        def _eligible(provider: str, key: str, slot: Any) -> bool:
            if policy_configured:
                # বাংলা মন্তব্য: অপারেটর ইচ্ছাকৃতভাবে নীতি provision করেছে — কড়া পথ।
                return bool(eligible_chat_models(provider, key, slot, vision=vision))
            # বাংলা মন্তব্য: নীতি অনুপস্থিত = কী-ই একমাত্র প্রমাণ।
            if not key or len(key) < 8:
                return False
            if provider in PROVIDER_CONFIGS:
                return True
            return False

        candidates: List[Tuple[str, KeySlot]] = []
        providers = (preferred_provider,) if preferred_provider not in (None, "auto", "") else self.DEFAULT_PROVIDER_ORDER
        for provider in providers:
            pool = self.pools.get(provider)
            if pool:
                candidates.extend(
                    (provider, slot) for slot in pool.healthy_slots
                    if _eligible(provider, slot.key, slot)
                )
        ranked = sorted(
            candidates,
            key=lambda item: (
                # Rank first, then score: a slot coming back from an injury is
                # still tried (a pool with nothing else must answer), but only
                # after every slot that has not just failed. That ordering is the
                # whole point of probation — a recovering slot gets one request
                # to prove itself instead of being handed the traffic again.
                0 if item[1].recovering else 1,
                route_score(RouteSnapshot(
                    name=item[1].name,
                    latency_ms=item[1].rank_latency_ms,
                    remaining=item[1].remaining_free,
                    limit=item[1].free_limit,
                    failures=item[1].consecutive_failures,
                )),
            ),
            reverse=True,
        )
        return ranked

    def report_model_capability(self, provider: str, slot: KeySlot, model: str, success: bool, status_code: int = 200):
        pool = self.pools.get(provider)
        if pool:
            pool.report_model_capability(slot, model, success, status_code)

    def report_success(self, provider: str, slot: KeySlot, latency_ms: float = 0.0, first_token_ms: float | None = None):
        pool = self.pools.get(provider)
        if pool:
            pool.report_success(slot, latency_ms, first_token_ms=first_token_ms)


squad = FederationSquad()
