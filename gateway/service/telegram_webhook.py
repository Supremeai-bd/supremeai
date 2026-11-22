"""
service/telegram_webhook.py — SupremeAI Telegram Inbound Webhook Listener.

Routes strategic Telegram queries (#gemini, /spark, !gemini, /idea) directly to
the SupremeAI Gemini Engine / Dynamic Squad, formats executive briefs,
and delivers responses with auto-chunking back to Telegram.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from .pool import squad
from .providers.adapters import PROVIDER_CONFIGS, forward_chat_completion, forward_stealth_webhook

logger = logging.getLogger("supremeai.telegram_webhook")

telegram_router = APIRouter(tags=["telegram"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", PROVIDER_CONFIGS["gemini"]["default_model"])

TRIGGER_TAGS = ["#gemini", "!gemini", "/spark", "/idea"]

SYSTEM_PROMPT = """You are the SupremeAI Strategy Agent powered by Gemini.
When the user sends a project idea or architecture question, provide a structured,
high-impact executive brief in Bengali and English. Keep it concise, clear, and actionable.
Structure:
1. Concept & Global Origin
2. Direct Benefit for SupremeAI
3. Optimal Implementation Roadmap
"""


_http_client: Optional[httpx.AsyncClient] = None


def get_telegram_client() -> httpx.AsyncClient:
    """Returns a shared, pooled AsyncClient with connection reuse for low-latency delivery."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=4.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _http_client


async def send_chat_action(chat_id: int | str, action: str = "typing") -> None:
    """Delivers instant typing status indicator to Telegram so users see immediate responsiveness."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    try:
        client = get_telegram_client()
        await client.post(url, json={"chat_id": chat_id, "action": action})
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to send typing chat action (%s)", type(exc).__name__)


async def send_telegram_message(
    chat_id: int | str,
    text: str,
    reply_to_message_id: Optional[int] = None
) -> bool:
    """Delivers formatted message chunks to Telegram via shared keep-alive pool."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured; cannot deliver message.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Auto-chunking for Telegram's 4096 character limit (safe margin at 3800)
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] if len(text) > 3800 else [text]

    client = get_telegram_client()
    success = True
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id

        try:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                # Markdown parsing failed on special chars; retry plain text
                payload.pop("parse_mode", None)
                res2 = await client.post(url, json=payload)
                if res2.status_code != 200:
                    logger.error("Failed to deliver Telegram chunk (HTTP %s)", res2.status_code)
                    success = False
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram network delivery error (%s)", type(exc).__name__)
            success = False

    return success


async def query_strategy_ai(prompt: str) -> str:
    """Send to the configured reply relay, then try eligible API slots."""
    payload = {
        "model": "auto",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
    }

    def reply(code, body):
        if 200 <= code < 300 and isinstance(body, dict):
            choices = body.get("choices") or []
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                message = choices[0].get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if isinstance(content, str) and content.strip():
                    return content.strip()
            if isinstance(body.get("reply"), str):
                return body["reply"].strip()
        return ""

    # No native Gemini or raw credential ladder: all API requests use the
    # same approved models, slot evidence, and adapter as Gateway chat.
    try:
        async with asyncio.timeout(15):
            stealth_url = (os.getenv("STEALTH_WEBHOOK_URL") or os.getenv("UPSTREAM_WEBHOOK_URL") or "").strip()
            if stealth_url:
                code, result = await forward_stealth_webhook(
                    stealth_url, os.getenv("STEALTH_WEBHOOK_SECRET") or os.getenv("UPSTREAM_WEBHOOK_SECRET"),
                    payload, timeout=6.0,
                )
                if content := reply(code, result):
                    return content
            for provider, slot in squad.get_candidate_slots():
                code, result = await forward_chat_completion(provider, slot.key, payload, slot=slot)
                if content := reply(code, result):
                    return content
    except TimeoutError:
        logger.warning("Telegram strategy request timed out")

    return "⚠️ দুঃখিত, এই মুহূর্তে কোনো এআই প্রোভাইডার উপলব্ধ নেই। অনুগ্রহ করে কিছুক্ষণ পর চেষ্টা করুন।"


async def _process_and_reply(chat_id: int | str, text: str, msg_id: Optional[int] = None):
    """Background task to generate and reply with instant typing status indicator."""
    # 1. Clean prompt
    clean_prompt = text
    for tag in TRIGGER_TAGS:
        clean_prompt = clean_prompt.replace(tag, "").strip()

    if not clean_prompt:
        help_msg = (
            "⚡ *[SPARK-STRATEGY] | #gemini*\n━━━━━━━━━━━━━━━━━━━\n"
            "অনুগ্রহ করে আপনার আইডিয়া বা বিষয়ের নাম লিখুন।\n\n"
            "💡 *উদাহরণ:*\n"
            "• `/spark latency optimization roadmap`\n"
            "• `#gemini নতুন ফিচারের আইডিয়া`\n"
            "• `/idea hybrid multi-agent consensus`"
        )
        await send_telegram_message(chat_id, help_msg, reply_to_message_id=msg_id)
        return

    # Send immediate typing action so Telegram shows "typing..." without lag
    await send_chat_action(chat_id, "typing")

    logger.info("Processing authenticated Telegram strategy query")
    ai_reply = await query_strategy_ai(clean_prompt)

    header = "⚡ *[SPARK-STRATEGY] | #gemini*\n━━━━━━━━━━━━━━━━━━━\n"
    full_message = header + ai_reply

    await send_telegram_message(chat_id, full_message, reply_to_message_id=msg_id)


@telegram_router.post("/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Inbound Webhook Listener for @SupremeAitele_bot.
    Returns 200 OK immediately and processes strategy query asynchronously.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not token or not secret:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(received.encode(), secret.encode()):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        update = await request.json()
    except Exception:  # noqa: BLE001
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    if not isinstance(update, dict):
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict) or not isinstance(message.get("text"), str):
        return {"status": "ignored_non_text"}

    chat = message.get("chat")
    if not isinstance(chat, dict) or type(chat.get("id")) is not int:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    chat_id = chat["id"]
    text = message["text"].strip()
    msg_id = message.get("message_id")

    # Auto-trigger for all 1-on-1 private messages; in groups, require trigger tags (#gemini, /spark, etc.)
    chat_type = chat.get("type", "private")
    is_triggered = (chat_type == "private") or any(text.startswith(tag) or tag in text.lower() for tag in TRIGGER_TAGS)

    if not is_triggered:
        return {"status": "passthrough"}

    # Process in background so Telegram receives instant 200 OK
    background_tasks.add_task(_process_and_reply, chat_id, text, msg_id)
    return {"status": "accepted"}


@telegram_router.get("/webhook/telegram/status")
async def telegram_webhook_status():
    """Telemetry endpoint for Telegram bot health."""
    configured = bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip())
    return {
        "status": "active" if configured else "unconfigured",
        "bot_configured": configured,
        "triggers": TRIGGER_TAGS,
        "default_model": GEMINI_MODEL,
    }
