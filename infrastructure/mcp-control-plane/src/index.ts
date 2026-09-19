#!/usr/bin/env node
/**
 * SupremeAI MCP Control Tower — Main Entry Point
 * Supports both stdio (local: Claude Desktop, Cursor) and HTTP Streamable (remote)
 */

import "dotenv/config";
import { timingSafeEqual, createHmac, randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { z } from "zod";
import { env } from "./lib/env.js";
import { registerAllTools } from "./tools/index.js";
import { RequestContextStore } from "./policy/auth.context.js";
import { getServiceDescriptors } from "./service-circles.js";
import { nowTimestamp, timestampDetails, withTimestamp } from "./lib/timestamps.js";
import { approveClient, changeClientProvider, changeClientRole, countClientsByTenant, defaultClientScopes, listClients, registerClient, resolveClient, revokeClient, rotateClient, roleAllows, scopeAllows, type ExternalClient } from "./policy/client-registry.js";
import { createBuiltinManifest } from "./registry/mcp.contracts.js";
import { accessModeFor, publicAccessManifest, isPublicSafeResource, toolAccessError } from "./policy/mcp-access.js";
import { verifyApprovalLink } from "./policy/approvals/signing.js";
import { pullSecretsIntoProcessEnv } from "./adapters/infisical/index.js";
import { MemorySubAdapter } from "./adapters/memory/index.js";
import {
  activateTenant,
  createTenant,
  getTenant,
  listTenants,
  rotateTenantAdminToken,
  suspendTenant,
  updateTenant,
  verifyTenantAdminToken,
} from "./tenancy/tenant.registry.js";

const SERVER_NAME = "supremeai-control-tower";
const SERVER_VERSION = "1.0.0";
const MAX_REQUEST_BYTES = 1_048_576;
const MCP_MANIFEST_URI = "control-tower://server/manifest";

function requestPath(req: IncomingMessage): string {
  return new URL(req.url ?? "/", `http://${req.headers.host || "localhost"}`).pathname;
}

// ── Per-IP rate limiting on /mcp (#695) ──────────────────────────────────────
// In-memory sliding window: MCP_RATE_LIMIT_MAX requests per client IP per
// MCP_RATE_LIMIT_WINDOW_MS (defaults: 60 requests / 60 000 ms). Exceeding the
// budget returns 429 with a Retry-After header.
// #686: the same sliding-window implementation is REUSED by the per-(identity,
// tool) rate limiter below — one bucket-table primitive, two tables.
const mcpRateBuckets = new Map<string, number[]>();
const toolIdentityRateBuckets = new Map<string, number[]>();

function mcpRateLimitConfig(): { max: number; windowMs: number } {
  const max = Number(process.env["MCP_RATE_LIMIT_MAX"] ?? 60);
  const windowMs = Number(process.env["MCP_RATE_LIMIT_WINDOW_MS"] ?? 60_000);
  return {
    max: Number.isFinite(max) && max > 0 ? Math.floor(max) : 60,
    windowMs: Number.isFinite(windowMs) && windowMs > 0 ? Math.floor(windowMs) : 60_000,
  };
}

function clientIpForRateLimit(req: IncomingMessage): string {
  // Behind Render/Cloudflare the real client IP arrives in X-Forwarded-For;
  // direct connections carry no such header and fall back to the socket address.
  const forwarded = req.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.trim()) {
    return forwarded.split(",")[0].trim();
  }
  return req.socket.remoteAddress ?? "unknown";
}

/**
 * Shared sliding-window consume primitive (#695, reused by #686).
 * `buckets` maps key → list of ms timestamps inside the current window.
 * Buckets are pruned lazily on each consume; the table itself is capped so
 * abandoned keys cannot grow memory without bound.
 */
function consumeSlidingWindow(buckets: Map<string, number[]>, key: string, max: number, windowMs: number): { allowed: boolean; retryAfterMs: number } {
  const now = Date.now();
  const cutoff = now - windowMs;
  let stamps = buckets.get(key);
  if (!stamps) { stamps = []; buckets.set(key, stamps); }
  while (stamps.length > 0 && stamps[0] <= cutoff) stamps.shift();
  // Memory guard: drop stale buckets if the table grows unboundedly.
  if (buckets.size > 10_000) {
    for (const [bucketKey, bucketStamps] of buckets) {
      if (bucketStamps.length === 0 || bucketStamps[bucketStamps.length - 1] <= cutoff) {
        buckets.delete(bucketKey);
      }
    }
  }
  if (stamps.length >= max) {
    const retryAfterMs = stamps.length > 0 ? Math.max(1, (stamps[0] ?? now) + windowMs - now) : windowMs;
    return { allowed: false, retryAfterMs };
  }
  stamps.push(now);
  return { allowed: true, retryAfterMs: 0 };
}

function consumeMcpRateLimit(key: string): { allowed: boolean; retryAfterMs: number } {
  const { max, windowMs } = mcpRateLimitConfig();
  return consumeSlidingWindow(mcpRateBuckets, key, max, windowMs);
}

// ── Per-tool execution governance (#686) ─────────────────────────────────────
// Applied inside the same server.tool wrapper as the #695 RBAC gate, in order:
// RBAC → per-(identity,tool) rate limit → input payload validation →
// timeout-guarded execution → output truncation.
//
//  1. Input payload cap — MCP_TOOL_PAYLOAD_MAX_BYTES (default 256 KB): a tool
//     call whose serialized `arguments` exceeds the cap is rejected with a
//     structured isError response, and `arguments` must be a JSON object.
//  2. Output truncation — MCP_TOOL_RESULT_MAX_BYTES (default 512 KB): results
//     above the cap are cut with an explicit "...[truncated N bytes]" marker
//     plus a metadata field instead of silently streaming huge payloads.
//  3. Hard execution timeout — MCP_TOOL_TIMEOUT_MS (default 30 000 ms): the
//     handler races the clock; the loser keeps running orphaned but the caller
//     gets a structured isError response immediately.
//  4. Per-(identity, tool) rate limit — MCP_TOOL_RATE_LIMIT_MAX calls per
//     MCP_TOOL_RATE_LIMIT_WINDOW_MS (defaults: 20 / 60 000 ms), keyed by
//     `<tenant>|<principal>||<tool>`. The per-IP limiter above only bounds the
//     transport; this bounds actual executions per caller per tool.
const TOOL_PAYLOAD_MAX_BYTES_DEFAULT = 262_144;
const TOOL_RESULT_MAX_BYTES_DEFAULT = 524_288;
const TOOL_TIMEOUT_MS_DEFAULT = 30_000;
const TOOL_RATE_LIMIT_MAX_DEFAULT = 20;
const TOOL_RATE_LIMIT_WINDOW_MS_DEFAULT = 60_000;

function positiveIntEnv(name: string, fallback: number): number {
  const value = Number(process.env[name] ?? fallback);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : fallback;
}

function toolPayloadMaxBytes(): number {
  return positiveIntEnv("MCP_TOOL_PAYLOAD_MAX_BYTES", TOOL_PAYLOAD_MAX_BYTES_DEFAULT);
}

function toolResultMaxBytes(): number {
  return positiveIntEnv("MCP_TOOL_RESULT_MAX_BYTES", TOOL_RESULT_MAX_BYTES_DEFAULT);
}

function toolTimeoutMs(): number {
  return positiveIntEnv("MCP_TOOL_TIMEOUT_MS", TOOL_TIMEOUT_MS_DEFAULT);
}

function toolRateLimitConfig(): { max: number; windowMs: number } {
  return {
    max: positiveIntEnv("MCP_TOOL_RATE_LIMIT_MAX", TOOL_RATE_LIMIT_MAX_DEFAULT),
    windowMs: positiveIntEnv("MCP_TOOL_RATE_LIMIT_WINDOW_MS", TOOL_RATE_LIMIT_WINDOW_MS_DEFAULT),
  };
}

/**
 * Rate-limit identity for the per-(identity, tool) limiter: the tenant plus the
 * client id (registered MCP clients) or the resolved role (env-key callers).
 * Anonymous public_viewer callers share one "viewer|anon" identity — they can
 * only reach the two public-safe tools, and the per-IP limiter still bounds
 * per-source volume (noted residual in the #686 PR).
 */
function toolRateLimitIdentity(): string {
  const store = RequestContextStore.get();
  if (!store) return "uncontexted";
  const principal = store.clientId ?? store.role ?? "anon";
  return `${store.tenantId ?? "default"}|${principal}`;
}

function consumeToolRateLimit(toolName: string): { allowed: boolean; retryAfterMs: number } {
  const { max, windowMs } = toolRateLimitConfig();
  return consumeSlidingWindow(toolIdentityRateBuckets, `${toolRateLimitIdentity()}||${toolName}`, max, windowMs);
}

/**
 * Input payload validation (#686 item 1). `toolArgs` is the parsed
 * CallToolRequest `params.arguments` as handed to the registered callback.
 * Returns null when the payload is acceptable, or a human-readable denial.
 */
function toolPayloadError(toolName: string, toolArgs: unknown): string | null {
  if (toolArgs === undefined || toolArgs === null) return null; // absent arguments
  if (typeof toolArgs !== "object" || Array.isArray(toolArgs)) {
    return `Invalid arguments for tool '${toolName}': arguments must be a JSON object.`;
  }
  let serialized: string;
  try {
    serialized = JSON.stringify(toolArgs) ?? "";
  } catch {
    return `Invalid arguments for tool '${toolName}': arguments are not JSON-serializable.`;
  }
  const maxBytes = toolPayloadMaxBytes();
  const byteLength = Buffer.byteLength(serialized, "utf8");
  if (byteLength > maxBytes) {
    return `Payload too large for tool '${toolName}': ${byteLength} bytes exceeds the ${maxBytes}-byte limit (MCP_TOOL_PAYLOAD_MAX_BYTES).`;
  }
  return null;
}

/** Error sentinel for the #686 execution-timeout race. */
class ToolExecutionTimeoutError extends Error {
  constructor(toolName: string, timeoutMs: number) {
    super(`Tool '${toolName}' execution timed out after ${timeoutMs}ms`);
    this.name = "ToolExecutionTimeoutError";
  }
}

/**
 * Output truncation (#686 item 2). Oversized results are replaced by a single
 * text item holding the byte-clipped serialization, an explicit
 * "...[truncated N bytes]" marker and a `metadata` field; results within the
 * cap (or that cannot be serialized) pass through untouched.
 */
function truncateToolResult(toolName: string, result: unknown): unknown {
  if (result === null || typeof result !== "object") return result;
  let serialized: string | undefined;
  try {
    serialized = JSON.stringify(result);
  } catch {
    return result; // non-serializable results pass through unchanged
  }
  if (serialized === undefined) return result;
  const originalBytes = Buffer.byteLength(serialized, "utf8");
  const maxBytes = toolResultMaxBytes();
  if (originalBytes <= maxBytes) return result;
  const clipped = Buffer.from(serialized, "utf8").subarray(0, maxBytes).toString("utf8");
  const truncatedBytes = originalBytes - maxBytes;
  const wasError = (result as { isError?: unknown }).isError === true;
  return {
    content: [{ type: "text", text: `${clipped}\n...[truncated ${truncatedBytes} bytes]` }],
    isError: wasError,
    metadata: {
      truncated: true,
      tool: toolName,
      originalBytes,
      maxBytes,
      truncatedBytes,
    },
  };
}

function writeJson(res: ServerResponse, status: number, payload: unknown, extraHeaders: Record<string, string> = {}): void {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    ...extraHeaders,
  });
  res.end(JSON.stringify(payload));
}

async function createMcpServer(memoryAdapter?: MemorySubAdapter): Promise<McpServer> {
  const server = new McpServer({
    name: SERVER_NAME,
    version: SERVER_VERSION,
  });

  // Sanitize tool names: replace dots '.' with underscores '_' so that tool names
  // strictly satisfy Anthropic / Cline / Antigravity regex ^[a-zA-Z0-9_-]{1,64}$
  // AND (#695) wrap EVERY tool handler in the central default-deny RBAC gate:
  // no tool callback executes without passing the role/capability check.
  // AND (#686) the SAME wrapper also enforces the per-(identity,tool) rate
  // limit, input payload validation, the hard execution timeout and output
  // truncation — one choke point, no competing wrappers.
  const originalTool = server.tool.bind(server);
  (server as any).tool = (name: string, ...args: any[]) => {
    const sanitizedName = typeof name === "string" ? name.replace(/\./g, "_") : name;
    let handlerIndex = -1;
    for (let i = args.length - 1; i >= 0; i--) {
      if (typeof args[i] === "function") { handlerIndex = i; break; }
    }
    if (handlerIndex >= 0) {
      const originalHandler = args[handlerIndex] as (toolArgs: unknown, extra: unknown) => unknown;
      const wrappedArgs = args.slice();
      wrappedArgs[handlerIndex] = async (toolArgs: unknown, extra: unknown) => {
        // 1) Central default-deny RBAC gate (#695).
        const denial = toolAccessError(sanitizedName);
        if (denial) {
          return { isError: true, content: [{ type: "text", text: denial }] };
        }

        // 2) Per-(identity, tool) rate limit (#686 item 4).
        const toolRate = consumeToolRateLimit(sanitizedName);
        if (!toolRate.allowed) {
          return {
            isError: true,
            content: [{
              type: "text",
              text: `Rate limit exceeded for tool '${sanitizedName}' (max ${toolRateLimitConfig().max} per ${toolRateLimitConfig().windowMs}ms per identity). Retry in ~${Math.ceil(toolRate.retryAfterMs / 1000)}s.`,
            }],
            metadata: { rateLimited: true, tool: sanitizedName, retryAfterMs: toolRate.retryAfterMs },
          };
        }

        // 3) Input payload validation + strict size cap (#686 item 1).
        const payloadError = toolPayloadError(sanitizedName, toolArgs);
        if (payloadError) {
          return { isError: true, content: [{ type: "text", text: payloadError }] };
        }

        // 4) Hard execution timeout (#686 item 3). The handler promise cannot
        // be cancelled, but the caller is released with a structured isError
        // denial as soon as the budget is spent.
        const timeoutBudgetMs = toolTimeoutMs();
        let timeoutTimer: ReturnType<typeof setTimeout> | undefined;
        let result: unknown;
        try {
          result = await Promise.race([
            Promise.resolve(originalHandler(toolArgs, extra)),
            new Promise<never>((_resolve, reject) => {
              timeoutTimer = setTimeout(
                () => reject(new ToolExecutionTimeoutError(sanitizedName, timeoutBudgetMs)),
                timeoutBudgetMs,
              );
              if (typeof timeoutTimer === "object" && timeoutTimer !== null && typeof (timeoutTimer as { unref?: () => void }).unref === "function") {
                (timeoutTimer as { unref: () => void }).unref();
              }
            }),
          ]);
        } catch (error) {
          if (error instanceof ToolExecutionTimeoutError) {
            return {
              isError: true,
              content: [{
                type: "text",
                text: `${error.message} (MCP_TOOL_TIMEOUT_MS). The call was aborted at the governance layer.`,
              }],
              metadata: { timedOut: true, tool: sanitizedName, timeoutMs: timeoutBudgetMs },
            };
          }
          throw error; // non-timeout failures keep the SDK's normal error path
        } finally {
          if (timeoutTimer !== undefined) clearTimeout(timeoutTimer);
        }

        // 5) Output truncation (#686 item 2).
        return truncateToolResult(sanitizedName, result);
      };
      args = wrappedArgs;
    }
    return (originalTool as any)(sanitizedName, ...args);
  };

  await registerAllTools(server, memoryAdapter);

  server.resource(
    MCP_MANIFEST_URI,
    "server-manifest",
    { description: "Verified SupremeAI MCP server identity and trust metadata", mimeType: "application/json" },
    async () => ({
      contents: [{
        uri: MCP_MANIFEST_URI,
        mimeType: "application/json",
        text: JSON.stringify({ ...createBuiltinManifest(SERVER_VERSION), publicAccess: publicAccessManifest() }),
      }],
    }),
  );

  // ── Resources (MCP Protocol — Data/State Exposure) ──
  server.resource(
    "control-tower://system/health",
    "system-health",
    { description: "Real-time health status of all SupremeAI services", mimeType: "application/json" },
    async () => {
      try {
        const { globalHealthCache } = await import("./health/snapshot.js");
        const snapshots = globalHealthCache.getAllSnapshots();
        const services = Object.entries(snapshots).map(([provider, snapshot]) => ({
          provider,
          status: snapshot.status,
          checkedAt: snapshot.checkedAt,
          latencyMs: snapshot.latencyMs,
        }));
        return { contents: [{ uri: "control-tower://system/health", mimeType: "application/json", text: JSON.stringify({ status: services.some((s) => s.status !== "healthy") ? "degraded" : "healthy", services, timestamp: new Date().toISOString() }, null, 2) }] };
      } catch (error) {
        return { contents: [{ uri: "control-tower://system/health", mimeType: "application/json", text: JSON.stringify({ status: "unknown", error: String(error) }) }] };
      }
    }
  );

  server.resource(
    "control-tower://system/dependencies",
    "system-dependencies",
    { description: "Service dependency graph — which services depend on which", mimeType: "application/json" },
    async () => {
      const context = RequestContextStore.get();
      if (context?.accessMode === "public_viewer" && !isPublicSafeResource("control-tower://system/dependencies")) {
        return { contents: [{ uri: "control-tower://system/dependencies", mimeType: "application/json", text: JSON.stringify({ error: "Authentication required for dependency details", code: "protected_capability" }) }] };
      }
      try {
        const { globalDependencyGraph } = await import("./health/dependency.js");
        return { contents: [{ uri: "control-tower://system/dependencies", mimeType: "application/json", text: JSON.stringify(globalDependencyGraph.getRawMap(), null, 2) }] };
      } catch (error) {
        return { contents: [{ uri: "control-tower://system/dependencies", mimeType: "application/json", text: JSON.stringify({ error: String(error) }) }] };
      }
    }
  );

  server.resource(
    "control-tower://clients/registry",
    "client-registry",
    { description: "Registered MCP clients and their roles/scopes", mimeType: "application/json" },
    async () => {
      const context = RequestContextStore.get();
      if (context?.accessMode !== "admin") {
        return { contents: [{ uri: "control-tower://clients/registry", mimeType: "application/json", text: JSON.stringify({ error: "Admin authentication required", code: "protected_capability" }) }] };
      }
      return { contents: [{ uri: "control-tower://clients/registry", mimeType: "application/json", text: JSON.stringify({ clients: listClients(), timestamp: new Date().toISOString() }, null, 2) }] };
    }
  );

  // ── Prompts (MCP Protocol — Reusable Workflow Templates) ──
  server.prompt(
    "diagnose_service",
    "Diagnose a service issue by checking health, dependencies, and recent changes",
    {
      serviceName: z.string().describe("Name of the service to diagnose"),
      includeHistory: z.boolean().optional().describe("Include recent health history"),
    },
    async ({ serviceName, includeHistory }) => {
      const lines = [
        "## Service Diagnosis - " + serviceName,
        "",
        "### Instructions",
        "1. Use system.health tool to check current status of " + serviceName,
        "2. Use system.summary tool to get service capabilities",
        "3. Read control-tower://system/dependencies to check dependency chain",
        "4. Read control-tower://system/health for full system health context",
      ];
      if (includeHistory) {
        lines.push("5. Analyze recent health trends from the snapshot history");
      }
      lines.push(
        "",
        "### Output Format",
        "Return a structured diagnosis report with:",
        "- service: " + serviceName,
        '- status: "healthy" | "degraded" | "down"',
        "- root_cause: identified or suspected root cause",
        "- dependencies_affected: list of dependent services impacted",
        "- recommendations: array of suggested actions",
        '- urgency: "low" | "medium" | "high" | "critical"'
      );
      return {
        messages: [{
          role: "user" as const,
          content: { type: "text" as const, text: lines.join("\n") },
        }],
      };
    }
  );

  server.prompt(
    "onboard_client",
    "Generate onboarding instructions for a new MCP client with appropriate scopes",
    {
      clientName: z.string().describe("Name for the new client"),
      role: z.enum(["viewer", "agent", "admin"]).describe("Role for the new client"),
      provider: z.string().optional().describe("Provider name (e.g. cursor, claude, custom)"),
    },
    async ({ clientName, role, provider }) => {
      const lines = [
        "## Client Onboarding - " + clientName,
        "",
        "### Task",
        "Register a new MCP client with the following details:",
        "- Name: " + clientName,
        "- Role: " + role,
        "- Provider: " + (provider || "generic"),
        "",
        "### Instructions",
        "1. Use client.register tool to create the client with appropriate scopes",
        "2. Display the generated credentials securely",
        "3. Provide connection instructions based on role:",
        "   - viewer: read-only access to health, resources, and prompts",
        "   - agent: viewer + tool execution capabilities",
        "   - admin: full access including client management and approvals",
        "",
        "### Security Notes",
        "- Credentials should be shown ONCE and never logged",
        "- Viewer tokens can be shared more freely",
        "- Admin tokens require secure storage",
        "- Set appropriate expiry based on use case",
        "",
        "### Output Format",
        "Return the client credentials and connection configuration in a secure format.",
      ];
      return {
        messages: [{
          role: "user" as const,
          content: { type: "text" as const, text: lines.join("\n") },
        }],
      };
    }
  );

  return server;
}

function safeEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

export type UserRole = "admin" | "agent" | "viewer" | null;

function resolveRole(req: IncomingMessage): UserRole {
  let token = "";
  const authHeader = req.headers.authorization ?? "";
  const prefix = "Bearer ";
  if (authHeader.startsWith(prefix)) {
    token = authHeader.slice(prefix.length);
  }
  // SECURITY: token/key query parameters are no longer accepted. Query strings
  // leak into proxy/CDN logs, browser history and Referer headers. Browser
  // 1-click approval links use per-request expiring HMAC signatures instead —
  // see policy/approvals/signing.ts and the /approve route below.

  if (!token) return null;

  if (env.mcpAdminKey && safeEqual(token, env.mcpAdminKey)) return "admin";
  if (env.mcpApiKey && safeEqual(token, env.mcpApiKey)) return "admin";
  if (env.mcpAgentKey && safeEqual(token, env.mcpAgentKey)) return "agent";
  if (env.mcpViewerKey && safeEqual(token, env.mcpViewerKey)) return "viewer";
  const client = resolveClient(token);
  return client?.role ?? null;
}

/**
 * Tenant-aware caller context.
 * global admin (env keys) → isGlobalAdmin, tenant scope "*".
 * registered client   → tenantId клиента (tenant isolation).
 * tenant admin token  → управляет своим tenant через заголовок x-tenant-id.
 */
interface CallerContext {
  role: UserRole;
  client?: ExternalClient;
  tenantId: string;
  isGlobalAdmin: boolean;
}

function resolveCaller(req: IncomingMessage): CallerContext {
  const role = resolveRole(req);
  const bearer = (req.headers.authorization ?? "").replace(/^Bearer\s+/i, "");
  const client = bearer ? resolveClient(bearer) : undefined;

  const isEnvAdmin =
    (env.mcpAdminKey && safeEqual(bearer, env.mcpAdminKey)) ||
    (env.mcpApiKey && safeEqual(bearer, env.mcpApiKey));

  // Tenant admin: отдельный заголовок x-tenant-id + x-tenant-admin-token
  const headerTenantId = String(req.headers["x-tenant-id"] ?? "");
  const headerAdminToken = String(req.headers["x-tenant-admin-token"] ?? "");
  let tenantId = "tenant_default";
  let isGlobalAdmin = false;

  if (isEnvAdmin || role === "admin") {
    if (isEnvAdmin) {
      isGlobalAdmin = true;
      tenantId = "*";
    } else {
      tenantId = client?.tenantId ?? "tenant_default";
    }
  } else if (client?.tenantId) {
    tenantId = client.tenantId;
  }

  // Tenant admin token override (only if not global admin already)
  if (!isGlobalAdmin && headerTenantId && headerAdminToken && verifyTenantAdminToken(headerTenantId, headerAdminToken)) {
    isGlobalAdmin = false; // tenant admin — НЕ global admin
    tenantId = headerTenantId;
  }

  return { role, client, tenantId, isGlobalAdmin };
}

function hasWebhookSignature(req: IncomingMessage, body: string, secret: string, header: string): boolean {
  const signature = req.headers[header]?.toString() ?? "";
  if (!secret || !signature.startsWith("sha256=")) return false;
  const expected = `sha256=${createHmac("sha256", secret).update(body).digest("hex")}`;
  return safeEqual(signature, expected);
}

async function startHttpServer(server: McpServer): Promise<void> {
  // Dynamically import transports
  const { StreamableHTTPServerTransport } = await import(
    "@modelcontextprotocol/sdk/server/streamableHttp.js"
  );
  const { SSEServerTransport } = await import(
    "@modelcontextprotocol/sdk/server/sse.js"
  );

  // Per-session transports for SSE
  const sseSessions = new Map<string, any>();

  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
  });

  const httpServer = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    const url = req.url ?? "/";
    const pathname = requestPath(req);
    const caller = resolveCaller(req);
    const role = caller.role;
    const client = caller.client;
    const tenantId = caller.tenantId;
    const isGlobalAdmin = caller.isGlobalAdmin;
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // বাংলা মন্তব্য: অথেনটিকেশন ও অ্যাক্সেস কন্ট্রোল পলিসি (MCP Auth Architecture)
    // ১. /mcp এন্ডপয়েন্ট: Claude Web (claude.ai), v0, Cursor বা যেকোনো পাবলিক এআই ক্লায়েন্টের 
    //    জন্য ওপেন রাখা হয়েছে (role = 'viewer' বা টোকেন দিলে সেই অনুযায়ী 'admin'/'agent')। 
    //    Claude Web যেহেতু ক���স্টম হেডার পাঠাতে পারে না, তাই এটি কোনো OAuth ছাড়াই সহজে সংযুক্ত হতে পারবে।
    // ২. অ্যাডমিন রুটসমূহ (/approve, /approvals, /clients, /autonomy/kill): এগুলো জীবনঘাতী বা সংবেদনশীল 
    //    অপারেশন। এগুলো কঠোরভাবে শুধুমাত্র ভ্যালিড MCP_API_KEY বা MCP_ADMIN_KEY দ্বারা সুরক্ষিত।
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // #698: admin-only routes must PREFIX-match consistently with the handlers
    // below, so suffix paths (/approvals/list, /autonomy/killswitch,
    // /approveXYZ, …) can never slip past the gate. The handlers themselves
    // re-check the caller role (defense in depth).
    const adminOnlyRoute = pathname.startsWith("/approve") || pathname.startsWith("/approvals") || pathname.startsWith("/clients") || pathname.startsWith("/autonomy/kill") || pathname.startsWith("/tenants");

    // Browser 1-click approval links: an HMAC signature bound to the request id,
    // the decision and an expiry — never a permanent credential in the URL.
    // The signature is verified again at the /approve endpoint (defense in depth).
    let isSignedApprovalLink = false;
    if (pathname === "/approve") {
      try {
        const guardUrl = new URL(url, `http://${req.headers.host || "localhost"}`);
        const gid = guardUrl.searchParams.get("id") ?? "";
        const gDecision = guardUrl.searchParams.get("decision") || "APPROVED";
        isSignedApprovalLink = Boolean(gid) && verifyApprovalLink(gid, gDecision, guardUrl.searchParams.get("exp") ?? "", guardUrl.searchParams.get("sig") ?? "");
      } catch {}
    }

    if (env.nodeEnv === "production" && adminOnlyRoute && !env.mcpApiKey && !env.mcpAdminKey) {
      res.writeHead(503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "MCP_API_KEY is required in production" }));
      return;
    }

    // Tenant routes: глобальный админ ИЛИ tenant admin (по заголовкам x-tenant-*).
    const isTenantAdminByHeader = Boolean(
      req.headers["x-tenant-id"] && req.headers["x-tenant-admin-token"] &&
      verifyTenantAdminToken(String(req.headers["x-tenant-id"]), String(req.headers["x-tenant-admin-token"]))
    );
    const canAccessProtectedRoute = role === "admin" || (pathname.startsWith("/clients") && (isTenantAdminByHeader || isGlobalAdmin));

    if (adminOnlyRoute && !canAccessProtectedRoute && !isSignedApprovalLink) {
      res.writeHead(role ? 403 : 401, { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" });
      res.end(JSON.stringify({ error: role ? "Forbidden: Admin role required for this endpoint" : "Unauthorized: Invalid or missing MCP Bearer token" }));
      return;
    }
    if (adminOnlyRoute && pathname.startsWith("/tenants") && role !== "admin") {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Forbidden: Tenants endpoints require global admin" }));
      return;
    }


    if (url === "/health" || url === "/") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(withTimestamp({ status: "ok", server: SERVER_NAME, version: SERVER_VERSION })));
      return;
    }

    if (url === "/health/summary") {
      try {
        const { globalHealthCache } = await import("./health/snapshot.js");
        const snapshots = globalHealthCache.getAllSnapshots();
        const services = Object.entries(snapshots).map(([provider, snapshot]) => ({
          provider,
          status: snapshot.status,
          checkedAt: snapshot.checkedAt,
          latencyMs: snapshot.latencyMs,
        }));
        const unhealthy = services.filter((service) => !["healthy"].includes(service.status)).length;
        res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        res.end(JSON.stringify({
          status: unhealthy ? "degraded" : "healthy",
          serviceCount: services.length,
          unhealthyCount: unhealthy,
          services: services.map((service) => ({
            ...service,
            circle: getServiceDescriptors().find((descriptor) => descriptor.provider === service.provider)?.circle ?? "unknown",
            configured: getServiceDescriptors().find((descriptor) => descriptor.provider === service.provider)?.configured ?? false,
          })),
          ...nowTimestamp(),
        }));
      } catch {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "unknown", error: "Summary unavailable" }));
      }
      return;
    }

    if (url === "/health/dashboard") {
      if (env.nodeEnv === "production" && !resolveRole(req)) {
        res.writeHead(401, { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" });
        res.end(JSON.stringify({ error: "Unauthorized" }));
        return;
      }
      try {
        const { globalHealthCache } = await import("./health/snapshot.js");
        const { globalDependencyGraph } = await import("./health/dependency.js");
        res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        res.end(JSON.stringify({
          snapshots: globalHealthCache.getAllSnapshots(),
          dependencies: globalDependencyGraph.getRawMap(),
          timestamp: new Date().toISOString(),
        }));
      } catch {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "unknown", error: "Dashboard unavailable" }));
      }
      return;
    }

    if (url === "/health/sweep") {
      if (env.nodeEnv === "production" && !resolveRole(req)) {
        res.writeHead(401, { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" });
        res.end(JSON.stringify({ error: "Unauthorized" }));
        return;
      }

      try {
        const { globalHealthEngine } = await import("./health/engine.js");
        const report = await globalHealthEngine.runFullSweep();
        res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        res.end(JSON.stringify(report));
      } catch {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "unknown", error: "Health sweep failed" }));
      }
      return;
    }

    if (url === "/health/summary" || url === "/health/dashboard" || url === "/health/sweep") {
      try {
        const { globalHealthEngine } = await import("./health/engine.js");
        const { globalHealthCache } = await import("./health/snapshot.js");
        const { globalDependencyGraph } = await import("./health/dependency.js");
        const isSweep = url === "/health/sweep";
        const report = isSweep ? await globalHealthEngine.runFullSweep() : undefined;
        const snapshots = report?.snapshots ?? globalHealthCache.getAllSnapshots();
        const services = Object.entries(snapshots).map(([provider, snapshot]) => ({
          provider,
          status: snapshot.status,
          checkedAt: snapshot.checkedAt,
          latencyMs: snapshot.latencyMs,
        }));
        const payload = url === "/health/dashboard"
          ? { snapshots, dependencies: globalDependencyGraph.getRawMap(), timestamp: new Date().toISOString() }
          : { status: report?.overallStatus ?? (services.some((service) => service.status !== "healthy") ? "degraded" : "healthy"), serviceCount: services.length, unhealthyCount: services.filter((service) => service.status !== "healthy").length, services, timestamp: new Date().toISOString() };
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(payload));
      } catch {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "unknown", error: "Health aggregation failed" }));
      }
      return;
    }

    if (url === "/health/ready") {
      try {
        const { globalHealthEngine } = await import("./health/engine.js");
        const report = await globalHealthEngine.runFullSweep();
        const degraded = Object.values(report.snapshots).filter((snapshot) => snapshot.status !== "healthy");
        res.writeHead(degraded.length ? 503 : 200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: degraded.length ? "degraded" : "ready", report }));
      } catch (error) {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "unknown", error: "Readiness sweep failed" }));
      }
      return;
    }

    if (url === "/clients" && req.method === "GET") {
      const scope = isGlobalAdmin ? "*" : tenantId;
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(withTimestamp({ scope, tenants: isGlobalAdmin ? listTenants() : undefined, clients: listClients(scope) })));
      return;
    }

    if (url === "/clients" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => { body += chunk.toString(); });
      req.on("end", () => {
        try {
          const input = JSON.parse(body || "{}");
          if (typeof input.name !== "string" || !input.name.trim()) throw new Error("name is required");
          if (!["viewer", "agent", "admin"].includes(input.role)) throw new Error("role must be viewer, agent, or admin");
          const provider = typeof input.provider === "string" && input.provider.trim() ? input.provider.trim() : "generic";
          const protocol = ["streamable-http", "sse", "stdio", "custom"].includes(input.protocol) ? input.protocol : "streamable-http";
          // Tenant isolation: client токен создаётся в tenant вызывающего.
          const targetTenant = isGlobalAdmin
            ? (typeof input.tenantId === "string" && input.tenantId ? input.tenantId : "tenant_default")
            : tenantId;
          const result = registerClient(input.name.trim(), input.role, input.scopes ?? defaultClientScopes(input.role), input.expiresAt, provider, protocol, targetTenant);
          res.writeHead(201, { "Content-Type": "application/json", "Cache-Control": "no-store" });
          res.end(JSON.stringify(withTimestamp({ ...result, tenantId: targetTenant })));
        } catch (error: any) { res.writeHead(400, { "Content-Type": "application/json" }); res.end(JSON.stringify({ error: error.message })); }
      });
      return;
    }

    if (url.startsWith("/clients/") && url.endsWith("/approve") && req.method === "POST") {
      const id = url.slice("/clients/".length, -"/approve".length);
      const scope = isGlobalAdmin ? "*" : tenantId;
      const client = approveClient(id, scope);
      res.writeHead(client ? 200 : 409, { "Content-Type": "application/json" });
      res.end(JSON.stringify(withTimestamp(client ?? { error: "Client is not pending or was not found" })));
      return;
    }

    if (url.startsWith("/clients/") && req.method === "PATCH") {
      const id = url.slice("/clients/".length);
      const scope = isGlobalAdmin ? "*" : tenantId;
      let body = "";
      req.on("data", (chunk) => { body += chunk.toString(); });
      req.on("end", () => {
        try {
          const input = JSON.parse(body || "{}");
          let client;
          if (input.role) {
            if (!["viewer", "agent", "admin"].includes(input.role)) throw new Error("role must be viewer, agent, or admin");
            client = changeClientRole(id, input.role, scope);
          } else if (input.provider) {
            client = changeClientProvider(id, String(input.provider), scope);
          } else {
            throw new Error("Provide 'role' or 'provider' to update");
          }
          if (!client) throw new Error("Client not found or inactive");
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify(withTimestamp(client)));
        } catch (error: any) { res.writeHead(400, { "Content-Type": "application/json" }); res.end(JSON.stringify({ error: error.message })); }
      });
      return;
    }

    if (url.startsWith("/clients/") && req.method === "DELETE") {
      const id = url.slice("/clients/".length);
      const scope = isGlobalAdmin ? "*" : tenantId;
      const ok = revokeClient(id, scope);
      res.writeHead(ok ? 200 : 404, { "Content-Type": "application/json" });
      res.end(JSON.stringify(withTimestamp({ revoked: ok, id })));
      return;
    }

    if (url.startsWith("/clients/") && url.endsWith("/rotate") && req.method === "POST") {
      const id = url.slice("/clients/".length, -"/rotate".length);
      const scope = isGlobalAdmin ? "*" : tenantId;
      const result = rotateClient(id, scope);
      res.writeHead(result ? 200 : 404, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(withTimestamp(result ?? { error: "Client not found or inactive" })));
      return;
    }

    const TENANT_BAD_REQUEST = 400;

    if (url === "/tenants" && req.method === "GET") {
      const tenants = listTenants();
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(withTimestamp({ tenants, scope: tenantId })));
      return;
    }

    if (url === "/tenants" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => { body += chunk.toString(); });
      req.on("end", () => {
        try {
          const input = JSON.parse(body || "{}");
          if (typeof input.name !== "string" || !input.name.trim()) throw new Error("name is required");
          const ownerEmail = typeof input.ownerEmail === "string" && input.ownerEmail.trim()
            ? input.ownerEmail.trim()
            : `${input.name.trim().toLowerCase().replace(/[^a-z0-9]/g, "")}@tenant.supremeai.local`;
          const limits = {
            ...(typeof input.maxClients === "number" && input.maxClients > 0 ? { maxClients: input.maxClients } : {}),
            ...(typeof input.maxToolsPerMinute === "number" && input.maxToolsPerMinute > 0 ? { maxToolsPerMinute: input.maxToolsPerMinute } : {}),
          };
          const result = createTenant({
            name: input.name.trim(),
            ownerEmail,
            type: input.type === "admin" ? "admin" : "customer",
            description: input.description,
            limits,
            plan: input.plan,
          });
          res.writeHead(201, { "Content-Type": "application/json", "Cache-Control": "no-store" });
          res.end(JSON.stringify(withTimestamp(result)));
        } catch (error: any) { res.writeHead(400, { "Content-Type": "application/json" }); res.end(JSON.stringify({ error: error.message })); }
      });
      return;
    }

    if (url === "/tenants" && req.method === "PATCH") {
      let body = "";
      req.on("data", (chunk) => { body += chunk.toString(); });
      req.on("end", () => {
        try {
          const input = JSON.parse(body || "{}");
          const targetId = String(input.id ?? tenantId);
          if (!isGlobalAdmin && targetId !== tenantId) throw new Error("Forbidden: can only modify own tenant");
          if (input.activate !== undefined || input.suspend !== undefined || input.status !== undefined) {
            if (input.activate) { activateTenant(targetId); }
            else if (input.suspend || input.status === "suspended") { suspendTenant(targetId); }
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify(withTimestamp({ id: targetId, status: getTenant(targetId)?.status ?? "unknown" })));
            return;
          }
          if (input.rotate !== undefined) {
            const result = rotateTenantAdminToken(targetId);
            res.writeHead(201, { "Content-Type": "application/json", "Cache-Control": "no-store" });
            res.end(JSON.stringify(withTimestamp(result)));
            return;
          }
          if (input.name !== undefined || input.description !== undefined || input.status !== undefined || input.plan !== undefined || input.limits !== undefined) {
            const existing = getTenant(targetId);
            if (!existing) throw new Error("Tenant not found");
            const updated = updateTenant(targetId, {
              name: input.name !== undefined ? String(input.name) : existing.name,
              description: input.description !== undefined ? String(input.description) : existing.description,
              status: input.status !== undefined ? input.status : existing.status,
              plan: input.plan !== undefined ? input.plan : existing.plan,
              limits: input.limits ? {
                ...existing.limits,
                ...(typeof input.limits.maxClients === "number" ? { maxClients: input.limits.maxClients } : {}),
                ...(typeof input.limits.maxToolsPerMinute === "number" ? { maxToolsPerMinute: input.limits.maxToolsPerMinute } : {}),
              } : existing.limits,
            });
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify(withTimestamp(updated)));
            return;
          }
          throw new Error("PATCH body must include activate, suspend, name/description/status/plan/limits, or rotate");
        } catch (error: any) { res.writeHead(400, { "Content-Type": "application/json" }); res.end(JSON.stringify({ error: error.message })); }
      });
      return;
    }


    if (url.startsWith("/tenants/") && url.endsWith("/clients") && req.method === "GET") {
      const tid = url.slice("/tenants/".length, -"/clients".length);
      const scope = isGlobalAdmin ? "*" : tenantId;
      if (!isGlobalAdmin && tid !== tenantId) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Forbidden: can only view own tenant clients" }));
        return;
      }
      const clients = listClients(scope === "*" ? "*" : scope);
      const count = countClientsByTenant(tid);
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(withTimestamp({ tenantId: tid, clientCount: count, clients })));
      return;
    }

    // বাংলা মন্তব্য: /mcp-তে টোকেন ছাড়া সংযোগ public_viewer হিসেবে safe, public read-only capability পায়।
    // Support SSE transport for Web AI clients (like Claude Web or legacy MCP SSE)
    if (pathname === "/sse" && req.method === "GET") {
      // Bounded session table: each SSE session pins a transport + socket.
      // Without a cap, reconnect storms exhaust memory on small instances.
      const maxSseSessions = Number(process.env["MCP_MAX_SSE_SESSIONS"] ?? 100);
      if (Number.isFinite(maxSseSessions) && sseSessions.size >= maxSseSessions) {
        writeJson(res, 503, { error: "Too many concurrent SSE sessions", activeSessions: sseSessions.size });
        return;
      }
      const activeRole = role ?? "viewer";
      const authenticated = role !== null;
      const accessMode = accessModeFor(role, authenticated);
      const scopes = client?.scopes ?? defaultClientScopes(activeRole);
      const sseTransport = new SSEServerTransport("/messages", res);
      sseSessions.set(sseTransport.sessionId, sseTransport);
      let dropped = false;
      const dropSession = () => {
        if (dropped) return;
        dropped = true;
        sseSessions.delete(sseTransport.sessionId);
        try { sseTransport.close(); } catch {}
      };
      // The SDK's onclose can miss abrupt TCP drops (client crash, proxy idle
      // timeout). The socket 'close' event is ground truth — clean up on either.
      res.once("close", dropSession);
      sseTransport.onclose = dropSession;
      try {
        await RequestContextStore.run({ role: activeRole, accessMode, authenticated, tenantBound: Boolean(client?.id), clientId: client?.id, scopes, isGlobalAdmin, tenantId }, async () => {
          await server.connect(sseTransport);
        });
      } catch (err) {
        dropSession();
        throw err;
      }
      return;
    }


    if (pathname === "/messages" && req.method === "POST") {
      const parsedUrl = new URL(req.url ?? "/", `http://${req.headers.host || "localhost"}`);
      const sid = parsedUrl.searchParams.get("sessionId");
      const sseTransport = sid ? sseSessions.get(sid) : undefined;
      if (!sseTransport) {
        writeJson(res, 404, { error: "Session not found" });
        return;
      }
      const activeRole = role ?? "viewer";
      const authenticated = role !== null;
      const accessMode = accessModeFor(role, authenticated);
      const scopes = client?.scopes ?? defaultClientScopes(activeRole);
      await RequestContextStore.run({ role: activeRole, accessMode, authenticated, tenantBound: Boolean(client?.id), clientId: client?.id, scopes, isGlobalAdmin, tenantId }, async () => {
        await sseTransport.handlePostMessage(req, res);
      });
      return;
    }

    if (pathname === "/mcp") {
      // Per-IP rate limit (#695): sliding window, 429 + Retry-After when exceeded.
      const rate = consumeMcpRateLimit(clientIpForRateLimit(req));
      if (!rate.allowed) {
        writeJson(
          res,
          429,
          { error: "Rate limit exceeded for /mcp", retryAfterMs: rate.retryAfterMs },
          { "Retry-After": String(Math.ceil(rate.retryAfterMs / 1000)) }
        );
        return;
      }
      if (!["GET", "POST", "DELETE"].includes(req.method ?? "")) {
        writeJson(res, 405, { error: "Method not allowed" }, { Allow: "GET, POST, DELETE" });
        return;
      }
      const contentLength = Number(req.headers["content-length"] ?? 0);
      if (Number.isFinite(contentLength) && contentLength > MAX_REQUEST_BYTES) {
        writeJson(res, 413, { error: "MCP request exceeds the maximum size" });
        return;
      }
      const activeRole = role ?? "viewer";
      const authenticated = role !== null;
      const accessMode = accessModeFor(role, authenticated);
      const scopes = client?.scopes ?? defaultClientScopes(activeRole);
      const requiredRole = accessMode === "admin" ? "admin" : accessMode === "agent" ? "agent" : "viewer";
      if (!roleAllows(activeRole, requiredRole)) {
        writeJson(res, 403, { error: "Forbidden: client role cannot access MCP tools", code: "protected_capability" });
        return;
      }

      // Intercept headers for universal client compatibility:
      // 1. Auto-inject Mcp-Session-Id if client did not send it
      if (!req.headers["mcp-session-id"] && transport.sessionId) {
        req.rawHeaders.push("mcp-session-id", transport.sessionId);
        req.headers["mcp-session-id"] = transport.sessionId;
      }
      // 2. Accept header compatibility (allow generic web fetchers)
      if (!req.headers["accept"] || req.headers["accept"] === "*/*") {
        req.headers["accept"] = "application/json, text/event-stream";
      }

      let body = "";
      req.on("data", (chunk) => { body += chunk.toString(); });
      req.on("end", async () => {
        let parsedBody: any;
        try {
          if (body) {
            parsedBody = JSON.parse(body);
            // Allow re-initialization per client connection
            if (parsedBody && (parsedBody.method === "initialize" || (Array.isArray(parsedBody) && parsedBody.some((m: any) => m.method === "initialize")))) {
              (transport as any)._webStandardTransport._initialized = false;
            }
          }
        } catch {}

        await RequestContextStore.run({ role: activeRole, accessMode, authenticated, tenantBound: Boolean(client?.id), clientId: client?.id, scopes, isGlobalAdmin, tenantId }, async () => {
          await transport.handleRequest(req, res, parsedBody);
        });
      });
      return;
    }

    if (url === "/approvals" || url.startsWith("/approvals")) {
      // Defense in depth (#698): the route gate prefix-matches /approvals*, but
      // the handler re-checks the caller role itself.
      if (role !== "admin") {
        writeJson(res, role ? 403 : 401, { error: role ? "Forbidden: Admin role required for approval listings" : "Unauthorized: Invalid or missing MCP Bearer token" }, { "WWW-Authenticate": "Bearer" });
        return;
      }
      try {
        const { globalApprovalManager } = await import("./policy/approvals/lifecycle.js");
        const items = globalApprovalManager.getAllRequests().map(req => ({
          id: req.id,
          action: `${req.context.provider}.${req.context.action}`,
          target: req.context.provider,
          requested_by: "agent",
          requested_at: new Date(req.createdAtMs).toISOString(),
          reason: `Action requires approval. Parameters: ${JSON.stringify(req.metadata ?? {})}`,
          status: req.state.toLowerCase(),
          ...timestampDetails(req.createdAtMs, req.expiresAtMs, req.resolvedAtMs ?? req.createdAtMs),
          resolvedAt: req.resolvedAtMs ? new Date(req.resolvedAtMs).toISOString() : undefined,
          resolvedAtMs: req.resolvedAtMs,
        }));
        res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        res.end(JSON.stringify({ items, total: items.length, storage: globalApprovalManager.storageMode }));
      } catch (err: any) {
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: err.message }));
      }
      return;
    }

    if (url.startsWith("/approve")) {
      const parsedUrl = new URL(url, `http://${req.headers.host}`);
      const id = parsedUrl.searchParams.get("id");
      const decision = (parsedUrl.searchParams.get("decision") || "APPROVED") as "APPROVED" | "REJECTED";
      if (!id) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing id parameter" }));
        return;
      }
      // Signed-link callers have no admin role; verify their signature again here
      // (the guard above already validated it — this is defense in depth).
      if (!role) {
        const linkOk = verifyApprovalLink(id, decision, parsedUrl.searchParams.get("exp") ?? "", parsedUrl.searchParams.get("sig") ?? "");
        if (!linkOk) {
          res.writeHead(401, { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" });
          res.end(JSON.stringify({ error: "Unauthorized: invalid, expired or missing approval link signature" }));
          return;
        }
      }
      // Defense in depth (#698): an authenticated non-admin can never resolve
      // approvals — only admin tokens or a valid signed link may.
      if (role && role !== "admin") {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Forbidden: Admin role or signed approval link required" }));
        return;
      }
      try {
        const { globalApprovalManager } = await import("./policy/approvals/lifecycle.js");
        globalApprovalManager.resolveRequest(id, decision);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: decision.toLowerCase(), id }));
      } catch (err: any) {
        res.writeHead(409, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: err.message, code: "approval_transition_rejected" }));
      }
      return;
    }

    if (url.startsWith("/webhooks/")) {
      let body = "";
      req.on("data", chunk => body += chunk.toString());
      req.on("end", async () => {
        try {
          const isGithub = url === "/webhooks/github";
          const secret = isGithub ? env.githubWebhookSecret : env.cloudflareWebhookSecret;
          const signatureHeader = isGithub ? "x-hub-signature-256" : "x-cloudflare-signature";
          if (env.nodeEnv === "production" && !hasWebhookSignature(req, body, secret, signatureHeader)) {
            res.writeHead(401, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Invalid webhook signature" }));
            return;
          }
          const payload = JSON.parse(body || "{}");
          const { globalEventGateway } = await import("./events/gateway.js");
          const { globalEventNormalizer } = await import("./events/normalizer.js");

          if (url === "/webhooks/github") {
            const eventName = req.headers["x-github-event"] as string || "unknown";
            const normalized = globalEventNormalizer.normalizeGitHubEvent(eventName, payload);
            await globalEventGateway.dispatch(normalized);
          } else if (url === "/webhooks/cloudflare") {
            const normalized = globalEventNormalizer.normalizeCloudflareEvent(payload);
            await globalEventGateway.dispatch(normalized);
          }
          
          res.writeHead(200);
          res.end(JSON.stringify({ status: "received" }));
        } catch (err: any) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: err.message }));
        }
      });
      return;
    }

    if (url.startsWith("/autonomy/kill")) {
      // Defense in depth (#698): the route gate prefix-matches /autonomy/kill*,
      // but the handler re-checks the caller role itself.
      if (role !== "admin") {
        writeJson(res, role ? 403 : 401, { error: role ? "Forbidden: Admin role required for the autonomy kill switch" : "Unauthorized: Invalid or missing MCP Bearer token" }, { "WWW-Authenticate": "Bearer" });
        return;
      }
      try {
        const { globalKillSwitch } = await import("./remediation/killswitch.js");
        globalKillSwitch.emergencyStop();
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(`<h1>🚨 AUTONOMY KILLED</h1><p>System dropped to L0 mode.</p>`);
      } catch (err: any) {
        res.writeHead(500, { "Content-Type": "text/html" });
        res.end(`<h1>Error</h1><p>${err.message}</p>`);
      }
      return;
    }

    res.writeHead(404);
    res.end("Not found");
  });

  await server.connect(transport);

  httpServer.listen(env.port, () => {
    console.error(`[MCP] SupremeAI Control Tower → http://localhost:${env.port}/mcp`);
    console.error(`[MCP] Health → http://localhost:${env.port}/health`);
  });
}

async function startStdioServer(server: McpServer): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // #698: RequestContextStore.getRole() is fail-closed — a missing request
  // context no longer silently grants "admin". stdio IS a genuinely trusted
  // local transport, so that trust is established EXPLICITLY here (the only
  // transport-internal opt-in path): every inbound message is wrapped in an
  // admin RequestContext. HTTP transports build their own per-request contexts
  // with the caller's real role and must never rely on this.
  const transportAny = transport as unknown as { onmessage?: (...args: unknown[]) => void };
  const innerOnmessage = transportAny.onmessage;
  if (typeof innerOnmessage === "function") {
    transportAny.onmessage = (...args: unknown[]) =>
      RequestContextStore.run(
        { role: "admin", accessMode: "admin", authenticated: true, isGlobalAdmin: true, tenantBound: false, tenantId: "*", scopes: ["*"] },
        () => innerOnmessage(...args),
      );
  } else {
    // Unexpected SDK shape: fail safe — stdio callers degrade to the fail-closed
    // default (viewer) instead of admin.
    console.error("[MCP] stdio transport did not expose onmessage; context-less calls stay fail-closed (viewer)");
  }
  console.error("[MCP] SupremeAI Control Tower running in stdio mode");
}

async function main(): Promise<void> {
  const mode = process.env["MCP_TRANSPORT"] ?? "http";

  // Unified Gateway: internal Python memory sidecar (stdio bridge).
  // Non-blocking start — tools degrade gracefully while it spawns.
  // Disable with SUPREMEAI_DISABLE_MEMORY_SIDECAR=1.
  const memoryAdapter = new MemorySubAdapter();
  if (process.env["SUPREMEAI_DISABLE_MEMORY_SIDECAR"] !== "1") {
    memoryAdapter.start().catch((err) =>
      console.error("[Memory Sidecar] Background start failed:", err),
    );
    const shutdown = () => {
      memoryAdapter.stop().catch(() => undefined);
    };
    process.on("exit", shutdown);
    process.on("SIGINT", () => { shutdown(); process.exit(0); });
    process.on("SIGTERM", () => { shutdown(); process.exit(0); });
  }
  // For local dev / debugging only: block until the sidecar is ready.
  const logReady = process.env["SUPREMEAI_LOG_MEMORY_READY"];
  if (logReady && logReady !== "0" && logReady !== "false") {
    try {
      const tools = await memoryAdapter.listTools();
      console.error("[Memory Sidecar] Successfully listed", tools.length, "tools from live Python MCP server.");
    } catch (err) {
      console.error("[Memory Sidecar] Could not list tools from live Python MCP server:", err);
    }
  }

  try {
    const infisicalResult = await pullSecretsIntoProcessEnv();
    if (infisicalResult.loaded > 0) {
      console.error(`[Infisical] Successfully injected ${infisicalResult.loaded} secrets from Infisical vault.`);
    }

    const server = await createMcpServer(memoryAdapter);

    if (mode === "stdio") {
      await startStdioServer(server);
    } else {
      await startHttpServer(server);
    }
  } catch (err) {
    console.error("[MCP] Fatal startup error:", err);
    process.exit(1);
  }
}

main();
