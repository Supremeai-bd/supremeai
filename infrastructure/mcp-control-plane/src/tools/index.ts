import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { registerSystemTools } from "./system.tools.js";
import { registerSystemSummaryTools } from "./system.summary.tools.js";
import { registerRenderTools } from "./render.tools.js";
import { registerGitHubTools } from "./github.tools.js";
import { registerSupabaseTools } from "./supabase.tools.js";
import { registerRedisTools } from "./redis.tools.js";
import { registerCloudflareTools } from "./cloudflare.tools.js";
import { registerInfisicalTools } from "./infisical.tools.js";
import { registerFirebaseTools } from "./firebase.tools.js";
import { registerAITools } from "./ai.tools.js";
import { registerNotifyTools } from "./notify.tools.js";
import { registerMiscTools } from "./misc.tools.js";
import { registerPolicyTools } from "./policy.tools.js";
import { registerActionTools } from "./action.tools.js";
import { registerAutonomyTools } from "./autonomy.tools.js";
import { registerDynamicTools } from "../dynamic/tool.registry.js";
import { registerContext7Adapter } from "../dynamic/context7.adapter.js";
import { registerTenantTools } from "./tenant.tools.js";
import { registerClientTools } from "./client.tools.js";
import { registerSourceTools } from "./source.tools.js";
import { registerKnowledgeTools } from "./knowledge.tools.js";
import { registerMemoryTools } from "./memory.tools.js";
import type { MemorySubAdapter } from "../adapters/memory/index.js";

/**
 * Registers all MCP tools with the server.
 * Tools are grouped by domain.
 */
export async function registerAllTools(
  server: McpServer,
  memoryAdapter?: MemorySubAdapter,
): Promise<void> {
  // ── System Tools
  await registerSystemTools(server);
  await registerSystemSummaryTools(server);
  await registerPolicyTools(server);
  await registerActionTools(server);
  await registerAutonomyTools(server);

  // ── Multi-Tenant Tools (admin/customer management)
  await registerTenantTools(server);
  await registerClientTools(server);

  // ── Provider Adapter Tools
  await registerRenderTools(server);
  await registerGitHubTools(server);
  await registerSupabaseTools(server);
  await registerRedisTools(server);
  await registerCloudflareTools(server);
  await registerInfisicalTools(server);
  await registerFirebaseTools(server);
  await registerAITools(server);
  await registerNotifyTools(server);
  await registerMiscTools(server);

  // ── Open Source Collection / Knowledge Store
  await registerSourceTools(server);
  await registerKnowledgeTools(server);

  // ── Dynamic Tools (Database-driven)
  await registerDynamicTools(server);

  // ── Memory Circle bridge (Python sidecar, optional — degrades gracefully).
  // registerMemoryTools() starts the sidecar via the adapter's shared
  // promise (parallel with remaining registrations) and falls back to a
  // static tool snapshot if the sidecar isn't ready yet.
  if (memoryAdapter) {
    await registerMemoryTools(server, memoryAdapter);
  }

  // ── Context7 Documentation Adapter
  await registerContext7Adapter(server);
}
