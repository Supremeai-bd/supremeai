"""Regression tests for the gateway provider transport + rate-limit keying.

Two production defects found in the 2026-11-19 audit, both reproduced here:

1. ``provider_chain._default_attempt`` joined every provider base URL with
   ``/v1/chat/completions`` unconditionally, so provider bases that already
   end in ``/v1`` (all the ``_FALLBACKS`` entries) were called at
   ``.../v1/v1/chat/completions`` and 404'd on every request.

2. ``main.check_rate_limit`` bucketed anonymous traffic by
   ``request.client.host`` — the platform proxy socket peer — so every
   anonymous caller shared ONE bucket and a single client could 429 the whole
   fleet, while rotating ``X-Forwarded-For`` bought nothing.

Also covers the payload pass-through: ``tools``/``temperature`` must reach the
provider instead of being silently dropped.
"""

from __future__ import annotations

import json

import pytest

from gateway.config import Endpoint, parse_routing_policy
from gateway.main import create_app
from gateway.provider_chain import AttemptResult, _completions_url, _default_attempt

# --- 1. provider URL joins ---------------------------------------------------


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://api.groq.com/openai/v1", "https://api.groq.com/openai/v1/chat/completions"),
        ("https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"),
        (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        ),
        ("https://api.example.com", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/", "https://api.example.com/v1/chat/completions"),
        (
            "https://api.example.com/v1/chat/completions",
            "https://api.example.com/v1/chat/completions",
        ),
    ],
)
def test_completions_url_is_joined_exactly_once(base: str, expected: str) -> None:
    assert _completions_url(base) == expected


class _FakeResponse:
    status_code = 200
    content = b'{"choices":[{"message":{"content":"ok"}}]}'
    headers = {"content-type": "application/json"}  # noqa: RUF012 - read-only fixture


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs.get("json") or {}))
        return _FakeResponse()


@pytest.mark.asyncio
async def test_default_attempt_uses_fallback_base_without_doubling_v1(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_unit_test_key_1234567890")
    monkeypatch.delenv("SUPREMEAI_PROVIDER_BASE_GROQ", raising=False)
    monkeypatch.delenv("SUPREMEAI_PROVIDER_KEY_GROQ", raising=False)

    fake = _FakeClient()
    monkeypatch.setattr("gateway.provider_chain._http_client", lambda: fake)

    await _default_attempt(
        Endpoint(provider="groq", model="llama-3.1-8b-instant"),
        json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode(),
    )

    url, body = fake.calls[0]
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    assert "/v1/v1/" not in url
    assert body["model"] == "llama-3.1-8b-instant"


@pytest.mark.asyncio
async def test_default_attempt_forwards_sampling_and_tools(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-unit-test-key-1234567890")
    monkeypatch.delenv("SUPREMEAI_PROVIDER_BASE_OPENAI", raising=False)

    fake = _FakeClient()
    monkeypatch.setattr("gateway.provider_chain._http_client", lambda: fake)

    tools = [
        {
            "type": "function",
            "function": {"name": "list_files", "parameters": {"type": "object"}},
        }
    ]
    await _default_attempt(
        Endpoint(provider="openai", model="gpt-4o-mini"),
        json.dumps(
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.2,
                "max_tokens": 64,
                "tools": tools,
            }
        ).encode(),
    )

    _, body = fake.calls[0]
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 64
    assert body["tools"] == tools


# --- 2. rate-limit bucketing -------------------------------------------------


_POLICY = {
    "schema_version": "gateway-routing/1",
    "chains": {"auto": [{"provider": "groq", "model": "llama-3.1-8b-instant"}]},
    "default_chain": "auto",
    "rate_limit": {"window_seconds": 60, "max_requests": 2},
    "api_keys": {},
}


def _app(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_GUEST_DAILY_MAX", "0")
    cfg = parse_routing_policy(_POLICY, env={})

    async def attempt(endpoint, payload):
        return AttemptResult(
            endpoint,
            200,
            {},
            json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode(),
            1,
        )

    return create_app(cfg, attempt_fn=attempt)


def _chat(client, ip: str) -> int:
    return client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
        headers={"x-forwarded-for": f"203.0.113.9, {ip}"},
    ).status_code


def test_anonymous_rate_limit_is_per_proxy_resolved_ip(monkeypatch):
    """Distinct clients behind the same proxy socket must not share a bucket."""
    from fastapi.testclient import TestClient

    client = TestClient(_app(monkeypatch))

    assert _chat(client, "198.51.100.10") == 200
    assert _chat(client, "198.51.100.10") == 200
    # A second client has its own budget...
    assert _chat(client, "198.51.100.11") == 200, (
        "a different client IP must not inherit another client's exhausted bucket"
    )
    # ...while the first client is genuinely limited.
    assert _chat(client, "198.51.100.10") == 429


def test_rate_limit_does_not_key_on_raw_api_key(monkeypatch):
    """Limiter keys are hashed so raw credentials never become Redis/memory keys."""
    from gateway.rate_limit import SlidingWindowLimiter

    seen: list[str] = []
    original = SlidingWindowLimiter.check

    async def spy(self, key: str):
        seen.append(key)
        return await original(self, key)

    monkeypatch.setattr(SlidingWindowLimiter, "check", spy)
    from fastapi.testclient import TestClient

    raw = "supremeai-key-rawsecret0123456789"
    cfg = parse_routing_policy(
        {**_POLICY, "api_keys": {raw: {"owner": "unit", "scopes": ["chat"]}}},
        env={"SUPREMEAI_API_KEY_UNIT": raw},
    )

    async def attempt(endpoint, payload):
        return AttemptResult(
            endpoint,
            200,
            {},
            json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode(),
            1,
        )

    client = TestClient(create_app(cfg, attempt_fn=attempt))
    client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
        headers={"x-supremeai-key": raw},
    )
    assert seen, "limiter must have been consulted"
    assert all("raw-secret-value" not in key for key in seen)
    assert seen[0].startswith("key:")
