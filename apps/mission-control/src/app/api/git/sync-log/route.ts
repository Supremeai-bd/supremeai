import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 40) || 40, 100);
  const rows = await db.gitSyncCheck.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
  });
  return NextResponse.json({
    rows: rows.map((r) => ({
      id: r.id,
      prNumber: r.prNumber,
      branch: r.branch,
      baseSha: r.baseSha,
      headSha: r.headSha,
      conflict: r.conflict,
      behindBy: r.behindBy,
      aheadBy: r.aheadBy,
      action: r.action,
      detail: r.detail,
      createdAt: r.createdAt.toISOString(),
    })),
  });
}
