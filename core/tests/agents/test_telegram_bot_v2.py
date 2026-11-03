import hashlib
import hmac
from unittest.mock import AsyncMock

import pytest

from tools.social.telegram_bot import TelegramBotHandler
from tools.social.telegram_security import security_guard


@pytest.fixture
def bot_handler(monkeypatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "7804133572")
    handler = TelegramBotHandler()
    handler.bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    handler.send_message = AsyncMock(return_value=True)
    handler.answer_callback_query = AsyncMock(return_value=True)
    return handler


FABRICATED_METRICS = ("38ms", "142 Tasks", "99.99%")
"""M18 P-C/P-I: এই সংখ্যাগুলো ছিল hardcoded জাল KPI — এখন কোথাও ফিরে আসা নিষিদ্ধ।"""


def test_telegram_commands_dictionary():
    handler = TelegramBotHandler()
    assert "/start" in handler.COMMANDS
    assert "/app" in handler.COMMANDS
    assert "/quick" in handler.COMMANDS
    assert "/telemetry" in handler.COMMANDS
    assert "/help" in handler.COMMANDS

    # বাংলা: স্ট্যাটিক /telemetry টেক্সটে বানানো মেট্রিক থাকা নিষিদ্ধ (সৎ বর্ণনা মাত্র)।
    for fake in FABRICATED_METRICS:
        assert fake not in handler.COMMANDS["/telemetry"]
    assert "Mini App" in handler.COMMANDS["/app"]

    # M18 P-I: /abort কমান্ড help-এ নথিভুক্ত ও admin-প্যানেলে উল্লিখিত।
    assert "/abort" in handler.COMMANDS["/help"]


def test_telegram_sync_handle_message():
    handler = TelegramBotHandler()
    assert "Mini App" in handler.handle_message("/app")
    assert "Quick Actions" in handler.handle_message("/quick")
    sync_text = handler.handle_message("/telemetry")
    for fake in FABRICATED_METRICS:
        assert fake not in sync_text


@pytest.mark.asyncio
async def test_handle_update_telemetry_command_live_reads(bot_handler, monkeypatch):
    """বাংলা: /telemetry এখন বাস্তব পাঠ দেখায় — ফেক supervisor-health + ফেক রান-কাউন্ট।"""

    async def fake_count():
        return 3

    monkeypatch.setattr(bot_handler, "_live_active_run_count", fake_count)
    monkeypatch.setattr(
        "core.agent_supervisor.agent_supervisor.get_health",
        lambda: {
            "scheduled-task-sweep": {
                "status": "running",
                "uptime": 42.0,
                "restart_count": 0,
            }
        },
    )

    update = {
        "message": {
            "chat": {"id": 12345},
            "from": {"id": 12345, "username": "testuser"},
            "text": "/telemetry",
        }
    }
    await bot_handler.handle_update(update)
    bot_handler.send_message.assert_called_once()
    args, kwargs = bot_handler.send_message.call_args
    # বাস্তব পাঠের চিহ্ন: সচল রান সংখ্যা (3) ও agent-নাম এসেছে।
    assert "Active Runs:</b> 3" in args[1]
    assert "scheduled-task-sweep" in args[1]
    for fake in FABRICATED_METRICS:
        assert fake not in args[1]


@pytest.mark.asyncio
async def test_handle_update_telemetry_reports_unavailable_honestly(bot_handler, monkeypatch):
    """বাংলা: পাঠ ব্যর্থ হলে 'unavailable' যায় — ভুয়া সংখ্যা বা ভুয়া ০ নয়।"""

    async def broken_count():
        raise RuntimeError("db down")

    monkeypatch.setattr(bot_handler, "_live_active_run_count", broken_count)
    monkeypatch.setattr(
        "core.agent_supervisor.agent_supervisor.get_health",
        lambda: _raise_health(),
    )

    update = {
        "message": {
            "chat": {"id": 12345},
            "from": {"id": 12345, "username": "testuser"},
            "text": "/telemetry",
        }
    }
    await bot_handler.handle_update(update)
    args, _kwargs = bot_handler.send_message.call_args
    assert "unavailable" in args[1]
    for fake in FABRICATED_METRICS:
        assert fake not in args[1]


def _raise_health():
    raise RuntimeError("supervisor broken")


@pytest.mark.asyncio
async def test_abort_admin_only_fail_closed(bot_handler, monkeypatch):
    """বাংলা: /abort admin-ছাড়া কারও কাছে ক্যান্সেল করাবে না (fail-closed)।"""
    called = {"cancel": False}

    async def _never_cancel(*args, **kwargs):  # pragma: no cover — কল হলেই টেস্ট ব্যর্থ
        called["cancel"] = True
        raise AssertionError("cancel কল হওয়া উচিত নয়")

    monkeypatch.setattr(
        "tools.social.telegram_bot.admin_handlers.AdminHandlersMixin._handle_abort",
        _never_cancel,
    )
    update = {
        "message": {
            "chat": {"id": 99999},  # admin নয় (is_admin ডিফল্ট admin-id আলাদা)
            "from": {"id": 99999, "username": "attacker"},
            "text": "/abort some-run-id",
        }
    }
    await bot_handler.handle_update(update)
    args, _kwargs = bot_handler.send_message.call_args
    assert "restricted" in args[1]
    assert called["cancel"] is False


@pytest.mark.asyncio
async def test_abort_admin_calls_real_cancel_service(bot_handler, monkeypatch):
    """বাংলা: admin-এর /abort প্রকৃত run_service.cancel পথেই যায় — ফেক নয়।"""
    from contextlib import asynccontextmanager

    cancelled = {}

    class FakeSession:
        async def commit(self):
            cancelled["committed"] = True

    @asynccontextmanager
    async def fake_ctx():
        yield FakeSession()

    async def fake_cancel(session, run_id, *, actor=None, reason=None):
        cancelled.update({"run_id": run_id, "actor": actor, "reason": reason})
        from types import SimpleNamespace

        return SimpleNamespace(status="cancelled")

    # বাংলা: full-suite-এ অন্য টেস্টের env-লিকে is_admin অনিশ্চিত হয় — এখানে বাঁধন।
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "7804133572")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr("database.session.get_db_session_context", fake_ctx)
    import runs.api as runs_api_mod

    monkeypatch.setattr(runs_api_mod.run_service, "cancel", fake_cancel)

    update = {
        "message": {
            "chat": {"id": 7804133572},  # ডিফল্ট admin chat id (is_admin পথ)
            "from": {"id": 7804133572, "username": "owner"},
            "text": "/abort 9b7f2a10-1111-2222-3333-444455556666",
        }
    }
    await bot_handler.handle_update(update)
    assert cancelled["run_id"] == "9b7f2a10-1111-2222-3333-444455556666"
    assert cancelled["actor"].startswith("telegram:admin:")
    assert cancelled["committed"] is True
    args, _kwargs = bot_handler.send_message.call_args
    assert "cancelled" in args[1]


@pytest.mark.asyncio
async def test_abort_unknown_run_reports_honestly(bot_handler, monkeypatch):
    """বাংলা: অজানা run_id → সৎ 'not found' — ভুয়া 'বাতিল হয়েছে' নয়।"""
    from contextlib import asynccontextmanager

    from runs.service import RunNotFound

    @asynccontextmanager
    async def fake_ctx():
        class FakeSession:
            async def commit(self):  # pragma: no cover — এখানে আসার কথা নয়
                raise AssertionError("commit হওয়া উচিত নয়")

        yield FakeSession()

    async def fake_cancel(session, run_id, **kwargs):
        raise RunNotFound(f"run {run_id!r} not found")

    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "7804133572")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr("database.session.get_db_session_context", fake_ctx)
    import runs.api as runs_api_mod

    monkeypatch.setattr(runs_api_mod.run_service, "cancel", fake_cancel)

    update = {
        "message": {
            "chat": {"id": 7804133572},
            "from": {"id": 7804133572, "username": "owner"},
            "text": "/abort deadbeef-0000-0000-0000-000000000000",
        }
    }
    await bot_handler.handle_update(update)
    args, _kwargs = bot_handler.send_message.call_args
    assert "খুঁজে পাওয়া যায়নি" in args[1]
    assert "cancelled" not in args[1]


@pytest.mark.asyncio
async def test_abort_without_run_id_shows_usage(bot_handler, monkeypatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "7804133572")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    update = {
        "message": {
            "chat": {"id": 7804133572},
            "from": {"id": 7804133572, "username": "owner"},
            "text": "/abort",
        }
    }
    await bot_handler.handle_update(update)
    args, _kwargs = bot_handler.send_message.call_args
    assert "/abort" in args[1]


@pytest.mark.asyncio
async def test_handle_update_app_command(bot_handler):
    update = {
        "message": {
            "chat": {"id": 12345},
            "from": {"id": 12345, "username": "testuser"},
            "text": "/app",
        }
    }
    await bot_handler.handle_update(update)
    bot_handler.send_message.assert_called_once()
    args, kwargs = bot_handler.send_message.call_args
    assert "Mini App" in args[1]
    assert "reply_markup" in kwargs
    assert "web_app" in str(kwargs["reply_markup"])


@pytest.mark.asyncio
async def test_handle_update_quick_actions_callback(bot_handler):
    update = {
        "callback_query": {
            "id": "cb-123",
            "data": "quick_self_healer",
            "message": {"chat": {"id": 12345}},
        }
    }
    await bot_handler.handle_update(update)
    bot_handler.answer_callback_query.assert_called_once_with("cb-123")
    bot_handler.send_message.assert_called_once()
    args, _ = bot_handler.send_message.call_args
    # বাংলা (M18 P-C): ভুয়া diagnosis-ফলাফল অবসান — সৎ নির্দেশক টেক্সট।
    assert "Self-Healer" in args[1]
    assert "100% HEALTHY" not in args[1]
    assert "38ms" not in args[1]


@pytest.mark.asyncio
async def test_handle_update_kb_search(bot_handler):
    update = {
        "message": {
            "chat": {"id": 12345},
            "from": {"id": 12345, "username": "testuser"},
            "text": "/kb browser",
        }
    }
    await bot_handler.handle_update(update)
    bot_handler.send_message.assert_called_once()
    args, _ = bot_handler.send_message.call_args
    assert "Autonomous Browser Suite" in args[1]


def test_telegram_security_webapp_validation():
    bot_token = "secret_bot_token_123"
    auth_date = "1700000000"
    user_json = '{"id":12345,"first_name":"Niloy"}'

    # Construct check string
    check_string = f"auth_date={auth_date}\nuser={user_json}"
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    valid_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    init_data = f"auth_date={auth_date}&user={user_json}&hash={valid_hash}"

    valid, parsed = security_guard.validate_webapp_init_data(init_data, bot_token)
    assert valid is True
    assert parsed["auth_date"] == auth_date

    # Invalid hash test
    invalid_init_data = f"auth_date={auth_date}&user={user_json}&hash=invalid_hash"
    invalid_res, _ = security_guard.validate_webapp_init_data(invalid_init_data, bot_token)
    assert invalid_res is False
