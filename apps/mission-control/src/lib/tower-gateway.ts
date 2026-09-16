"use client";

/**
 * Client-side gateway to the server-side MCP tower proxy.
 * NEVER import server-only modules (db/tower-client) from components —
 * always go through these REST wrappers.
 */

import type { ToolCallResult } from "@/lib/mission-types";

/**
 * Call a governed tower tool through the console proxy.
 * @param silent skip activity-stream/telemetry journaling for this call —
 *        used by background polls so the operator feed stays meaningful.
 */
export async function callTowerTool(
  tool: string,
  args: Record<string, unknown> = {},
  opts?: { silent?: boolean },
): Promise<ToolCallResult> {
  const res = await fetch("/api/tower/call", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool, args, silent: opts?.silent === true }),
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
