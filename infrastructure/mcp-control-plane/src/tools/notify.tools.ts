import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { checkTelegram, checkDiscord } from "../adapters/notify/index.js";

export async function registerNotifyTools(server: McpServer): Promise<void> {
  server.tool(
    "notify.telegram",
    "Ping the Telegram Bot API to check bot token validity.",
    {},
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
    "notify.discord",
    "Ping the Discord webhook URL to check its validity.",
    {},
    async () => {
      try {
        const status = await checkDiscord();
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
}
