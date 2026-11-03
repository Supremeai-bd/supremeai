"""Adversarial webhook signature tests.

Gap closure: webhook endpoints must fail closed on missing/tampered/wrong
signatures, reject replay (stale timestamps), and bind the signature to the
exact request body. We exercise the three signature implementations that back
the exposed webhooks:
- /cdc/webhook            (Supabase HMAC-SHA256, x-supabase-signature)
- /api/v1/webhooks/n8n   (HMAC-SHA256 over timestamp.body, replay-window)
- /pr-review/webhook     (GitHub HMAC-SHA256, X-Hub-Signature-256)

These are pure-function/unit-level adversarial tests; no live service needed.
"""

import hashlib
import hmac
import time

import pytest

from api.routes.cdc_webhooks import _verify_webhook_signature as verify_cdc
from api.routes.n8n_webhooks import _verify_n8n_signature as verify_n8n
from api.routes.pr_review_api import _verify_signature as verify_github

SECRET = "adversarial-test-secret-0123456789"


class DummyRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


# ---------------------------------------------------------------------------
# CDC webhook (Supabase HMAC-SHA256 over raw body)
# ---------------------------------------------------------------------------


def _cdc_sig(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_cdc_valid_signature_accepted(monkeypatch):
    monkeypatch.setattr("api.routes.cdc_webhooks.SUPABASE_WEBHOOK_SECRET", SECRET)
    body = b'{"type":"INSERT","table":"docs","record":{"id":"1"}}'
    req = DummyRequest({"x-supabase-signature": _cdc_sig(body)})
    assert await verify_cdc(req, body) is True


@pytest.mark.asyncio
async def test_cdc_missing_signature_rejected(monkeypatch):
    monkeypatch.setattr("api.routes.cdc_webhooks.SUPABASE_WEBHOOK_SECRET", SECRET)
    req = DummyRequest({})
    assert await verify_cdc(req, b'{"type":"DELETE"}') is False


@pytest.mark.asyncio
async def test_cdc_tampered_body_rejected(monkeypatch):
    monkeypatch.setattr("api.routes.cdc_webhooks.SUPABASE_WEBHOOK_SECRET", SECRET)
    original = b'{"type":"INSERT","table":"docs","record":{"id":"1"}}'
    tampered = b'{"type":"INSERT","table":"docs","record":{"id":"2"}}'
    req = DummyRequest({"x-supabase-signature": _cdc_sig(original)})
    assert await verify_cdc(req, tampered) is False


@pytest.mark.asyncio
async def test_cdc_wrong_secret_rejected(monkeypatch):
    monkeypatch.setattr("api.routes.cdc_webhooks.SUPABASE_WEBHOOK_SECRET", SECRET)
    body = b'{"type":"UPDATE","table":"docs"}'
    req = DummyRequest({"x-supabase-signature": _cdc_sig(body, secret="other-secret")})
    assert await verify_cdc(req, body) is False


@pytest.mark.asyncio
async def test_cdc_no_secret_configured_pins_dev_skip(monkeypatch):
    """Hardened behavior (P0 fail-closed): unconfigured secret rejects webhook."""
    monkeypatch.setattr("api.routes.cdc_webhooks.SUPABASE_WEBHOOK_SECRET", "")
    body = b'{"type":"INSERT"}'
    assert await verify_cdc(DummyRequest({}), body) is False


# ---------------------------------------------------------------------------
# n8n webhook (replay-window HMAC over timestamp.body)
# ---------------------------------------------------------------------------


def _n8n_sig(body: bytes, timestamp: int, secret: str = SECRET) -> str:
    message = f"{timestamp}.{body.decode('utf-8')}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_n8n_valid_signature_accepted(monkeypatch):
    monkeypatch.setattr("api.routes.n8n_webhooks.N8N_WEBHOOK_SECRET", SECRET)
    body = b'{"event_id":"e1","status":"success"}'
    ts = int(time.time())
    req = DummyRequest({"X-N8N-Signature": _n8n_sig(body, ts)})
    assert await verify_n8n(req, body, str(ts)) is True


@pytest.mark.asyncio
async def test_n8n_stale_timestamp_replay_rejected(monkeypatch):
    monkeypatch.setattr("api.routes.n8n_webhooks.N8N_WEBHOOK_SECRET", SECRET)
    body = b'{"event_id":"e1","status":"success"}'
    old_ts = int(time.time()) - 10 * 60  # 10 minutes old -> outside 300s window
    req = DummyRequest({"X-N8N-Signature": _n8n_sig(body, old_ts)})
    assert await verify_n8n(req, body, str(old_ts)) is False


@pytest.mark.asyncio
async def test_n8n_tampered_body_rejected(monkeypatch):
    monkeypatch.setattr("api.routes.n8n_webhooks.N8N_WEBHOOK_SECRET", SECRET)
    ts = int(time.time())
    original = b'{"event_id":"e1","status":"success"}'
    tampered = b'{"event_id":"e1","status":"failed"}'
    req = DummyRequest({"X-N8N-Signature": _n8n_sig(original, ts)})
    assert await verify_n8n(req, tampered, str(ts)) is False


@pytest.mark.asyncio
async def test_n8n_missing_signature_rejected(monkeypatch):
    monkeypatch.setattr("api.routes.n8n_webhooks.N8N_WEBHOOK_SECRET", SECRET)
    assert await verify_n8n(DummyRequest({}), b"{}", str(int(time.time()))) is False


@pytest.mark.asyncio
async def test_n8n_no_secret_fails_closed(monkeypatch):
    """n8n fails closed when the shared secret is missing (stronger posture)."""
    monkeypatch.setattr("api.routes.n8n_webhooks.N8N_WEBHOOK_SECRET", "")
    body = b'{"event_id":"e1","status":"success"}'
    ts = int(time.time())
    req = DummyRequest({"X-N8N-Signature": _n8n_sig(body, ts)})
    assert await verify_n8n(req, body, str(ts)) is False


# ---------------------------------------------------------------------------
# GitHub PR review webhook (X-Hub-Signature-256 HMAC-SHA256)
# ---------------------------------------------------------------------------


def _gh_sig(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_github_valid_signature_accepted():
    body = b'{"action":"opened","pull_request":{"number":42}}'
    assert verify_github(body, _gh_sig(body), SECRET) is True


def test_github_tampered_body_rejected():
    body = b'{"action":"opened","pull_request":{"number":42}}'
    tampered = b'{"action":"closed","pull_request":{"number":42}}'
    assert verify_github(tampered, _gh_sig(body), SECRET) is False


def test_github_wrong_signature_rejected():
    body = b'{"action":"opened"}'
    assert verify_github(body, "sha256=deadbeef", SECRET) is False


def test_github_missing_signature_rejected():
    assert verify_github(b"{}", None, SECRET) is False


def test_github_no_secret_fails_closed():
    """CONTRACT UPDATE (Wave-1 security): unconfigured secret rejects the hook.

    বাংলা মন্তব্য: আগে dev-mode নামে fail-open ছিল (secret None → True) —
    এখন n8n/cdc-র মতোই কঠোর fail-closed।
    """
    assert verify_github(b"{}", None, None) is False
    assert verify_github(b"{}", "sha256=deadbeef", None) is False
