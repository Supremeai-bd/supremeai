import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { buildAccountRegistry, ProviderAccount } from "../registry/account.registry.js";
import { listResources, getResourceStatus } from "../registry/resource.registry.js";
import { httpRequest } from "../lib/http.js";

/**
 * System-level MCP tools: summary, health, dependencies, and resource discovery.
 */

/* ── Provider-aware health probing ──────────────────────────────────────
 * Every provider exposes health differently: Render services answer /health,
 * GitHub's health IS the repo API with auth, Supabase has a public
 * /auth/v1/health, Upstash Redis speaks the REST protocol with a bearer
 * token. A blind `${url}/api/v1/health` appended to all of them produced
 * false "degraded" statuses (404/403/401) for services that were perfectly
 * healthy — the probe below checks what can actually be healthy. */

type HealthStatus = "healthy" | "degraded" | "unreachable";

interface HealthProbe {
  id: string;
  displayName: string;
  url: string;
  status: HealthStatus;
  httpStatus: number | null;
  latencyMs: number | null;
  error?: string;
}

function bearerFor(apiKeyRef: string): string | undefined {
  const primary = process.env[apiKeyRef];
  if (primary && primary.length > 0) return primary;
  // GitHub accounts allow the generic fallback name (same rule as the registry)
  if (apiKeyRef === "GH_TOKEN") {
    const alt = process.env["GITHUB_TOKEN"];
    if (alt && alt.length > 0) return alt;
  }
  return undefined;
}

type ProbeOutcome = "degraded" | "unreachable" | { ok: true; status: number; latencyMs: number };

async function probeHttp(url: string, headers: Record<string, string> = {}, timeoutMs = 6000): Promise<ProbeOutcome> {
  try {
    const res = await httpRequest(url, { timeoutMs, retries: 0, headers });
    if (res.ok) return { ok: true, status: res.status, latencyMs: res.latencyMs };
    return "degraded";
  } catch {
    return "unreachable";
  }
}

/** Upstash REST ping: rediss://default:TOKEN@host:6379 → https://host/ping */
function upstashRestUrl(rawUrl: string): { url: string; token?: string } | null {
  try {
    const parsed = new URL(rawUrl.replace(/^rediss:\/\//, "https://").replace(/^redis:\/\//, "https://"));
    const token = decodeURIComponent(parsed.username || "");
    return { url: `https://${parsed.host}/ping`, token: token || undefined };
  } catch {
    return null;
  }
}

async function probeServiceHealth(svc: ProviderAccount): Promise<HealthProbe> {
  const base: Pick<HealthProbe, "id" | "displayName"> = { id: svc.id, displayName: svc.displayName };

  // ── GitHub: repo API with auth IS the health check ──
  if (svc.provider === "github") {
    const token = bearerFor(svc.apiKeyRef);
    try {
      const res = await httpRequest(svc.url!, {
        timeoutMs: 6000,
        retries: 0,
        headers: {
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      return {
        ...base,
        url: svc.url!,
        status: res.ok ? "healthy" : "degraded",
        httpStatus: res.status,
        latencyMs: res.latencyMs,
        ...(res.ok ? {} : { error: res.status === 401 || res.status === 403 ? "GitHub auth rejected — token missing, invalid or expired" : `GitHub responded ${res.status}` }),
      };
    } catch (err) {
      return { ...base, url: svc.url!, status: "unreachable", httpStatus: null, latencyMs: null, error: (err as Error).message };
    }
  }

  // ── Supabase: public auth health endpoint (no key required) ──
  if (svc.provider === "supabase") {
    const url = `${svc.url!.replace(/\/+$/, "")}/auth/v1/health`;
    const out = await probeHttp(url);
    if (out === "unreachable") return { ...base, url, status: "unreachable", httpStatus: null, latencyMs: null, error: "connection failed" };
    if (out === "degraded") return { ...base, url, status: "degraded", httpStatus: null, latencyMs: null, error: "auth health endpoint responded non-2xx" };
    return { ...base, url, status: "healthy", httpStatus: out.status, latencyMs: out.latencyMs };
  }

  // ── Redis (Upstash): REST ping with the URL-embedded bearer token ──
  if (svc.provider === "redis") {
    const rest = upstashRestUrl(svc.url!);
    if (!rest) return { ...base, url: svc.url!, status: "unreachable", httpStatus: null, latencyMs: null, error: "unparseable redis URL" };
    try {
      const res = await httpRequest<{ result?: string }>(rest.url, {
        timeoutMs: 6000,
        retries: 0,
        headers: rest.token ? { Authorization: `Bearer ${rest.token}` } : {},
      });
      const pong = res.ok && res.data?.result === "pong";
      return { ...base, url: rest.url, status: pong ? "healthy" : "degraded", httpStatus: res.status, latencyMs: res.latencyMs, ...(pong ? {} : { error: "PING did not return pong" }) };
    } catch (err) {
      return { ...base, url: rest.url, status: "unreachable", httpStatus: null, latencyMs: null, error: (err as Error).message };
    }
  }

  // ── HTTP services (render et al.): explicit path → /health → /api/v1/health ──
  const candidates = [
    ...(svc.healthPath ? [svc.healthPath] : []),
    "/health",
    "/api/v1/health",
  ].map((p) => `${svc.url!.replace(/\/+$/, "")}${p}`);

  for (const url of candidates) {
    const out = await probeHttp(url);
    if (out !== "unreachable" && out !== "degraded") {
      return { ...base, url, status: "healthy", httpStatus: out.status, latencyMs: out.latencyMs };
    }
  }

  // No 2xx anywhere — one more pass to classify degraded (HTTP answered) vs unreachable
  for (const url of candidates) {
    const out = await probeHttp(url);
    if (out === "degraded") {
      return { ...base, url, status: "degraded", httpStatus: null, latencyMs: null, error: "health endpoint responded non-2xx" };
    }
    if (out !== "unreachable") {
      return { ...base, url, status: "healthy", httpStatus: out.status, latencyMs: out.latencyMs };
    }
  }
  return { ...base, url: candidates[0], status: "unreachable", httpStatus: null, latencyMs: null, error: "no health endpoint answered" };
}

export async function registerSystemTools(server: McpServer): Promise<void> {

  // ── system.summary
  server.tool(
    "system.summary",
    "Get a high-level summary of all SupremeAI services — availability, roles, and capabilities",
    {},
    async () => {
      const registry = buildAccountRegistry();
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
      const registry = buildAccountRegistry();
      const httpServices = registry.filter((r) => r.url && r.available);

      const results = await Promise.allSettled(
        httpServices.map(async (svc) => probeServiceHealth(svc))
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

  // NOTE (master audit 2026-09-02): the static "system.dependencies" tool that
  // lived here was removed — it collided with the dynamic, richer implementation
  // in system.summary.tools.ts (the MCP SDK throws
  // "Tool system.dependencies is already registered" on duplicates, which
  // crashed the whole control tower at boot). The dynamic
  // globalDependencyGraph.getRawMap() version supersedes this static graph.

  // ── resource.list
  server.tool(
    "resource.list",
    "List all discovered resources across all configured providers.",
    {},
    async () => {
      const resources = await listResources();
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                total: resources.length,
                resources,
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  // ── resource.status
  server.tool(
    "resource.status",
    "Get the current status of a specific resource by ID.",
    {
      resourceId: z.string().describe("The ID of the resource (e.g. render/render-primary)"),
    },
    async ({ resourceId }) => {
      const status = await getResourceStatus(resourceId);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                resourceId,
                status,
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
