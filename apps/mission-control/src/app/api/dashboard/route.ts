import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { towerHealth, callTowerTool, wakeTower, listTowerTools } from "@/lib/tower-client";
import { getSettings, logActivity } from "@/lib/settings";
import type { DashboardData, ServiceStatus, ActivityItem } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

interface TowerServiceRow {
  provider?: string;
  service?: string;
  name?: string;
  status?: string;
  healthy?: boolean;
  available?: boolean;
  displayName?: string;
  role?: string;
  latencyMs?: number | null;
  latency_ms?: number | null;
  note?: string;
  checkedAt?: string;
  lastChecked?: string;
}

function normalizeServices(raw: unknown): ServiceStatus[] {
  if (!raw) return [];
  let rows: TowerServiceRow[] = [];
  if (Array.isArray(raw)) rows = raw as TowerServiceRow[];
  else if (typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    // byProvider shape: { render: [...], github: [...], ... } → flatten
    if (obj.byProvider && typeof obj.byProvider === "object") {
      const inner = obj.byProvider as Record<string, unknown>;
      for (const [prov, list] of Object.entries(inner)) {
        if (Array.isArray(list)) {
          for (const item of list as TowerServiceRow[]) rows.push({ ...item, provider: item.displayName ?? item.id ?? prov });
        } else if (typeof list === "object" && list) {
          rows.push({ ...(list as TowerServiceRow), provider: (list as TowerServiceRow).displayName ?? prov });
        }
      }
    } else {
      // Detect a provider map passed directly (values are arrays/objects of services)
      const values = Object.values(obj);
      const looksLikeProviderMap = values.some(
        (v) => Array.isArray(v) && v.length > 0 && typeof v[0] === "object" && v[0] !== null && ("available" in (v[0] as object) || "displayName" in (v[0] as object) || "status" in (v[0] as object)),
      );
      if (looksLikeProviderMap) {
        for (const [prov, list] of Object.entries(obj)) {
          if (Array.isArray(list)) {
            for (const item of list as TowerServiceRow[]) rows.push({ ...item, provider: item.displayName ?? item.id ?? prov });
          } else if (typeof list === "object" && list) {
            rows.push({ ...(list as TowerServiceRow), provider: (list as TowerServiceRow).displayName ?? prov });
          }
        }
      } else {
        for (const [k, v] of Object.entries(obj)) {
          if (typeof v === "object" && v) rows.push({ ...(v as TowerServiceRow), provider: (v as TowerServiceRow).provider ?? k });
        }
      }
    }
  }
  return rows.slice(0, 24).map((r) => ({
    provider: String(r.provider ?? r.service ?? r.name ?? r.displayName ?? "unknown"),
    status: (() => {
      const s = String(r.status ?? (r.healthy === true || r.available === true ? "healthy" : r.healthy === false || r.available === false ? "down" : "unknown")).toLowerCase();
      if (["healthy", "ok", "live", "up", "green"].includes(s)) return "healthy";
      if (["degraded", "warn", "yellow", "slow"].includes(s)) return "degraded";
      if (["down", "error", "critical", "red", "fail", "failed"].includes(s)) return "down";
      return "unknown";
    })(),
    latencyMs: (r.latencyMs ?? r.latency_ms ?? null) as number | null,
    checkedAt: String(r.checkedAt ?? r.lastChecked ?? new Date().toISOString()),
    note: r.note ?? r.role,
  }));
}

async function recentActivity(limit = 12): Promise<ActivityItem[]> {
  const rows = await db.activityEvent.findMany({ orderBy: { createdAt: "desc" }, take: limit });
  return rows.map((r) => ({ id: r.id, type: r.type, level: r.level, title: r.title, detail: r.detail, createdAt: r.createdAt.toISOString() }));
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const force = url.searchParams.get("refresh") === "1";
  const started = Date.now();
  try {
    const settings = await getSettings();
    const health = await towerHealth(force);

    // If tower asleep and autoWake on → wake it once, then re-read health
    let towerStatus = health.status;
    let wakeAttempts = 0;
    if (health.status !== "live" && settings.autoWake === "true") {
      const wake = await wakeTower(2);
      wakeAttempts = wake.attempts;
      if (wake.woke) {
        const fresh = await towerHealth(true);
        towerStatus = fresh.status;
      }
    }

    let services: ServiceStatus[] = [];
    let summary: string | null = null;
    let toolsCount = 0;

    if (towerStatus === "live") {
      // Prefer system_summary; fallback to health_dashboard (both cached tower-side)
      const sum = await callTowerTool("system_summary", {});
      if (sum.ok) {
        const payload = sum.result as Record<string, unknown> | null;
        summary =
          typeof payload?.summary === "string"
            ? payload.summary
            : typeof payload?.text === "string"
              ? payload.text
              : JSON.stringify(payload ?? {}).slice(0, 600);
        const rawServices = payload?.services ?? payload?.byProvider ?? payload?.health ?? payload?.data ?? null;
        services = normalizeServices(rawServices);
      }
      if (services.length === 0) {
        const dash = await callTowerTool("health_dashboard", {});
        if (dash.ok) services = normalizeServices(dash.result);
      }
      const tools = await listTowerTools();
      toolsCount = tools.tools.length;

      // Persist snapshots (zero-cost cache + history)
      try {
        for (const s of services.slice(0, 12)) {
          await db.serviceSnapshot.create({
            data: {
              provider: s.provider,
              status: s.status,
              latencyMs: s.latencyMs ?? null,
              checkedAt: new Date(),
              raw: JSON.stringify(s).slice(0, 2000),
            },
          });
        }
        const total = await db.serviceSnapshot.count();
        if (total > 800) await db.serviceSnapshot.deleteMany({ where: { checkedAt: { lt: new Date(Date.now() - 6 * 3600_000) } } });
      } catch {
        /* history is best-effort */
      }
    }

    // If tower didn't provide services, fall back to latest known snapshots
    if (services.length === 0) {
      try {
        const providers = await db.serviceSnapshot.groupBy({ by: ["provider"], _max: { checkedAt: true } });
        for (const p of providers) {
          if (!p._max.checkedAt) continue;
          const snap = await db.serviceSnapshot.findFirst({
            where: { provider: p.provider, checkedAt: p._max.checkedAt },
          });
          if (snap)
            services.push({
              provider: snap.provider,
              status: snap.status as ServiceStatus["status"],
              latencyMs: snap.latencyMs,
              checkedAt: snap.checkedAt.toISOString(),
              note: "cached",
            });
        }
      } catch {
        /* ignore */
      }
    }

    const openPrs = await db.gitSyncCheck.count({ where: { action: { in: ["checked", "synced_main"] } } }).catch(() => 0);

    const data: DashboardData = {
      tower: {
        status: towerStatus,
        latencyMs: health.latencyMs,
        version: health.version,
        serverName: health.serverName,
        toolsCount,
        checkedAt: new Date().toISOString(),
        wakeAttempts,
        detail: health.serverName ? `${health.serverName} v${health.version ?? "?"}` : undefined,
      },
      services,
      summary,
      toolsCount,
      openPrs,
      activity: await recentActivity(),
      updatedAt: new Date().toISOString(),
    };

    if (Date.now() - started > 1500) {
      await logActivity("system", "info", "Dashboard refresh", `tower=${towerStatus}, services=${services.length}, ${Date.now() - started}ms`);
    }
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
