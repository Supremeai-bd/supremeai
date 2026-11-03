import { NextResponse } from "next/server";
import { wakeTower } from "@/lib/tower-client";
import { logActivity } from "@/lib/settings";

export const dynamic = "force-dynamic";

export async function POST() {
  const res = await wakeTower(4);
  await logActivity("system", res.woke ? "success" : "error", res.woke ? "Tower awakened" : "Tower wake failed", `attempts=${res.attempts}${res.latencyMs ? `, ${res.latencyMs}ms` : ""}`);
  return NextResponse.json(res, { status: res.woke ? 200 : 503 });
}
