"""Telegram MCP server contract suite — backend/tools/mcp/mcp_telegram.py.

Target: Telegram Bot MCP server (FastMCP("telegram_mcp")) — 276 missed lines
@ 0% before this suite (one of the owner audit's remaining P1 ramps:
Task-33 list — mcp_server ✓, mcp_telegram, playwright_browser_agent ✓,
dependency_manager_agent). Goal: full statement coverage without touching
owner code (wire-first doctrine), no network, no credentials.

Coverage map
------------
- ``telegram_send_message``  : explicit chat_id / env fallback / missing
                               chat_id guard / handler failure / empty
                               parse_mode → None contract
- ``telegram_get_bot_status``: unconfigured / configured+online /
                               configured+offline (error text)
- ``telegram_send_document`` : success round-trip (bytes+caption+HTML) /
                               missing-file guard / no-chat guard /
                               handler-exception containment
- ``telegram_broadcast_alert``: severity icon map (all four + unknown
                               fallback), no-chat guard, delivered receipt
- input models               : str_strip_whitespace, field defaults
- module wiring              : FastMCP instance name

Test-environment notes
----------------------
- ``_get_handler()`` is lazy; it is replaced wholesale with a scripted fake
  so ``tools.social.telegram_bot`` (which wants a real TELEGRAM_BOT_TOKEN and
  network) is never imported — exactly the production contract boundary.
- ``TELEGRAM_CHAT_ID`` is monkeypatched per test; never read from the real
  environment.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

import tools.mcp.mcp_telegram as mt

# =============================================================================
# Fakes
# =============================================================================


class FakeTelegramHandler:
    """Scripted double honouring the exact handler surface the tools call."""

    def __init__(
        self,
        *,
        configured: bool = True,
        me: dict | None = None,
        send_result: bool = True,
        doc_result: bool = True,
        raise_on_document: Exception | None = None,
    ) -> None:
        self.configured = configured
        self._me = me
        self._send_result = send_result
        self._doc_result = doc_result
        self._raise_on_document = raise_on_document
        self.sent: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []

    async def send_message(self, chat_id, text, parse_mode=None, **kwargs):
        self.sent.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
        return self._send_result

    async def get_me(self):
        return self._me

    async def send_document(
        self, chat_id, document, filename, caption="", parse_mode=None, **kwargs
    ):
        if self._raise_on_document is not None:
            raise self._raise_on_document
        self.documents.append(
            {
                "chat_id": chat_id,
                "document": document,
                "filename": filename,
                "caption": caption,
                "parse_mode": parse_mode,
            }
        )
        return self._doc_result


@pytest.fixture()
def handler(monkeypatch: pytest.MonkeyPatch) -> FakeTelegramHandler:
    fake = FakeTelegramHandler()
    monkeypatch.setattr(mt, "_get_handler", lambda: fake)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    return fake


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _json(payload: str) -> dict:
    return json.loads(payload)


# =============================================================================
# telegram_send_message
# =============================================================================


class TestSendMessage:
    async def test_success_with_explicit_chat_id(self, handler):
        out = _json(
            await mt.telegram_send_message(mt.SendMessageInput(text="hello", chat_id="12345"))
        )
        assert out == {"success": True, "chat_id": "12345", "status": "delivered"}
        assert handler.sent[0]["text"] == "hello"
        assert handler.sent[0]["parse_mode"] == "HTML"

    async def test_env_chat_id_used_when_omitted(self, handler, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100env")
        out = _json(await mt.telegram_send_message(mt.SendMessageInput(text="ping")))
        assert out["success"] is True
        assert out["chat_id"] == "-100env"

    async def test_missing_chat_id_is_guarded(self, handler):
        out = _json(await mt.telegram_send_message(mt.SendMessageInput(text="ping")))
        assert out["success"] is False
        assert "TELEGRAM_CHAT_ID" in out["error"]
        assert handler.sent == []

    async def test_handler_failure_reports_failed_status(self, handler):
        handler._send_result = False
        out = _json(await mt.telegram_send_message(mt.SendMessageInput(text="ping", chat_id="42")))
        assert out == {"success": False, "chat_id": "42", "status": "failed"}

    async def test_empty_parse_mode_passed_as_none(self, handler):
        await mt.telegram_send_message(mt.SendMessageInput(text="x", chat_id="42", parse_mode=""))
        assert handler.sent[0]["parse_mode"] is None


# =============================================================================
# telegram_get_bot_status
# =============================================================================


class TestGetBotStatus:
    async def test_unconfigured_reports_missing_token(self, handler):
        handler.configured = False
        out = _json(await mt.telegram_get_bot_status())
        assert out == {
            "configured": False,
            "status": "TELEGRAM_BOT_TOKEN is missing or set to placeholder.",
        }

    async def test_configured_and_online(self, handler):
        handler._me = {"id": 7, "username": "SupremeAIBot", "first_name": "Ünïcode ✓"}
        out = _json(await mt.telegram_get_bot_status())
        assert out["configured"] is True and out["online"] is True
        assert out["bot"]["username"] == "SupremeAIBot"

    async def test_configured_but_offline(self, handler):
        handler._me = None
        out = _json(await mt.telegram_get_bot_status())
        assert out == {
            "configured": True,
            "online": False,
            "error": "Failed to communicate with Telegram API. "
            "Token might be invalid or network blocked.",
        }


# =============================================================================
# telegram_send_document
# =============================================================================


class TestSendDocument:
    async def test_success_roundtrip(self, handler, tmp_path):
        doc = tmp_path / "report.txt"
        doc.write_bytes(b"PDF-BYTES-001")
        out = _json(
            await mt.telegram_send_document(
                mt.SendDocumentInput(file_path=str(doc), caption="nightly", chat_id="77")
            )
        )
        assert out == {"success": True, "filename": "report.txt", "chat_id": "77"}
        assert handler.documents[0]["document"] == b"PDF-BYTES-001"
        assert handler.documents[0]["caption"] == "nightly"
        assert handler.documents[0]["parse_mode"] == "HTML"

    async def test_missing_file_is_guarded(self, handler, tmp_path):
        out = _json(
            await mt.telegram_send_document(
                mt.SendDocumentInput(file_path=str(tmp_path / "nope.bin"), chat_id="77")
            )
        )
        assert out["success"] is False
        assert "File does not exist" in out["error"]
        assert handler.documents == []

    async def test_missing_chat_is_guarded(self, handler, tmp_path):
        doc = tmp_path / "report.txt"
        doc.write_bytes(b"x")
        out = _json(await mt.telegram_send_document(mt.SendDocumentInput(file_path=str(doc))))
        assert out["success"] is False
        assert "TELEGRAM_CHAT_ID" in out["error"]

    async def test_handler_exception_is_contained(self, handler, tmp_path):
        doc = tmp_path / "report.txt"
        doc.write_bytes(b"x")
        handler._raise_on_document = RuntimeError("upload boom")
        out = _json(
            await mt.telegram_send_document(mt.SendDocumentInput(file_path=str(doc), chat_id="77"))
        )
        assert out == {"success": False, "error": "upload boom"}


# =============================================================================
# telegram_broadcast_alert
# =============================================================================


class TestBroadcastAlert:
    @pytest.mark.parametrize(
        "severity,icon",
        [
            ("INFO", "ℹ️"),
            ("WARNING", "⚠️"),
            ("ERROR", "🚨"),
            ("CRITICAL", "🔥"),
            ("weird", "📢"),
        ],
    )
    async def test_severity_icons_and_delivery(self, handler, monkeypatch, severity, icon):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100ops")
        out = _json(
            await mt.telegram_broadcast_alert(
                mt.BroadcastAlertInput(title="CI red", details="lint gate", severity=severity)
            )
        )
        assert out == {"success": True, "chat_id": "-100ops", "severity": severity.upper()}
        text = handler.sent[0]["text"]
        assert text.startswith(f"{icon} <b>[SupremeAI Alert] {severity.upper()}</b>")
        assert "<b>CI red</b>" in text and "lint gate" in text
        assert handler.sent[0]["parse_mode"] == "HTML"

    async def test_missing_chat_env_is_guarded(self, handler):
        out = _json(
            await mt.telegram_broadcast_alert(mt.BroadcastAlertInput(title="t", details="d"))
        )
        assert out["success"] is False
        assert "TELEGRAM_CHAT_ID" in out["error"]

    async def test_broadcast_failure_propagates(self, handler, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100ops")
        handler._send_result = False
        out = _json(
            await mt.telegram_broadcast_alert(
                mt.BroadcastAlertInput(title="t", details="d", severity="ERROR")
            )
        )
        assert out["success"] is False


# =============================================================================
# Input models + module wiring
# =============================================================================


class TestInputModelsAndWiring:
    def test_send_message_input_strips_whitespace_and_defaults(self):
        inp = mt.SendMessageInput(text="  padded  ")
        assert inp.text == "padded"
        assert inp.parse_mode == "HTML"
        assert inp.chat_id is None

    def test_send_document_input_defaults(self):
        inp = mt.SendDocumentInput(file_path="/tmp/x")
        assert inp.caption == ""
        assert inp.chat_id is None

    def test_broadcast_alert_input_defaults(self):
        inp = mt.BroadcastAlertInput(title="t", details="d")
        assert inp.severity == "INFO"

    def test_fastmcp_instance_name(self):
        assert mt.mcp.name == "telegram_mcp"

    def test_get_handler_lazy_loads_real_class(self, monkeypatch):
        """The real _get_handler imports the owner handler lazily — the import
        itself must not require credentials or network (import-clean)."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        real = mt._get_handler()
        assert real is not None
