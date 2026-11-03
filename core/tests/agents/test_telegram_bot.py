import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.social.telegram_bot import TelegramBotHandler


@pytest.fixture
def handler():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"}):
        return TelegramBotHandler()


def test_configured(handler):
    assert handler.configured is True
    assert handler.bot_token == "test-token"


def test_configured_no_token():
    with patch.dict(os.environ, {}, clear=True):
        h = TelegramBotHandler()
    assert h.configured is False


def test_configured_mock_token():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token"}):
        h = TelegramBotHandler()
    assert h.configured is False


@pytest.mark.asyncio
async def test_send_message_disabled():
    with patch.dict(os.environ, {}, clear=True):
        h = TelegramBotHandler()
    result = await h.send_message(chat_id=123, text="hello")
    assert result is False


@pytest.mark.asyncio
async def test_send_typing_disabled():
    with patch.dict(os.environ, {}, clear=True):
        h = TelegramBotHandler()
    await h.send_typing(chat_id=123)


@pytest.mark.asyncio
async def test_set_webhook_disabled():
    with patch.dict(os.environ, {}, clear=True):
        h = TelegramBotHandler()
    result = await h.set_webhook("https://example.com")
    assert result is False


@pytest.mark.asyncio
async def test_get_me_disabled():
    with patch.dict(os.environ, {}, clear=True):
        h = TelegramBotHandler()
    result = await h.get_me()
    assert result is None


@pytest.mark.asyncio
async def test_send_message_success(handler):
    mock_post = AsyncMock()
    mock_post.return_value.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient.post", mock_post):
        result = await handler.send_message(chat_id=123, text="hi")
    assert result is True


@pytest.mark.asyncio
async def test_send_message_failure(handler):
    mock_post = AsyncMock(side_effect=Exception("network error"))
    with patch("httpx.AsyncClient.post", mock_post):
        result = await handler.send_message(chat_id=123, text="hi")
    assert result is False


@pytest.mark.asyncio
async def test_set_webhook_success(handler):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient.post", mock_post):
        result = await handler.set_webhook("https://example.com")
    assert result is True


@pytest.mark.asyncio
async def test_set_webhook_error(handler):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "bad url"}
    mock_post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient.post", mock_post):
        result = await handler.set_webhook("https://example.com")
    assert result is False


@pytest.mark.asyncio
async def test_get_me_success(handler):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": {"id": 1, "username": "bot"}}
    mock_get = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient.get", mock_get):
        result = await handler.get_me()
    assert result == {"id": 1, "username": "bot"}


@pytest.mark.asyncio
async def test_get_me_failure(handler):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False}
    mock_get = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient.get", mock_get):
        result = await handler.get_me()
    assert result is None


def test_handle_message_command(handler):
    response = handler.handle_message("/start")
    assert "Welcome" in response


def test_handle_message_help(handler):
    response = handler.handle_message("/help")
    assert "Commands" in response


def test_handle_message_admin(handler):
    response = handler.handle_message("/admin")
    assert "Admin" in response


def test_handle_message_rules(handler):
    response = handler.handle_message("/rules")
    assert "rules" in response.lower() or "directions" in response.lower()


def test_handle_message_unknown_command(handler):
    response = handler.handle_message("/unknown")
    assert "SupremeAI 2.0" in response


def test_handle_message_ai_fallback_no_orchestrator(handler):
    response = handler.handle_message("hello bot")
    assert "SupremeAI 2.0" in response


def test_handle_message_ai_fallback_with_orchestrator(handler):
    mock_orchestrator = MagicMock()
    mock_orchestrator.execute_task.return_value = {"result": "Mock AI reply"}
    handler.processor = mock_orchestrator
    response = handler.handle_message("hello bot", user_id="user1")
    assert response == "Mock AI reply"


def test_handle_message_ai_fallback_error(handler):
    mock_orchestrator = MagicMock()
    mock_orchestrator.execute_task.side_effect = Exception("LLM error")
    handler.processor = mock_orchestrator
    response = handler.handle_message("hello bot", user_id="user1")
    assert "SupremeAI 2.0" in response or "Error" in response


@pytest.mark.asyncio
async def test_handle_update_no_message(handler):
    await handler.handle_update({"update_id": 1, "edited_message": {"chat": {"id": 1}}})
    # Should return without error


@pytest.mark.asyncio
async def test_handle_update_command(handler):
    mock_send = AsyncMock()
    handler.send_message = mock_send
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456, "username": "tester"},
            "text": "/start",
        },
    }
    await handler.handle_update(update)
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_update_ai_fallback(handler):
    "বাংলা মন্তব্য: রেস কন্ডিশন ফিক্স — ব্যাকগ্রাউন্ড টাস্ক কমপ্লিট হওয়ার জন্য লুপে কন্ট্রোল ইল্ড (Yield) করা হলো।"
    mock_send = AsyncMock()
    mock_send_typing = AsyncMock()
    handler.send_message = mock_send
    handler.send_typing = mock_send_typing
    handler._ai_response = AsyncMock(return_value="AI reply")
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "what is ai",
        },
    }
    await handler.handle_update(update)
    await asyncio.sleep(0.05)
    mock_send_typing.assert_called_once_with(123)
    mock_send.assert_called_once_with(123, "AI reply")


@pytest.mark.asyncio
async def test_handle_status_no_urls(handler):
    mock_send = AsyncMock()
    handler.send_message = mock_send
    await handler._handle_status(chat_id=1)
    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "Telemetry" in body or "SupremeAI" in body


@pytest.mark.asyncio
async def test_run_polling_disabled():
    with patch.dict(os.environ, {}, clear=True):
        h = TelegramBotHandler()
    with patch.object(h, "get_me", return_value=None):
        await h.run_polling()


def test_create_telegram_router(handler):
    from tools.social.telegram_bot import create_telegram_router

    router = create_telegram_router(handler)
    assert router is not None
    assert any(route.path == "/telegram/webhook" for route in router.routes)
