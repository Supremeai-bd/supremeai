import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { getServiceHealth } from "../adapters/render/index.js";
import { getHealth as getSupabaseHealth } from "../adapters/supabase/index.js";
import { pingRedis } from "../adapters/redis/index.js";
import { getWorkerStatus } from "../adapters/cloudflare/index.js";
import { auditSecrets } from "../adapters/infisical/index.js";
import { getAuthStatus } from "../adapters/firebase/index.js";
import { checkStripe, checkVercel } from "../adapters/misc/index.js";

export async function registerSystemSummaryTools(server: McpServer): Promise<void> {
  server.tool(
    "system.summary",
    "Universal Observe Layer: Gets a high-level status summary of the entire ecosystem concurrently.",
    {},
    async () => {
      try {
        const start = Date.now();
        // Execute all health checks in parallel
        const results = await Promise.allSettled([
          getServiceHealth("render-primary", "srv-dabiaknqj5pc73a47mvg").catch((e) => ({ error: e.message })),
          getSupabaseHealth("supabase-primary").catch((e) => ({ error: e.message })),
          pingRedis().catch((e) => ({ error: e.message })),
          getWorkerStatus().catch((e) => ({ error: e.message })),
          auditSecrets().catch((e) => ({ error: e.message })),
          getAuthStatus().catch((e) => ({ error: e.message })),
          checkStripe().catch((e) => ({ error: e.message })),
          checkVercel().catch((e) => ({ error: e.message }))
        ]);

        const summary = {
          latencyMs: Date.now() - start,
          services: {
            render: results[0].status === "fulfilled" ? results[0].value : "Failed",
            supabase: results[1].status === "fulfilled" ? results[1].value : "Failed",
            redis: results[2].status === "fulfilled" ? results[2].value : "Failed",
            cloudflare: results[3].status === "fulfilled" ? results[3].value : "Failed",
            infisical: results[4].status === "fulfilled" ? "Healthy (Secrets Accessible)" : "Failed",
            firebase: results[5].status === "fulfilled" ? results[5].value : "Failed",
            stripe: results[6].status === "fulfilled" ? results[6].value : "Failed",
            vercel: results[7].status === "fulfilled" ? results[7].value : "Failed"
          }
        };

        return {
          content: [{ type: "text", text: JSON.stringify(summary, null, 2) }],
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
    "system.dependencies",
    "Universal Observe Layer: Returns a static map of service dependencies.",
    {},
    async () => {
      const deps = {
        "mcp-control-plane": ["render", "github", "supabase", "redis", "cloudflare", "infisical", "firebase", "ai-providers", "notify"],
        "frontend": ["firebase-auth", "supabase-db", "vercel"],
        "backend": ["supabase-db", "redis", "render"],
        "ping-worker": ["cloudflare"]
      };
      return {
        content: [{ type: "text", text: JSON.stringify(deps, null, 2) }],
      };
    }
  );
}
