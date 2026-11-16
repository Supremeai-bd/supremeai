"""SupremeAI 6-Model Dual-Pool Priority Router & Live Telemetry Engine.

Combines `supremeai-api` (API Key pools) and `supremeai-web` (Stealth Webhooks &
Web Session bridges) into a single pre-ranked Priority List:
- Zero per-message latency check overhead (reads pre-ranked list).
- Task-Fit capability filtering + Lowest Latency priority.
- Multi-key rotation per model before demoting a model.
- Instant Rank-2 -> Rank-1 promotion on 429/402/403 or latency spike.
- Background recheck & auto-recovery back to the top.
- Safe Admin Dashboard telemetry snapshot (never exposes raw secrets).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
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
                active_model_name="gemini-2.5-flash",
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
                keys=self._scan_keys(("STEALTH_WEBHOOK_URL", "BLAZE_SESSION_JWT"), src),
            ),
            PoolModelEntry(
                model_id="web-logic",
                provider="chatgpt_web",
                pool="supremeai-web",
                capabilities=("reasoning", "general"),
                active_model_name="core-logic",
                latency_ms=1200.0,
                keys=self._scan_keys(("CHATGPT_WEB_TOKEN", "CHATGPT_SESSION_TOKEN"), src),
            ),
            PoolModelEntry(
                model_id="web-speed",
                provider="gemini_v0_web",
                pool="supremeai-web",
                capabilities=("spark", "design"),
                active_model_name="core-speed",
                latency_ms=1100.0,
                keys=self._scan_keys(("GEMINI_WEB_TOKEN", "V0_TOKEN"), src),
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
        task = task_type.lower().strip()
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
                was_demoted = m.status in ("RATE_LIMITED", "LATENCY_SPIKE", "OFFLINE")
                m.latency_ms = round(latency_ms, 1)
                m.status = "STANDBY"
                m.reason = f"Recovered ({m.latency_ms}ms)" if was_demoted else f"Healthy ({m.latency_ms}ms)"
                if was_demoted:
                    self._record_event(f"{m.model_id} recovered ({m.latency_ms}ms) -> re-ranked")
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


def _probe_url_for(model: PoolModelEntry, slot: KeySlot, secret: str) -> tuple[str, dict[str, str]]:
    if model.provider == "gemini":
        return f"https://generativelanguage.googleapis.com/v1beta/models?key={secret}", {}
    if model.provider == "openrouter_kilo":
        if slot.env_key.startswith("KILO"):
            return "https://api.kilocode.ai/api/openrouter/models", {"Authorization": f"Bearer {secret}"}
        return "https://openrouter.ai/api/v1/models", {"Authorization": f"Bearer {secret}"}
    if model.provider == "groq_cerebras":
        if slot.env_key.startswith("CEREBRAS"):
            return "https://api.cerebras.ai/v1/models", {"Authorization": f"Bearer {secret}"}
        return "https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {secret}"}
    if model.pool == "supremeai-web":
        url = os.getenv("STEALTH_WEBHOOK_URL", "").strip()
        headers = {"X-Stealth-Secret": os.getenv("STEALTH_WEBHOOK_SECRET", "")}
        return (url.rstrip("/") + "/health") if url else ("", {}), headers
    return "", {}


def live_http_probe(model: PoolModelEntry, slot: KeySlot, timeout: float = 5.0) -> tuple[bool, float, int, str | None]:
    """Real HTTP live probe for `/models` or stealth webhook health + latency."""
    secret = os.getenv(slot.env_key, "").strip()
    if not secret:
        return False, model.latency_ms, 401, None
    url, headers = _probe_url_for(model, slot, secret)
    if not url:
        return False, model.latency_ms, 0, None

    started = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "SupremeAI-Prober/1.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.monotonic() - started) * 1000.0, 1)
            status = getattr(resp, "status", 200)
            discovered: str | None = None
            if model.provider == "openrouter_kilo" and status == 200:
                data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
                for item in data.get("data", []):
                    mid = item.get("id", "")
                    if mid.endswith(":free"):
                        discovered = mid
                        break
            return 200 <= status < 300, latency_ms, status, discovered
    except urllib.error.HTTPError as exc:
        return False, round((time.monotonic() - started) * 1000.0, 1), exc.code, None
    except Exception:
        return False, round((time.monotonic() - started) * 1000.0, 1), 0, None


async def start_background_recheck_loop(interval_seconds: float = 900.0) -> None:
    """Background scheduler: re-probes all 6 models every 15 minutes without blocking."""
    router = get_dual_pool_router()
    while True:
        await asyncio.to_thread(router.run_background_recheck, live_http_probe)
        await asyncio.sleep(interval_seconds)
