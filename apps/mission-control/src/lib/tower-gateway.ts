"use client";

/**
 * Client-side gateway to the server-side MCP tower proxy.
 * NEVER import server-only modules (db/tower-client) from components —
 * always go through these REST wrappers.
 */

import type { ToolCallResult } from "@/lib/mission-types";

export async function callTowerTool(tool: string, args: Record<string, unknown> = {}): Promise<ToolCallResult> {
  const res = await fetch("/api/tower/call", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool, args }),
    cache: "no-store",
  });
  const data = (await res.json()) as ToolCallResult & { error?: string };
  return {
    ok: res.ok && data.ok !== false,
    tool,
    durationMs: data.durationMs ?? 0,
    result: data.result ?? null,
    error: data.error ?? (res.ok ? undefined : `HTTP ${res.status}`),
  };
}
