import { NextResponse } from "next/server";
import { callTowerTool } from "@/lib/tower-client";
import { db } from "@/lib/db";
import { logActivity } from "@/lib/settings";
import type { ToolCallResult } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: { tool?: string; args?: Record<string, unknown> };
  try {
    body = (await request.json()) as { tool?: string; args?: Record<string, unknown> };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const tool = body.tool?.trim();
  if (!tool) return NextResponse.json({ error: "Missing 'tool'" }, { status: 400 });

  const args = body.args && typeof body.args === "object" ? body.args : {};
  const res = await callTowerTool(tool, args);

  const out: ToolCallResult = {
    ok: res.ok,
    tool,
    durationMs: res.durationMs,
    result: res.result,
    error: res.error,
  };

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

  return NextResponse.json(out, { status: res.ok ? 200 : 502 });
}
