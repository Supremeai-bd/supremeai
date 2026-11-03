import { NextResponse } from "next/server";
import { listTowerTools } from "@/lib/tower-client";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const force = url.searchParams.get("refresh") === "1";
  const res = await listTowerTools(force);
  return NextResponse.json(res, { status: res.ok ? 200 : 503 });
}
