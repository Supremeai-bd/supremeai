"""Regression: guest daily budget must bucket by the trusted client IP.

The per-IP guest daily limiter (gateway/main.py) originally keyed on the
LEFTMOST X-Forwarded-For hop, which is fully client-controlled: a guest
could rotate a fake leftmost value and mint a fresh daily budget on every
request, defeating the anti-abuse cap. The platform proxy appends the real
client IP as the LAST hop (same doctrine as
gateway/service/app.py::_client_ip), so bucketing must use that hop.

Fully offline: provider transport is a deterministic fake, the app is
driven via fastapi.testclient.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gateway.config import parse_routing_policy
from gateway.main import create_app
from gateway.provider_chain import AttemptResult

BODY = {"messages": [{"role": "user", "content": "hi"}]}


def _config():
    return parse_routing_policy(
        {
            "schema_version": "gateway-routing/1",
            "chains": {
                "auto": [{"provider": "groq", "model": "llama-3.1-8b-instant"}],
            },
            "default_chain": "auto",
            # High general limit so only the guest-daily budget can trip.
            "rate_limit": {"window_seconds": 60, "max_requests": 1000},
            "api_keys": {},
        },
        env={},
    )


def _ok_attempt(cfg):
    async def attempt(endpoint, payload: bytes) -> AttemptResult:
        body: dict[str, Any] = {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hello"},
                    "finish_reason": "stop",
                }
            ]
        }
        return AttemptResult(
            endpoint=cfg.chains["auto"][0],
            status=200,
            headers={},
            body=json.dumps(body).encode(),
            latency_ms=1,
        )

    return attempt


@pytest.fixture()
def guest_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SUPREMEAI_GUEST_DAILY_MAX", "2")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("SUPREMEAI_REDIS_URL", raising=False)
    cfg = _config()
    return TestClient(create_app(config=cfg, attempt_fn=_ok_attempt(cfg)))


def _guest_post(client: TestClient, xff: str):
    return client.post(
        "/v1/chat/completions",
        headers={"X-Forwarded-For": xff},
        json=BODY,
    )


def test_rotating_spoofed_leftmost_xff_does_not_reset_budget(guest_client):
    # Same real client (last hop 203.0.113.7, appended by the proxy),
    # rotating a fake leftmost hop on every request.
    assert _guest_post(guest_client, "10.0.0.1, 203.0.113.7").status_code == 200
    assert _guest_post(guest_client, "10.0.0.2, 203.0.113.7").status_code == 200
    r = _guest_post(guest_client, "10.0.0.3, 203.0.113.7")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "guest_daily_limit"


def test_distinct_real_clients_get_distinct_budgets(guest_client):
    assert _guest_post(guest_client, "198.51.100.1").status_code == 200
    assert _guest_post(guest_client, "198.51.100.1").status_code == 200
    assert _guest_post(guest_client, "198.51.100.1").status_code == 429
    # A different real client is unaffected by the first client's cap.
    assert _guest_post(guest_client, "198.51.100.2").status_code == 200
