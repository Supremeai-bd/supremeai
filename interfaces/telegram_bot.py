"""
SupremeAI 2.0 — Telegram Bot Handler (Production-Ready)

Features:
- Webhook support (recommended for production)
- Polling mode fallback (dev/local)
- /start, /help, /status, /admin commands
- Auto-routes to SupremeOrchestrator

Setup:
  1. Get token from @BotFather → /newbot
  2. Set TELEGRAM_BOT_TOKEN in .env
  3. For webhook: set TELEGRAM_WEBHOOK_URL = https://your-domain.com/telegram/webhook
  4. Register webhook:
     curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WEBHOOK_URL>"
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import httpx
from loguru import logger


class TelegramBotHandler:
    """
    Production Telegram Bot — handles messages via webhook payload.
    Integrates with SupremeOrchestrator for AI responses.
    """

    COMMANDS = {
        "/start": "👋 Welcome to *SupremeAI 2.0*!\nSend any message and I'll respond with AI power.",
        "/help": (
            "📖 *Commands:*\n"
            "/start — Welcome\n"
            "/help  — Show this help\n"
            "/status — System health check\n"
            "/admin — Admin menu (authorized only)\n\n"
            "Or just type anything and I'll handle it!"
        ),
        "/admin": "🔐 *Admin menu:*\n/rules /limit /block /unblock",
        "/rules": "📜 Constitutional rules: 5 directions (North, South, East, West, Center)",
    }

    def __init__(self, orchestrator=None) -> None:
        self.bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.api_base: str = f"https://api.telegram.org/bot{self.bot_token}"
        self.orchestrator = orchestrator

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.bot_token != "mock_token")

    # ── Telegram API helpers ──────────────────────────────────────

    async def send_message(self, chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.error(f"Telegram sendMessage failed: {exc}")
            return False

    async def send_typing(self, chat_id: int | str) -> None:
        if not self.configured:
            return
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{self.api_base}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                )
        except Exception:
            pass

    async def set_webhook(self, webhook_url: str) -> bool:
        """Register webhook URL with Telegram."""
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.api_base}/setWebhook",
                    json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]},
                )
                data = resp.json()
                if data.get("ok"):
                    logger.info(f"✅ Telegram webhook set: {webhook_url}")
                    return True
                logger.error(f"Webhook error: {data}")
                return False
        except Exception as exc:
            logger.error(f"set_webhook failed: {exc}")
            return False

    async def get_me(self) -> Optional[Dict[str, Any]]:
        """Verify bot token and get bot info."""
        if not self.configured:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.api_base}/getMe")
                data = resp.json()
                return data.get("result") if data.get("ok") else None
        except Exception as exc:
            logger.error(f"getMe failed: {exc}")
            return None

    # ── Message handling ──────────────────────────────────────────

    # ── Synchronous convenience wrapper ───────────────────────────

    def handle_message(self, text: str, user_id: str = "user") -> str:
        """Synchronous message handler used by tests and scripts."""
        command = text.strip().split()[0].lower() if text.strip().startswith("/") else None
        if command and command in self.COMMANDS:
            return self.COMMANDS[command]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._ai_response(text, user_id))
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def handle_update(self, update: Dict[str, Any]) -> None:
        """Process a Telegram update payload (from webhook or polling)."""
        message = update.get("message")
        if not message:
            return

        chat_id: int = message["chat"]["id"]
        text: str = message.get("text", "").strip()
        user_id: str = str(message["from"]["id"])
        username: str = message["from"].get("username", user_id)

        logger.info(f"Telegram message from @{username} ({user_id}): '{text}'")

        # Command handling
        command = text.split()[0].lower() if text.startswith("/") else None
        if command:
            reply = self.COMMANDS.get(command)
            if reply:
                await self.send_message(chat_id, reply)
                return
            if command == "/status":
                await self._handle_status(chat_id)
                return

        # AI fallback
        await self.send_typing(chat_id)
        ai_response = await self._ai_response(text, user_id)
        await self.send_message(chat_id, ai_response)

    async def _handle_status(self, chat_id: int | str) -> None:
        import httpx as _httpx
        gcp_url = os.getenv("GCP_CLOUD_RUN_URL", "")
        status_lines = ["🔍 *System Status:*\n"]
        for name, url in [
            ("GCP", gcp_url),
            ("Railway", os.getenv("RAILWAY_URL", "")),
            ("Render", os.getenv("RENDER_URL", "")),
        ]:
            if not url:
                status_lines.append(f"⚪ {name}: not configured")
                continue
            try:
                async with _httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(url + "/health")
                    icon = "✅" if r.status_code == 200 else "⚠️"
                    status_lines.append(f"{icon} {name}: `{r.status_code}`")
            except Exception:
                status_lines.append(f"❌ {name}: unreachable")
        await self.send_message(chat_id, "\n".join(status_lines))

    async def _ai_response(self, text: str, user_id: str) -> str:
        if self.orchestrator:
            try:
                task_type = "coding" if any(k in text.lower() for k in ["code", "function", "script"]) else "general"
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: self.orchestrator.execute_task(text, task_type)
                )
                return result.get("result", "Sorry, I couldn't process that.")
            except Exception as exc:
                logger.error(f"Orchestrator error: {exc}")
                return "⚠️ Error processing request. Please try again."
        return "🤖 SupremeAI 2.0 is ready! (Orchestrator not connected)"

    # ── Polling mode (dev/local) ─────────────────────────────────

    async def run_polling(self) -> None:
        """Long-polling loop — use only in local/dev mode."""
        if not self.configured:
            logger.warning("Telegram bot not configured — skipping polling.")
            return

        me = await self.get_me()
        if not me:
            logger.error("Invalid TELEGRAM_BOT_TOKEN — cannot start polling.")
            return

        logger.info(f"🤖 Telegram bot @{me['username']} started (polling mode)")
        offset: Optional[int] = None

        while True:
            try:
                async with httpx.AsyncClient(timeout=35) as client:
                    params: Dict[str, Any] = {"timeout": 30, "allowed_updates": ["message"]}
                    if offset is not None:
                        params["offset"] = offset
                    resp = await client.get(f"{self.api_base}/getUpdates", params=params)
                    data = resp.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        asyncio.create_task(self.handle_update(update))
            except httpx.TimeoutException:
                continue
            except Exception as exc:
                logger.error(f"Polling error: {exc}")
                await asyncio.sleep(5)


# ── FastAPI webhook endpoint helper ──────────────────────────────

def create_telegram_router(handler: TelegramBotHandler):
    """Returns a FastAPI router for Telegram webhook endpoint."""
    from fastapi import APIRouter, Request, Response

    router = APIRouter(prefix="/telegram", tags=["telegram"])

    @router.post("/webhook")
    async def telegram_webhook(request: Request):
        update = await request.json()
        asyncio.create_task(handler.handle_update(update))
        return Response(status_code=200)

    @router.get("/health")
    async def telegram_health():
        me = await handler.get_me()
        return {"configured": handler.configured, "bot": me}

    return router


# ── Standalone entrypoint ─────────────────────────────────────────

if __name__ == "__main__":
    handler = TelegramBotHandler()
    asyncio.run(handler.run_polling())
