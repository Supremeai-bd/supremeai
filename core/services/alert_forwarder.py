"""Forward platform alerts to the Studio alert hub (admin → Services & Health → Alerts).

বাংলা মন্তব্য: Studio edge `/api/internal/alerts` অ্যালার্টকে অ্যাডমিনের বেছে নেওয়া
চ্যানেলে (Telegram / Discord / Slack / webhook) পাঠায় ও ইতিহাসে রাখে। এখান থেকে শুধু
best-effort POST — ব্যর্থ হলে লগ করে চুপচাপ ফিরে আসে, অনুরোধ কখনো আটকায় না।
"""

from __future__ import annotations

import os

import httpx
from loguru import logger

DEFAULT_INGEST_URL = "https://supremeai-studio.pages.dev/api/internal/alerts"
_TIMEOUT_S = 8.0

_LEVEL_TO_SEVERITY = {
    "critical": "critical",
    "fatal": "critical",
    "error": "critical",
    "warning": "warning",
    "warn": "warning",
}


def severity_for_level(level: str) -> str:
    """Map a free-form log level to the hub's info / warning / critical."""
    return _LEVEL_TO_SEVERITY.get((level or "").strip().lower(), "info")


def build_payload(
    severity: str, source: str, title: str, body: str | None = None, dedupe_key: str | None = None
) -> dict:
    payload = {
        "severity": severity if severity in ("info", "warning", "critical") else "info",
        "source": (source or "core")[:60],
        "title": (title or "Alert")[:200],
    }
    if body:
        payload["body"] = body[:2000]
    if dedupe_key:
        payload["dedupeKey"] = dedupe_key[:200]
    return payload


async def forward_alert(
    severity: str,
    source: str,
    title: str,
    body: str | None = None,
    dedupe_key: str | None = None,
    token: str | None = None,
) -> bool:
    """POST one alert to the hub. Returns True when the hub accepted it."""
    if token is None:
        from core.config import settings

        token = settings.supremeai_api_token
    if not token:
        logger.debug("alert_forwarder: no SUPREMEAI_API_TOKEN, alert kept local only")
        return False
    url = os.getenv("ALERT_INGEST_URL", "").strip() or DEFAULT_INGEST_URL
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            res = await client.post(
                url,
                json=build_payload(severity, source, title, body, dedupe_key),
                headers={"Authorization": f"Bearer {token}"},
            )
        if res.status_code >= 400:
            logger.warning(f"alert_forwarder: hub returned HTTP {res.status_code}")
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning(f"alert_forwarder: hub unreachable ({type(exc).__name__})")
        return False
