import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { registerSystemTools } from "./system.tools.js";

/**
 * Registers all MCP tools with the server.
 * Tools are grouped by domain.
 */
export async function registerAllTools(server: McpServer): Promise<void> {
  // ── System Tools
  await registerSystemTools(server);
}
