"""
tests/test_web_session_fleet.py — Test Web Session Engine & Infisical Cookie Hydration
"""
from __future__ import annotations

import base64
import gzip
import json
import pytest

from service.providers.web_session import WebSessionBridge, WebSessionAccount, WebSessionAdapter
from service.router import ADAPTER_REGISTRY


@pytest.fixture
def sample_fleet_gzip_b64():
    sample_cookies = [
        {"domain": ".google.com", "name": "__Secure-1PSID", "value": "test_google_1psid"},
        {"domain": ".google.com", "name": "SID", "value": "test_google_sid"},
        {"domain": ".chatgpt.com", "name": "__Secure-next-auth.session-token", "value": "test_chatgpt_token"},
        {"domain": ".perplexity.ai", "name": "__Secure-next-auth.session-token", "value": "test_pplx_token"},
        {"domain": ".grok.com", "name": "sso-token", "value": "test_grok_token"},
    ]
    raw_json = json.dumps(sample_cookies).encode("utf-8")
    compressed = gzip.compress(raw_json)
    return base64.b64encode(compressed).decode("utf-8")


def test_web_session_adapter_registered():
    assert "web_session" in ADAPTER_REGISTRY
    assert ADAPTER_REGISTRY["web_session"] is WebSessionAdapter


def test_fleet_cookies_hydration(monkeypatch, sample_fleet_gzip_b64):
    monkeypatch.setenv("AI_FLEET_COOKIES_GZIP_B64", sample_fleet_gzip_b64)
    bridge = WebSessionBridge()

    assert bridge.has_active_accounts is True
    providers = {a.provider for a in bridge.accounts}
    assert "gemini" in providers
    assert "chatgpt" in providers
    assert "perplexity" in providers
    assert "grok" in providers


@pytest.mark.asyncio
async def test_web_session_adapter_generate(monkeypatch, sample_fleet_gzip_b64):
    monkeypatch.setenv("AI_FLEET_COOKIES_GZIP_B64", sample_fleet_gzip_b64)
    adapter = WebSessionAdapter()

    assert await adapter.health_check() is True

    messages = [{"role": "user", "content": "Hello SupremeAI"}]
    res = await adapter.generate(model="auto", messages=messages)

    assert "id" in res
    assert res["object"] == "chat.completion"
    assert len(res["choices"]) > 0
    assert "content" in res["choices"][0]["message"]
