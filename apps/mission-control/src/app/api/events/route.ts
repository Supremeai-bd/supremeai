import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 30) || 30, 100);
  const type = url.searchParams.get("type");
  const rows = await db.activityEvent.findMany({
    where: type && type !== "all" ? { type } : undefined,
    orderBy: { createdAt: "desc" },
    take: limit,
  });
  return NextResponse.json({
    events: rows.map((r) => ({
      id: r.id,
      type: r.type,
      level: r.level,
      title: r.title,
      detail: r.detail,
      meta: r.meta,
      createdAt: r.createdAt.toISOString(),
    })),
  });
}
