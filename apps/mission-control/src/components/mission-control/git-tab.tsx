"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, CircleDashed, ExternalLink, GitBranch, GitCommitHorizontal, GitMerge, GitPullRequest, Loader2, RefreshCw, ShieldCheck, Terminal, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { GitStatusData, GitSyncResult, PullRequestInfo } from "@/lib/mission-types";
import { MetricBadge, SectionHeader, StatusDot, ago } from "./widgets";

interface SyncResponse {
  ok: boolean;
  autoSync: boolean;
  mainHead: { branch: string; sha: string };
  results: GitSyncResult[];
  prs: PullRequestInfo[];
  ranAt: string;
  error?: string;
}

interface SyncLogRow {
  id: string;
  prNumber: number;
  branch: string;
  baseSha: string;
  headSha: string;
  conflict: string;
  behindBy: number;
  aheadBy: number;
  action: string;
  detail: string | null;
  createdAt: string;
}

interface CiRun {
  id: number;
  name: string;
  event: string;
  status: string;
  conclusion: string | null;
  branch: string;
  sha: string;
  url: string;
  createdAt: string;
}

export function GitTab() {
  const qc = useQueryClient();

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["git-status"],
    queryFn: async (): Promise<GitStatusData> => {
      const res = await fetch("/api/git/status", { cache: "no-store" });
      if (!res.ok) throw new Error(`git status ${res.status}`);
      return res.json();
    },
    refetchInterval: 90_000,
  });

  const { data: logData } = useQuery({
    queryKey: ["git-log"],
    queryFn: async (): Promise<SyncLogRow[]> => {
      const res = await fetch("/api/git/sync-log", { cache: "no-store" });
      const j = await res.json();
      return j.rows ?? [];
    },
    refetchInterval: 60_000,
  });

  const { data: ciData, isLoading: ciLoading } = useQuery({
    queryKey: ["git-ci"],
    queryFn: async (): Promise<{ runs: CiRun[] }> => {
      const res = await fetch("/api/git/ci?limit=8", { cache: "no-store" });
      if (!res.ok) throw new Error("ci");
      return res.json();
    },
    refetchInterval: 120_000,
    retry: 1,
  });

  const syncMutation = useMutation({
    mutationFn: async (): Promise<SyncResponse> => {
      const res = await fetch("/api/git/sync", { method: "POST" });
      return res.json();
    },
    onSuccess: (r) => {
      if (!r.ok) {
        toast.error(`Sync sweep failed: ${r.error ?? "unknown"}`);
        return;
      }
      const conflicts = r.results.filter((x) => x.conflict === "conflict");
      const synced = r.results.filter((x) => x.action === "synced_main");
      const clean = r.results.filter((x) => x.conflict === "clean" || x.action === "checked");
      if (conflicts.length) toast.warning(`${conflicts.length} PR(s) in CONFLICT — manual resolution needed`);
      else if (synced.length) toast.success(`${synced.length} PR(s) synced with main — conflict-free ✓`);
      else toast.info(`${clean.length} PR(s) checked — all clean, main unchanged`);
      qc.invalidateQueries({ queryKey: ["git-status"] });
      qc.invalidateQueries({ queryKey: ["git-log"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(String(e)),
  });

  const prs = data?.prs ?? [];
  const conflicts = prs.filter((p) => p.mergeable === "conflicting");
  const stale = prs.filter((p) => p.behindBy > 0 && p.mergeable !== "conflicting");

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Git Sync Center"
        desc="Standing directive: PR ↔ main must stay conflict-free — every sweep is logged"
        right={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
              Check
            </Button>
            <Button size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              <GitMerge className="mr-1.5 h-3.5 w-3.5" />
              {syncMutation.isPending ? "Sweeping…" : "Run Sync Sweep"}
            </Button>
          </div>
        }
      />

      {/* Main head + watch banner */}
      <Card className="overflow-hidden">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <GitBranch className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">
                {data?.defaultBranch ?? "main"} <span className="font-mono text-xs text-muted-foreground">· {data?.mainHeadSha?.slice(0, 7) ?? "…"} </span>
              </p>
              <p className="text-xs text-muted-foreground">
                repo SaifulHaqueNiloy/supremeai · branch <span className="font-mono">{data?.branch ?? "feat/mission-control-console"}</span>
                {data?.checkedAt ? ` · checked ${ago(data.checkedAt)}` : ""}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {conflicts.length === 0 && stale.length === 0 && (
              <Badge variant="default" className="gap-1.5 bg-emerald-600/90 hover:bg-emerald-600/90">
                <ShieldCheck className="h-3.5 w-3.5" /> No conflicts
              </Badge>
            )}
            {conflicts.length > 0 && (
              <Badge variant="destructive" className="gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5" /> {conflicts.length} conflict(s)
              </Badge>
            )}
            {stale.length > 0 && (
              <Badge variant="secondary" className="gap-1.5">
                <GitCommitHorizontal className="h-3.5 w-3.5" /> {stale.length} behind main
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        {/* PR cards */}
        <div className="space-y-3 lg:col-span-3">
          <CiPanel runs={ciData?.runs ?? []} loading={ciLoading} />

          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)
          ) : isError ? (
            <Card className="border-red-500/30 bg-red-500/5">
              <CardContent className="py-8 text-center text-sm text-red-500">
                GitHub API unreachable (token may be missing/expired) — check Settings.
              </CardContent>
            </Card>
          ) : prs.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
                <GitPullRequest className="h-10 w-10 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No open PRs. The Mission Control branch PR will appear here once opened.</p>
              </CardContent>
            </Card>
          ) : (
            prs.map((pr, i) => <PrCard key={pr.number} pr={pr} index={i} />)
          )}
        </div>

        {/* Sync log */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-4 w-4 text-primary" />
              Sync Ledger
            </CardTitle>
            <p className="text-xs text-muted-foreground">every conflict check & merge — durable proof</p>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[420px] px-4 pb-4">
              {(logData?.length ?? 0) === 0 ? (
                <p className="py-10 text-center text-xs text-muted-foreground">No sweeps yet — run the first sync sweep.</p>
              ) : (
                <ol className="relative space-y-3 border-l border-border/60 pl-4">
                  {logData!.map((r) => (
                    <li key={r.id} className="relative">
                      <span className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-current ${r.conflict === "conflict" ? "text-red-500" : r.action === "synced_main" ? "text-emerald-500" : "text-muted-foreground"}`} />
                      <p className="text-xs font-medium">
                        PR #{r.prNumber} · <span className="font-mono text-[11px]">{r.branch}</span>
                      </p>
                      <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{r.detail}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <MetricBadge tone={r.action === "synced_main" ? "good" : r.conflict === "conflict" ? "bad" : "default"}>{r.action}</MetricBadge>
                        <MetricBadge tone={r.behindBy > 0 ? "warn" : "good"}>behind {r.behindBy}</MetricBadge>
                        <span className="text-[10px] text-muted-foreground/60">{ago(r.createdAt)}</span>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PrCard({ pr, index }: { pr: PullRequestInfo; index: number }) {
  const state =
    pr.mergeable === "conflicting"
      ? { label: "CONFLICT", tone: "destructive" as const, icon: <AlertTriangle className="h-3.5 w-3.5" /> }
      : pr.behindBy > 0
        ? { label: `behind ${pr.behindBy}`, tone: "secondary" as const, icon: <GitCommitHorizontal className="h-3.5 w-3.5" /> }
        : { label: "conflict-free", tone: "default" as const, icon: <CheckCircle2 className="h-3.5 w-3.5" /> };

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, delay: index * 0.05 }}>
      <Card className="transition-all hover:border-primary/40">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <a href={pr.url} target="_blank" rel="noreferrer" className="truncate text-sm font-semibold hover:text-primary hover:underline">
                #{pr.number} · {pr.title}
              </a>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5">{pr.branch}</span>
                <span>→ {pr.base}</span>
              </p>
            </div>
            <Badge variant={state.tone} className="shrink-0 gap-1.5">
              {state.icon}
              {state.label}
            </Badge>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <MetricBadge tone={pr.ciStatus === "success" ? "good" : pr.ciStatus === "failure" ? "bad" : "default"}>CI: {pr.ciStatus ?? "n/a"}</MetricBadge>
            <MetricBadge tone={pr.behindBy > 0 ? "warn" : "good"}>behind {pr.behindBy}</MetricBadge>
            <MetricBadge>ahead {pr.aheadBy}</MetricBadge>
            <MetricBadge>{pr.draft ? "draft" : pr.state}</MetricBadge>
            <span className="ml-auto text-[10px] text-muted-foreground/60">updated {ago(pr.updatedAt)}</span>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

/* ── CI Pipeline panel (workflow runs via GitHub API) ───────────── */
function CiPanel({ runs, loading }: { runs: CiRun[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-44 w-full" />;
  if (runs.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 p-4 text-xs text-muted-foreground">
          <Terminal className="h-4 w-4 shrink-0 opacity-50" />
          No workflow runs visible (token scope or none triggered yet).
        </CardContent>
      </Card>
    );
  }

  const iconFor = (r: CiRun) => {
    if (r.status !== "completed") return <Loader2 className="h-4 w-4 animate-spin text-amber-500" />;
    if (r.conclusion === "success") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    if (r.conclusion === "failure" || r.conclusion === "timed_out") return <XCircle className="h-4 w-4 text-red-500" />;
    return <CircleDashed className="h-4 w-4 text-muted-foreground" />;
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Terminal className="h-4 w-4 text-primary" />
          CI Pipeline
          <Badge variant="secondary" className="text-[10px]">{runs.length} runs</Badge>
        </CardTitle>
        <a href={runs[0]?.url ?? "#"} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-primary">
          Actions <ExternalLink className="h-3 w-3" />
        </a>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border/60">
          {runs.slice(0, 6).map((r) => (
            <li key={r.id}>
              <a href={r.url} target="_blank" rel="noreferrer" className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-primary/5">
                {iconFor(r)}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-medium">{r.name}</span>
                  <span className="block truncate font-mono text-[10px] text-muted-foreground">
                    {r.branch} · {r.sha} · {r.event}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className={`block text-[10px] font-semibold uppercase tracking-wide ${r.conclusion === "success" ? "text-emerald-500" : r.conclusion === "failure" ? "text-red-500" : "text-amber-500"}`}>
                    {r.status === "completed" ? r.conclusion : r.status}
                  </span>
                  <span className="block text-[10px] text-muted-foreground/60">{ago(r.createdAt)}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
