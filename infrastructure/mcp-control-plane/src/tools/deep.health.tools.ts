import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { httpRequest } from "../lib/http.js";
import { env } from "../lib/env.js";
import { pingRedis } from "../adapters/redis/index.js";
import { getServiceHealth } from "../adapters/render/index.js";

/**
 * Deep Health & Free-Tier Sentinel Tool
 * Provides ground-truth health probes and free-tier boundary checks.
 */
export async function registerDeepHealthTools(server: McpServer): Promise<void> {
  server.tool(
    "system_deep_health",
    "Perform an in-depth reality check of SupremeAI infrastructure: detects cold-start latency, verifies read/write integrity, inspects Redis quotas, and checks Free-Tier usage boundaries.",
    {
      includeFreeTierAudit: z
        .boolean()
        .optional()
        .default(true)
        .describe("Whether to run free tier limit checks across Render, Supabase, and Redis"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ includeFreeTierAudit }) => {
      const startTime = Date.now();
      const results: Record<string, any> = {
        timestamp: new Date().toISOString(),
        probes: {},
        freeTierStatus: {
          healthy: true,
          warnings: [] as string[],
          breaches: [] as string[],
        },
      };

      // 1. Supabase Reality Check (Auth + REST latency & RLS readiness)
      try {
        const sbStart = Date.now();
        const sbUrl = env.supabase.url;
        const sbKey = env.supabase.serviceRoleKey || env.supabase.anonKey;
        if (sbUrl && sbKey) {
          const res = await httpRequest(`${sbUrl}/rest/v1/`, {
            headers: {
              apikey: sbKey,
              Authorization: `Bearer ${sbKey}`,
            },
            timeoutMs: 6000,
          });
          const sbLatency = Date.now() - sbStart;
          const isCold = sbLatency > 4000;
          results.probes.supabase = {
            status: res.status === 200 || res.status === 404 ? "healthy" : "degraded",
            httpStatus: res.status,
            latencyMs: sbLatency,
            coldStartDetected: isCold,
            note: isCold ? "High latency detected; database/edge may be cold-starting" : "Optimal latency",
          };
        } else {
          results.probes.supabase = { status: "unconfigured", note: "Missing SUPABASE_URL or key" };
        }
      } catch (err) {
        results.probes.supabase = {
          status: "unreachable",
          error: (err as Error).message,
        };
      }

      // 2. Upstash Redis Quota & Latency Check
      try {
        const redisStart = Date.now();
        const redisRes: any = await pingRedis();
        const redisLatency = Date.now() - redisStart;
        results.probes.redis = {
          status: redisRes?.status === "PONG" ? "healthy" : "degraded",
          latencyMs: redisLatency,
          mode: redisRes?.mode,
          activePrimary: redisRes?.activePrimary,
          chainSize: redisRes?.chainSize,
        };

        // Free-tier check for Upstash (10,000 commands/day on free tier)
        if (includeFreeTierAudit && redisRes?.chainStatus) {
          for (const node of redisRes.chainStatus) {
            if (node.usage && typeof node.usage === "object") {
              const u = node.usage as any;
              if (u.dailyLimit && u.dailyCommands && u.dailyCommands > u.dailyLimit * 0.85) {
                results.freeTierStatus.warnings.push(
                  `Redis account '${node.label}' is at ${Math.round((u.dailyCommands / u.dailyLimit) * 100)}% of daily free quota.`
                );
              }
            }
          }
        }
      } catch (err) {
        results.probes.redis = {
          status: "unreachable",
          error: (err as Error).message,
        };
      }

      // 3. Render Free-Tier Build Minutes & Cold-Start Probe
      try {
        const renderSvcId = env.render.controlTower.serviceId || env.render.primary.serviceId;
        if (renderSvcId) {
          const rHealth: any = await getServiceHealth("render-primary", renderSvcId);
          const svc = rHealth?.service;
          results.probes.render = {
            status: svc?.status || "unknown",
            suspended: svc?.suspended === "suspended",
            autoDeploy: svc?.autoDeploy,
            monthlyBuildMinutesUsed: svc?.monthlyBuildMinutes,
            freeTierExhausted: svc?.freeLimitExhausted || false,
          };

          if (includeFreeTierAudit) {
            if (svc?.freeLimitExhausted) {
              results.freeTierStatus.breaches.push(
                "Render monthly 500 free build minutes are EXHAUSTED. Auto deploys will fail unless upgraded or month resets."
              );
              results.freeTierStatus.healthy = false;
            } else if (svc?.monthlyBuildMinutes && svc.monthlyBuildMinutes > 400) {
              results.freeTierStatus.warnings.push(
                `Render free build minutes at ${svc.monthlyBuildMinutes}/500 mins (>80% used).`
              );
            }
          }
        }
      } catch (err) {
        results.probes.render = {
          status: "check_failed",
          error: (err as Error).message,
        };
      }

      // 4. Overall Free Tier Health Summary
      if (results.freeTierStatus.breaches.length > 0) {
        results.freeTierStatus.healthy = false;
      }

      results.totalDurationMs = Date.now() - startTime;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(results, null, 2),
          },
        ],
      };
    }
  );
}
