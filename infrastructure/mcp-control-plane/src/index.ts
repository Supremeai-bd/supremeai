#!/usr/bin/env node
/**
 * SupremeAI MCP Control Tower — Main Entry Point
 * Supports both stdio (local: Claude Desktop, Cursor) and HTTP Streamable (remote)
 */

import "dotenv/config";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { env } from "./lib/env.js";
import { registerAllTools } from "./tools/index.js";

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

    if (url === "/health" || url === "/") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          status: "ok",
          server: SERVER_NAME,
          version: SERVER_VERSION,
          timestamp: new Date().toISOString(),
        })
      );
      return;
    }

    if (url === "/mcp" || url.startsWith("/mcp")) {
      await transport.handleRequest(req, res);
      return;
    }

    if (url.startsWith("/approve")) {
      const parsedUrl = new URL(url, `http://${req.headers.host}`);
      const id = parsedUrl.searchParams.get("id");
      const decision = (parsedUrl.searchParams.get("decision") || "APPROVED") as "APPROVED" | "REJECTED";
      
      if (!id) {
        res.writeHead(400);
        res.end("Missing id parameter");
        return;
      }
      
      try {
        const { globalApprovalManager } = await import("./policy/approvals/lifecycle.js");
        const success = globalApprovalManager.resolveRequest(id, decision);
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(`<h1>Approval Request ${id} marked as ${decision}</h1><p>You can close this window.</p>`);
      } catch (err: any) {
        res.writeHead(400, { "Content-Type": "text/html" });
        res.end(`<h1>Error</h1><p>${err.message}</p>`);
      }
      return;
    }

    if (url.startsWith("/webhooks/")) {
      let body = "";
      req.on("data", chunk => body += chunk.toString());
      req.on("end", async () => {
        try {
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
