import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * Per-service uptime history for the System Matrix sparklines.
 * Reads local ServiceSnapshot rows (last 6h window, 16 points per provider).
 * Zero tower dependency — works from the local reliability memory while the
 * tower sleeps.
 */

interface ProviderHistory {
  provider: string;
  /** oldest → newest, 2=healthy 1=degraded 0=down/unknown, null=no data */
  points: (0 | 1 | 2 | null)[];
  uptimePct: number | null;
  checks: number;
}

const WINDOW_MS = 6 * 3600_000;
const POINTS = 16;

function statusLevel(status: string): 0 | 1 | 2 | null {
  if (status === "healthy") return 2;
  if (status === "degraded") return 1;
  if (status === "down") return 0;
  // "unknown"/"unconfigured" = NO live evidence — must not paint a fake DOWN bar.
  return null;
}

export async function GET() {
  try {
    const since = new Date(Date.now() - WINDOW_MS);
    const snaps = await db.serviceSnapshot.findMany({
      where: { checkedAt: { gte: since } },
      orderBy: { checkedAt: "asc" },
      select: { provider: true, status: true, checkedAt: true },
    }).catch(() => []);

    const byProvider = new Map<string, { status: string; at: number }[]>();
    for (const s of snaps) {
      const list = byProvider.get(s.provider) ?? [];
      list.push({ status: s.status, at: s.checkedAt.getTime() });
      byProvider.set(s.provider, list);
    }

    // Drop stale provider identities (old tower payload shapes) — keep only
    // providers observed in a recent batch, so names match the live matrix.
    const FRESH_MS = 15 * 60_000;
    for (const [provider, list] of byProvider) {
      const latest = Math.max(...list.map((i) => i.at));
      if (Date.now() - latest > FRESH_MS) byProvider.delete(provider);
    }

    const now = Date.now();
    const bucketMs = WINDOW_MS / POINTS;
    const history: ProviderHistory[] = [];

    for (const [provider, list] of byProvider) {
      // Bucket the window into POINTS slots; latest snapshot per slot wins.
      const buckets: (0 | 1 | 2 | null)[] = Array(POINTS).fill(null);
      for (const item of list) {
        const idx = Math.min(POINTS - 1, Math.floor((item.at - (now - WINDOW_MS)) / bucketMs));
        if (idx >= 0) buckets[idx] = statusLevel(item.status);
      }
      const knownLevels = buckets.filter((b) => b !== null) as (0 | 1 | 2)[];
      const upCount = knownLevels.filter((l) => l === 2).length;
      history.push({
        provider,
        points: buckets,
        uptimePct: knownLevels.length ? Math.round((upCount / knownLevels.length) * 100) : null,
        checks: list.length,
      });
    }

    history.sort((a, b) => a.provider.localeCompare(b.provider));
    return NextResponse.json({ ok: true, windowHours: WINDOW_MS / 3600_000, history });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err), history: [] }, { status: 500 });
  }
}
