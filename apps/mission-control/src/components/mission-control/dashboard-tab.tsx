"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Activity, Bell, Gauge, GitPullRequest, Hammer, RadioTower, RefreshCw, ServerCog, Wrench, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { DashboardData } from "@/lib/mission-types";
import { KpiCard, SectionHeader, StatusDot, MetricBadge, ago } from "./widgets";

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
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    refetchInterval: 45_000,
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

  const tower = data?.tower;
  const services = data?.services ?? [];
  const healthy = services.filter((s) => s.status === "healthy").length;
  const degraded = services.filter((s) => s.status === "degraded" || s.status === "unknown").length;
  const down = services.filter((s) => s.status === "down").length;

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

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Service matrix */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="lg:col-span-3">
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
                <div className="overflow-hidden rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40">
                        <TableHead className="h-9">Service</TableHead>
                        <TableHead className="h-9">Status</TableHead>
                        <TableHead className="h-9 text-right">Latency</TableHead>
                        <TableHead className="h-9 text-right">Checked</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {services.map((s) => (
                        <TableRow key={s.provider} className="text-sm">
                          <TableCell className="max-w-[220px] truncate py-2 font-medium">{s.provider}</TableCell>
                          <TableCell className="py-2">
                            <span className="inline-flex items-center gap-2 capitalize">
                              <StatusDot status={s.status} />
                              {s.status}
                            </span>
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs">
                            {s.latencyMs != null ? <MetricBadge tone={s.latencyMs < 500 ? "good" : s.latencyMs < 2000 ? "warn" : "bad"}>{s.latencyMs}ms</MetricBadge> : "—"}
                          </TableCell>
                          <TableCell className="py-2 text-right text-xs text-muted-foreground">{ago(s.checkedAt)}</TableCell>
                        </TableRow>
                      ))}
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
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, delay: 0.06 }} className="lg:col-span-2">
          <Card className="flex h-full flex-col">
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-primary" />
                Activity Stream
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

      {/* Philosophy strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["Zero Cost", "free-tier everything"],
          ["Fast & Light", "low-latency links"],
          ["Intelligent", "self-deciding"],
          ["Easy", "customer & admin"],
          ["Secure", "not complex"],
          ["Dynamic", "config over code"],
        ].map(([t, d]) => (
          <div key={t} className="rounded-lg border bg-card/60 p-3 text-center">
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
