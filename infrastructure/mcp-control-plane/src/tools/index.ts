import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { registerSystemTools } from "./system.tools.js";
import { registerRenderTools } from "./render.tools.js";
import { registerGitHubTools } from "./github.tools.js";
import { registerSupabaseTools } from "./supabase.tools.js";
import { registerRedisTools } from "./redis.tools.js";
import { registerCloudflareTools } from "./cloudflare.tools.js";
import { registerInfisicalTools } from "./infisical.tools.js";
import { registerFirebaseTools } from "./firebase.tools.js";

/**
 * Registers all MCP tools with the server.
 * Tools are grouped by domain.
 */
export async function registerAllTools(server: McpServer): Promise<void> {
  // ── System Tools
  await registerSystemTools(server);
  
  // ── Provider Adapter Tools
  await registerRenderTools(server);
  await registerGitHubTools(server);
  await registerSupabaseTools(server);
  await registerRedisTools(server);
  await registerCloudflareTools(server);
  await registerInfisicalTools(server);
  await registerFirebaseTools(server);
}
