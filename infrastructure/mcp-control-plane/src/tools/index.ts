import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { buildRegistry } from "../registry/provider.registry.js";
import { registerSystemTools } from "./system.tools.js";

/**
 * Registers all MCP tools with the server.
 * Tools are grouped by domain.
 */
export async function registerAllTools(server: McpServer): Promise<void> {
  // ── Registry Tools
  server.tool(
    "resource.list",
    "List all registered providers and their availability status",
    {},
    async () => {
      const registry = buildRegistry();
      const available = registry.filter((r) => r.available);
      const unavailable = registry.filter((r) => !r.available);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                total: registry.length,
                available: available.length,
                unavailable: unavailable.length,
                providers: registry.map((r) => ({
                  id: r.id,
                  provider: r.provider,
                  displayName: r.displayName,
                  role: r.role,
                  capabilities: r.capabilities,
                  available: r.available,
                  url: r.url ?? null,
                })),
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  // ── System Tools
  await registerSystemTools(server);
}
