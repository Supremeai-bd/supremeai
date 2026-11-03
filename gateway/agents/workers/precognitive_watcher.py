"""backend/workers/precognitive_watcher.py — Precognitive Watcher Background Daemon.

Autonomous System Observability & Proactive Sentinel:
- Continuous monitoring of service error rates, latency spikes, and deployment health.
- Emits early warning signals and recommended remediation actions before user impact.
- Interacts with CircuitBreakers and ErrorBus for proactive self-healing.

বাংলা মন্তব্য (#2706 Gap-G): আগে scan_system_health() শুধু circle_registry
manifest-গণনা করত (১-মেট্রিক সেন্টিনেল) এবং production-এ কোনো scheduler-ই একে
ডাকত না। এখন ৬টি আসল মেট্রিক চেক হয় এবং Orchestrator (PeriodicTaskScheduler)
প্রতি টিকে (৩০০ সে.) এই সুইপ চালায়; সনাক্ত anomaly সরাসরি
AutoHealer.proactive_guardian_cycle()-এ গিয়ে সত্যিকারের proactive PR পথ খোলে।
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from core.logging_config import logger

# বাংলা মন্তব্য: থ্রেশহোল্ড-নীতি — এক জায়গায় টিউনযোগ্য, ম্যাজিক-নাম্বার ছড়ানো নয়।
_DLQ_BACKLOG_WARNING = 50
_DLQ_BACKLOG_CRITICAL = 200
_ERROR_RATE_WARNING_PCT = 5.0
_ERROR_RATE_CRITICAL_PCT = 20.0
_LATENCY_P95_WARNING_MS = 2000.0
_LATENCY_P95_CRITICAL_MS = 8000.0


class SentinelAlert(BaseModel):
    alert_id: str
    severity: str  # info | warning | critical
    service: str
    message: str
    suggested_action: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    # বাংলা মন্তব্য (#2706): anomaly → PR সেতুর জন্য ঐচ্ছিক কোড-ফিক্স মেটাডেটা।
    target_file: str | None = None
    patch_hint: str | None = None
    metric_value: str | None = None


class PrecognitiveWatcher:
    """Proactive system sentinel monitoring deployment and error vectors."""

    def __init__(self) -> None:
        self._running = False
        self._alerts: list[SentinelAlert] = []
        # বাংলা মন্তব্য (#2706): সুইপ-অবজারভেবিলিটি — Rule #5 (Fleet Observability)।
        self._sweep_count = 0
        self._last_sweep_at: str | None = None

    async def scan_system_health(self) -> list[SentinelAlert]:
        """Runs a single health sweep across core subsystems.

        বাংলা মন্তব্য (#2706): ৬টি আসল মেট্রিক — প্রতিটি বাস্তব উৎস থেকে
        (circle_registry, error_event_bus, rolling-window, latency buffer,
        circuit breakers, GitHub CI) — কোনো হার্ডকোডেড/ভানের সংখ্যা নেই।
        """
        alerts: list[SentinelAlert] = []
        seq = int(time.time())

        # ── Metric 1: Route registry integrity ─────────────────────────────
        try:
            from core.circles.registry import circle_registry

            manifest_count = len(circle_registry.manifests())
            if manifest_count == 0:
                alerts.append(
                    SentinelAlert(
                        alert_id=f"alert_{seq}_1",
                        severity="warning",
                        service="circle_registry",
                        message="Circle registry has 0 manifests loaded.",
                        suggested_action="Invoke build_circle_registry() during startup lifespan.",
                    )
                )
        except Exception as exc:
            # বাংলা মন্তব্য: graceful degradation (Rule #3) — প্রোব ব্যর্থ হলে সৎ নোট।
            alerts.append(
                SentinelAlert(
                    alert_id=f"alert_{seq}_1e",
                    severity="info",
                    service="circle_registry",
                    message=f"Registry probe unavailable: {str(exc)[:120]}",
                    suggested_action="Verify circle registry import health.",
                )
            )

        # ── Metric 2: Error-bus DLQ backlog (real emitted/dead-letter counts) ──
        try:
            from core.messaging.event_bus import error_event_bus

            stats = error_event_bus.stats()
            dlq_size = int(stats.get("dlq_current_size", 0))
            if dlq_size >= _DLQ_BACKLOG_CRITICAL:
                alerts.append(
                    SentinelAlert(
                        alert_id=f"alert_{seq}_2",
                        severity="critical",
                        service="error_event_bus",
                        message=(
                            f"Dead-letter queue backlog critical: {dlq_size} items "
                            f"(total emitted: {stats.get('total_emitted', 0)})."
                        ),
                        suggested_action="Process DLQ via admin console; inspect failing listeners.",
                        metric_value=str(dlq_size),
                    )
                )
            elif dlq_size >= _DLQ_BACKLOG_WARNING:
                alerts.append(
                    SentinelAlert(
                        alert_id=f"alert_{seq}_2",
                        severity="warning",
                        service="error_event_bus",
                        message=f"Dead-letter queue backlog growing: {dlq_size} items.",
                        suggested_action="Monitor listener failure rates; replay DLQ if trend continues.",
                        metric_value=str(dlq_size),
                    )
                )
        except Exception as exc:
            logger.debug(f"[PrecognitiveWatcher] error-bus probe skipped: {exc}")

        # ── Metric 3: 5xx error-rate (real rolling window) ─────────────────
        try:
            from core.observability.metrics_registry import get_window_metrics

            window = get_window_metrics()
            error_rate = window.get("error_rate")
            if error_rate is not None and error_rate >= _ERROR_RATE_CRITICAL_PCT:
                alerts.append(
                    SentinelAlert(
                        alert_id=f"alert_{seq}_3",
                        severity="critical",
                        service="http_traffic",
                        message=(
                            f"5xx error-rate {error_rate}% over last "
                            f"{window.get('window_seconds', 60)}s window."
                        ),
                        suggested_action="Inspect failing endpoints; check downstream provider health.",
                        metric_value=f"{error_rate}%",
                    )
                )
            elif error_rate is not None and error_rate >= _ERROR_RATE_WARNING_PCT:
                alerts.append(
                    SentinelAlert(
                        alert_id=f"alert_{seq}_3",
                        severity="warning",
                        service="http_traffic",
                        message=f"5xx error-rate elevated: {error_rate}% in rolling window.",
                        suggested_action="Watch traffic; correlate with recent deploys.",
                        metric_value=f"{error_rate}%",
                    )
                )
        except Exception as exc:
            logger.debug(f"[PrecognitiveWatcher] error-rate probe skipped: {exc}")

        # ── Metric 4: Latency p95 (real last-1000-request buffer) ──────────
        try:
            from core.observability.metrics_registry import metrics_engine

            history = list(metrics_engine.latency_history)
            if history:
                ordered = sorted(history)
                p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
                p95_ms = p95 * 1000.0
                if p95_ms >= _LATENCY_P95_CRITICAL_MS:
                    alerts.append(
                        SentinelAlert(
                            alert_id=f"alert_{seq}_4",
                            severity="critical",
                            service="latency",
                            message=f"p95 latency {p95_ms:.0f}ms (threshold {_LATENCY_P95_CRITICAL_MS:.0f}ms).",
                            suggested_action="Profile slow endpoints; check DB pool saturation.",
                            metric_value=f"{p95_ms:.0f}ms",
                        )
                    )
                elif p95_ms >= _LATENCY_P95_WARNING_MS:
                    alerts.append(
                        SentinelAlert(
                            alert_id=f"alert_{seq}_4",
                            severity="warning",
                            service="latency",
                            message=f"p95 latency elevated: {p95_ms:.0f}ms.",
                            suggested_action="Monitor; correlate with traffic spikes.",
                            metric_value=f"{p95_ms:.0f}ms",
                        )
                    )
        except Exception as exc:
            logger.debug(f"[PrecognitiveWatcher] latency probe skipped: {exc}")

        # ── Metric 5: Open circuit breakers (real breaker registry) ────────
        try:
            from services.auto_healer import get_healer

            open_breakers = [
                name
                for name, cb in get_healer().circuit_breakers.items()
                if getattr(cb, "state", None) is not None
                and str(getattr(cb.state, "value", cb.state)).upper() == "OPEN"
            ]
            if open_breakers:
                alerts.append(
                    SentinelAlert(
                        alert_id=f"alert_{seq}_5",
                        severity="warning",
                        service="circuit_breakers",
                        message=f"Circuit breaker(s) OPEN: {', '.join(open_breakers[:5])}.",
                        suggested_action="Verify downstream service health; breakers auto-half-open after cooldown.",
                        metric_value=str(len(open_breakers)),
                    )
                )
        except Exception as exc:
            logger.debug(f"[PrecognitiveWatcher] breaker probe skipped: {exc}")

        # ── Metric 6: CI red count (optional external probe, honest skip) ──
        ci_alert = await self._probe_ci_red_count(seq)
        if ci_alert is not None:
            alerts.append(ci_alert)

        self._alerts.extend(alerts)
        # বাংলা মন্তব্য: আলার্ট-বাফার bounded — মেমরি-ব্লোট রোধ (Rule #2 free-tier)।
        if len(self._alerts) > 500:
            self._alerts = self._alerts[-500:]
        self._sweep_count += 1
        self._last_sweep_at = datetime.now(UTC).isoformat()

        if alerts:
            logger.warning(
                f"[PrecognitiveWatcher] Sweep #{self._sweep_count}: "
                f"{len(alerts)} alert(s) — {[a.service for a in alerts]}"
            )
        return alerts

    async def _probe_ci_red_count(self, seq: int) -> SentinelAlert | None:
        """বাংলা মন্তব্য: GitHub CI red-count প্রোব — বাহ্যিক, ঐচ্ছিক, সৎ-স্কিপ।

        GITHUB_TOKEN/GITHUB_REPOSITORY না থাকলে বা নেটওয়ার্ক ব্যর্থ হলে
        কোনো ভান-সংখ্যা নয় — None (স্কিপ) ফেরায়; ৫-সেকেন্ড টাইমআউট।
        """
        token = os.getenv("GITHUB_TOKEN", "").strip()
        repo = os.getenv("GITHUB_REPOSITORY", "").strip()
        if not token or not repo or "/" not in repo:
            return None
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{repo}/actions/runs"
                    "?per_page=20&status=completed",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "supremeai-precognitive-watcher",
                    },
                )
                resp.raise_for_status()
                runs = resp.json().get("workflow_runs", [])
                red = [
                    r
                    for r in runs
                    if r.get("conclusion") in ("failure", "timed_out", "startup_failure")
                ]
                if len(red) >= 3:
                    return SentinelAlert(
                        alert_id=f"alert_{seq}_6",
                        severity="warning",
                        service="github_ci",
                        message=f"{len(red)}/{len(runs)} recent completed CI runs red.",
                        suggested_action="Inspect failing workflows; correlate with recent main merges.",
                        metric_value=f"{len(red)}/{len(runs)}",
                    )
        except Exception as exc:
            logger.debug(f"[PrecognitiveWatcher] CI probe skipped: {exc}")
        return None

    def get_active_alerts(self, limit: int = 50) -> list[SentinelAlert]:
        return self._alerts[-limit:]

    def get_status(self) -> dict[str, Any]:
        """বাংলা মন্তব্য: সেন্টিনেল-স্বাস্থ্য স্ট্যাটাস — সুইপ-গণনাসহ (Rule #5)।"""
        return {
            "sweep_count": self._sweep_count,
            "last_sweep_at": self._last_sweep_at,
            "total_alerts_recorded": len(self._alerts),
            "running": self._running,
        }


precognitive_watcher = PrecognitiveWatcher()
