import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { buildRegistry } from "../registry/provider.registry.js";
import { httpRequest } from "../lib/http.js";

/**
 * System-level MCP tools: summary, health, dependencies.
 */
export async function registerSystemTools(server: McpServer): Promise<void> {

  // ── system.summary
  server.tool(
    "system.summary",
    "Get a high-level summary of all SupremeAI services — availability, roles, and capabilities",
    {},
    async () => {
      const registry = buildRegistry();
      const byProvider = registry.reduce(
        (acc, r) => {
          const key = r.provider;
          if (!acc[key]) acc[key] = [];
          acc[key]!.push({
            id: r.id,
            displayName: r.displayName,
            role: r.role,
            available: r.available,
            capabilities: r.capabilities,
          });
          return acc;
        },
        {} as Record<string, unknown[]>
      );

      const available = registry.filter((r) => r.available).length;
      const total = registry.length;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                summary: `${available}/${total} services available`,
                timestamp: new Date().toISOString(),
                byProvider,
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  // ── system.health (ping all HTTP services)
  server.tool(
    "system.health",
    "Ping all backend services and report their HTTP health status",
    {},
    async () => {
      const registry = buildRegistry();
      const httpServices = registry.filter((r) => r.url && r.available);

      const results = await Promise.allSettled(
        httpServices.map(async (svc) => {
          const url = `${svc.url}/api/v1/health`;
          try {
            const res = await httpRequest(url, { timeoutMs: 6000, retries: 0 });
            return {
              id: svc.id,
              displayName: svc.displayName,
              url,
              status: res.ok ? "healthy" : "degraded",
              httpStatus: res.status,
              latencyMs: res.latencyMs,
            };
          } catch (err) {
            return {
              id: svc.id,
              displayName: svc.displayName,
              url,
              status: "unreachable",
              error: (err as Error).message,
            };
          }
        })
      );

      const health = results.map((r) => (r.status === "fulfilled" ? r.value : r.reason));
      const healthy = health.filter((h: Record<string, unknown>) => h.status === "healthy").length;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                summary: `${healthy}/${health.length} services healthy`,
                timestamp: new Date().toISOString(),
                services: health,
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  // ── system.dependencies
  server.tool(
    "system.dependencies",
    "Show the dependency graph between SupremeAI services",
    {},
    async () => {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                graph: {
                  "render-primary": ["supabase-primary", "redis-upstash", "ai-gemini", "ai-groq"],
                  "render-worker": ["supabase-primary", "redis-upstash"],
                  "render-scraper": ["firecrawl-scraper"],
                  "cloudflare-worker": ["render-primary", "render-worker", "render-scraper"],
                  "vercel-frontend": ["cloudflare-worker", "firebase-supremeai-a"],
                },
                note: "Cloudflare Worker pings all 3 backends every 8 minutes to prevent sleep.",
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );
}
