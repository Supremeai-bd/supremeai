"""Wave-1 security & honesty tests.

Covers the previously unauthenticated Telegram AI hook endpoints
(/api/v1/webhooks/telegram/*) and the fail-closed conversions of the
CI dashboard submission endpoint and the Telegram bot HTTP boundary.

বাংলা মন্তব্য: এই টেস্টগুলো নিশ্চিত করে —
  ১. secret ছাড়া / tampered secret / secret-শূন্য কনফিগ — তিন অবস্থাতেই প্রত্যাখ্যান (fail-closed)
  ২. /send-alert ভুয়া "sent" আর কখনো দেয় না — বট কনফিগার না থাকলে সৎ 503,
     পাঠানো ব্যর্থ হলে সৎ 502
  ৩. Telegram বটের /health বটের identity ফাঁস করে না

Pattern: mini-app + TestClient at the HTTP boundary — auth middleware is
deliberately excluded because these endpoints own their own secret checks
(same spirit as tests/security/test_adversarial_webhook_signatures.py).
All tests are offline and deterministic.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routes.ci_dashboard_api import CISummaryModel, WebhookPayload, receive_ci_webhook
from api.routes.webhooks_ai import router as webhooks_ai_router
from core.config import settings

SECRET = "wave1-offline-secret-0123456789abcdef"
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def _patch_cached_secrets(monkeypatch, telegram: str = "", ci: str = "") -> None:
    """settings._get_cached_secret প্রতিস্থাপন — env/vault ছাড়া deterministic।"""

    def fake_get_cached_secret(key: str) -> str:
        return {
            "TELEGRAM_WEBHOOK_SECRET": telegram,
            "CI_WEBHOOK_SECRET": ci,
        }.get(key, "")

    monkeypatch.setattr(settings, "_get_cached_secret", fake_get_cached_secret)


@pytest.fixture()
def ai_client() -> TestClient:
    app = FastAPI()
    app.include_router(webhooks_ai_router)
    return TestClient(app)


# ── /callback — secret verification (fail-closed) ─────────────────────────


def _callback_body(action: str = "approve_pr") -> dict:
    return {"callback_id": "cb-1", "user_id": "user-1", "action": action, "pr_id": "PR-42"}


def test_callback_without_secret_header_rejected(ai_client, monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    resp = ai_client.post("/api/v1/webhooks/telegram/callback", json=_callback_body())
    assert resp.status_code == 401


def test_callback_with_valid_secret_accepted(ai_client, monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/callback",
        json=_callback_body(),
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["pr_id"] == "PR-42"


def test_callback_with_tampered_secret_rejected(ai_client, monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/callback",
        json=_callback_body(),
        headers={SECRET_HEADER: SECRET + "tampered"},
    )
    assert resp.status_code == 401


def test_callback_fails_closed_when_secret_unset(ai_client, monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram="")
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/callback",
        json=_callback_body(),
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 401


def test_callback_unknown_action_is_400_not_401(ai_client, monkeypatch):
    """সঠিক secret দিয়ে ভুল action → বিজনেস লজিকের 400; auth-এর 401 নয়।"""
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/callback",
        json=_callback_body(action="nuke_everything"),
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 400


# ── /send-alert — honest behavior (never fake success) ────────────────────


class _FakeBot:
    def __init__(self, configured: bool = True, send_result: bool = True):
        self._configured = configured
        self._send_result = send_result
        self.calls: list[tuple] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self.calls.append((chat_id, text, parse_mode, reply_markup))
        return self._send_result


@pytest.fixture()
def _honest_chat_id(monkeypatch):
    monkeypatch.setattr(settings, "admin_telegram_chat_id", "12345")


def test_send_alert_without_secret_rejected(ai_client, monkeypatch, _honest_chat_id):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/send-alert",
        json={"title": "t", "description": "d"},
    )
    assert resp.status_code == 401


def test_send_alert_not_configured_is_honest_503(ai_client, monkeypatch, _honest_chat_id):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    monkeypatch.setattr(
        "tools.social.telegram_bot.handler.TelegramBotHandler",
        lambda: _FakeBot(configured=False),
    )
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/send-alert",
        json={"title": "t", "description": "d"},
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"].lower()


def test_send_alert_without_chat_id_is_honest_503(ai_client, monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    monkeypatch.setattr(settings, "admin_telegram_chat_id", "")
    monkeypatch.setattr(
        "tools.social.telegram_bot.handler.TelegramBotHandler",
        lambda: _FakeBot(configured=True),
    )
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/send-alert",
        json={"title": "t", "description": "d"},
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 503


def test_send_alert_success_reports_real_send(ai_client, monkeypatch, _honest_chat_id):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    bot = _FakeBot(configured=True, send_result=True)
    monkeypatch.setattr("tools.social.telegram_bot.handler.TelegramBotHandler", lambda: bot)
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/send-alert",
        json={"title": "GPU hot", "description": "temp 90C", "pr_id": "PR-7"},
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["chat_id"] == "12345"
    # সত্যিই পাঠানো হয়েছে — fake handler-এ কল রেকর্ড হয়েছে কিনা যাচাই
    assert len(bot.calls) == 1
    assert bot.calls[0][0] == "12345"


def test_send_alert_send_failure_is_honest_502(ai_client, monkeypatch, _honest_chat_id):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    monkeypatch.setattr(
        "tools.social.telegram_bot.handler.TelegramBotHandler",
        lambda: _FakeBot(configured=True, send_result=False),
    )
    resp = ai_client.post(
        "/api/v1/webhooks/telegram/send-alert",
        json={"title": "t", "description": "d"},
        headers={SECRET_HEADER: SECRET},
    )
    assert resp.status_code == 502


# ── CI dashboard webhook — fail-closed + settings-backed secret ───────────


@pytest.mark.asyncio
async def test_ci_webhook_rejects_when_secret_unset(monkeypatch):
    _patch_cached_secrets(monkeypatch, ci="")
    payload = WebhookPayload(secret=SECRET, summary=CISummaryModel(run_id=990001))
    with pytest.raises(HTTPException) as excinfo:
        await receive_ci_webhook(payload)
    assert excinfo.value.status_code == 401
    assert "not configured" in str(excinfo.value.detail).lower()


@pytest.mark.asyncio
async def test_ci_webhook_rejects_wrong_secret(monkeypatch):
    _patch_cached_secrets(monkeypatch, ci=SECRET)
    payload = WebhookPayload(secret="wrong-secret", summary=CISummaryModel(run_id=990002))
    with pytest.raises(HTTPException) as excinfo:
        await receive_ci_webhook(payload)
    assert excinfo.value.status_code == 401
    assert "invalid" in str(excinfo.value.detail).lower()


@pytest.mark.asyncio
async def test_ci_webhook_accepts_valid_secret(monkeypatch):
    _patch_cached_secrets(monkeypatch, ci=SECRET)
    payload = WebhookPayload(secret=SECRET, summary=CISummaryModel(run_id=990003, run_number=3))
    result = await receive_ci_webhook(payload)
    assert result["status"] == "received"
    assert result["run_id"] == 990003


# ── Telegram bot router — HTTP boundary secret + health honesty ───────────


class _StubTelegramHandler:
    """config-required সর্বনিম্ন handler stub (no network, no token)."""

    def __init__(self, configured: bool = False):
        self._configured = configured
        self.updates: list[dict] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def handle_update(self, update: dict) -> None:
        self.updates.append(update)

    async def get_me(self) -> dict:
        # এই ডেটা কখনো /health রেসপন্সে ফাঁস হওয়া উচিত নয়
        return {"id": 1, "username": "leaky_bot", "first_name": "Leaky"}


def _bot_client(handler: _StubTelegramHandler) -> TestClient:
    from tools.social.telegram_bot.router import create_telegram_router

    app = FastAPI()
    app.include_router(create_telegram_router(handler))
    return TestClient(app)


def test_telegram_webhook_without_secret_header_rejected(monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    handler = _StubTelegramHandler(configured=True)
    client = _bot_client(handler)
    resp = client.post("/telegram/webhook", json={"update_id": 1})
    assert resp.status_code == 401
    assert handler.updates == []


def test_telegram_webhook_with_tampered_secret_rejected(monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    handler = _StubTelegramHandler(configured=True)
    client = _bot_client(handler)
    resp = client.post("/telegram/webhook", json={"update_id": 1}, headers={SECRET_HEADER: "nope"})
    assert resp.status_code == 401
    assert handler.updates == []


def test_telegram_webhook_with_valid_secret_accepted(monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram=SECRET)
    handler = _StubTelegramHandler(configured=True)
    client = _bot_client(handler)
    resp = client.post("/telegram/webhook", json={"update_id": 1}, headers={SECRET_HEADER: SECRET})
    assert resp.status_code == 200


def test_telegram_webhook_fails_closed_when_secret_unset(monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram="")
    handler = _StubTelegramHandler(configured=True)
    client = _bot_client(handler)
    resp = client.post("/telegram/webhook", json={"update_id": 1}, headers={SECRET_HEADER: SECRET})
    assert resp.status_code == 401
    assert handler.updates == []


def test_telegram_health_does_not_leak_bot_identity(monkeypatch):
    _patch_cached_secrets(monkeypatch, telegram="")
    handler = _StubTelegramHandler(configured=True)
    client = _bot_client(handler)
    resp = client.get("/telegram/health")
    assert resp.status_code == 200
    body = resp.json()
    # বট identity (get_me) আর ফাঁস হয় না — শুধু সৎ configured স্টেট
    assert "bot" not in body
    assert body["configured"] is True
    assert body["status"] == "ok"
