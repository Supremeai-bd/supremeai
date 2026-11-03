import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * Watchdog history — filterable reliability audit over watchdog ActivityEvents.
 * Zero tower dependency: everything is journaled locally, so this works while
 * the tower sleeps and survives tower restarts.
 */

interface WatchdogEvent {
  id: string;
  level: string;
  title: string;
  detail: string | null;
  kind: string | null;
  provider: string | null;
  channel: string | null;
  drill: boolean;
  createdAt: string;
}

interface ProviderSummary {
  provider: string;
  down: number;
  degraded: number;
  recovered: number;
  notifies: number;
  lastAt: string | null;
}

function parseMeta(raw: string | null): { provider?: string; kind?: string; channel?: string; drill?: boolean } {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as { provider?: string; kind?: string; channel?: string; drill?: boolean };
  } catch (err) {
    console.warn('[watchdog/history] meta JSON parse failed, using empty fallback:', err);
    return {};
  }
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const kind = url.searchParams.get("kind"); // all | down | degraded | recovered | notify
  const provider = url.searchParams.get("provider");
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 60) || 60, 200);

  try {
    const rows = await db.activityEvent.findMany({
      where: { type: "watchdog" },
      orderBy: { createdAt: "desc" },
      take: 300,
    }).catch(() => []);

    const events: WatchdogEvent[] = [];
    const byProvider = new Map<string, ProviderSummary>();
    const since24h = Date.now() - 24 * 3600_000;
    let total24h = 0;

    for (const r of rows) {
      const meta = parseMeta(r.meta);
      const isNotify = r.title.includes("notify");
      const evKind = isNotify ? "notify" : (meta.kind ?? null);
      if (kind && kind !== "all" && evKind !== kind) continue;
      if (provider && meta.provider !== provider) continue;
      events.push({
        id: r.id,
        level: r.level,
        title: r.title,
        detail: r.detail,
        kind: evKind,
        provider: meta.provider ?? null,
        channel: meta.channel ?? null,
        drill: meta.drill === true,
        createdAt: r.createdAt.toISOString(),
      });
      if (r.createdAt.getTime() >= since24h) total24h++;
      if (meta.provider && evKind) {
        const s = byProvider.get(meta.provider) ?? { provider: meta.provider, down: 0, degraded: 0, recovered: 0, notifies: 0, lastAt: null };
        if (evKind === "down") s.down++;
        else if (evKind === "degraded") s.degraded++;
        else if (evKind === "recovered") s.recovered++;
        else if (evKind === "notify") s.notifies++;
        if (!s.lastAt || r.createdAt.toISOString() > s.lastAt) s.lastAt = r.createdAt.toISOString();
        byProvider.set(meta.provider, s);
      }
    }

    const providers = [...byProvider.values()].sort((a, b) => b.down + b.degraded - (a.down + a.degraded)).slice(0, 8);

    return NextResponse.json({
      ok: true,
      total: events.length,
      total24h,
      events: events.slice(0, limit),
      providers,
      checkedAt: new Date().toISOString(),
    });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err), events: [], providers: [], total24h: 0 }, { status: 500 });
  }
}
