"""Hybrid Top AI Detector: 30-min proactive latency/health probe + instant reactive failover.

.. deprecated:: 2026-11-19
   **Unused in production.** Nothing outside `tests/test_top_ai_detector.py`
   imports this module (verified repo-wide), so the live request path never
   consults it — while `gateway/provider_chain.py` now implements the same
   two-signal idea (proactive skip via `gateway/circuit_breaker.py` +
   reactive `record_failure`) *and* is actually wired into
   `execute_chain()`.

   Two implementations of the same policy is how the two diverge, so do not
   wire this one up. Either adopt it deliberately (replacing the breaker) or
   delete it with its test; `tests/test_top_ai_detector_deprecation.py` fails
   the day something starts importing it in production code, which is the
   signal to make that decision instead of silently growing a third path.

   Kept for now because its probe list is the only place the per-provider
   liveness URLs are written down.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROBE_INTERVAL_SECONDS = 1800  # 30 minutes
DEFAULT_COOLDOWN_SECONDS = 300  # 5 minutes on 429/5xx


@dataclass
class ProviderHealth:
    """Health and latency snapshot for a single AI provider."""

    provider_id: str
    configured: bool = False
    healthy: bool = False
    latency_ms: float = 9999.0
    last_checked_at: float = 0.0
    cooldown_until: float = 0.0
    last_error: str | None = None
    consecutive_errors: int = 0

    @property
    def is_available(self) -> bool:
        return self.configured and self.healthy and time.time() >= self.cooldown_until


# Default lightweight probe endpoints (minimal bandwidth, no token generation cost)
DEFAULT_PROBE_ENDPOINTS: dict[str, tuple[str, str]] = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1/models"),
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1/models"),
    "huggingface": ("HF_API_KEY", "https://huggingface.co/api/whoami-v2"),
    "cohere": ("COHERE_API_KEY", "https://api.cohere.ai/v1/models"),
}


class HybridTopAIDetector:
    """Maintains a ranked Top AI list via 30-min proactive probes and instant error demotion."""

    def __init__(
        self,
        probe_interval_seconds: int = PROBE_INTERVAL_SECONDS,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        custom_prober: Callable[[str, str], Awaitable[tuple[bool, float, str | None]]] | None = None,
    ) -> None:
        self.probe_interval_seconds = probe_interval_seconds
        self.cooldown_seconds = cooldown_seconds
        self._custom_prober = custom_prober
        self._providers: dict[str, ProviderHealth] = {}
        self._last_full_probe: float = 0.0
        self._lock = asyncio.Lock()

    def _get_api_key(self, env_var: str) -> str | None:
        val = os.getenv(env_var, "").strip()
        return val if val else None

    async def _probe_one(self, provider_id: str, env_var: str, url: str) -> ProviderHealth:
        api_key = self._get_api_key(env_var)
        if not api_key:
            return ProviderHealth(provider_id=provider_id, configured=False, healthy=False)

        if self._custom_prober is not None:
            ok, latency_ms, err = await self._custom_prober(provider_id, api_key)
            return ProviderHealth(
                provider_id=provider_id,
                configured=True,
                healthy=ok,
                latency_ms=latency_ms,
                last_checked_at=time.time(),
                last_error=err,
            )

        headers = {"Authorization": f"Bearer {api_key}"}
        probe_url = f"{url}?key={api_key}" if provider_id == "gemini" else url
        if provider_id == "gemini":
            headers = {}

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(probe_url, headers=headers)
            latency_ms = (time.perf_counter() - start) * 1000.0
            if resp.status_code == 200:
                return ProviderHealth(
                    provider_id=provider_id,
                    configured=True,
                    healthy=True,
                    latency_ms=round(latency_ms, 2),
                    last_checked_at=time.time(),
                )
            return ProviderHealth(
                provider_id=provider_id,
                configured=True,
                healthy=False,
                latency_ms=round(latency_ms, 2),
                last_checked_at=time.time(),
                last_error=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return ProviderHealth(
                provider_id=provider_id,
                configured=True,
                healthy=False,
                latency_ms=round(latency_ms, 2),
                last_checked_at=time.time(),
                last_error=str(exc),
            )

    async def refresh_if_stale(self, force: bool = False) -> list[str]:
        """Run a proactive probe if 30 minutes have elapsed (or force=True)."""
        now = time.time()
        if not force and (now - self._last_full_probe) < self.probe_interval_seconds and self._providers:
            return self.get_top_providers()

        async with self._lock:
            now = time.time()
            if not force and (now - self._last_full_probe) < self.probe_interval_seconds and self._providers:
                return self.get_top_providers()

            tasks = [
                self._probe_one(pid, env_var, url)
                for pid, (env_var, url) in DEFAULT_PROBE_ENDPOINTS.items()
            ]
            results = await asyncio.gather(*tasks)
            for health in results:
                self._providers[health.provider_id] = health
            self._last_full_probe = time.time()
            return self.get_top_providers()

    def report_error(self, provider_id: str, error: str = "rate_limit_or_error") -> list[str]:
        """Instantly demote a provider on live 429/5xx/timeout and return updated Top AI list."""
        health = self._providers.get(provider_id)
        if health is None:
            health = ProviderHealth(provider_id=provider_id, configured=True)
            self._providers[provider_id] = health

        health.healthy = False
        health.consecutive_errors += 1
        health.last_error = error
        health.cooldown_until = time.time() + self.cooldown_seconds
        logger.warning("TopAI demoted %s for %ss (%s)", provider_id, self.cooldown_seconds, error)
        return self.get_top_providers()

    def report_success(self, provider_id: str, latency_ms: float | None = None) -> None:
        """Record a successful live call, resetting error counters."""
        health = self._providers.get(provider_id)
        if health is None:
            return
        health.healthy = True
        health.consecutive_errors = 0
        health.cooldown_until = 0.0
        health.last_error = None
        if latency_ms is not None:
            health.latency_ms = round(latency_ms, 2)

    def get_top_providers(self) -> list[str]:
        """Return available providers sorted by lowest latency."""
        available = [h for h in self._providers.values() if h.is_available]
        available.sort(key=lambda h: h.latency_ms)
        return [h.provider_id for h in available]

    def snapshot(self) -> dict[str, Any]:
        """Return diagnostic snapshot of all tracked providers."""
        return {
            "top_providers": self.get_top_providers(),
            "last_full_probe": self._last_full_probe,
            "probe_interval_seconds": self.probe_interval_seconds,
            "providers": {
                pid: {
                    "configured": h.configured,
                    "available": h.is_available,
                    "latency_ms": h.latency_ms,
                    "last_error": h.last_error,
                    "cooldown_until": h.cooldown_until,
                }
                for pid, h in self._providers.items()
            },
        }
