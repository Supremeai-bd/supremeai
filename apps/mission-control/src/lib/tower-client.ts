import { db } from "@/lib/db";
import { createHash, randomUUID } from "node:crypto";

/**
 * SupremeAI MCP Tower client.
 * Speaks MCP Streamable HTTP (JSON-RPC over POST /mcp) with:
 *  - header auth (admin key)
 *  - session management (cached, re-initialized on invalidation)
 *  - auto-wake: Render free tier sleeps → ping /health, then retry
 *  - in-memory response cache (Zero Cost philosophy)
 *
 * Zero-hardcode policy: tower URL/key resolve dynamically from DB settings
 * → environment (TOWER_URL / TOWER_ADMIN_KEY). Never stored in source.
 */

type Session = { id: string; createdAt: number };

const g = globalThis as unknown as {
  __towerSession?: Session;
  __towerToolsCache?: { at: number; tools: unknown[] };
  __towerHealthCache?: { at: number; data: unknown };
  __towerInflight?: Promise<unknown> | null;
};

async function getTowerConfig(): Promise<{ url: string; key: string; configured: boolean }> {
  let url = process.env.TOWER_URL || "";
  let key = process.env.TOWER_ADMIN_KEY || "";
  try {
    const rows = await db.setting.findMany({
      where: { key: { in: ["towerUrl", "towerKey"] } },
    });
    for (const r of rows) {
      if (r.key === "towerUrl" && r.value) url = r.value;
      if (r.key === "towerKey" && r.value) key = r.value;
    }
  } catch {
    // DB not ready — env fallback is fine
  }
  return { url: url.replace(/\/+$/, ""), key, configured: Boolean(url && key) };
}

const UNCONFIGURED = "Tower not configured — set TOWER_URL / TOWER_ADMIN_KEY (env or Settings tab)";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function rawJsonPost(url: string, body: unknown, headers: Record<string, string>, timeoutMs = 25000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream", ...headers },
      body: JSON.stringify(body),
      signal: ctrl.signal,
      cache: "no-store",
    });
    const text = await res.text();
    let payload: unknown = null;
    if (text) {
      if (text.startsWith("event:") || text.includes("\ndata:")) {
        // SSE envelope → take first data line
        const line = text.split(/\r?\n/).find((l) => l.startsWith("data:"));
        payload = line ? safeJson(line.slice(5).trim()) : null;
      } else {
        payload = safeJson(text);
      }
    }
    return { status: res.status, headers: res.headers, payload, text };
  } finally {
    clearTimeout(t);
  }
}

function safeJson(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

/** Wake a sleeping Render instance: GET /health until it answers 200. */
export async function wakeTower(maxAttempts = 3): Promise<{ woke: boolean; attempts: number; latencyMs: number | null }> {
  const { url, configured } = await getTowerConfig();
  if (!configured) return { woke: false, attempts: 0, latencyMs: null };
  for (let i = 1; i <= maxAttempts; i++) {
    const t0 = Date.now();
    try {
      const res = await fetch(`${url}/health`, { cache: "no-store", signal: AbortSignal.timeout(30000) });
      if (res.ok) return { woke: true, attempts: i, latencyMs: Date.now() - t0 };
    } catch {
      /* keep trying */
    }
    await sleep(1500);
  }
  return { woke: false, attempts: maxAttempts, latencyMs: null };
}

async function rpc(method: string, params?: unknown, isNotification = false): Promise<{ status: number; result?: unknown; error?: unknown; sessionId?: string }> {
  const { url, key } = await getTowerConfig();
  const body: Record<string, unknown> = { jsonrpc: "2.0", method };
  if (params !== undefined) body.params = params;
  if (!isNotification) body.id = Math.floor(Math.random() * 1e6) + 1;

  const headers: Record<string, string> = { "X-Admin-Key": key };
  if (g.__towerSession) headers["mcp-session-id"] = g.__towerSession.id;

  const res = await rawJsonPost(`${url}/mcp`, body, headers);

  // Session expired/invalid → re-initialize once
  if (res.status === 404 || res.status === 400) {
    if (g.__towerSession) {
      g.__towerSession = undefined;
      return rpc(method, params, isNotification);
    }
  }

  const sid = res.headers.get("mcp-session-id") ?? undefined;
  const payload = res.payload as { result?: unknown; error?: unknown } | null;

  if (!isNotification && payload && (payload as { error?: unknown }).error) {
    return { status: res.status, error: (payload as { error: unknown }).error, sessionId: sid };
  }
  return { status: res.status, result: payload?.result, sessionId: sid };
}

async function ensureSession(): Promise<boolean> {
  if (g.__towerSession) return true;
  const init = await rpc("initialize", {
    protocolVersion: "2025-03-26",
    capabilities: {},
    clientInfo: { name: "supremeai-mission-control", version: "1.0.0" },
  });
  if (!init.sessionId) return false;
  g.__towerSession = { id: init.sessionId, createdAt: Date.now() };
  await rpc("notifications/initialized", undefined, true);
  return true;
}

/** Execute an RPC with auto-wake + retry loop (handles Render cold starts). */
async function withTower<T>(fn: () => Promise<T>, opts: { wake?: boolean } = {}): Promise<T> {
  let wakeAttempts = 0;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const msg = String(err);
      const cold = msg.includes("503") || msg.includes("hibernate") || msg.includes("abort") || msg.includes("fetch failed");
      if (!cold || !opts.wake) throw err;
      wakeAttempts++;
      if (wakeAttempts > 2) throw err;
      await wakeTower(3);
      g.__towerSession = undefined;
    }
  }
  throw new Error("unreachable");
}

export interface TowerHealthResult {
  status: "live" | "sleeping" | "unreachable";
  latencyMs: number | null;
  version: string | null;
  serverName: string | null;
  wakeAttempts: number;
}

export async function towerHealth(force = false): Promise<TowerHealthResult> {
  const { configured } = await getTowerConfig();
  if (!configured) {
    return { status: "unreachable", latencyMs: null, version: null, serverName: null, wakeAttempts: 0 };
  }
  const cached = g.__towerHealthCache as { at: number; data: TowerHealthResult } | undefined;
  if (!force && cached && Date.now() - cached.at < 15_000) return cached.data;

  const { url } = await getTowerConfig();
  const t0 = Date.now();
  let out: TowerHealthResult;
  try {
    const res = await fetch(`${url}/health`, { cache: "no-store", signal: AbortSignal.timeout(30000) });
    const data = (await res.json().catch(() => null)) as { server?: string; version?: string } | null;
    out = {
      status: res.ok ? "live" : "unreachable",
      latencyMs: Date.now() - t0,
      version: data?.version ?? null,
      serverName: data?.server ?? null,
      wakeAttempts: 0,
    };
  } catch (err) {
    const msg = String(err);
    const sleeping = msg.includes("503") || msg.includes("hibernate");
    out = { status: sleeping ? "sleeping" : "unreachable", latencyMs: null, version: null, serverName: null, wakeAttempts: 0 };
  }
  g.__towerHealthCache = { at: Date.now(), data: out };
  return out;
}

export async function listTowerTools(force = false): Promise<{ ok: boolean; tools: McpToolInfo[]; error?: string }> {
  const { configured } = await getTowerConfig();
  if (!configured) return { ok: false, tools: [], error: UNCONFIGURED };
  const cached = g.__towerToolsCache as { at: number; tools: McpToolInfo[] } | undefined;
  if (!force && cached && Date.now() - cached.at < 120_000) return { ok: true, tools: cached.tools };

  try {
    await withTower(
      async () => {
        if (!(await ensureSession())) throw new Error("session init failed");
      },
      { wake: true },
    );
    const res = await withTower(() => rpc("tools/list"), { wake: true });
    const tools = ((res.result as { tools?: unknown[] })?.tools ?? []) as { name: string; description?: string; inputSchema?: unknown }[];
    const mapped: McpToolInfo[] = tools.map((t) => ({
      name: t.name,
      description: t.description ?? "",
      inputSchema: t.inputSchema ?? {},
      category: categorize(t.name),
    }));
    g.__towerToolsCache = { at: Date.now(), tools: mapped };
    return { ok: true, tools: mapped };
  } catch (err) {
    return { ok: false, tools: [], error: String(err) };
  }
}

function categorize(name: string): string {
  if (name.startsWith("memory_")) return "Memory";
  if (name.startsWith("github_")) return "GitHub";
  if (name.startsWith("render_")) return "Render";
  if (name.startsWith("supabase_")) return "Supabase";
  if (name.startsWith("redis_")) return "Redis";
  if (name.startsWith("cloudflare_")) return "Cloudflare";
  if (name.startsWith("firebase_")) return "Firebase";
  if (name.startsWith("tenant_")) return "Tenancy";
  if (name.startsWith("client_")) return "Clients";
  if (name.startsWith("ai_")) return "AI";
  if (name.startsWith("notify_")) return "Notify";
  if (name.startsWith("action_")) return "Actions";
  if (name.startsWith("autonomy_")) return "Autonomy";
  if (name.startsWith("policy_")) return "Policy";
  if (name.startsWith("health_")) return "Health";
  if (name.startsWith("resource")) return "Resources";
  if (name.startsWith("qdrant_")) return "Qdrant";
  if (name.startsWith("docs_")) return "Docs";
  if (name.startsWith("misc_")) return "Misc";
  if (name.startsWith("system_")) return "System";
  if (name.startsWith("firecrawl")) return "Scout";
  if (name.startsWith("agent_")) return "Agents";
  return "Core";
}

export interface TowerCallResult {
  ok: boolean;
  result: unknown;
  error?: string;
  durationMs: number;
}

export async function callTowerTool(tool: string, args: Record<string, unknown> = {}): Promise<TowerCallResult> {
  const t0 = Date.now();
  const { configured } = await getTowerConfig();
  if (!configured) return { ok: false, result: null, error: UNCONFIGURED, durationMs: 0 };
  try {
    await withTower(
      async () => {
        if (!(await ensureSession())) throw new Error("session init failed");
      },
      { wake: true },
    );
    const res = await withTower(() => rpc("tools/call", { name: tool, arguments: args }), { wake: true });
    const payload = res.result as { isError?: boolean; content?: { type: string; text?: string }[] } | undefined;
    const errItem = res.error as { message?: string } | undefined;
    if (errItem?.message) {
      return { ok: false, result: null, error: errItem.message, durationMs: Date.now() - t0 };
    }
    let result: unknown = payload;
    const textBlock = payload?.content?.find((c) => c.type === "text")?.text;
    if (textBlock) {
      const parsed = safeJson(textBlock);
      result = parsed ?? textBlock;
    }
    return { ok: !payload?.isError, result, durationMs: Date.now() - t0, error: payload?.isError ? "Tool reported isError" : undefined };
  } catch (err) {
    return { ok: false, result: null, error: String(err), durationMs: Date.now() - t0 };
  }
}

export function towerSessionAge(): number {
  return g.__towerSession ? Date.now() - g.__towerSession.createdAt : -1;
}

export function sessionFingerprint(): string {
  return g.__towerSession ? createHash("sha1").update(g.__towerSession.id).digest("hex").slice(0, 8) : "none";
}

export function newRequestId(): string {
  return randomUUID();
}
