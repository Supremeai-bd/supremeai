"""Legacy dual-pool ranking and telemetry model (does not perform I/O).

Combines `supremeai-api` (API Key pools) and `supremeai-web` (Stealth Webhooks &
Web Session bridges) into a single pre-ranked Priority List:
- Zero per-message latency check overhead (reads pre-ranked list).
- Task-Fit capability filtering + Lowest Latency priority.
- Multi-key rotation per model before demoting a model.
- Instant Rank-2 -> Rank-1 promotion on 429/402/403 or latency spike.
- Recheck against caller-supplied observations only.
- Safe Admin Dashboard telemetry snapshot (never exposes raw secrets).
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class KeySlot:
    """Single API key or webhook credential slot inside a model's pool."""

    alias: str
    env_key: str
    healthy: bool = True
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    last_status: int = 200


@dataclass
class PoolModelEntry:
    """Represents one of the 6 models across supremeai-api and supremeai-web."""

    model_id: str
    provider: str
    pool: str  # "supremeai-api" | "supremeai-web"
    capabilities: tuple[str, ...]  # e.g. ("reasoning", "spark", "design", "general")
    active_model_name: str
    latency_ms: float = 1000.0
    status: str = "STANDBY"  # ACTIVE_TOP | STANDBY | RATE_LIMITED | LATENCY_SPIKE | OFFLINE
    reason: str = "Initialized"
    keys: list[KeySlot] = field(default_factory=list)
    _rr_index: int = 0

    def healthy_keys(self, now: float) -> list[KeySlot]:
        return [k for k in self.keys if k.healthy and k.cooldown_until <= now]

    def next_healthy_key(self, now: float) -> KeySlot | None:
        healthy = self.healthy_keys(now)
        if not healthy:
            return None
        slot = healthy[self._rr_index % len(healthy)]
        self._rr_index = (self._rr_index + 1) % len(healthy)
        return slot


ProbeFn = Callable[[PoolModelEntry, KeySlot], tuple[bool, float, int, str | None]]


class DualPoolPriorityRouter:
    """Pre-ranked 6-Model Dual-Pool Router with Multi-Key Rotation & Live Telemetry."""

    LATENCY_SPIKE_MS = 2500.0
    COOLDOWN_SECONDS = 300.0

    def __init__(
        self,
        models: list[PoolModelEntry] | None = None,
        clock: Callable[[], float] = time.time,
        max_events: int = 50,
    ) -> None:
        self._clock = clock
        self._models: list[PoolModelEntry] = models if models is not None else self._default_models_from_env()
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._recompute_ranks()

    @staticmethod
    def _scan_keys(prefixes: tuple[str, ...], src: dict[str, str]) -> list[KeySlot]:
        slots: list[KeySlot] = []
        for env_name, val in sorted(src.items()):
            if not val or len(val.strip()) < 4:
                continue
            if any(env_name == p or env_name.startswith(p + "_") for p in prefixes):
                slots.append(KeySlot(alias=env_name.lower(), env_key=env_name))
        return slots

    @staticmethod
    def _scan_web_keys(
        bundle_names: tuple[str, ...],
        individual_names: tuple[str, ...],
        src: dict[str, str],
    ) -> list[KeySlot]:
        """Key slots for a web (stealth/cookie) model.

        Prefers the unified cookie bundle (SSOT, e.g. AI_FLEET_COOKIES_GZIP_B64 /
        SUPREMEAI_GEMINI_COOKIES) so renewing one secret updates every web model,
        and falls back to the legacy individual token env vars for backward compat.
        """
        slots: list[KeySlot] = []
        for name in bundle_names:
            if (src.get(name) or "").strip():
                slots.append(KeySlot(alias=name.lower(), env_key=name))
                break
        for name in individual_names:
            if (src.get(name) or "").strip() and all(s.env_key != name for s in slots):
                slots.append(KeySlot(alias=name.lower(), env_key=name))
        return slots

    def _default_models_from_env(self) -> list[PoolModelEntry]:
        src = dict(os.environ)
        return [
            PoolModelEntry(
                model_id="api-spark",
                provider="groq_cerebras",
                pool="supremeai-api",
                capabilities=("spark", "general"),
                active_model_name="qwen/qwen3.8-27b",
                latency_ms=380.0,
                keys=self._scan_keys(("CEREBRAS_API_KEY", "GROQ_API_KEY"), src),
            ),
            PoolModelEntry(
                model_id="api-multimodal",
                provider="gemini",
                pool="supremeai-api",
                capabilities=("spark", "general", "design"),
                active_model_name="gemini-flash-lite-latest",
                latency_ms=950.0,
                keys=self._scan_keys(("GEMINI_API_KEY", "GOOGLE_API_KEY"), src),
            ),
            PoolModelEntry(
                model_id="api-reasoning",
                provider="openrouter_kilo",
                pool="supremeai-api",
                capabilities=("reasoning", "general"),
                active_model_name="nvidia/nemotron-3.5-lightning:free",
                latency_ms=650.0,
                keys=self._scan_keys(("OPENROUTER_API_KEY", "KILO_API_KEY", "KILOCODE_API_KEY"), src),
            ),
            PoolModelEntry(
                model_id="web-architect",
                provider="claude_web",
                pool="supremeai-web",
                capabilities=("reasoning", "design"),
                active_model_name="core-architect",
                latency_ms=1400.0,
                keys=self._scan_web_keys(
                    bundle_names=("AI_FLEET_COOKIES_GZIP_B64",),
                    individual_names=("STEALTH_WEBHOOK_URL", "BLAZE_SESSION_JWT"),
                    src=src,
                ),
            ),
            PoolModelEntry(
                model_id="web-logic",
                provider="chatgpt_web",
                pool="supremeai-web",
                capabilities=("reasoning", "general"),
                active_model_name="core-logic",
                latency_ms=1200.0,
                keys=self._scan_web_keys(
                    bundle_names=("AI_FLEET_COOKIES_GZIP_B64",),
                    individual_names=("CHATGPT_WEB_TOKEN", "CHATGPT_SESSION_TOKEN"),
                    src=src,
                ),
            ),
            PoolModelEntry(
                model_id="web-speed",
                provider="gemini_v0_web",
                pool="supremeai-web",
                capabilities=("spark", "design"),
                active_model_name="core-speed",
                latency_ms=1100.0,
                keys=self._scan_web_keys(
                    bundle_names=("AI_FLEET_COOKIES_GZIP_B64", "SUPREMEAI_GEMINI_COOKIES"),
                    individual_names=("GEMINI_WEB_TOKEN", "V0_TOKEN"),
                    src=src,
                ),
            ),
        ]

    def _record_event(self, message: str) -> None:
        self._events.appendleft({"ts": self._clock(), "message": message})

    def _recompute_ranks(self) -> None:
        now = self._clock()

        def sort_key(m: PoolModelEntry) -> tuple[int, float]:
            has_healthy = len(m.healthy_keys(now)) > 0
            is_available = has_healthy and m.status not in ("RATE_LIMITED", "OFFLINE")
            tier_penalty = 0 if is_available else (1 if m.status == "LATENCY_SPIKE" else 2)
            return (tier_penalty, m.latency_ms)

        self._models.sort(key=sort_key)
        for idx, m in enumerate(self._models):
            if idx == 0 and m.status not in ("RATE_LIMITED", "OFFLINE"):
                m.status = "ACTIVE_TOP"
            elif m.status == "ACTIVE_TOP":
                m.status = "STANDBY"

    def select_best_model(self, task_type: str = "general") -> tuple[PoolModelEntry, KeySlot] | None:
        """Zero-overhead selection from the pre-ranked Priority List (exact task-fit first)."""
        now = self._clock()
        raw_task = task_type.lower().strip()
        if "spark" in raw_task or "fast" in raw_task:
            task = "spark"
        elif "reason" in raw_task or "deep" in raw_task:
            task = "reasoning"
        elif "design" in raw_task or "web" in raw_task:
            task = "design"
        elif "general" in raw_task or "core" in raw_task:
            task = "general"
        else:
            task = raw_task
        fallback: tuple[PoolModelEntry, KeySlot] | None = None
        for m in self._models:
            if m.status in ("RATE_LIMITED", "OFFLINE"):
                continue
            slot = m.next_healthy_key(now)
            if slot is None:
                continue
            if task in m.capabilities:
                return m, slot
            if fallback is None and "general" in m.capabilities:
                fallback = (m, slot)
        return fallback

    def report_outcome(
        self,
        model_id: str,
        key_alias: str,
        success: bool,
        latency_ms: float,
        status_code: int = 200,
    ) -> None:
        """Updates key/model health and triggers instant Rank-2 promotion on failure/spike."""
        now = self._clock()
        model = next((m for m in self._models if m.model_id == model_id), None)
        if model is None:
            return
        slot = next((k for k in model.keys if k.alias == key_alias), None)

        if success and status_code == 200:
            if slot:
                slot.healthy = True
                slot.consecutive_failures = 0
                slot.last_status = 200
            model.latency_ms = round(latency_ms, 1)
            if latency_ms > self.LATENCY_SPIKE_MS:
                model.status = "LATENCY_SPIKE"
                model.reason = f"Latency spike ({model.latency_ms}ms)"
                self._record_event(f"{model.model_id} demoted: {model.reason}")
            else:
                model.status = "STANDBY"
                model.reason = f"Healthy ({model.latency_ms}ms)"
        else:
            if slot:
                slot.last_status = status_code
                slot.consecutive_failures += 1
                if status_code in (402, 403, 429):
                    slot.healthy = False
                    slot.cooldown_until = now + self.COOLDOWN_SECONDS
            if len(model.healthy_keys(now)) == 0:
                model.status = "RATE_LIMITED"
                model.reason = f"All {len(model.keys)} keys exhausted ({status_code})"
                self._record_event(f"{model.model_id} exhausted ({status_code}) -> promoted next healthy model")
            else:
                self._record_event(f"{model.model_id} rotated key ({key_alias} hit {status_code})")

        self._recompute_ranks()

        # Cross-router bridge: sync true latency and health directly to FederationSquad
        try:
            from gateway.service.pool import squad
            if squad:
                env_secret = os.getenv(slot.env_key) if slot else ""
                for prov_name, p_pool in squad.pools.items():
                    for s in p_pool.slots:
                        if s.name == key_alias or (env_secret and s.key == env_secret):
                            if success and status_code == 200:
                                squad.report_success(prov_name, s, latency_ms)
                            else:
                                p_pool.report_injury(s, status_code, latency_ms)
        except Exception:
            pass

    def run_background_recheck(self, probe_fn: ProbeFn) -> None:
        """Periodically probes models; recovered models automatically climb back to the top."""
        now = self._clock()
        for m in self._models:
            # Reset expired cooldowns before probing
            for k in m.keys:
                if not k.healthy and k.cooldown_until <= now:
                    k.healthy = True
                    k.consecutive_failures = 0
            slot = m.next_healthy_key(now)
            if slot is None:
                continue
            ok, latency_ms, status_code, discovered_model = probe_fn(m, slot)
            if ok:
                if discovered_model:
                    m.active_model_name = discovered_model
                self.report_outcome(m.model_id, slot.alias, True, latency_ms, status_code)
            else:
                self.report_outcome(m.model_id, slot.alias, False, latency_ms, status_code)
        self._recompute_ranks()

    def get_live_telemetry(self) -> dict[str, Any]:
        """Safe Admin Dashboard telemetry snapshot (zero raw secrets)."""
        now = self._clock()
        return {
            "priority_list": [
                {
                    "rank": idx + 1,
                    "model_id": m.model_id,
                    "provider": m.provider,
                    "pool": m.pool,
                    "active_model": m.active_model_name,
                    "capabilities": list(m.capabilities),
                    "status": m.status,
                    "latency_ms": m.latency_ms,
                    "reason": m.reason,
                }
                for idx, m in enumerate(self._models)
            ],
            "key_pool_health": {
                m.model_id: {
                    "total_keys": len(m.keys),
                    "healthy_keys": len(m.healthy_keys(now)),
                    "cooldown_keys": len(m.keys) - len(m.healthy_keys(now)),
                }
                for m in self._models
            },
            "recent_events": list(self._events),
        }


_ROUTER_SINGLETON: DualPoolPriorityRouter | None = None


def get_dual_pool_router() -> DualPoolPriorityRouter:
    """Return the process-wide DualPoolPriorityRouter singleton."""
    global _ROUTER_SINGLETON
    if _ROUTER_SINGLETON is None:
        _ROUTER_SINGLETON = DualPoolPriorityRouter()
    return _ROUTER_SINGLETON
