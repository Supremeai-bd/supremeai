import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

export const GRAPHIFY_FEDERATION_REPOSITORIES = {
  primary: {
    id: "f22b437d-c67d-49a2-8f54-f922ecd48787",
    fullName: "Supremeai-bd/supremeai",
  },
  public: {
    id: "7968140b-ae7a-45c5-8484-47525beacd35",
    fullName: "Supremeai-bd/supremeai-public",
  },
} as const;

function resolveRepositoryTarget(raw?: string): { id?: string; fullName?: string } {
  if (!raw || !raw.trim()) {
    return GRAPHIFY_FEDERATION_REPOSITORIES.primary;
  }
  const needle = raw.trim().toLowerCase();
  if (
    needle === "public" ||
    needle.includes("supremeai-public") ||
    needle === GRAPHIFY_FEDERATION_REPOSITORIES.public.id.toLowerCase()
  ) {
    return GRAPHIFY_FEDERATION_REPOSITORIES.public;
  }
  if (
    needle === "primary" ||
    needle === "supremeai" ||
    needle === "core" ||
    needle.includes("supremeai-bd/supremeai") ||
    needle === GRAPHIFY_FEDERATION_REPOSITORIES.primary.id.toLowerCase()
  ) {
    return GRAPHIFY_FEDERATION_REPOSITORIES.primary;
  }
  return { id: raw.trim(), fullName: raw.trim() };
}

function getGraphifyEndpoint(): string {
  return process.env.GRAPHIFY_ENDPOINT || "https://api.graphify.com/mcp";
}

function getGraphifyTokens(): string[] {
  // বাংলা মন্তব্য: একমাত্র সক্রিয় প্রাইমারি কি (GRAPHIPHY_API_KEY) ব্যবহার করা হচ্ছে।
  // অতিরিক্ত বাসি ফর্কের কি (.env বা Infisical-এ ব্যাকআপ হিসেবে সংরক্ষিত থাকলেও)
  // MCP কন্ট্রোল প্লেন থেকে সম্পূর্ণ এড়িয়ে চলা হবে যেন ভুল/বাসি ফর্কে কল না যায়।
  const primary = process.env.GRAPHIPHY_API_KEY || process.env.GRAPIPHY_API_KEY;
  if (primary && primary.trim()) {
    return [primary.trim()];
  }
  return [];
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
      } catch (err) { console.error(err instanceof Error ? err.name : "error"); }
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

  // বাংলা মন্তব্য: যদি রেপো উল্লেখ না থাকে, তবে অটোমেটিক প্রাইমারি রেপো (Supremeai-bd/supremeai)
  // অথবা 'public' কিওয়ার্ড থাকলে (Supremeai-bd/supremeai-public) সিলেক্ট করা হচ্ছে।
  const normalizedArgs: Record<string, any> = { ...args };
  if (toolName !== "list_repositories" && toolName !== "graphify_help") {
    const rawRepo = normalizedArgs.repository_id || normalizedArgs.repository;
    const resolved = resolveRepositoryTarget(rawRepo ? String(rawRepo) : undefined);
    if (resolved.id) {
      normalizedArgs.repository_id = resolved.id;
    }
    if (resolved.fullName) {
      normalizedArgs.repository = resolved.fullName;
    }
  }

  // If operation is list_repositories, federate and aggregate across ALL configured API keys dynamically
  if (toolName === "list_repositories") {
    const allRepos: any[] = [];
    const seenIds = new Set<string>();
    const seenNames = new Set<string>();
    let lastError: Error | null = null;

    for (const token of tokens) {
      try {
        const res = await executeWithToken(endpoint, token, toolName, normalizedArgs);
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
          } catch (err) { console.error(err instanceof Error ? err.name : "error"); }
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

  // For targeted tools (query_graph, search, graphify_trace, recall, etc.), try token
  let lastErr: Error | null = null;
  for (const token of tokens) {
    try {
      const res = await executeWithToken(endpoint, token, toolName, normalizedArgs);
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
    "Call any Graphify MCP tool directly using the Infisical Graphify token (e.g. query_graph, search, list_repositories, graphify_trace, recall, remember). Defaults to Supremeai-bd/supremeai repository; pass repository: 'public' or repository_id: '7968140b-ae7a-45c5-8484-47525beacd35' for supremeai-public.",
    {
      tool: z.string().describe("Graphify tool name (e.g. query_graph, search, list_repositories, recall)"),
      arguments: z.record(z.string(), z.any()).optional().describe("Arguments to pass to the Graphify tool (defaults to Supremeai-bd/supremeai; set repository to 'public' for supremeai-public)"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ tool, arguments: args }) => {
      try {
        const result = await callGraphifyMcp(tool, args ?? {});
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (err: any) {
  console.error(err instanceof Error ? err.name : "error");
        return {
          isError: true,
          content: [{ type: "text", text: `Error: ${err.message}` }],
        };
      }
    }
  );
}
