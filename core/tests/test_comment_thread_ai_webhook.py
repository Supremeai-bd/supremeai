"""Unit tests for CommentThreadAI GitHub webhook HMAC-SHA256 signature verification.
# বাংলা মন্তব্য: CommentThreadAI ওয়েবহুক HMAC-SHA256 যাচাইকরণ ও fail-closed আচরণ নিশ্চিত করার ইউনিট টেস্ট।
"""

import hashlib
import hmac
import importlib
from unittest.mock import AsyncMock

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


@pytest.mark.parametrize("event", ["issue_comment", "pull_request_review_comment"])
def test_signed_comment_event_reaches_processor(monkeypatch, event):
    module = importlib.import_module(_verify_signature.__module__)
    process = AsyncMock(return_value={"status": "processed"})
    monkeypatch.setattr(ctai, "settings", _SettingsStub(SECRET))
    monkeypatch.setattr(module._comment_ai, "handle_github_webhook", process)
    app = FastAPI()
    app.include_router(router)
    body = b'{"action":"created","comment":{"body":"@supremeai fix this"}}'
    with TestClient(app) as client:
        response = client.post(
            "/comment-ai/webhook",
            content=body,
            headers={"X-GitHub-Event": event, "X-Hub-Signature-256": _calc_signature(body)},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    process.assert_awaited_once_with(
        {"action": "created", "comment": {"body": "@supremeai fix this"}}
    )


def test_webhook_has_one_post_owner():
    owners = [
        route
        for route in router.routes
        if route.path == "/comment-ai/webhook" and "POST" in route.methods
    ]
    assert len(owners) == 1


@pytest.mark.parametrize(
    "body,signature,event,status",
    [
        (b"{}", None, "issue_comment", 401),
        (b"{}", "sha256=wrong", "issue_comment", 401),
        (b"not-json", "valid", "issue_comment", 400),
        (b"[]", "valid", "issue_comment", 400),
        (b"{}", "valid", "push", 200),
    ],
)
def test_webhook_rejects_or_ignores_without_processing(monkeypatch, body, signature, event, status):
    module = importlib.import_module(_verify_signature.__module__)
    process = AsyncMock()
    monkeypatch.setattr(ctai, "settings", _SettingsStub(SECRET))
    monkeypatch.setattr(module._comment_ai, "handle_github_webhook", process)
    app = FastAPI()
    app.include_router(router)
    headers = {"X-GitHub-Event": event}
    if signature is not None:
        headers["X-Hub-Signature-256"] = (
            _calc_signature(body) if signature == "valid" else signature
        )
    with TestClient(app) as client:
        response = client.post("/comment-ai/webhook", content=body, headers=headers)
    assert response.status_code == status
    if event == "push":
        assert response.json() == {"status": "ignored", "event": "push"}
    process.assert_not_awaited()
