"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BellOff, History, RefreshCw, ShieldAlert } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MetricBadge, ago } from "./widgets";
import { cn } from "@/lib/utils";

/**
 * Watchdog History — filterable reliability audit of every automated
 * transition event + notify attempt. Reads local journal (tower-independent).
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

interface HistoryResponse {
  ok: boolean;
  total: number;
  total24h: number;
  events: WatchdogEvent[];
  providers: ProviderSummary[];
  error?: string;
}

type KindFilter = "all" | "down" | "degraded" | "recovered" | "notify";

const KIND_TONE: Record<string, { cls: string; label: string }> = {
  down: { cls: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400", label: "DOWN" },
  degraded: { cls: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400", label: "DEGRADED" },
  recovered: { cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400", label: "RECOVERED" },
  notify: { cls: "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400", label: "NOTIFY" },
};

const LEVEL_DOT: Record<string, string> = {
  error: "bg-red-500",
  warn: "bg-amber-500",
  success: "bg-emerald-500",
  info: "bg-muted-foreground",
};

export function WatchdogHistory() {
  const [kind, setKind] = React.useState<KindFilter>("all");
  const [provider, setProvider] = React.useState<string | null>(null);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["watchdog-history", kind, provider],
    queryFn: async (): Promise<HistoryResponse> => {
      const params = new URLSearchParams({ limit: "80" });
      if (kind !== "all") params.set("kind", kind);
      if (provider) params.set("provider", provider);
      const res = await fetch(`/api/watchdog/history?${params.toString()}`, { cache: "no-store" });
      return res.json();
    },
    refetchInterval: 60_000,
  });

  const events = data?.events ?? [];
  const providers = data?.providers ?? [];

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <ShieldAlert className="h-4 w-4 text-primary" />
          Watchdog History
          <MetricBadge tone={data && data.total24h > 0 ? "warn" : "good"}>{data ? `${data.total24h} in 24h` : "…"}</MetricBadge>
          <span className="ml-auto flex gap-1.5">
            {(["all", "down", "degraded", "recovered", "notify"] as KindFilter[]).map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                aria-pressed={kind === k}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize transition-colors",
                  kind === k
                    ? "border-primary bg-primary/10 text-primary"
                    : "text-muted-foreground hover:border-foreground/30 hover:text-foreground",
                )}
              >
                {k}
              </button>
            ))}
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh watchdog history">
              <RefreshCw className={cn("h-3 w-3", isFetching && "animate-spin")} />
            </Button>
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="min-w-0">
        {/* Per-provider reliability summary */}
        {providers.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {providers.map((p) => (
              <button
                key={p.provider}
                onClick={() => setProvider(provider === p.provider ? null : p.provider)}
                aria-pressed={provider === p.provider}
                title={`${p.provider} — ${p.down} down · ${p.degraded} degraded · ${p.recovered} recovered${p.lastAt ? ` · last ${ago(p.lastAt)}` : ""}`}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] transition-colors",
                  provider === p.provider ? "border-primary bg-primary/10 text-primary" : "hover:border-foreground/30",
                )}
              >
                <span className="max-w-[160px] truncate font-medium">{p.provider}</span>
                {p.down > 0 && <span className="font-mono text-red-500">↓{p.down}</span>}
                {p.degraded > 0 && <span className="font-mono text-amber-500">≈{p.degraded}</span>}
                {p.recovered > 0 && <span className="font-mono text-emerald-500">↑{p.recovered}</span>}
                {p.notifies > 0 && <span className="font-mono text-sky-500">✉{p.notifies}</span>}
              </button>
            ))}
            {provider && (
              <Button variant="ghost" size="sm" className="h-6 px-2 text-[10px]" onClick={() => setProvider(null)}>
                clear filter
              </Button>
            )}
          </div>
        )}

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : isError ? (
          <p className="flex items-center gap-2 py-6 text-xs text-muted-foreground">
            <BellOff className="h-4 w-4" /> History unavailable ({String((error as Error)?.message ?? "").slice(0, 60)}).
          </p>
        ) : events.length === 0 ? (
          <p className="flex items-center gap-2 py-6 text-xs text-muted-foreground">
            <History className="h-4 w-4 opacity-50" />
            No watchdog events for this filter — the watchdog journals every service transition here.
          </p>
        ) : (
          <ScrollArea className="h-[300px]">
            <ol className="relative space-y-2.5 border-l border-border/60 pl-4 pr-2">
              {events.map((e, i) => {
                const tone = e.kind ? KIND_TONE[e.kind] : null;
                return (
                  <motion.li
                    key={e.id}
                    initial={{ opacity: 0, x: 6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.18, delay: Math.min(i * 0.03, 0.3) }}
                    className="relative"
                  >
                    <span className={cn("absolute -left-[21px] top-1.5 h-2 w-2 rounded-full", LEVEL_DOT[e.level] ?? "bg-muted-foreground")} />
                    <div className="flex flex-wrap items-center gap-1.5">
                      <p className="min-w-0 flex-1 truncate text-xs font-medium">{e.title}</p>
                      {e.drill && (
                        <Badge variant="outline" className="h-4 shrink-0 border border-violet-500/40 bg-violet-500/10 px-1 text-[9px] text-violet-600 dark:text-violet-400">
                          DRILL
                        </Badge>
                      )}
                      {tone && <Badge variant="outline" className={cn("h-4 shrink-0 border px-1 text-[9px]", tone.cls)}>{tone.label}</Badge>}
                      {e.channel && <Badge variant="outline" className="h-4 shrink-0 px-1 text-[9px] text-muted-foreground">{e.channel}</Badge>}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{e.detail}</p>
                    <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/60">{ago(e.createdAt)}</p>
                  </motion.li>
                );
              })}
            </ol>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
