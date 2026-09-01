import { env } from "../../lib/env.js";
import { httpRequest } from "../../lib/http.js";

export async function checkTelegram(): Promise<unknown> {
  const { telegramBotToken } = env.notify;
  if (!telegramBotToken) {
    throw new Error("TELEGRAM_BOT_TOKEN is not configured.");
  }

  const start = Date.now();
  // Using getMe to verify the bot token
  const res = await httpRequest(`https://api.telegram.org/bot${telegramBotToken}/getMe`);
  
  const data = res.data as any;
  if (data.ok) {
    return {
      status: "healthy",
      botUsername: data.result.username,
      latencyMs: Date.now() - start
    };
  }
  
  throw new Error(`Telegram API Error: ${data.description}`);
}

export async function checkDiscord(): Promise<unknown> {
  const { discordWebhookUrl } = env.notify;
  if (!discordWebhookUrl) {
    throw new Error("DISCORD_WEBHOOK_URL is not configured.");
  }

  const start = Date.now();
  // A GET request to a Discord webhook URL returns the webhook info
  const res = await httpRequest(discordWebhookUrl);
  
  const data = res.data as any;
  if (data.id && data.name) {
    return {
      status: "healthy",
      webhookName: data.name,
      channelId: data.channel_id,
      latencyMs: Date.now() - start
    };
  }
  
  throw new Error(`Discord API Error: ${JSON.stringify(data)}`);
}
