"""Alert forwarding to the Studio alert hub (core → /api/internal/alerts)."""

from __future__ import annotations

import asyncio
import json

import httpx

from core.services import alert_forwarder
from core.services.alert_forwarder import (
    build_payload,
    forward_alert,
    severity_for_level,
)


def test_severity_mapping():
    assert severity_for_level("ERROR") == "critical"
    assert severity_for_level("warn") == "warning"
    assert severity_for_level("debug") == "info"
    assert severity_for_level("") == "info"


def test_payload_is_trimmed_and_optional_fields_omitted():
    payload = build_payload("loud", "", "x" * 500)
    assert payload == {"severity": "info", "source": "core", "title": "x" * 200}
    full = build_payload("critical", "core", "Down", "b" * 3000, "k")
    assert len(full["body"]) == 2000
    assert full["dedupeKey"] == "k"


def _patch_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(alert_forwarder.httpx, "AsyncClient", factory)


def test_forward_posts_with_bearer(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"success": True})

    monkeypatch.delenv("ALERT_INGEST_URL", raising=False)
    _patch_client(monkeypatch, handler)
    ok = asyncio.run(
        forward_alert("critical", "core", "Down", dedupe_key="core:x", token="tok")
    )
    assert ok is True
    assert seen["url"] == alert_forwarder.DEFAULT_INGEST_URL
    assert seen["auth"] == "Bearer tok"
    assert seen["body"] == {
        "severity": "critical",
        "source": "core",
        "title": "Down",
        "dedupeKey": "core:x",
    }


def test_forward_never_raises(monkeypatch):
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _patch_client(monkeypatch, refused)
    assert asyncio.run(forward_alert("warning", "core", "x", token="tok")) is False
    _patch_client(monkeypatch, lambda r: httpx.Response(403))
    assert asyncio.run(forward_alert("warning", "core", "x", token="tok")) is False
    assert asyncio.run(forward_alert("warning", "core", "x", token="")) is False
