#!/usr/bin/env node
/**
 * SupremeAI MCP Control Tower — Main Entry Point
 * Supports both stdio (local: Claude Desktop, Cursor) and HTTP Streamable (remote)
 */

import "dotenv/config";
import { timingSafeEqual, createHmac } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { env } from "./lib/env.js";
import { registerAllTools } from "./tools/index.js";
import { RequestContextStore } from "./policy/auth.context.js";
import { getServiceDescriptors } from "./service-circles.js";
import { nowTimestamp, timestampDetails, withTimestamp } from "./lib/timestamps.js";
import { defaultClientScopes, listClients, registerClient, resolveClient, revokeClient, rotateClient, roleAllows, scopeAllows } from "./policy/client-registry.js";

const SERVER_NAME = "supremeai-control-tower";
const SERVER_VERSION = "1.0.0";

async function createMcpServer(): Promise<McpServer> {
  const server = new McpServer({
    name: SERVER_NAME,
    version: SERVER_VERSION,
  });

  await registerAllTools(server);
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

function hasWebhookSignature(req: IncomingMessage, body: string, secret: string, header: string): boolean {
  const signature = req.headers[header]?.toString() ?? "";
  if (!secret || !signature.startsWith("sha256=")) return false;
  const expected = `sha256=${createHmac("sha256", secret).update(body).digest("hex")}`;
  return safeEqual(signature, expected);
}

async function startHttpServer(server: McpServer): Promise<void> {
  // Dynamically import StreamableHTTPServerTransport (optional dep path varies)
  const { StreamableHTTPServerTransport } = await import(
    "@modelcontextprotocol/sdk/server/streamableHttp.js"
  );

  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => crypto.randomUUID(),
  });

  const httpServer = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    const url = req.url ?? "/";

    const protectedRoute = url.startsWith("/mcp") || url.startsWith("/approve") || url.startsWith("/approvals") || url.startsWith("/clients") || url.startsWith("/autonomy/kill");
    const role = resolveRole(req);
    const bearer = (req.headers.authorization ?? "").replace(/^Bearer\s+/i, "");
    const client = bearer ? resolveClient(bearer) : undefined;

    if (env.nodeEnv === "production" && protectedRoute && !env.mcpApiKey && !env.mcpAdminKey) {
      res.writeHead(503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "MCP_API_KEY is required in production" }));
      return;
    }

    if (protectedRoute && !role) {
      res.writeHead(401, { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" });
      res.end(JSON.stringify({ error: "Unauthorized: Invalid or missing MCP Bearer token" }));
      return;
    }

    // RBAC: Restricted administrative endpoints only for admin
    if ((url.startsWith("/approvals") || url.startsWith("/approve") || url.startsWith("/clients") || url.startsWith("/autonomy/kill")) && role !== "admin") {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Forbidden: Admin role required for approval or emergency stop" }));
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
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(withTimestamp({ clients: listClients() })));
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
          const result = registerClient(input.name.trim(), input.role, input.scopes ?? defaultClientScopes(input.role), input.expiresAt);
          res.writeHead(201, { "Content-Type": "application/json", "Cache-Control": "no-store" });
          res.end(JSON.stringify(withTimestamp(result)));
        } catch (error: any) { res.writeHead(400, { "Content-Type": "application/json" }); res.end(JSON.stringify({ error: error.message })); }
      });
      return;
    }

    if (url.startsWith("/clients/") && req.method === "DELETE") {
      const id = url.slice("/clients/".length);
      const ok = revokeClient(id);
      res.writeHead(ok ? 200 : 404, { "Content-Type": "application/json" });
      res.end(JSON.stringify(withTimestamp({ revoked: ok, id })));
      return;
    }

    if (url.startsWith("/clients/") && url.endsWith("/rotate") && req.method === "POST") {
      const id = url.slice("/clients/".length, -"/rotate".length);
      const result = rotateClient(id);
      res.writeHead(result ? 200 : 404, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify(withTimestamp(result ?? { error: "Client not found or inactive" })));
      return;
    }

    if (url === "/mcp" || url.startsWith("/mcp")) {
      const activeRole = role ?? "viewer";
      const requiredRole = activeRole === "admin" ? "admin" : activeRole === "agent" ? "agent" : "viewer";
      if (!roleAllows(activeRole, requiredRole)) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Forbidden: client role cannot access MCP tools" }));
        return;
      }
      await RequestContextStore.run({ role: activeRole, clientId: client?.id, scopes: client?.scopes ?? defaultClientScopes(activeRole) }, async () => {
        await transport.handleRequest(req, res);
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

  try {
    const server = await createMcpServer();

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
