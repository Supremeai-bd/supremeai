"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Activity, CheckCircle2, Clock, Download, Gauge, ScrollText, Search, Timer, TrendingUp, X, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { KpiCard, SectionHeader, MetricBadge, JsonViewer, ago } from "./widgets";
import { ApprovalsPanel } from "./approvals-panel";
import { consumeJournalIntent } from "@/lib/journal-intent";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface TopTool {
  tool: string;
  calls: number;
  failures: number;
  avgMs: number;
  p95Ms: number | null;
}

interface JournalStats {
  total24h: number;
  ok24h: number;
  failed24h: number;
  successRate: number;
  avgDurationMs: number;
  p95DurationMs: number | null;
  topTools: TopTool[];
}

interface JournalEntry {
  id: string;
  tool: string;
  ok: boolean;
  durationMs: number;
  snippet: string | null;
  createdAt: string;
}

interface JournalResponse {
  ok: boolean;
  stats: JournalStats | null;
  entries: JournalEntry[];
  error?: string;
}

type StatusFilter = "all" | "ok" | "failed";

/** Quick time-window presets (minutes back from now). */
const TIME_PRESETS: { label: string; sinceMin: number | null }[] = [
  { label: "All", sinceMin: null },
  { label: "1h", sinceMin: 60 },
  { label: "6h", sinceMin: 360 },
  { label: "24h", sinceMin: 1440 },
];

export function JournalTab() {
  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("all");
  const [detail, setDetail] = React.useState<JournalEntry | null>(null);
  // Time window: null sinceMin = all; untilMin only set for single-bucket deep links.
  const [sinceMin, setSinceMin] = React.useState<number | null>(null);
  const [untilMin, setUntilMin] = React.useState<number | null>(null);
  const [windowLabel, setWindowLabel] = React.useState<string | null>(null);

  // Deep-link intent from the dashboard (uptime-bucket click) — consumed once on mount.
  React.useEffect(() => {
    const intent = consumeJournalIntent();
    if (intent) {
      setSinceMin(intent.sinceMin);
      setUntilMin(intent.untilMin ?? null);
      setWindowLabel(intent.label ?? `${intent.sinceMin}m window`);
      toast.info(`Journal filtered to ${intent.label ?? `${intent.sinceMin}m window`}`);
    }
  }, []);

  // Debounced search keeps the journal query cheap
  const [debounced, setDebounced] = React.useState("");
  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["journal", debounced, statusFilter, sinceMin, untilMin],
    queryFn: async (): Promise<JournalResponse> => {
      const params = new URLSearchParams();
      if (debounced) params.set("q", debounced);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (sinceMin != null) params.set("sinceMin", String(sinceMin));
      if (untilMin != null) params.set("untilMin", String(untilMin));
      params.set("limit", "80");
      const res = await fetch(`/api/journal?${params.toString()}`, { cache: "no-store" });
      return res.json();
    },
    refetchInterval: 45_000,
  });

  const stats = data?.stats;
  const entries = data?.entries ?? [];

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Operations Journal"
        desc="Every governed tool call, journaled locally — telemetry that works even while the tower sleeps"
        right={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const params = new URLSearchParams({ format: "csv", csvLimit: "1000" });
                if (debounced) params.set("q", debounced);
                if (statusFilter !== "all") params.set("status", statusFilter);
                if (sinceMin != null) params.set("sinceMin", String(sinceMin));
                if (untilMin != null) params.set("untilMin", String(untilMin));
                window.location.assign(`/api/journal?${params.toString()}`);
                toast.success("Journal export started (CSV, max 1000 rows)");
              }}
              aria-label="Export journal as CSV"
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh journal">
              <ScrollText className={cn("mr-1.5 h-3.5 w-3.5", isFetching && "animate-spin")} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* HITL approvals — tower policy engine (collapses when clear) */}
      <ApprovalsPanel />

      {/* KPI rail */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          label="Calls · 24h"
          value={stats ? stats.total24h : "—"}
          sub="governed tool invocations"
          icon={<Activity className="h-5 w-5" />}
          loading={!stats}
        />
        <KpiCard
          label="Success rate"
          value={stats ? `${stats.successRate}%` : "—"}
          sub={stats ? `${stats.failed24h} failed` : undefined}
          icon={<CheckCircle2 className="h-5 w-5" />}
          tone={stats ? (stats.successRate >= 95 ? "good" : stats.successRate >= 80 ? "warn" : "bad") : "default"}
          loading={!stats}
        />
        <KpiCard
          label="Avg latency"
          value={stats && stats.avgDurationMs > 0 ? `${stats.avgDurationMs}ms` : "—"}
          sub="mean across tools, 24h"
          icon={<Timer className="h-5 w-5" />}
          loading={!stats}
        />
        <KpiCard
          label="P95 · 24h"
          value={stats?.p95DurationMs != null ? `${stats.p95DurationMs}ms` : "—"}
          sub={stats && stats.p95DurationMs != null && stats.p95DurationMs > 800 ? "slow tail — inspect top tool" : "95th percentile latency"}
          icon={<Gauge className="h-5 w-5" />}
          tone={stats?.p95DurationMs != null && stats.p95DurationMs > 800 ? "warn" : "default"}
          loading={!stats}
        />
        <KpiCard
          label="Top tool"
          value={<span className="text-base">{stats?.topTools[0]?.tool ?? "—"}</span>}
          sub={stats?.topTools[0] ? `${stats.topTools[0].calls} calls · avg ${stats.topTools[0].avgMs}ms` : "no calls yet"}
          icon={<TrendingUp className="h-5 w-5" />}
          loading={!stats}
        />
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-3">
        {/* Entries table */}
        <Card className="min-w-0 lg:col-span-2">
          <CardContent className="p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2 sm:flex-nowrap">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter by tool name — system_summary, memory_…"
                  className="pl-9"
                  aria-label="Filter journal by tool"
                />
              </div>
              <div className="flex gap-1.5" role="group" aria-label="Filter journal by status">
                {(["all", "ok", "failed"] as StatusFilter[]).map((key) => (
                  <button
                    key={key}
                    onClick={() => setStatusFilter(key)}
                    aria-pressed={statusFilter === key}
                    className={cn(
                      "rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize transition-colors",
                      statusFilter === key
                        ? "border-primary bg-primary/10 text-primary"
                        : "text-muted-foreground hover:border-foreground/30 hover:text-foreground",
                    )}
                  >
                    {key}
                    <span className="ml-1 opacity-60">
                      {key === "all" ? entries.length : key === "ok" ? entries.filter((e) => e.ok).length : entries.filter((e) => !e.ok).length}
                    </span>
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter journal by time window">
                {TIME_PRESETS.map((p) => {
                  const active = sinceMin === p.sinceMin && untilMin == null;
                  return (
                    <button
                      key={p.label}
                      onClick={() => {
                        setSinceMin(p.sinceMin);
                        setUntilMin(null);
                        setWindowLabel(null);
                      }}
                      aria-pressed={active}
                      className={cn(
                        "rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors",
                        active
                          ? "border-primary bg-primary/10 text-primary"
                          : "text-muted-foreground hover:border-foreground/30 hover:text-foreground",
                      )}
                    >
                      {p.label}
                    </button>
                  );
                })}
                {sinceMin != null && untilMin != null && (
                  <button
                    onClick={() => {
                      setSinceMin(null);
                      setUntilMin(null);
                      setWindowLabel(null);
                    }}
                    className="inline-flex items-center gap-1 rounded-full border border-violet-500/50 bg-violet-500/10 px-2.5 py-0.5 text-[11px] font-medium text-violet-600 dark:text-violet-400"
                    aria-label="Clear custom time window"
                    title="Custom window from an uptime bucket — click to clear"
                  >
                    <Clock className="h-3 w-3" />
                    {windowLabel ?? "custom"}
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>

            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
              </div>
            ) : isError || !data?.ok ? (
              <div className="flex flex-col items-center gap-2 py-10 text-center">
                <XCircle className="h-8 w-8 text-red-500/60" />
                <p className="text-sm text-muted-foreground">Journal unavailable ({data?.error ?? "database error"}).</p>
              </div>
            ) : entries.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 text-center">
                <ScrollText className="h-8 w-8 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">
                  No journaled calls match this filter. Tool invocations from the Tower Explorer and background sweeps appear here.
                </p>
              </div>
            ) : (
              <div className="max-h-[460px] min-w-0 overflow-auto rounded-lg border">
                <Table>
                  <TableHeader className="sticky top-0 z-10 bg-background/95 backdrop-blur">
                    <TableRow className="bg-muted/40">
                      <TableHead className="h-9">Tool</TableHead>
                      <TableHead className="h-9">Result</TableHead>
                      <TableHead className="h-9 text-right">Duration</TableHead>
                      <TableHead className="h-9 text-right">When</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((e, i) => (
                      <TableRow
                        key={e.id}
                        className="cursor-pointer text-sm transition-colors odd:bg-muted/10 hover:bg-primary/5"
                        onClick={() => setDetail(e)}
                        aria-label={`Inspect ${e.tool} call`}
                      >
                        <TableCell className="max-w-[220px] py-2">
                          <span className="truncate font-mono text-xs font-medium text-primary/90">{e.tool}</span>
                        </TableCell>
                        <TableCell className="py-2">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            {e.ok ? (
                              <><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> ok</>
                            ) : (
                              <><XCircle className="h-3.5 w-3.5 text-red-500" /> failed</>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="py-2 text-right font-mono text-xs tabular-nums">
                          {e.durationMs}ms
                        </TableCell>
                        <TableCell className="py-2 text-right text-xs text-muted-foreground">{ago(e.createdAt)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top tools mini chart */}
        <Card className="h-fit min-w-0">
          <CardContent className="p-4">
            <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Gauge className="h-4 w-4 text-primary" />
              Most used · 24h
            </p>
            {!stats ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
              </div>
            ) : stats.topTools.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">No calls in the last 24h window.</p>
            ) : (
              <ul className="space-y-2.5">
                {stats.topTools.map((t, i) => {
                  const max = stats.topTools[0].calls || 1;
                  return (
                    <motion.li
                      key={t.tool}
                      initial={{ opacity: 0, x: 8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2, delay: i * 0.05 }}
                    >
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                        <button
                          onClick={() => {
                            setSearch(t.tool);
                            toast.info(`Filtering journal by ${t.tool}`);
                          }}
                          className="truncate font-mono text-primary/90 hover:text-primary hover:underline focus-visible:outline focus-visible:outline-1 focus-visible:outline-primary"
                          aria-label={`Filter journal by ${t.tool}`}
                          title="Click to filter the journal by this tool"
                        >
                          {t.tool}
                        </button>
                        <span className="shrink-0 font-mono tabular-nums text-muted-foreground">
                          {t.calls}
                          {t.failures > 0 && <span className="ml-1 text-red-500">·{t.failures}✕</span>}
                          {t.p95Ms != null && <span className="ml-1 opacity-80" title="95th percentile latency">p95 {t.p95Ms}ms</span>}
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(6, (t.calls / max) * 100)}%` }}
                          transition={{ duration: 0.5, delay: i * 0.05, ease: "easeOut" }}
                          className={cn("h-full rounded-full", t.failures > 0 ? "bg-gradient-to-r from-primary to-amber-500" : "bg-gradient-to-r from-primary to-emerald-500")}
                        />
                      </div>
                    </motion.li>
                  );
                })}
              </ul>
            )}
            {stats && stats.failed24h > 0 && (
              <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-2.5 py-1.5 text-[11px] text-amber-600 dark:text-amber-400">
                {stats.failed24h} failed call{stats.failed24h === 1 ? "" : "s"} in 24h — filter the journal to inspect.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Entry detail dialog */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-h-[80vh] max-w-xl overflow-hidden sm:rounded-xl">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex flex-wrap items-center gap-2 font-mono text-base">
                  <ScrollText className="h-4 w-4 text-primary" />
                  {detail.tool}
                  <MetricBadge tone={detail.ok ? "good" : "bad"}>{detail.ok ? "ok" : "failed"}</MetricBadge>
                  <MetricBadge>{detail.durationMs}ms</MetricBadge>
                </DialogTitle>
                <DialogDescription>
                  Journaled {ago(detail.createdAt)} · {new Date(detail.createdAt).toUTCString()}
                </DialogDescription>
              </DialogHeader>
              <div className="max-h-[50vh] overflow-y-auto pr-1">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Response snippet</p>
                {detail.snippet ? (
                  <JsonViewer data={(() => { try { return JSON.parse(detail.snippet!); } catch { return detail.snippet; } })()} maxHeight={280} />
                ) : (
                  <p className="text-sm text-muted-foreground">No snippet captured for this call (silent/background calls skip journaling detail).</p>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
