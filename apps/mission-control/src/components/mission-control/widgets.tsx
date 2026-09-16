"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/* ── Status dot with ping ───────────────────────────────────────── */
export function StatusDot({ status, className }: { status: string; className?: string }) {
  const color =
    {
      healthy: "bg-emerald-500 text-emerald-500",
      live: "bg-emerald-500 text-emerald-500",
      success: "bg-emerald-500 text-emerald-500",
      degraded: "bg-amber-500 text-amber-500",
      sleeping: "bg-amber-500 text-amber-500",
      warn: "bg-amber-500 text-amber-500",
      down: "bg-red-500 text-red-500",
      error: "bg-red-500 text-red-500",
      unreachable: "bg-red-500 text-red-500",
    }[status] ?? "bg-zinc-400 text-zinc-400";

  const animate = ["healthy", "live", "degraded", "sleeping"].includes(status);

  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5 shrink-0", color, className)} aria-label={`status: ${status}`}>
      {animate && <span className="mc-ping" aria-hidden />}
    </span>
  );
}

/* ── Latency / value badge ──────────────────────────────────────── */
export function MetricBadge({ children, tone = "default", className }: { children: React.ReactNode; tone?: "default" | "good" | "warn" | "bad"; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] leading-none",
        tone === "default" && "bg-muted text-muted-foreground",
        tone === "good" && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
        tone === "warn" && "bg-amber-500/10 text-amber-600 dark:text-amber-400",
        tone === "bad" && "bg-red-500/10 text-red-600 dark:text-red-400",
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ── KPI card ───────────────────────────────────────────────────── */
export function KpiCard({
  label,
  value,
  sub,
  icon,
  tone = "default",
  loading,
  onClick,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "default" | "good" | "warn" | "bad";
  loading?: boolean;
  onClick?: () => void;
}) {
  return (
    <Card
      className={cn(
        "group relative overflow-hidden transition-all",
        onClick && "cursor-pointer hover:border-primary/40 hover:shadow-[0_0_24px_-6px] hover:shadow-primary/20",
      )}
      onClick={onClick}
    >
      <div className={cn("absolute inset-x-0 top-0 h-px", tone === "good" && "bg-gradient-to-r from-transparent via-emerald-500/60 to-transparent", tone === "warn" && "bg-gradient-to-r from-transparent via-amber-500/60 to-transparent", tone === "bad" && "bg-gradient-to-r from-transparent via-red-500/60 to-transparent", tone === "default" && "bg-gradient-to-r from-transparent via-primary/40 to-transparent")} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
            {loading ? (
              <Skeleton className="mt-2 h-7 w-20" />
            ) : (
              <p className="mt-1 truncate font-mono text-2xl font-semibold tabular-nums">{value}</p>
            )}
            {sub && !loading && <p className="mt-1 truncate text-xs text-muted-foreground">{sub}</p>}
          </div>
          {icon && (
            <div className={cn(
              "rounded-lg p-2 transition-colors",
              tone === "good" && "bg-emerald-500/10 text-emerald-500",
              tone === "warn" && "bg-amber-500/10 text-amber-500",
              tone === "bad" && "bg-red-500/10 text-red-500",
              tone === "default" && "bg-primary/10 text-primary",
            )}>
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ── Section header ─────────────────────────────────────────────── */
export function SectionHeader({ title, desc, right }: { title: string; desc?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
        {desc && <p className="mt-0.5 text-xs text-muted-foreground/70">{desc}</p>}
      </div>
      {right}
    </div>
  );
}

/* ── JSON viewer (copyable) ─────────────────────────────────────── */
export function JsonViewer({ data, maxHeight = 320, className }: { data: unknown; maxHeight?: number; className?: string }) {
  const text = React.useMemo(() => {
    try {
      return typeof data === "string" ? data : JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  }, [data]);

  const copy = React.useCallback(() => {
    navigator.clipboard.writeText(text).catch(() => {});
  }, [text]);

  return (
    <div className={cn("group relative overflow-hidden rounded-lg border bg-zinc-950/95", className)}>
      <button
        onClick={copy}
        className="absolute right-2 top-2 z-10 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-[11px] text-zinc-300 opacity-0 backdrop-blur transition-opacity hover:bg-black/60 group-hover:opacity-100"
        aria-label="Copy JSON"
      >
        Copy
      </button>
      <pre className="overflow-auto p-3 font-mono text-[11.5px] leading-relaxed text-emerald-300/90" style={{ maxHeight }}>
        {text}
      </pre>
    </div>
  );
}

/* ── Tooltipped icon button wrapper ─────────────────────────────── */
export function Tip({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side="top" className="text-xs">{label}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/* ── Relative time (compact) ────────────────────────────────────── */
export function ago(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.max(0, Math.floor(diff / 1000));
  if (s < 10) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
