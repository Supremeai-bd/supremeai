import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { towerHealth, callTowerTool, wakeTower, listTowerTools } from "@/lib/tower-client";
import { getSettings, logActivity } from "@/lib/settings";
import { listOpenPRs } from "@/lib/github-client";
import { detectServiceTransitions, handleServiceTransitions } from "@/lib/watchdog";
import type { DashboardData, ServiceStatus, ActivityItem } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

interface TowerServiceRow {
  id?: string;
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
  error?: string;
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
  return rows.slice(0, 24).map((r) => {
    const status = (() => {
      // IMPORTANT: registry `available: true` means "API key present", NOT
      // "live-verified healthy" — only explicit evidence (status / healthy
      // flag) can produce a healthy verdict; everything else is unknown.
      const s = String(r.status ?? (r.healthy === true ? "healthy" : r.healthy === false || r.available === false ? "unknown" : "unknown")).toLowerCase();
      if (["healthy", "ok", "live", "up", "green"].includes(s)) return "healthy";
      if (["degraded", "warn", "yellow", "slow"].includes(s)) return "degraded";
      if (["down", "error", "critical", "red", "fail", "failed", "unreachable"].includes(s)) return "down";
      // "unconfigured" (and anything unrecognized) → unknown: honest gray, NOT down
      return "unknown";
    })();
    // Surface WHY: probe error verbatim, an explicit "not configured" hint for
    // registry rows whose API key is missing, or a "registry-only" marker.
    const notConfigured =
      r.available === false && !r.error
        ? `not configured on tower — ${r.note ?? r.role ?? "API key missing"}`
        : null;
    const registryOnly =
      !r.status && r.healthy === undefined && r.available !== false && !r.error
        ? `registry only — no live probe (${r.note ?? r.role ?? "no target"})`
        : null;
    return {
      provider: String(r.provider ?? r.service ?? r.name ?? r.displayName ?? "unknown"),
      status,
      latencyMs: (r.latencyMs ?? r.latency_ms ?? null) as number | null,
      checkedAt: String(r.checkedAt ?? r.lastChecked ?? new Date().toISOString()),
      note: r.error ?? notConfigured ?? registryOnly ?? r.note ?? r.role,
    };
  });
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
      // Prefer system.health (LIVE provider-aware probes with real latency /
      // httpStatus / error) over system.summary (static registry availability).
      const healthCall = await callTowerTool("system_health", {});
      if (healthCall.ok) {
        const payload = healthCall.result as Record<string, unknown> | null;
        const rawServices = payload?.services ?? payload?.health ?? payload?.data ?? null;
        services = normalizeServices(rawServices);
        summary = typeof payload?.summary === "string" ? payload.summary : null;
      }

      // Merge registry rows the health tool did NOT cover (older tower builds
      // skip services without a probeable url, e.g. Cloudflare without an API
      // token) so they show as "unknown · not configured" instead of silently
      // disappearing. Live probe results always win over registry availability.
      const sum = await callTowerTool("system_summary", {});
      if (sum.ok) {
        const payload = sum.result as Record<string, unknown> | null;
        if (!summary && typeof payload?.summary === "string") summary = payload.summary;
        const rawReg = payload?.services ?? payload?.byProvider ?? null;
        const regRows = normalizeServices(rawReg);
        const known = new Set(services.map((s) => s.provider));
        for (const r of regRows) {
          if (!known.has(r.provider)) services.push(r);
        }
      }

      if (services.length === 0) {
        const dash = await callTowerTool("health_dashboard", {});
        if (dash.ok) services = normalizeServices(dash.result);
      }
      const tools = await listTowerTools();
      toolsCount = tools.tools.length;

      // Watchdog: detect status transitions BEFORE persisting fresh snapshots
      // (comparison must be against the previous generation of evidence)
      let watchdogHandled: Promise<void> = Promise.resolve();
      try {
        const transitions = await detectServiceTransitions(services);
        if (transitions.length > 0) watchdogHandled = handleServiceTransitions(transitions).catch(() => undefined);
      } catch {
        /* watchdog is best-effort */
      }

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
      // Notify/journal after snapshots are durably written
      await watchdogHandled.catch(() => undefined);
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

    // REAL open PR count from the GitHub API (cached 60s in-process) — the
    // previous value counted git-sync LEDGER entries, not actual PRs.
    let openPrs: number | null = null;
    try {
      const g = globalThis as typeof globalThis & { __mcOpenPrCache?: { at: number; n: number } };
      const cached = g.__mcOpenPrCache;
      if (cached && Date.now() - cached.at < 60_000) {
        openPrs = cached.n;
      } else {
        const prs = await listOpenPRs();
        openPrs = prs.length;
        g.__mcOpenPrCache = { at: Date.now(), n: openPrs };
      }
    } catch {
      openPrs = null; // GitHub not configured / API error → show —, never a fake number
    }

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
