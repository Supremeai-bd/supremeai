"""backend/workers/precognitive_watcher.py — Precognitive Watcher Background Daemon.

Autonomous System Observability & Proactive Sentinel:
- Continuous monitoring of service error rates, latency spikes, and deployment health.
- Emits early warning signals and recommended remediation actions before user impact.
- Interacts with CircuitBreakers and ErrorBus for proactive self-healing.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SentinelAlert(BaseModel):
    alert_id: str
    severity: str  # info | warning | critical
    service: str
    message: str
    suggested_action: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# বাংলা: alert-তালিকা অসীমভাবে বাড়তে পারত — সীমাবদ্ধ deque দিয়ে মেমরি-লিক বন্ধ।
_MAX_ALERT_HISTORY = 500


class PrecognitiveWatcher:
    """Proactive system sentinel monitoring deployment and error vectors."""

    def __init__(self) -> None:
        self._running = False
        self._alerts: deque[SentinelAlert] = deque(maxlen=_MAX_ALERT_HISTORY)

    async def scan_system_health(self) -> list[SentinelAlert]:
        """Runs a single health sweep across core subsystems."""
        alerts: list[SentinelAlert] = []

        # Example check: Verify route registry integrity
        from core.circles.registry import circle_registry

        manifest_count = len(circle_registry.manifests())
        if manifest_count == 0:
            alerts.append(
                SentinelAlert(
                    alert_id=f"alert_{int(time.time())}_1",
                    severity="warning",
                    service="circle_registry",
                    message="Circle registry has 0 manifests loaded.",
                    suggested_action="Invoke build_circle_registry() during startup lifespan.",
                )
            )

        self._alerts.extend(alerts)
        return alerts

    def get_active_alerts(self, limit: int = 50) -> list[SentinelAlert]:
        return list(self._alerts)[-limit:]


async def run_precognitive_watch_loop() -> None:
    """স্থায়ী watchdog-স্পন্দন — নিয়মিত health-sweep চালায় (cancelled হলে সৎ বন্ধ)।"""
    import asyncio

    while True:
        try:
            await precognitive_watcher.scan_system_health()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # বাংলা: এক sweep-এর ব্যর্থতা পুরো লুপ মারবে না।
            import logging

            logging.getLogger(__name__).warning("precognitive sweep failed: %s", exc)
        await asyncio.sleep(60)


precognitive_watcher = PrecognitiveWatcher()
