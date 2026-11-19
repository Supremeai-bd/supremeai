"""Inbound strategy webhook on the same app shipped by Docker. No network I/O."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from gateway.service.app import app
from gateway.service import telegram_webhook
from gateway.service.pool import FederationSquad, KeySlot

HOOK = "/webhook/telegram"
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": "fixture-hook-secret"}
UPDATE = {"message": {"message_id": 101, "chat": {"id": 12345}, "text": "/spark latency roadmap"}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fixture-bot-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", HEADERS["X-Telegram-Bot-Api-Secret-Token"])
    processor = AsyncMock()
    monkeypatch.setattr(telegram_webhook, "_process_and_reply", processor)
    # No lifespan startup; this fixture exercises only the HTTP contract.
    client = TestClient(app)
    try:
        yield client, processor
    finally:
        client.close()


def test_status_is_not_proof_of_webhook_delivery(client):
    resp = client[0].get(HOOK + "/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert "/spark" in resp.json()["triggers"]
    assert "fixture-bot-token" not in resp.text


def test_only_authenticated_configured_hook_schedules_work(client, monkeypatch):
    api, processor = client
    assert api.post(HOOK, json=UPDATE).status_code == 401
    assert api.post(HOOK, json=UPDATE, headers={next(iter(HEADERS)): "wrong-token"}).status_code == 401
    processor.assert_not_called()
    assert api.post(HOOK, json=UPDATE, headers=HEADERS).json() == {"status": "accepted"}
    processor.assert_awaited_once_with(12345, "/spark latency roadmap", 101)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET")
    assert api.post(HOOK, json=UPDATE, headers=HEADERS).status_code == 503
    assert processor.await_count == 1


def test_authenticated_non_triggered_input_does_not_dispatch(client):
    api, processor = client
    assert api.post(HOOK, json={}, headers=HEADERS).json() == {"status": "ignored_non_text"}
    assert api.post(HOOK, json=[], headers=HEADERS).status_code == 400
    assert api.post(HOOK, json={"message": {"text": "/spark"}}, headers=HEADERS).status_code == 400
    update = {"message": {"chat": {"id": 12345, "type": "group"}, "text": "Not a command"}}
    assert api.post(HOOK, json=update, headers=HEADERS).json() == {"status": "passthrough"}
    processor.assert_not_called()


@pytest.mark.asyncio
async def test_raw_credentials_cannot_trigger_strategy_inference(monkeypatch):
    for env in ("SUPREMEAI_FREE_ROUTE_POLICY", "STEALTH_WEBHOOK_URL", "UPSTREAM_WEBHOOK_URL"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-provider-secret")
    squad = FederationSquad()
    assert squad.pools["gemini"].slots
    monkeypatch.setattr(telegram_webhook, "squad", squad)
    provider = AsyncMock()
    monkeypatch.setattr(telegram_webhook, "forward_chat_completion", provider)
    outbound = Mock(side_effect=AssertionError("no direct provider request"))
    monkeypatch.setattr(telegram_webhook, "get_telegram_client", outbound)
    assert await telegram_webhook.query_strategy_ai("fixture question")
    provider.assert_not_awaited()
    outbound.assert_not_called()


@pytest.mark.asyncio
async def test_strategy_route_passes_the_eligible_slot_to_shared_adapter(monkeypatch):
    for env in ("STEALTH_WEBHOOK_URL", "UPSTREAM_WEBHOOK_URL"):
        monkeypatch.delenv(env, raising=False)
    slot = KeySlot("fixture-slot", "fixture-key", "openrouter")
    monkeypatch.setattr(telegram_webhook.squad, "get_candidate_slots", lambda: [("openrouter", slot)])
    provider = AsyncMock(return_value=(200, {"choices": [{"message": {"content": "Approved reply"}}]}))
    monkeypatch.setattr(telegram_webhook, "forward_chat_completion", provider)
    assert await telegram_webhook.query_strategy_ai("fixture prompt") == "Approved reply"
    assert provider.await_args.kwargs["slot"] is slot
