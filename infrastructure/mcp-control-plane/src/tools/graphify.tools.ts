import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

function getGraphifyEndpoint(): string {
  return process.env.GRAPHIFY_ENDPOINT || "https://api.graphify.com/mcp";
}

function getGraphifyTokens(): string[] {
  const tokens: string[] = [];
  const primary = process.env.GRAPHIPHY_API_KEY || process.env.GRAPIPHY_API_KEY;
  if (primary && primary.trim()) {
    tokens.push(primary.trim());
  }

  // Dynamically discover all additional Graphify tokens in environment (e.g. GRAPHIPHY_API_KEY_2, GRAPHIPHY_API_KEY_3, etc.)
  for (const [key, val] of Object.entries(process.env)) {
    if (!val || !val.trim()) continue;
    const upper = key.toUpperCase();
    if (
      (upper.startsWith("GRAPHIPHY_API_KEY_") || upper.startsWith("GRAPHIFY_API_KEY_") || upper.startsWith("GRAPIPHY_API_KEY_")) &&
      !tokens.includes(val.trim())
    ) {
      tokens.push(val.trim());
    }
  }

  return tokens;
}

async function executeWithToken(endpoint: string, token: string, toolName: string, args: Record<string, any>) {
  // 1. Handshake
  const initRes = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "SupremeAI-Tower", version: "1.0.0" },
      },
    }),
  });

  if (!initRes.ok) {
    throw new Error(`Graphify MCP initialize failed: HTTP ${initRes.status}`);
  }

  const sessionId = initRes.headers.get("mcp-session-id");
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
  };
  if (sessionId) {
    headers["mcp-session-id"] = sessionId;
  }

  // 2. Call Tool
  const callRes = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: toolName,
        arguments: args,
      },
    }),
  });

  if (!callRes.ok) {
    throw new Error(`Graphify tool call failed: HTTP ${callRes.status}`);
  }

  const raw = await callRes.text();
  for (const line of raw.split("\n")) {
    if (line.startsWith("data:")) {
      try {
        return JSON.parse(line.slice(5).trim());
      } catch {
        // ignore
      }
    }
  }

  return { raw };
}

async function callGraphifyMcp(toolName: string, args: Record<string, any>) {
  const tokens = getGraphifyTokens();
  const endpoint = getGraphifyEndpoint();

  if (tokens.length === 0) {
    throw new Error("GRAPHIPHY_API_KEY is not configured in environment or vault.");
  }

  // If operation is list_repositories, federate and aggregate across ALL configured API keys dynamically
  if (toolName === "list_repositories") {
    const allRepos: any[] = [];
    const seenIds = new Set<string>();
    const seenNames = new Set<string>();
    let lastError: Error | null = null;

    for (const token of tokens) {
      try {
        const res = await executeWithToken(endpoint, token, toolName, args);
        // Extract repositories list
        let repos: any[] = [];
        if (res?.result?.structuredContent?.repositories && Array.isArray(res.result.structuredContent.repositories)) {
          repos = res.result.structuredContent.repositories;
        } else if (res?.result?.content?.[0]?.text) {
          try {
            const parsedInner = JSON.parse(res.result.content[0].text);
            if (Array.isArray(parsedInner?.repositories)) {
              repos = parsedInner.repositories;
            }
          } catch {
            // ignore inner parse error
          }
        }

        for (const r of repos) {
          const id = r.repositoryId || r.fullName;
          const name = r.fullName;
          if (id && !seenIds.has(id) && (!name || !seenNames.has(name))) {
            seenIds.add(id);
            if (name) seenNames.add(name);
            allRepos.push(r);
          }
        }
      } catch (err: any) {
        lastError = err;
      }
    }

    if (allRepos.length > 0) {
      return {
        repositories: allRepos,
        total: allRepos.length,
        tokensQueried: tokens.length,
      };
    }

    if (lastError) {
      throw lastError;
    }
    return { repositories: [], total: 0, tokensQueried: tokens.length };
  }

  // For targeted tools (query_graph, search, graphify_trace, recall, etc.), try each token until one succeeds
  let lastErr: Error | null = null;
  for (const token of tokens) {
    try {
      const res = await executeWithToken(endpoint, token, toolName, args);
      // Check if result contains an explicit error indicating not found / unindexed under this token
      const resStr = JSON.stringify(res);
      if (resStr.includes('"isError":true') && tokens.length > 1) {
        lastErr = new Error(resStr);
        continue;
      }
      return res;
    } catch (err: any) {
      lastErr = err;
    }
  }

  if (lastErr) {
    throw lastErr;
  }

  throw new Error("No responses returned from Graphify tokens.");
}

export async function registerGraphifyTools(server: McpServer): Promise<void> {
  server.tool(
    "graphify_call",
    "Call any Graphify MCP tool directly using the Infisical Graphify token (e.g. query_graph, search, list_repositories, graphify_trace, recall, remember).",
    {
      tool: z.string().describe("Graphify tool name (e.g. query_graph, search, list_repositories, recall)"),
      arguments: z.record(z.string(), z.any()).optional().describe("Arguments to pass to the Graphify tool"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ tool, arguments: args }) => {
      try {
        const result = await callGraphifyMcp(tool, args ?? {});
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (err: any) {
        return {
          isError: true,
          content: [{ type: "text", text: `Error: ${err.message}` }],
        };
      }
    }
  );
}
