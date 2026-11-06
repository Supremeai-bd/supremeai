import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { isIP } from "node:net";
import { redactSensitiveData } from "../diagnostics/redaction.js";

/**
 * Validate that an external dynamic tool URL is not targeting private, loopback, or metadata endpoints.
 */
function assertSafeDynamicUrl(raw: string): URL {
  const parsed = new URL(raw);
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("Only HTTP(S) handler URLs are permitted for dynamic tools");
  }
    const hostname = parsed.hostname.toLowerCase();
    // Normalize bracketed IPv6
    const host = hostname.startsWith("[") && hostname.endsWith("]") ? hostname.slice(1, -1) : hostname;
    const ipVer = isIP(host);
    let isPrivate = false;
    if (host === "localhost" || host.endsWith(".local") || host === "::1" || host === "0.0.0.0") {
      isPrivate = true;
    } else if (ipVer === 4) {
      const parts = host.split(".").map((p) => Number(p));
      if (parts[0] === 10) isPrivate = true;
      else if (parts[0] === 192 && parts[1] === 168) isPrivate = true;
      else if (parts[0] === 169 && parts[1] === 254) isPrivate = true;
      else if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) isPrivate = true;
      else if (parts[0] === 127) isPrivate = true;
    } else if (ipVer === 6) {
      // fc00::/7 (ULA) and fe80::/10 (link-local)
      if (host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe80")) isPrivate = true;
    }
    if (isPrivate) {
      throw new Error("Private, loopback, or link-local targets are prohibited (SSRF guard)");
    }
  return parsed;
}

/**
 * Dynamic Tool Registry - Database-driven tool registration
 * Enables tools to be registered from Supabase database rather than hardcoded
 */

interface ToolDefinition {
  tool_id: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  handler_type: "http" | "stdio" | "webhook";
  handler_config: Record<string, unknown>;
  risk_level: "R0" | "R1" | "R2" | "R3" | "R4" | "R5" | "R6";
  enabled: boolean;
}

// Cache for dynamic tools
let dynamicToolsCache: ToolDefinition[] | null = null;
let lastCacheTime = 0;
const CACHE_TTL_MS = 60_000; // 1 minute cache

/**
 * Fetch dynamic tools from Supabase database
 */
async function fetchDynamicTools(): Promise<ToolDefinition[]> {
  const now = Date.now();
  if (dynamicToolsCache && now - lastCacheTime < CACHE_TTL_MS) {
    return dynamicToolsCache;
  }

  try {
    // Dynamic import to avoid circular dependencies
    const supabaseModule = await import("@supabase/supabase-js").catch(() => null);
    // বাংলা: নীরব no-op ফাঁদ বন্ধ — অপারেটর SUPABASE_URL/SERVICE_KEY সেট করেছে
    // কিন্তু optional প্যাকেজটি ইনস্টল না থাকলে আগে নীরবে [] ফিরত হতো; এখন
    // একটি loud warn দেয় যাতে dynamic tools কেন লোড হচ্ছে না তা দৃশ্যমান হয়।
    // ডিপেন্ডেন্সি ইচ্ছাকৃতভাবে optional (zero-cost/lightweight নীতি) —
    // env না থাকলে static tools-ই যথেষ্ট, কোনো ভুয়া ডেটা তৈরি হয় না।
    if (!supabaseModule) {
      const configured = Boolean(
        process.env.SUPABASE_URL &&
          (process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_ANON_KEY),
      );
      if (configured) {
        console.warn(
          "[tool.registry] SUPABASE_URL/credentials are configured but the optional " +
            "@supabase/supabase-js package is not installed — dynamic tools will NOT load. " +
            "Install the package or unset SUPABASE_URL.",
        );
      }
      return [];
    }
    const { createClient } = supabaseModule;
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
      return [];
    }

    const supabase = createClient(supabaseUrl, supabaseKey) as unknown as {
      from: (table: string) => {
        select: (columns: string) => {
          eq: (column: string, value: unknown) => {
            order: (column: string) => Promise<{ data: ToolDefinition[] | null; error: { message: string } | null }>;
          };
        };
      };
    };

    const { data, error } = await supabase
      .from("tools_registry")
      .select("*")
      .eq("enabled", true)
      .order("name");

    if (error) {
      console.error("[MCP Dynamic] Failed to fetch tools:", error.message);
      return [];
    }

    dynamicToolsCache = data || [];
    lastCacheTime = now;
    return dynamicToolsCache;
  } catch (err) {
    console.error("[MCP Dynamic] Error fetching tools:", err);
    return [];
  }
}

/**
 * Register dynamic tools with the MCP server
 */
export async function registerDynamicTools(server: McpServer): Promise<number> {
  const tools = await fetchDynamicTools();
  let registered = 0;

  for (const tool of tools) {
    try {
      server.tool(
        tool.name,
        tool.description,
        buildSchemaFromJSON(tool.input_schema),
        async (args: Record<string, unknown>) => {
          const result = await executeDynamicTool(tool, args);
          return {
            content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
          };
        }
      );
      registered++;
    } catch (err) {
      console.error("[MCP Dynamic] Failed to register tool " + tool.name + ":", err);
    }
  }

  if (registered > 0) {
    console.error("[MCP Dynamic] Registered " + registered + " dynamic tools from database");
  }
  return registered;
}

/**
 * Execute a dynamic tool based on its handler type
 */
async function executeDynamicTool(
  tool: ToolDefinition,
  args: Record<string, unknown>
): Promise<unknown> {
  const MAX_PAYLOAD_BYTES = 500_000;
  const payloadStr = JSON.stringify(args);
  if (payloadStr.length > MAX_PAYLOAD_BYTES) {
    throw new Error(`Dynamic tool payload exceeds 500KB limit (${payloadStr.length} bytes)`);
  }

  switch (tool.handler_type) {
    case "http": {
      const config = tool.handler_config as { url: string; method?: string };
      const safeUrl = assertSafeDynamicUrl(config.url);
      const response = await fetch(safeUrl.toString(), {
        method: config.method || "POST",
        headers: { "Content-Type": "application/json" },
        body: payloadStr,
        signal: AbortSignal.timeout(15_000),
      });
      const data = await response.json();
      return redactSensitiveData(data);
    }
    case "webhook": {
      const config = tool.handler_config as { url: string };
      const safeUrl = assertSafeDynamicUrl(config.url);
      const response = await fetch(safeUrl.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool_id: tool.tool_id, args }),
        signal: AbortSignal.timeout(15_000),
      });
      const data = await response.json();
      return redactSensitiveData(data);
    }
    default:
      return { error: "Unsupported handler type: " + tool.handler_type };
  }
}

/**
 * Build MCP schema from JSON Schema
 */
function buildSchemaFromJSON(schema: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const properties = (schema.properties || {}) as Record<string, Record<string, unknown>>;
  const required = (schema.required || []) as string[];

  for (const [key, prop] of Object.entries(properties)) {
    const isRequired = required.includes(key);
    result[key] = {
      type: prop.type || "string",
      description: prop.description || "",
      optional: !isRequired,
    };
  }

  return result;
}

/**
 * Invalidate the dynamic tools cache (call when tools are updated)
 */
export function invalidateToolsCache(): void {
  dynamicToolsCache = null;
  lastCacheTime = 0;
}
