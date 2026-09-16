"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Activity, Bell, Bot, Cpu, ExternalLink, EyeOff, Gauge, GitPullRequest, Hammer, RadioTower, RefreshCw, Rocket, ServerCog, ShieldCheck, Wrench, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { DashboardData, SettingsData } from "@/lib/mission-types";
import { setJournalIntent } from "@/lib/journal-intent";
import { cn } from "@/lib/utils";
import { callTowerTool } from "@/lib/tower-gateway";
import { KpiCard, SectionHeader, StatusDot, MetricBadge, JsonViewer, ago, serviceIcon, UptimeStrip, type UptimeBucketInfo } from "./widgets";

async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch("/api/dashboard", { cache: "no-store" });
  if (!res.ok) throw new Error(`Dashboard fetch failed (${res.status})`);
  return res.json() as Promise<DashboardData>;
}

const LEVEL_STYLE: Record<string, string> = {
  info: "text-muted-foreground",
  success: "text-emerald-500",
  warn: "text-amber-500",
  error: "text-red-500",
};

export function DashboardTab({ onNavigate }: { onNavigate?: (tab: string) => void }) {
  const qc = useQueryClient();
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: async () =>
      (await fetch("/api/settings")).json() as Promise<{ refreshIntervalSec: number; watchdogOverrides?: string }>,
    staleTime: 120_000,
  });
  const refreshMs = Math.max(10, settings?.refreshIntervalSec ?? 45) * 1000;

  // Providers muted via per-provider watchdog overrides (surfaced as eye-off in the matrix).
  // Prefix-aware: "cloudflare" mutes "Cloudflare (DNS + Workers + Analytics)" too.
  const mutedProviderKeys = React.useMemo(() => {
    try {
      const obj = JSON.parse(settings?.watchdogOverrides ?? "{}") as Record<string, { enabled?: boolean }>;
      return Object.entries(obj)
        .filter(([, o]) => o?.enabled === false)
        .map(([p]) => p.toLowerCase());
    } catch {
      return [] as string[];
    }
  }, [settings?.watchdogOverrides]);
  const isMuted = React.useCallback(
    (provider: string) => {
      const p = provider.trim().toLowerCase();
      return mutedProviderKeys.some((k) => p === k || p.startsWith(k));
    },
    [mutedProviderKeys],
  );

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    refetchInterval: refreshMs,
  });

  const wakeMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/tower/wake", { method: "POST" });
      return res.json();
    },
    onSuccess: (d: { woke?: boolean }) => {
      toast[d.woke ? "success" : "error"](d.woke ? "Tower is awake — link re-established" : "Tower could not be woken (Render cold start may take ~50s)");
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  // Local reliability memory: per-service uptime trend (6h window, zero tower dependency)
  const { data: uptimeData } = useQuery({
    queryKey: ["matrix-history"],
    queryFn: async () => {
      const res = await fetch("/api/matrix/history", { cache: "no-store" });
      return res.json() as Promise<{ ok: boolean; history: { provider: string; points: (0 | 1 | 2 | null)[]; uptimePct: number | null }[] }>;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  const uptimeByProvider = React.useMemo(() => {
    const map = new Map<string, { points: (0 | 1 | 2 | null)[]; uptimePct: number | null }>();
    for (const h of uptimeData?.history ?? []) map.set(h.provider, { points: h.points, uptimePct: h.uptimePct });
    return map;
  }, [uptimeData]);
  const uptimeFor = React.useCallback(
    (provider: string) => {
      const exact = uptimeByProvider.get(provider);
      if (exact) return exact;
      const p = provider.toLowerCase();
      for (const [k, v] of uptimeByProvider) {
        const kk = k.toLowerCase();
        if (kk.includes(p) || p.includes(kk)) return v;
      }
      return undefined;
    },
    [uptimeByProvider],
  );

  const tower = data?.tower;
  const services = data?.services ?? [];
  const healthy = services.filter((s) => s.status === "healthy").length;
  const degraded = services.filter((s) => s.status === "degraded" || s.status === "unknown").length;
  const down = services.filter((s) => s.status === "down").length;
  const [statusFilter, setStatusFilter] = React.useState("all");
  const filteredServices = services
    .filter((s) => (statusFilter === "all" ? true : statusFilter === "degraded" ? s.status === "degraded" || s.status === "unknown" : s.status === statusFilter))
    .sort((a, b) => {
      // Severity-first glanceability: down → degraded → unknown → healthy, then name
      const rank: Record<string, number> = { down: 0, degraded: 1, unknown: 2, healthy: 3 };
      const d = (rank[a.status] ?? 9) - (rank[b.status] ?? 9);
      return d !== 0 ? d : a.provider.localeCompare(b.provider);
    });

  const towerTone = tower?.status === "live" ? "good" : tower?.status === "sleeping" ? "warn" : "bad";

  return (
    <div className="space-y-6">
      {/* KPI rail */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="MCP Tower"
          value={
            <span className="flex items-center gap-2">
              <StatusDot status={tower?.status ?? "unknown"} />
              <span className="capitalize">{tower?.status ?? "…"}</span>
            </span>
          }
          sub={tower?.status === "live" ? `${tower.latencyMs ?? "?"}ms · v${tower.version ?? "?"}` : tower?.status === "sleeping" ? "Render cold start — wake me" : "awaiting link"}
          tone={towerTone}
          icon={<RadioTower className="h-5 w-5" />}
          loading={isLoading}
        />
        <KpiCard
          label="Services"
          value={services.length ? `${healthy}/${services.length}` : "—"}
          sub={services.length ? `${degraded} degraded · ${down} down` : "no telemetry yet"}
          tone={down > 0 ? "bad" : degraded > 0 ? "warn" : services.length ? "good" : "default"}
          icon={<ServerCog className="h-5 w-5" />}
          loading={isLoading}
          onClick={() => onNavigate?.("tower")}
        />
        <KpiCard
          label="Capabilities"
          value={data?.toolsCount || "—"}
          sub="governed tower tools"
          icon={<Wrench className="h-5 w-5" />}
          loading={isLoading}
          onClick={() => onNavigate?.("tower")}
        />
        <KpiCard
          label="PR Watch"
          value={data?.openPrs ?? 0}
          sub="sync checks logged"
          icon={<GitPullRequest className="h-5 w-5" />}
          loading={isLoading}
          onClick={() => onNavigate?.("git")}
        />
      </div>

      <div className="grid min-w-0 gap-6 lg:grid-cols-5">
        {/* Service matrix */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="min-w-0 lg:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Gauge className="h-4 w-4 text-primary" />
                Quick System Matrix
              </CardTitle>
              <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-muted-foreground">
                <span>source: central tower</span>
                {data?.updatedAt && <span>· updated {ago(data.updatedAt)}</span>}
                {tower?.wakeAttempts ? <MetricBadge tone="warn">wake×{tower.wakeAttempts}</MetricBadge> : null}
              </div>
              <div className="flex flex-wrap gap-1.5 pt-2" role="group" aria-label="Filter services by status">
                {([
                  ["all", services.length],
                  ["healthy", healthy],
                  ["degraded", degraded],
                  ["down", down],
                ] as [string, number][]).map(([key, n]) => (
                  <button
                    key={key}
                    onClick={() => setStatusFilter(key)}
                    aria-pressed={statusFilter === key}
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize transition-colors ${
                      statusFilter === key
                        ? "border-primary bg-primary/10 text-primary"
                        : "text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                    }`}
                  >
                    {key} <span className="opacity-60">{n}</span>
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
                </div>
              ) : services.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <RadioTower className="h-10 w-10 text-muted-foreground/40" />
                  <p className="max-w-sm text-sm text-muted-foreground">
                    {tower?.status === "sleeping"
                      ? "The control tower is in Render sleep mode. Free-tier services nap after 15 idle minutes."
                      : "No live telemetry from the tower yet."}
                  </p>
                  <Button size="sm" variant="outline" disabled={wakeMutation.isPending} onClick={() => wakeMutation.mutate()}>
                    {wakeMutation.isPending ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
                    Wake Tower
                  </Button>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40">
                        <TableHead className="h-9">Service</TableHead>
                        <TableHead className="h-9">Status</TableHead>
                        <TableHead className="hidden h-9 md:table-cell">Trend · 6h</TableHead>
                        <TableHead className="h-9 text-right">Latency</TableHead>
                        <TableHead className="h-9 text-right">Checked</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredServices.map((s) => {
                        const { Icon, cls } = serviceIcon(s.provider);
                        return (
                          <TableRow
                            key={s.provider}
                            className={cn(
                              "text-sm transition-colors hover:bg-primary/5",
                              s.status === "down"
                                ? "bg-red-500/[0.06] hover:bg-red-500/10"
                                : s.status === "degraded"
                                  ? "bg-amber-500/[0.05] hover:bg-amber-500/10"
                                  : "odd:bg-muted/10",
                            )}
                          >
                            <TableCell className="max-w-[170px] py-2 sm:max-w-[240px]">
                              <span className="flex items-center gap-2">
                                <Icon className={`h-3.5 w-3.5 shrink-0 ${cls}`} aria-hidden />
                                <span className="truncate font-medium">{s.provider}</span>
                                {isMuted(s.provider) && (
                                  <span
                                    title="Watchdog muted via per-provider override"
                                    aria-label="watchdog muted"
                                  >
                                    <EyeOff className="h-3 w-3 text-amber-500" />
                                  </span>
                                )}
                              </span>
                            </TableCell>
                            <TableCell className="py-2">
                              <span className="inline-flex items-center gap-2 capitalize">
                                <StatusDot status={s.status} />
                                {s.status}
                              </span>
                            </TableCell>
                            <TableCell className="hidden py-2 md:table-cell">
                              {(() => {
                                const u = uptimeFor(s.provider);
                                if (!u) return <span className="text-xs text-muted-foreground/40">gathering…</span>;
                                return (
                                  <span className="flex items-center gap-2">
                                    <UptimeStrip
                                      points={u.points}
                                      onBucketClick={(info: UptimeBucketInfo) => {
                                        setJournalIntent({
                                          sinceMin: info.sinceMin,
                                          untilMin: info.untilMin,
                                          label: `${info.rangeLabel} UTC · ${info.status}`,
                                        });
                                        window.dispatchEvent(new CustomEvent("mc-navigate", { detail: "journal" }));
                                      }}
                                    />
                                    {u.uptimePct != null && (
                                      <MetricBadge tone={u.uptimePct >= 95 ? "good" : u.uptimePct >= 75 ? "warn" : "bad"}>
                                        {u.uptimePct}%
                                      </MetricBadge>
                                    )}
                                  </span>
                                );
                              })()}
                            </TableCell>
                            <TableCell className="py-2 text-right font-mono text-xs">
                              {s.latencyMs != null ? <MetricBadge tone={s.latencyMs < 500 ? "good" : s.latencyMs < 2000 ? "warn" : "bad"}>{s.latencyMs}ms</MetricBadge> : <span className="text-muted-foreground">—</span>}
                            </TableCell>
                            <TableCell className="py-2 text-right text-xs text-muted-foreground">{ago(s.checkedAt)}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {data?.summary && (
                <div className="mt-4 rounded-lg border bg-muted/30 p-3">
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <Bell className="h-3.5 w-3.5" /> Tower Summary
                  </p>
                  <p className="line-clamp-4 text-xs leading-relaxed text-muted-foreground">{data.summary}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Activity feed */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, delay: 0.06 }} className="min-w-0 lg:col-span-2">
          <Card className="flex h-full flex-col">
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-primary" />
                Activity Stream
                <WatchdogChip />
              </CardTitle>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => refetch()} aria-label="Refresh dashboard">
                <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
              </Button>
            </CardHeader>
            <CardContent className="flex-1 p-0">
              <ScrollArea className="h-[380px] px-4 pb-4">
                {isLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
                  </div>
                ) : (data?.activity.length ?? 0) === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
                    <Hammer className="h-8 w-8 opacity-30" />
                    <p className="text-xs">No activity yet — operations will appear here</p>
                  </div>
                ) : (
                  <ol className="relative space-y-3 border-l border-border/60 pl-4">
                    {data!.activity.map((e) => (
                      <li key={e.id} className="relative">
                        <span className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ${LEVEL_STYLE[e.level]?.split(" ")[0] ?? ""} bg-current`} />
                        <p className={`text-xs font-medium ${LEVEL_STYLE[e.level] ?? ""}`}>{e.title}</p>
                        <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{e.detail}</p>
                        <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/60">{e.type} · {ago(e.createdAt)}</p>
                      </li>
                    ))}
                  </ol>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Dependency map + AI provider pools + Render fleet + philosophy strip */}
      <div className="grid gap-6 lg:grid-cols-2">
        <DependencyMap />
        <AiProviderPools />
        <RenderFleet className="min-w-0 lg:col-span-2" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["Zero Cost", "free-tier everything"],
          ["Fast & Light", "low-latency links"],
          ["Intelligent", "self-deciding"],
          ["Easy", "customer & admin"],
          ["Secure", "not complex"],
          ["Dynamic", "config over code"],
        ].map(([t, d]) => (
          <div key={t} className="rounded-lg border bg-card/60 p-3 text-center shadow-xs transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wider text-primary">{t}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">{d}</p>
          </div>
        ))}
      </div>

      {isError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-500">
          Failed to load dashboard: {String(error)} —{" "}
          <button className="underline" onClick={() => refetch()}>retry</button>
        </div>
      )}
    </div>
  );
}

/* ── AI provider key pools (lazy: tower ai_list_providers) ─────── */
function AiProviderPools() {
  const [open, setOpen] = React.useState(false);
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["ai-pools"],
    queryFn: async (): Promise<{ name: string; keys: number | null; healthy?: boolean }[]> => {
      const r = await callTowerTool("ai_list_providers", {});
      const payload = r.result as unknown;
      let list: Record<string, unknown>[] = [];
      if (Array.isArray(payload)) list = payload as Record<string, unknown>[];
      else if (payload && typeof payload === "object") {
        const rec = payload as Record<string, unknown>;
        for (const k of ["providers", "pools", "items", "data"]) {
          if (Array.isArray(rec[k])) {
            list = rec[k] as Record<string, unknown>[];
            break;
          }
        }
        if (!list.length) {
          // shape: { gemini: {keys: 6}, groq: {...} }
          list = Object.entries(rec)
            .filter(([, v]) => v && typeof v === "object")
            .map(([k, v]) => ({ name: k, ...(v as Record<string, unknown>) }));
        }
      }
      return list.slice(0, 24).map((p) => ({
        name: String(p.name ?? p.provider ?? p.id ?? "provider"),
        keys: typeof p.keys === "number" ? p.keys : typeof p.keyCount === "number" ? p.keyCount : typeof p.count === "number" ? p.count : null,
        healthy: typeof p.healthy === "boolean" ? p.healthy : typeof p.status === "string" ? p.status === "healthy" : undefined,
      }));
    },
    enabled: open,
    refetchInterval: 180_000,
  });

  const rows = data ?? [];
  const totalKeys = rows.reduce((a, r) => a + (r.keys ?? 0), 0);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer select-none pb-3 transition-colors hover:bg-muted/30">
            <CardTitle className="flex items-center gap-2 text-base">
              <Cpu className="h-4 w-4 text-primary" />
              AI Provider Pools
              {rows.length > 0 && <Badge variant="secondary" className="text-[10px]">{rows.length} pools · {totalKeys} keys</Badge>}
              <span className="ml-auto flex items-center gap-1 text-[11px] font-normal text-muted-foreground">
                {open ? "collapse" : "expand from tower"}
                {isFetching && <RefreshCw className="h-3 w-3 animate-spin" />}
              </span>
            </CardTitle>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-1">
            {isLoading ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : rows.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                No AI provider pools reported (tower asleep or none configured) — wake and re-scan.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {rows.map((p, i) => (
                  <motion.div
                    key={p.name}
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.15, delay: Math.min(i * 0.04, 0.3) }}
                    className="rounded-lg border bg-muted/20 p-2.5 transition-colors hover:border-primary/40"
                  >
                    <p className="flex items-center gap-1.5 truncate text-xs font-semibold">
                      <Bot className="h-3.5 w-3.5 text-primary" /> {p.name}
                    </p>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <MetricBadge tone={p.keys == null ? "default" : p.keys > 0 ? "good" : "bad"}>
                        {p.keys == null ? "n/a" : `${p.keys} keys`}
                      </MetricBadge>
                      {p.healthy === false && <MetricBadge tone="bad">unhealthy</MetricBadge>}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
            <div className="mt-3 flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
                <RefreshCw className={`mr-1.5 h-3 w-3 ${isFetching ? "animate-spin" : ""}`} /> Test pools
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

/* ── System dependency map (lazy: fetches from tower on expand) ── */
function DependencyMap() {
  const [open, setOpen] = React.useState(false);
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["deps"],
    queryFn: async (): Promise<Record<string, string[]>> => {
      const r = await callTowerTool("system_dependencies", {});
      const payload = r.result as Record<string, unknown> | string | null;
      if (!payload) return {};
      // normalize: { provider: [deps] } | { provider: {depends_on:[...]} } | text
      if (typeof payload === "string") return {};
      const out: Record<string, string[]> = {};
      const walk = (obj: Record<string, unknown>, prefix = "") => {
        for (const [k, v] of Object.entries(obj)) {
          const name = prefix ? `${prefix}.${k}` : k;
          if (Array.isArray(v)) {
            const deps = v.map(String);
            if (deps.length) out[name] = deps;
          } else if (v && typeof v === "object") {
            const rec = v as Record<string, unknown>;
            const deps = (rec.depends_on ?? rec.dependencies ?? rec.deps) as unknown;
            if (Array.isArray(deps) && deps.length) out[name] = deps.map(String);
            else if (Object.values(rec).some((x) => typeof x === "object")) walk(rec, name);
          }
        }
      };
      walk(payload);
      return out;
    },
    enabled: open,
    refetchInterval: 180_000,
  });

  const entries = Object.entries(data ?? {});

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer select-none pb-3 transition-colors hover:bg-muted/30">
            <CardTitle className="flex items-center gap-2 text-base">
              <Gauge className="h-4 w-4 text-primary" />
              System Dependency Map
              <Badge variant="secondary" className="ml-1 text-[10px]">{entries.length || "…"} nodes</Badge>
              <span className="ml-auto flex items-center gap-1 text-[11px] font-normal text-muted-foreground">
                {open ? "collapse" : "expand from tower"}
                {isFetching && <RefreshCw className="h-3 w-3 animate-spin" />}
              </span>
            </CardTitle>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-1">
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
              </div>
            ) : entries.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                Tower did not return a dependency graph (service may be asleep — wake it and try again).
              </p>
            ) : (
              <ScrollArea className="max-h-72">
                <ul className="space-y-2 pr-3">
                  {entries.map(([node, deps]) => (
                    <li key={node} className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/20 p-2.5 text-xs">
                      <span className="font-mono font-semibold text-foreground/90">{node}</span>
                      <span className="text-muted-foreground">depends on →</span>
                      <span className="flex flex-wrap gap-1.5">
                        {deps.map((d) => (
                          <span key={d} className="rounded-md bg-primary/10 px-1.5 py-0.5 font-mono text-[10.5px] text-primary">
                            {d}
                          </span>
                        ))}
                      </span>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            )}
            <div className="mt-3 flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
                <RefreshCw className={`mr-1.5 h-3 w-3 ${isFetching ? "animate-spin" : ""}`} /> Re-scan graph
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

/* ── Render fleet (lazy: render_list_services + deploy info/trigger) ── */

interface RenderService {
  id: string;
  name: string;
  url: string | null;
  dashboardUrl: string | null;
  region: string | null;
  plan: string | null;
  suspended: boolean;
  branch: string | null;
  updatedAt: string | null;
}

function normalizeServices(payload: unknown): RenderService[] {
  let list: Record<string, unknown>[] = [];
  if (Array.isArray(payload)) list = payload as Record<string, unknown>[];
  else if (payload && typeof payload === "object") {
    const rec = payload as Record<string, unknown>;
    for (const k of ["services", "items", "data", "results"]) {
      if (Array.isArray(rec[k])) { list = rec[k] as Record<string, unknown>[]; break; }
    }
  }
  return list
    .map((row) => {
      const s = (row.service ?? row) as Record<string, unknown>;
      const det = (s.serviceDetails ?? {}) as Record<string, unknown>;
      return {
        id: String(s.id ?? s.serviceId ?? ""),
        name: String(s.name ?? s.slug ?? s.id ?? "service"),
        url: typeof s.url === "string" ? s.url : null,
        dashboardUrl: typeof s.dashboardUrl === "string" ? s.dashboardUrl : null,
        region: typeof det.region === "string" ? det.region : null,
        plan: typeof det.plan === "string" ? det.plan : null,
        suspended: String(s.suspended ?? "not_suspended") === "suspended",
        branch: typeof s.branch === "string" ? s.branch : null,
        updatedAt: typeof s.updatedAt === "string" ? s.updatedAt : null,
      };
    })
    .filter((s) => s.id);
}

function RenderFleet({ className }: { className?: string }) {
  const [open, setOpen] = React.useState(false);
  const [infoFor, setInfoFor] = React.useState<RenderService | null>(null);

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => (await fetch("/api/settings")).json() as Promise<{ renderAccountId: string }>,
    staleTime: 120_000,
  });

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["render-fleet", settings?.renderAccountId],
    queryFn: async (): Promise<RenderService[]> => {
      const r = await callTowerTool("render_list_services", { accountId: settings?.renderAccountId || "render-primary" }, { silent: true });
      return normalizeServices(r.result);
    },
    enabled: open && Boolean(settings),
    refetchInterval: 300_000,
  });

  const services = data ?? [];

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={className}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer select-none pb-3 transition-colors hover:bg-muted/30">
            <CardTitle className="flex items-center gap-2 text-base">
              <Rocket className="h-4 w-4 text-primary" />
              Render Fleet
              {services.length > 0 && <Badge variant="secondary" className="text-[10px]">{services.length} service{services.length === 1 ? "" : "s"}</Badge>}
              {services.some((s) => s.suspended) && <MetricBadge tone="warn">suspended</MetricBadge>}
              <span className="ml-auto flex items-center gap-1 text-[11px] font-normal text-muted-foreground">
                {open ? "collapse" : "expand from tower"}
                {isFetching && <RefreshCw className="h-3 w-3 animate-spin" />}
              </span>
            </CardTitle>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-1">
            {isLoading ? (
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}
              </div>
            ) : services.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                No Render services reported (check the account id in Settings — default render-primary).
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {services.map((s, i) => (
                  <motion.div
                    key={s.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.18, delay: Math.min(i * 0.05, 0.3) }}
                    className="flex flex-col gap-2 rounded-lg border bg-muted/20 p-3 transition-colors hover:border-primary/40"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold" title={s.name}>{s.name}</p>
                        <p className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">{s.id}</p>
                      </div>
                      <span className={`inline-flex shrink-0 items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide ${s.suspended ? "text-amber-500" : "text-emerald-500"}`}>
                        <StatusDot status={s.suspended ? "sleeping" : "healthy"} /> {s.suspended ? "suspended" : "live"}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {s.region && <MetricBadge>{s.region}</MetricBadge>}
                      {s.plan && <MetricBadge tone={s.plan === "free" ? "good" : "default"}>{s.plan}</MetricBadge>}
                      {s.branch && <MetricBadge>ↈ {s.branch}</MetricBadge>}
                    </div>
                    <div className="mt-auto flex flex-wrap items-center gap-1.5 border-t pt-2">
                      <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => setInfoFor(s)}>
                        Latest deploy
                      </Button>
                      <TriggerDeploy serviceId={s.id} serviceName={s.name} />
                      {s.url && (
                        <a href={s.url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-primary" aria-label={`Open ${s.name}`}>
                          <ExternalLink className="h-3 w-3" /> url
                        </a>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
            <div className="mt-3 flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
                <RefreshCw className={`mr-1.5 h-3 w-3 ${isFetching ? "animate-spin" : ""}`} /> Re-scan fleet
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>

      {/* Latest deploy info dialog */}
      <DeployInfoDialog service={infoFor} onClose={() => setInfoFor(null)} />
    </Collapsible>
  );
}

interface DeployInfo {
  id: string | null;
  status: string | null;
  commitMessage: string | null;
  commitId: string | null;
  createdAt: string | null;
  raw: unknown;
}

function DeployInfoDialog({ service, onClose }: { service: RenderService | null; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["deploy-info", service?.id],
    enabled: Boolean(service),
    queryFn: async (): Promise<DeployInfo> => {
      const r = await callTowerTool("render_get_logs", { accountId: "render-primary", serviceId: service!.id }, { silent: true });
      const payload = (r.result ?? {}) as Record<string, unknown>;
      const dep = (payload.latestDeploy ?? payload.deploy ?? {}) as Record<string, unknown>;
      const commit = (dep.commit ?? {}) as Record<string, unknown>;
      return {
        id: typeof dep.id === "string" ? dep.id : null,
        status: typeof dep.status === "string" ? dep.status : null,
        commitMessage: typeof commit.message === "string" ? commit.message.split("\n")[0] : null,
        commitId: typeof commit.id === "string" ? commit.id.slice(0, 7) : null,
        createdAt: typeof dep.createdAt === "string" ? dep.createdAt : typeof dep.finishedAt === "string" ? dep.finishedAt : null,
        raw: r.result,
      };
    },
  });

  return (
    <Dialog open={Boolean(service)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Rocket className="h-4 w-4 text-primary" /> Latest deploy — {service?.name}
          </DialogTitle>
          <DialogDescription>
            Render v1 returns latest deploy info (full log streaming is not exposed by the API).
          </DialogDescription>
        </DialogHeader>
        {isLoading || !data ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : (
          <div className="space-y-2.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              {data.id && <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">{data.id}</code>}
              {data.status && (
                <MetricBadge tone={/fail|error|cancel|deactivate/i.test(data.status) ? "bad" : data.status === "live" ? "good" : "warn"}>
                  {data.status}
                </MetricBadge>
              )}
              {data.createdAt && <span className="text-xs text-muted-foreground">{ago(data.createdAt)}</span>}
            </div>
            {data.commitMessage && (
              <p className="rounded-lg border bg-muted/30 p-2.5 text-xs leading-relaxed">
                <span className="font-mono text-primary">{data.commitId}</span> — {data.commitMessage}
              </p>
            )}
            <JsonViewer data={data.raw} maxHeight={220} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TriggerDeploy({ serviceId, serviceName }: { serviceId: string; serviceName: string }) {
  const qc = useQueryClient();
  const deploy = useMutation({
    mutationFn: async () => callTowerTool("action_render_deploy", { serviceId }),
    onSuccess: (r) => {
      if (r.ok) toast.success(`Deploy queued for ${serviceName} (${r.durationMs}ms)`);
      else toast.error(`Deploy rejected: ${(r.error ?? "policy").slice(0, 90)}`);
      qc.invalidateQueries({ queryKey: ["render-fleet"] });
    },
  });

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px] text-amber-600 hover:text-amber-500" disabled={deploy.isPending}>
          {deploy.isPending ? "Queueing…" : "Trigger deploy"}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Deploy {serviceName}?</AlertDialogTitle>
          <AlertDialogDescription>
            Triggers a fresh deployment of the current branch via the governed policy engine. Risky actions may require HITL approval — you will see a pending request on the Autonomy tab.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction className="bg-amber-600 hover:bg-amber-700" onClick={() => deploy.mutate()}>
            Trigger deploy
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/* ── Watchdog status chip (dynamic settings, silent poll) ────────── */
function WatchdogChip() {
  const { data } = useQuery({
    queryKey: ["settings"],
    queryFn: async (): Promise<SettingsData> => fetch("/api/settings", { cache: "no-store" }).then((r) => r.json()),
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  if (!data) return null;
  const armed = data.watchdogEnabled === true;
  const channel = data.watchdogNotifyChannel;
  return (
    <span
      className={cn(
        "ml-1 inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider",
        armed ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "border-muted bg-muted/40 text-muted-foreground",
      )}
      title={
        armed
          ? `Service watchdog armed — transitions alert via ${channel === "none" ? "activity stream" : channel}${channel !== "none" ? ` (cooldown ${data.watchdogCooldownMin}m)` : ""}`
          : "Service watchdog disarmed — enable in Settings"
      }
    >
      <ShieldCheck className="h-2.5 w-2.5" />
      watchdog {armed ? (channel === "none" ? "on" : channel) : "off"}
    </span>
  );
}
