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
import { accessModeFor, publicAccessManifest, isPublicSafeResource } from "./policy/mcp-access.js";
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
  } else {
    // Also support token or key query parameter for browser 1-click approval links
    try {
      const parsedUrl = new URL(req.url ?? "/", `http://${req.headers.host || "localhost"}`); 
      token = parsedUrl.searchParams.get("token") || parsedUrl.searchParams.get("key") || "";
    } catch {}
  }

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
    const adminOnlyRoute = pathname === "/approve" || pathname === "/approvals" || pathname === "/clients" || pathname.startsWith("/clients/") || pathname === "/autonomy/kill" || pathname === "/tenants" || pathname.startsWith("/tenants/");

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

    if (adminOnlyRoute && !canAccessProtectedRoute) {
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
      const activeRole = role ?? "viewer";
      const authenticated = role !== null;
      const accessMode = accessModeFor(role, authenticated);
      const scopes = client?.scopes ?? defaultClientScopes(activeRole);
      const sseTransport = new SSEServerTransport("/messages", res);
      sseSessions.set(sseTransport.sessionId, sseTransport);
      sseTransport.onclose = () => sseSessions.delete(sseTransport.sessionId);
      await RequestContextStore.run({ role: activeRole, accessMode, authenticated, tenantBound: Boolean(client?.id), clientId: client?.id, scopes }, async () => {
        await server.connect(sseTransport);
      });
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
      await RequestContextStore.run({ role: activeRole, accessMode, authenticated, tenantBound: Boolean(client?.id), clientId: client?.id, scopes }, async () => {
        await sseTransport.handlePostMessage(req, res);
      });
      return;
    }

    if (pathname === "/mcp") {
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

        await RequestContextStore.run({ role: activeRole, accessMode, authenticated, tenantBound: Boolean(client?.id), clientId: client?.id, scopes }, async () => {
          await transport.handleRequest(req, res, parsedBody);
        });
      });
      return;
    }

    if (url === "/approvals" || url.startsWith("/approvals")) {
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
