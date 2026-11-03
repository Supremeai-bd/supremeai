"""MESH-4 Telegram command-handler tests — issue #942 (P2-medium).

বাংলা: সব HTTP (Telegram + Tower) httpx.MockTransport দিয়ে mock — কোনো
নেটওয়ার্ক কল নেই। কভারেজ: কমান্ড রাউটিং, অ্যাক্সেস-কন্ট্রোল (fail-closed),
HITL approve/reject/defer, defer-limit auto-reject, watcher card flow।
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from integrations.telegram_bot import MeshTelegramBot, TowerClient
from integrations.telegram_config import MeshTelegramConfig
from integrations.telegram_handlers import DeferStore, KeyRegistry

# ── Fixtures ─────────────────────────────────────────────────────────────────
ADMIN_CHAT = "111"
TG_API = "https://api.telegram.org/botTESTTOKEN"


def make_config(**overrides: Any) -> MeshTelegramConfig:
    base = dict(
        bot_token="TESTTOKEN",
        admin_chat_id=ADMIN_CHAT,
        tower_base_url="http://tower.test",
        tower_admin_token="admin-token",
        hitl_ask_timeout_sec=300,
        defer_limit=3,
        hitl_poll_interval_sec=20,
    )
    base.update(overrides)
    return MeshTelegramConfig(**base)


class RecordingTelegram:
    """TelegramClient-এর কাঠামোগত ডাবল — পাঠানো মেসেজ/উত্তর রেকর্ড করে।"""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.answers: list[tuple[str, str]] = []
        self.edits: list[tuple[str, int, str]] = []

    async def send_message(
        self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None
    ) -> int | None:
        self.sent.append({"chat_id": chat_id, "text": text, "markup": reply_markup})
        return 100 + len(self.sent)

    async def answer_callback(self, callback_query_id: str, text: str) -> None:
        self.answers.append((callback_query_id, text))

    async def edit_message(self, chat_id: str, message_id: int, text: str) -> None:
        self.edits.append((chat_id, message_id, text))


class TowerStub:
    """TowerClient ডাবল — path অনুযায়ী প্রি-সেট রেসপন্স, কল-রেকর্ডিং সহ।"""

    def __init__(self, responses: dict[str, tuple[int, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def request(
        self, method: str, path: str, json_body: dict[str, Any] | None = None
    ) -> tuple[int, Any]:
        self.calls.append((method, path, json_body))
        return self.responses.get(path, (404, {"detail": "unstubbed " + path}))


def make_bot(config: MeshTelegramConfig | None = None) -> MeshTelegramBot:
    bot = MeshTelegramBot(config or make_config())
    bot.tg = RecordingTelegram()  # type: ignore[assignment]
    return bot


def wire_tower(bot: MeshTelegramBot, tower: Any) -> None:
    """টেস্ট-টাওয়ার সব খাঁড়িতে লাগাও — commands/callbacks একই রেফারেন্স শেয়ার করে।"""
    bot.tower = tower  # type: ignore[assignment]
    bot.commands.tower = tower  # type: ignore[assignment]
    bot.callbacks.tower = tower  # type: ignore[assignment]


def msg_update(text: str, chat_id: str = ADMIN_CHAT) -> dict[str, Any]:
    return {"update_id": 1, "message": {"chat": {"id": int(chat_id)}, "text": text}}


def cb_update(data: str, chat_id: str = ADMIN_CHAT) -> dict[str, Any]:
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cbq-1",
            "data": data,
            "message": {"chat": {"id": int(chat_id)}},
        },
    }


# ── Command tests ────────────────────────────────────────────────────────────
def test_task_command_creates_task_in_tower():
    tower = TowerStub(
        {
            "/api/v1/mesh/tasks": (201, {"task_id": "t-42", "status": "pending"}),
        }
    )
    bot = make_bot()
    wire_tower(bot, tower)
    reply = asyncio.run(bot.handle_update(msg_update("/task add rate limiting")))
    assert "t-42" in reply
    method, path, body = tower.calls[0]
    assert (method, path) == ("POST", "/api/v1/mesh/tasks")
    assert body["task_type"] == "custom"
    assert body["title"] == "add rate limiting"
    assert body["payload"]["source"] == "telegram"


def test_task_command_without_description_shows_usage():
    bot = make_bot()
    wire_tower(bot, TowerStub())
    reply = asyncio.run(bot.handle_update(msg_update("/task")))
    assert "ব্যবহার" in reply


def test_status_command_formats_queue():
    tower = TowerStub(
        {
            "/api/v1/mesh/tasks": (
                200,
                {
                    "count": 2,
                    "stats": {"pending": 1, "leased": 1},
                    "tasks": [
                        {
                            "task_id": "t1",
                            "status": "pending",
                            "title": "one",
                            "lease_node_id": None,
                        },
                        {
                            "task_id": "t2",
                            "status": "leased",
                            "title": "two",
                            "lease_node_id": "pc-1",
                        },
                    ],
                },
            ),
        }
    )
    bot = make_bot()
    wire_tower(bot, tower)
    reply = asyncio.run(bot.handle_update(msg_update("/status")))
    assert "t2" in reply and "pc-1" in reply and "50%" in reply
    assert "pending=1" in reply


def test_nodes_command_lists_agents():
    tower = TowerStub(
        {
            "/api/v1/nodes": (
                200,
                {"nodes": [{"node_id": "pc-1", "role": "coder", "status": "online"}]},
            ),
        }
    )
    bot = make_bot()
    wire_tower(bot, tower)
    reply = asyncio.run(bot.handle_update(msg_update("/nodes")))
    assert "pc-1" in reply and "coder" in reply


def test_cancel_command_calls_cancel_endpoint():
    tower = TowerStub({"/api/v1/mesh/tasks/t9/cancel": (200, {"task_id": "t9"})})
    bot = make_bot()
    wire_tower(bot, tower)
    reply = asyncio.run(bot.handle_update(msg_update("/cancel t9")))
    assert "বাতিল" in reply
    assert tower.calls[0][1] == "/api/v1/mesh/tasks/t9/cancel"


# ── Access-control tests (fail-closed) ───────────────────────────────────────
def test_non_admin_chat_is_ignored_completely():
    tower = TowerStub()
    bot = make_bot()
    wire_tower(bot, tower)
    asyncio.run(bot.handle_update(msg_update("/status", chat_id="999")))
    assert tower.calls == []  # Tower-এ কোনো কলই হয়নি


def test_non_admin_callback_is_ignored():
    tower = TowerStub()
    bot = make_bot()
    wire_tower(bot, tower)
    asyncio.run(bot.handle_update(cb_update("hitl:a:1", chat_id="999")))
    assert tower.calls == []


def test_unknown_command_gets_hint():
    bot = make_bot()
    wire_tower(bot, TowerStub())
    reply = asyncio.run(bot.handle_update(msg_update("/frobnicate")))
    assert "অজানা" in reply


# ── HITL callback tests ──────────────────────────────────────────────────────
def test_approve_callback_calls_hitl_approve():
    tower = TowerStub({"/api/v1/hitl/approve/rec-1": (200, {"status": "approved"})})
    bot = make_bot()
    wire_tower(bot, tower)
    key = bot.registry.key_for("rec-1")
    reply = asyncio.run(bot.handle_update(cb_update(f"hitl:a:{key}")))
    assert "অনুমোদিত" in reply
    assert tower.calls[0][1] == "/api/v1/hitl/approve/rec-1"
    assert tower.calls[0][2]["resolved_by"] == "telegram-admin"


def test_reject_callback_calls_hitl_reject():
    tower = TowerStub({"/api/v1/hitl/reject/rec-2": (200, {"status": "rejected"})})
    bot = make_bot()
    wire_tower(bot, tower)
    key = bot.registry.key_for("rec-2")
    reply = asyncio.run(bot.handle_update(cb_update(f"hitl:r:{key}")))
    assert "প্রত্যাখ্যাত" in reply


def test_approve_without_admin_token_fails_closed():
    bot = make_bot(make_config(tower_admin_token=""))
    wire_tower(bot, TowerStub())
    key = bot.registry.key_for("rec-x")
    reply = asyncio.run(bot.handle_update(cb_update(f"hitl:a:{key}")))
    assert "TOWER_ADMIN_TOKEN" in reply


def test_stale_callback_key_reports_invalid():
    bot = make_bot()
    wire_tower(bot, TowerStub())
    reply = asyncio.run(bot.handle_update(cb_update("hitl:a:999")))
    assert "বৈধ নয়" in reply


def test_defer_button_increments_and_auto_rejects_at_limit():
    tower = TowerStub(
        {
            "/api/v1/hitl/reject/rec-3": (200, {"status": "rejected"}),
        }
    )
    bot = make_bot(make_config(defer_limit=2))
    wire_tower(bot, tower)
    key = bot.registry.key_for("rec-3")
    first = asyncio.run(bot.handle_update(cb_update(f"hitl:d:{key}")))
    assert "Deferred (1/2)" in first
    second = asyncio.run(bot.handle_update(cb_update(f"hitl:d:{key}")))
    assert "Auto-reject" in second
    assert tower.calls[0][1] == "/api/v1/hitl/reject/rec-3"


# ── HITL watcher tests ───────────────────────────────────────────────────────
def test_hitl_tick_sends_card_for_new_pending_record():
    tower = TowerStub(
        {
            "/api/v1/hitl/pending": (
                200,
                [{"id": "rec-9", "target_resource": "deploy:prod", "payload": {"env": "prod"}}],
            ),
        }
    )
    bot = make_bot()
    wire_tower(bot, tower)
    asyncio.run(bot.hitl_tick())
    assert len(bot.tg.sent) == 1
    card = bot.tg.sent[0]
    assert card["chat_id"] == ADMIN_CHAT
    assert "HITL required" in card["text"]
    assert "✅ Approve" in json.dumps(card["markup"], ensure_ascii=False)


def test_hitl_tick_auto_rejects_after_defer_limit_without_response():
    tower = TowerStub(
        {
            "/api/v1/hitl/pending": (
                200,
                [{"id": "rec-10", "target_resource": "db:migrate", "payload": {}}],
            ),
            "/api/v1/hitl/reject/rec-10": (200, {"status": "rejected"}),
        }
    )
    bot = make_bot(make_config(defer_limit=2, hitl_ask_timeout_sec=0))
    wire_tower(bot, tower)
    # tick1: কার্ড পাঠায় (defers=1); tick2: re-ask (defers=2); tick3: auto-reject
    asyncio.run(bot.hitl_tick())
    asyncio.run(bot.hitl_tick())
    asyncio.run(bot.hitl_tick())
    reject_calls = [c for c in tower.calls if c[1] == "/api/v1/hitl/reject/rec-10"]
    assert len(reject_calls) == 1
    assert (
        "auto-reject" in reject_calls[0][2]["reason"] and "defers" in reject_calls[0][2]["reason"]
    )


def test_hitl_tick_forgets_resolved_records():
    tower = TowerStub(
        {
            "/api/v1/hitl/pending": (200, []),
        }
    )
    bot = make_bot()
    wire_tower(bot, tower)
    bot.defers.ensure("rec-gone", 0)
    asyncio.run(bot.hitl_tick())
    assert bot.defers.get("rec-gone") is None


# ── Unit: registries ─────────────────────────────────────────────────────────
def test_key_registry_is_stable_per_record():
    reg = KeyRegistry()
    k1 = reg.key_for("abc")
    assert reg.key_for("abc") == k1
    assert reg.record_for(k1) == "abc"
    assert reg.record_for("nope") is None


def test_defer_store_mark_and_forget():
    ds = DeferStore()
    ds.ensure("r", 100)
    assert ds.mark_asked("r", 100, 300) == 1
    assert ds.get("r")["next_ask"] == 400
    ds.forget("r")
    assert ds.get("r") is None


# ── TowerClient (httpx.MockTransport) ────────────────────────────────────────
def test_tower_client_parses_json_and_sends_auth_header(monkeypatch):
    seen = {"auth": None, "method": None, "url": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "nodes": []})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return real_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("integrations.telegram_bot.httpx.AsyncClient", factory)
    client = TowerClient("http://tower.test", admin_token="secret-token")
    code, data = asyncio.run(client.request("GET", "/api/v1/nodes"))
    assert code == 200 and data["ok"] is True
    assert seen["auth"] == "Bearer secret-token"
    assert seen["url"].startswith("http://tower.test/api/v1/nodes")


def test_tower_client_non_json_body_becomes_detail_dict(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>bad gateway</html>")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return real_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("integrations.telegram_bot.httpx.AsyncClient", factory)
    client = TowerClient("http://tower.test")
    code, data = asyncio.run(client.request("POST", "/api/v1/mesh/tasks", json_body={"a": 1}))
    assert code == 502
    assert "bad gateway" in str(data["detail"])
