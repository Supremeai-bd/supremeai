import { env } from "../../lib/env.js";
import { httpRequest } from "../../lib/http.js";

/**
 * Notify — активная отправка сообщений (не только health-проверки).
 * Telegram Bot API + Discord Webhook.
 */

export async function sendTelegram(
  message: string,
  chatId?: string,
  parseMode?: "Markdown" | "HTML"
): Promise<unknown> {
  const token = env.notify.telegramBotToken;
  if (!token) throw new Error("TELEGRAM_BOT_TOKEN is not configured.");
  const chat = chatId || env.notify.telegramChatId;
  if (!chat) throw new Error("TELEGRAM_CHAT_ID is not configured and no chatId was provided.");

  const res = await httpRequest(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: {
      chat_id: chat,
      text: message.slice(0, 4096),
      ...(parseMode ? { parse_mode: parseMode } : {}),
      disable_web_page_preview: true,
    },
    timeoutMs: 10_000,
  });

  const data = res.data as any;
  if (!data?.ok) throw new Error(`Telegram send failed: ${data?.description ?? res.status}`);
  return { ok: true, messageId: data.result?.message_id, chatId: chat, sentAt: new Date().toISOString() };
}

export async function sendDiscord(message: string): Promise<unknown> {
  const url = env.notify.discordWebhookUrl;
  if (!url) throw new Error("DISCORD_WEBHOOK_URL is not configured.");

  const res = await httpRequest(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: {
      content: message.slice(0, 2000),
      allowed_mentions: { parse: [] },
    },
    timeoutMs: 10_000,
  });

  if (!res.ok) throw new Error(`Discord send failed: ${res.status}`);
  return { ok: true, channel: url.split("/").slice(-2, -1)[0] ?? "unknown", sentAt: new Date().toISOString() };
}