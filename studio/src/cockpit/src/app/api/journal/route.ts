import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { getSettings } from "@/lib/settings";

export const dynamic = "force-dynamic";

/**
 * Operations Journal — governed telemetry over every tool call the console made.
 * Zero tower dependency: reads the local ToolCallLog (SQLite) so it works even
 * while the tower sleeps. Supports `?format=csv` export (respects filters).
 */

interface JournalEntry {
  id: string;
  tool: string;
  ok: boolean;
  durationMs: number;
  snippet: string | null;
  createdAt: string;
}

interface TopTool {
  tool: string;
  calls: number;
  failures: number;
  avgMs: number;
  p95Ms: number | null;
}

/** Nearest-rank percentile over a sample of durations. */
function percentile(sorted: number[], p: number): number | null {
  if (sorted.length === 0) return null;
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[idx];
}

function csvEscape(v: string | number | boolean): string {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = (url.searchParams.get("q") ?? "").trim().toLowerCase();
  const status = url.searchParams.get("status") ?? "all"; // all | ok | failed
  const format = url.searchParams.get("format"); // undefined | "csv"
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 60) || 60, 200);
  const csvLimit = Math.min(Number(url.searchParams.get("csvLimit") ?? 1000) || 1000, 5000);
  // Optional time window in minutes-ago (uptime-bucket deep links + presets). 0 = no bound.
  const sinceMin = Math.min(Math.max(Number(url.searchParams.get("sinceMin") ?? 0) || 0, 0), 10_080);
  const untilMin = Math.min(Math.max(Number(url.searchParams.get("untilMin") ?? 0) || 0, 0), 10_080);

  try {
    const since24h = new Date(Date.now() - 24 * 3600_000);

    // ── Retention pruning (dynamic setting, best-effort) ──
    try {
      const s = await getSettings();
      const days = Math.max(1, Math.min(365, Number(s.journalRetentionDays) || 14));
      const cutoff = new Date(Date.now() - days * 24 * 3600_000);
      const stale = await db.toolCallLog.deleteMany({ where: { createdAt: { lt: cutoff } } });
      if (stale.count > 0) console.log(`[journal] retention pruned ${stale.count} rows (>${days}d)`);
    } catch (err) {
      console.warn('[journal] retention pruning failed:', err);
    }

    // ── Stats over the last 24h ──
    const grouped = await db.toolCallLog.groupBy({
      by: ["tool"],
      where: { createdAt: { gte: since24h } },
      _count: { _all: true },
      _avg: { durationMs: true },
    }).catch(() => []);

    let total24h = 0;
    let ok24h = 0;
    const failsByTool = new Map<string, number>();
    try {
      const [t, f] = await Promise.all([
        db.toolCallLog.count({ where: { createdAt: { gte: since24h } } }),
        db.toolCallLog.count({ where: { createdAt: { gte: since24h }, ok: false } }),
      ]);
      total24h = t;
      ok24h = t - f;
      const failGroups = await db.toolCallLog.groupBy({
        by: ["tool"],
        where: { createdAt: { gte: since24h }, ok: false },
        _count: { _all: true },
      });
      for (const g of failGroups) failsByTool.set(g.tool, g._count._all);
    } catch (err) {
      console.warn('[journal] 24h stats collection failed:', err);
    }

    // ── Per-tool p95 (24h) — sampled durations, nearest-rank ──
    const durationsByTool = new Map<string, number[]>();
    try {
      const samples = await db.toolCallLog.findMany({
        where: { createdAt: { gte: since24h } },
        select: { tool: true, durationMs: true },
        orderBy: { createdAt: "desc" },
        take: 3000,
      });
      for (const s of samples) {
        const list = durationsByTool.get(s.tool) ?? [];
        list.push(s.durationMs);
        durationsByTool.set(s.tool, list);
      }
    } catch (err) {
      console.warn('[journal] duration sampling failed:', err);
    }

    const topTools: TopTool[] = grouped
      .map((g) => {
        const durations = (durationsByTool.get(g.tool) ?? []).sort((a, b) => a - b);
        return {
          tool: g.tool,
          calls: g._count._all,
          failures: failsByTool.get(g.tool) ?? 0,
          avgMs: Math.round(g._avg.durationMs ?? 0),
          p95Ms: percentile(durations, 95),
        };
      })
      .sort((a, b) => b.calls - a.calls)
      .slice(0, 6);

    const avgDurationMs = grouped.length
      ? Math.round(grouped.reduce((acc, g) => acc + (g._avg.durationMs ?? 0), 0) / grouped.length)
      : 0;
    const globalP95 = percentile(
      [...durationsByTool.values()].flat().sort((a, b) => a - b),
      95,
    );

    // ── Filtered entries ──
    const where: Record<string, unknown> = {};
    if (status === "ok") where.ok = true;
    if (status === "failed") where.ok = false;
    if (q) where.tool = { contains: q };
    if (sinceMin > 0 || untilMin > 0) {
      const created: { gte?: Date; lte?: Date } = {};
      if (sinceMin > 0) created.gte = new Date(Date.now() - sinceMin * 60_000);
      if (untilMin > 0) created.lte = new Date(Date.now() - untilMin * 60_000);
      where.createdAt = created;
    }

    const rows = await db.toolCallLog.findMany({
      where,
      orderBy: { createdAt: "desc" },
      take: format === "csv" ? csvLimit : limit,
    }).catch(() => []);

    const entries: JournalEntry[] = rows.map((r) => ({
      id: r.id,
      tool: r.tool,
      ok: r.ok,
      durationMs: r.durationMs,
      snippet: r.snippet,
      createdAt: r.createdAt.toISOString(),
    }));

    // ── CSV export ──
    if (format === "csv") {
      const header = "timestamp_utc,tool,result,duration_ms,snippet";
      const lines = entries.map((e) =>
        [e.createdAt, e.tool, e.ok ? "ok" : "failed", e.durationMs, csvEscape(e.snippet ?? "")].join(","),
      );
      const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      return new NextResponse([header, ...lines].join("\n"), {
        status: 200,
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": `attachment; filename="supremeai-journal-${stamp}.csv"`,
        },
      });
    }

    return NextResponse.json({
      ok: true,
      stats: {
        total24h,
        ok24h,
        failed24h: total24h - ok24h,
        successRate: total24h > 0 ? Math.round((ok24h / total24h) * 100) : 100,
        avgDurationMs,
        p95DurationMs: globalP95,
        topTools,
      },
      entries,
      checkedAt: new Date().toISOString(),
    });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err), stats: null, entries: [] }, { status: 500 });
  }
}
