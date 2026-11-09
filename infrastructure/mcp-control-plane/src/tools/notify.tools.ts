import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { checkTelegram } from "../adapters/notify/index.js";
import { sendTelegram } from "../adapters/notify/actions.js";
import { globalKillSwitch } from "../remediation/killswitch.js";

export async function registerNotifyTools(server: McpServer): Promise<void> {
  server.tool(
    "notify.telegram",
    "Ping the Telegram Bot API to check bot token validity.",
    {},
    { readOnlyHint: true, idempotentHint: true },
    async () => {
      try {
        const status = await checkTelegram();
        return {
          content: [{ type: "text", text: JSON.stringify(status, null, 2) }],
        };
      } catch (err) {
        return {
          isError: true,
          content: [{ type: "text", text: `Error: ${(err as Error).message}` }],
        };
      }
    }
  );

  server.tool(
    "notify.send_telegram",
    "Send a message via Telegram bot to the configured (or a specific) chat.",
    {
      message: z.string().min(1).max(4000).describe("Message text"),
      chatId: z.string().optional().describe("Override chat id (default: TELEGRAM_CHAT_ID)"),
      parseMode: z.enum(["Markdown", "HTML"]).optional().describe("Optional parse mode"),
    },
    { readOnlyHint: false, idempotentHint: false },
    async ({ message, chatId, parseMode }) => {
      try {
        const result = await sendTelegram(message, chatId, parseMode);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      } catch (err) {
        return { isError: true, content: [{ type: "text", text: `Error: ${(err as Error).message}` }] };
      }
    }
  );

  /**
   * Omnichannel Telegram ChatOps & Command Router (restores capabilities from PR #505/#582).
   * Supports:
   *   /status or /runway -> Control tower runway status + active agent claims.
   *   /stop              -> Emergency kill-switch arming (halts autonomy to L0).
   *   /help              -> Omnichannel admin command list.
   */
  server.tool(
    "notify.telegram_command",
    "Process an incoming omnichannel admin command from Telegram (/status, /runway, /stop, /help).",
    {
      commandText: z.string().describe("The incoming message text (e.g. '/status', '/stop')"),
      senderChatId: z.string().optional().describe("Telegram chat ID of the sender"),
      replyToChat: z.boolean().default(true).describe("Whether to auto-reply to Telegram chat if chatId is known"),
    },
    { readOnlyHint: false, idempotentHint: false },
    async ({ commandText, senderChatId, replyToChat }) => {
      const text = commandText.trim();
      let reply = "";
      let action = "reply";

      if (text.startsWith("/status") || text.startsWith("/runway")) {
        const autonomy = globalKillSwitch.isAutonomyEnabled() ? "🟢 ACTIVE (L2 Autonomous)" : "🛑 KILLED (L0 Read-Only)";
        reply = `🏰 *SupremeAI Control Tower Status*\n` +
          `• Autonomy: ${autonomy}\n` +
          `• Topology: Pure Single-Repository Monorepo SSOT (Supremeai-bd/supremeai)\n` +
          `• Primary Monorepo: Supremeai-bd/supremeai`;
        action = "status";
      } else if (text.startsWith("/stop")) {
        globalKillSwitch.emergencyStop();
        reply = `🚨 *EMERGENCY KILL-SWITCH ARMED*\n` +
          `Autonomy disabled. System dropped to L0 (Read-Only Mode). Background task schedulers stopped.`;
        action = "kill_switch";
      } else if (text.startsWith("/help") || text.startsWith("/start")) {
        reply = `*SupremeAI Omnichannel Admin Control*\n` +
          `Commands:\n` +
          `  /status   - Control Tower runway + system status\n` +
          `  /runway   - Runway summary (alias of /status)\n` +
          `  /stop     - Arm the emergency kill-switch\n` +
          `  /help     - This help text`;
        action = "help";
      } else {
        reply = `⚠️ Unknown command: '${text}'. Type /help for available commands.`;
      }

      if (replyToChat && senderChatId) {
        try {
          await sendTelegram(reply, senderChatId, "Markdown");
        } catch {
          // Fall back gracefully if chat sending fails
        }
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ ok: true, action, reply }, null, 2),
          },
        ],
      };
    }
  );
}

