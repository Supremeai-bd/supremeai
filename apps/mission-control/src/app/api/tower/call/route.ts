import { NextResponse } from "next/server";
import { callTowerTool } from "@/lib/tower-client";
import { db } from "@/lib/db";
import { logActivity } from "@/lib/settings";
import type { ToolCallResult } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

/**
 * FE-10 (issue #503): defense-in-depth tool allowlist.
 *
 * Even with the middleware auth gate in front of /api/*, the set of tools
 * reachable through this endpoint is explicitly bounded. Anything outside
 * the allowed families is rejected with 403 before ever reaching the tower.
 * Operators can tighten/extend via TOWER_TOOL_ALLOWLIST (comma-separated
 * prefixes); the default mirrors the tool families the console actually uses.
 */
const DEFAULT_TOOL_FAMILIES = [
  "memory_",
  "github_",
  "render_",
  "supabase_",
  "tenant_",
  "notify_",
  "autonomy_",
  "policy_",
  "system_",
  "git_",
  "web_",
  "kaggle_",
  "telegram_",
  "docs_",
  "resource_",
  "health_",
  "action_",
  "client_",
  "misc_",
  "qdrant_",
  "firebase_",
  "cloudflare_",
  "firecrawl_",
  "redis_",
  "ai_",
  "agent_review_",
  "guardian_",
  "remote_",
];

function toolAllowed(tool: string): boolean {
  const families = (process.env.TOWER_TOOL_ALLOWLIST || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const list = families.length > 0 ? families : DEFAULT_TOOL_FAMILIES;
  return list.some((prefix) => tool.startsWith(prefix));
}

export async function POST(request: Request) {
  let body: { tool?: string; args?: Record<string, unknown>; silent?: boolean };
  try {
    body = (await request.json()) as { tool?: string; args?: Record<string, unknown>; silent?: boolean };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const tool = body.tool?.trim();
  if (!tool) return NextResponse.json({ error: "Missing 'tool'" }, { status: 400 });

  if (!toolAllowed(tool)) {
    return NextResponse.json(
      { error: `Tool '${tool}' is not on the mission-control allowlist` },
      { status: 403 },
    );
  }

  const args = body.args && typeof body.args === "object" ? body.args : {};
  const silent = body.silent === true;
  const res = await callTowerTool(tool, args);

  const out: ToolCallResult = {
    ok: res.ok,
    tool,
    durationMs: res.durationMs,
    result: res.result,
    error: res.error,
  };

  // Silent calls (background polls) skip journaling entirely — keeps the
  // activity stream meaningful and prevents telemetry table bloat.
  if (!silent) {
    try {
      await db.toolCallLog.create({
        data: {
          tool,
          args: JSON.stringify(args).slice(0, 4000),
          ok: res.ok,
          durationMs: res.durationMs,
          snippet: JSON.stringify(res.result ?? res.error ?? "").slice(0, 1000),
        },
      });
      await logActivity("tower_call", res.ok ? "info" : "warn", `Tool: ${tool}`, res.ok ? `${res.durationMs}ms` : (res.error ?? "failed"), { tool, durationMs: res.durationMs });
    } catch {
      /* journal best-effort */
    }
  }

  return NextResponse.json(out, { status: res.ok ? 200 : 502 });
}
