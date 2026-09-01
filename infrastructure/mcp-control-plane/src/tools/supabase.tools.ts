import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getHealth, getAuthUsers } from "../adapters/supabase/index.js";

export async function registerSupabaseTools(server: McpServer): Promise<void> {
  server.tool(
    "supabase.health",
    "Ping the Supabase REST API to check connectivity and latency.",
    {
      accountId: z.string().describe("The account ID (e.g. supabase-primary)"),
    },
    async ({ accountId }) => {
      try {
        const health = await getHealth(accountId);
        return {
          content: [{ type: "text", text: JSON.stringify(health, null, 2) }],
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
    "supabase.auth_users",
    "Get the total number of authenticated users in Supabase.",
    {
      accountId: z.string().describe("The account ID (e.g. supabase-primary)"),
    },
    async ({ accountId }) => {
      try {
        const users = await getAuthUsers(accountId);
        return {
          content: [{ type: "text", text: JSON.stringify(users, null, 2) }],
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
