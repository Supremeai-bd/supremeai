"""Unit tests for CommentThreadAI GitHub webhook HMAC-SHA256 signature verification.
# বাংলা মন্তব্য: CommentThreadAI ওয়েবহুক HMAC-SHA256 যাচাইকরণ ও fail-closed আচরণ নিশ্চিত করার ইউনিট টেস্ট।
"""

import hashlib
import hmac

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import tools.comment_thread_ai as ctai
from core.tools.comment_thread_ai import _verify_signature, router

SECRET = "test-webhook-secret-12345"


class _SettingsStub:
    def __init__(self, secret: str | None):
        self.github_webhook_secret = secret


def _calc_signature(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_signature_valid():
    """Valid HMAC signature passes without exception."""
    body = b'{"action":"created"}'
    sig = _calc_signature(body, SECRET)
    _verify_signature(body, sig, SECRET)


def test_verify_signature_missing_secret():
    """Missing or empty secret raises HTTP 503 Service Unavailable (fail-closed)."""
    body = b'{"action":"created"}'
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(body, "sha256=123", "")
    assert exc_info.value.status_code == 503
    assert "not configured" in exc_info.value.detail


def test_verify_signature_missing_header():
    """Missing X-Hub-Signature-256 header raises HTTP 401 Unauthorized."""
    body = b'{"action":"created"}'
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(body, None, SECRET)
    assert exc_info.value.status_code == 401
    assert "Missing X-Hub-Signature-256" in exc_info.value.detail


def test_verify_signature_invalid_header():
    """Invalid HMAC signature raises HTTP 401 Unauthorized."""
    body = b'{"action":"created"}'
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(body, "sha256=invalid_signature_hex", SECRET)
    assert exc_info.value.status_code == 401
    assert "Invalid webhook signature" in exc_info.value.detail


def test_webhook_endpoint_flow(monkeypatch):
    """End-to-end webhook endpoint flow covering valid ping, invalid, and missing signatures."""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    monkeypatch.setattr(ctai, "settings", _SettingsStub(SECRET))

    body = b'{"action":"ping"}'
    sig = _calc_signature(body, SECRET)

    # 1. Valid signature on ping event -> 200 pong
    response = client.post(
        "/comment-ai/webhook",
        content=body,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "pong"}

    # 2. Missing signature header -> 401
    response = client.post(
        "/comment-ai/webhook",
        content=body,
        headers={"X-GitHub-Event": "ping"},
    )
    assert response.status_code == 401

    # 3. Invalid signature header -> 401
    response = client.post(
        "/comment-ai/webhook",
        content=body,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=wrong"},
    )
    assert response.status_code == 401

    # 4. Unconfigured secret -> 503
    monkeypatch.setattr(ctai, "settings", _SettingsStub(""))
    response = client.post(
        "/comment-ai/webhook",
        content=body,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
    )
    assert response.status_code == 503
