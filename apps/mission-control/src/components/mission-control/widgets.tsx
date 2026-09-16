"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Bot, Brain, Cloud, Database, Flame, GitBranch, Globe, KeyRound, Megaphone,
  Radio, Rocket, Server, ShieldCheck, Sparkles, Zap,
  type LucideIcon,
} from "lucide-react";

/* ── Service icon by provider name heuristic ────────────────────── */
export function serviceIcon(provider: string): { Icon: LucideIcon; cls: string } {
  const p = provider.toLowerCase();
  if (p.includes("render")) return { Icon: Server, cls: "text-emerald-500" };
  if (p.includes("github")) return { Icon: GitBranch, cls: "text-foreground/70" };
  if (p.includes("supabase")) return { Icon: Database, cls: "text-teal-500" };
  if (p.includes("redis")) return { Icon: Zap, cls: "text-red-500" };
  if (p.includes("cloudflare")) return { Icon: Cloud, cls: "text-orange-500" };
  if (p.includes("infisical")) return { Icon: KeyRound, cls: "text-violet-500" };
  if (p.includes("firebase")) return { Icon: Flame, cls: "text-amber-500" };
  if (p.includes("gemini") || p.includes("groq") || p.includes("openrouter") || p.includes("mistral") || p.includes("kaggle"))
    return { Icon: Brain, cls: "text-primary" };
  if (p.includes("telegram")) return { Icon: Radio, cls: "text-sky-500" };
  if (p.includes("discord")) return { Icon: Megaphone, cls: "text-indigo-400" };
  if (p.includes("worker") || p.includes("scrape")) return { Icon: Rocket, cls: "text-emerald-500" };
  if (p.includes("mcp") || p.includes("tower")) return { Icon: RadioTower, cls: "text-primary" };
  if (p.includes("auth") || p.includes("policy")) return { Icon: ShieldCheck, cls: "text-emerald-500" };
  if (p.includes("ai") || p.includes("agent")) return { Icon: Bot, cls: "text-primary" };
  if (p.includes("web") || p.includes("edge")) return { Icon: Globe, cls: "text-emerald-500" };
  return { Icon: Sparkles, cls: "text-muted-foreground" };
}

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
            {sub && !loading && <p className="mt-1 line-clamp-2 text-xs leading-snug text-muted-foreground">{sub}</p>}
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

/* ── Uptime sparkline strip (local reliability memory) ───────────── */
export interface UptimeBucketInfo {
  /** Window start, minutes back from now. */
  sinceMin: number;
  /** Window end, minutes back from now. */
  untilMin: number;
  /** Bucket width in minutes. */
  windowMin: number;
  status: "down" | "degraded" | "healthy" | "no data";
  /** UTC label like "14:20–14:40". */
  rangeLabel: string;
}

export function UptimeStrip({
  points,
  className,
  windowMinutes = 360,
  onBucketClick,
}: {
  points: (0 | 1 | 2 | null)[];
  className?: string;
  /** Size of the whole window in minutes (default 6h) — used for per-bucket tooltips. */
  windowMinutes?: number;
  /** When provided, each bucket becomes a button that deep-links (e.g. journal filtered to that bucket). */
  onBucketClick?: (info: UptimeBucketInfo) => void;
}) {
  const now = Date.now();
  const bucketMin = windowMinutes / Math.max(1, points.length);
  const statusWord = (p: 0 | 1 | 2 | null) =>
    p === 2 ? "healthy" : p === 1 ? "degraded" : p === 0 ? "down" : "no data";
  const healthy = points.filter((p) => p === 2).length;
  const known = points.filter((p) => p !== null).length;
  const uptimePct = known > 0 ? Math.round((healthy / known) * 100) : null;
  const label = `uptime trend: ${uptimePct == null ? "no data" : `${uptimePct}% healthy`} over last ${windowMinutes >= 60 ? `${Math.round(windowMinutes / 60)}h` : `${windowMinutes}m`}${onBucketClick ? " — click a bar to inspect the journal for that interval" : ""}`;

  return (
    <span className={cn("inline-flex items-end gap-px", className)} role="img" aria-label={label} title={label}>
      {points.map((p, i) => {
        const start = new Date(now - (points.length - i) * bucketMin * 60_000);
        const end = new Date(now - (points.length - 1 - i) * bucketMin * 60_000);
        const range = `${start.toUTCString().slice(17, 22)}–${end.toUTCString().slice(17, 22)} UTC`;
        const info: UptimeBucketInfo = {
          sinceMin: Math.round((points.length - i) * bucketMin),
          untilMin: Math.round((points.length - 1 - i) * bucketMin),
          windowMin: Math.round(bucketMin),
          status: p === 2 ? "healthy" : p === 1 ? "degraded" : p === 0 ? "down" : "no data",
          rangeLabel: `${start.toUTCString().slice(17, 22)}–${end.toUTCString().slice(17, 22)}`,
        };
        const barCls = cn(
          "w-1 rounded-[2px] transition-transform",
          p === 2 && "h-2.5 bg-emerald-500/80",
          p === 1 && "h-2 bg-amber-500/90",
          p === 0 && "h-2.5 bg-red-500/90",
          p === null && "h-1 bg-muted-foreground/20",
        );
        if (!onBucketClick) {
          return <span key={i} className={cn(barCls, "hover:scale-y-125")} title={`${range} · ${statusWord(p)}`} />;
        }
        return (
          <button
            key={i}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onBucketClick(info);
            }}
            className={cn(barCls, "cursor-pointer hover:scale-y-150 focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-primary")}
            title={`${range} · ${statusWord(p)} · click to inspect journal`}
            aria-label={`Inspect journal ${range} · ${statusWord(p)}`}
          />
        );
      })}
    </span>
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
