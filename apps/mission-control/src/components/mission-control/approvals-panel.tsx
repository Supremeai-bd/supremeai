"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, ClipboardCheck, Clock, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { callTowerTool } from "@/lib/tower-gateway";
import { MetricBadge, ago } from "./widgets";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/**
 * HITL Approvals — pending policy requests from the tower's policy engine.
 * Polls silently (no journal spam); approve/reject decisions ARE journaled
 * (silent:false) so every HITL decision is auditable in the Operations Journal.
 */

interface PendingRequest {
  id: string;
  summary: string;
  tool: string | null;
  requestedAt: string | null;
  raw: Record<string, unknown>;
}

function normalizePending(payload: unknown): { items: PendingRequest[]; note: string | null } {
  let list: unknown[] = [];
  if (Array.isArray(payload)) list = payload;
  else if (payload && typeof payload === "object") {
    const rec = payload as Record<string, unknown>;
    const inner = rec.requests ?? rec.items ?? rec.pending ?? rec.data ?? rec.content;
    if (Array.isArray(inner)) list = inner;
    else if (typeof rec.text === "string") {
      try {
        const parsed = JSON.parse(rec.text);
        if (Array.isArray(parsed)) list = parsed;
      } catch {
        return { items: [], note: rec.text.slice(0, 200) };
      }
    }
  }
  const items: PendingRequest[] = list.map((it) => {
    if (typeof it === "string") return { id: it, summary: "", tool: null, requestedAt: null, raw: {} };
    const rec = (it ?? {}) as Record<string, unknown>;
    const id = String(rec.requestId ?? rec.request_id ?? rec.id ?? rec.reqId ?? "");
    const tool = typeof rec.tool === "string" ? rec.tool : typeof rec.toolName === "string" ? rec.toolName : null;
    const summary = String(
      rec.reason ?? rec.summary ?? rec.description ?? rec.detail ?? rec.action ?? (tool ? `Invoke ${tool}` : "Pending request"),
    ).slice(0, 220);
    const requestedAtRaw = rec.requestedAt ?? rec.createdAt ?? rec.created_at ?? rec.timestamp;
    const requestedAt = typeof requestedAtRaw === "string" || typeof requestedAtRaw === "number" ? String(requestedAtRaw) : null;
    return { id, summary, tool, requestedAt, raw: rec };
  }).filter((it) => it.id);
  return { items, note: null };
}

export function ApprovalsPanel() {
  const qc = useQueryClient();
  const [showEmpty, setShowEmpty] = React.useState(false);

  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["approvals"],
    queryFn: async () => {
      const r = await callTowerTool("policy_list_pending", {}, { silent: true });
      return r;
    },
    refetchInterval: 60_000,
    retry: false,
    staleTime: 30_000,
  });

  const decide = useMutation({
    mutationFn: async ({ requestId, decision }: { requestId: string; decision: "APPROVED" | "REJECTED" }) =>
      callTowerTool("policy_approve", { requestId, decision }),
    onSuccess: (res, vars) => {
      if (res.ok) {
        toast.success(`${vars.requestId} → ${vars.decision.toLowerCase()}`);
        qc.invalidateQueries({ queryKey: ["approvals"] });
      } else {
        toast.error(`Decision failed: ${(res.error ?? "tower unreachable").slice(0, 120)}`);
      }
    },
    onError: (e) => toast.error(`Decision failed: ${String(e).slice(0, 120)}`),
  });

  const pending = React.useMemo(() => {
    if (!data?.ok) return { items: [] as PendingRequest[], note: null };
    return normalizePending(data.result);
  }, [data]);

  // Tower down → render nothing (approvals are optional chrome, never block the journal)
  if (!data && !isLoading && isError) return null;
  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-40" />
        </CardContent>
      </Card>
    );
  }
  if (isError) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          Approvals unavailable — tower unreachable ({String((error as Error)?.message ?? "").slice(0, 60)}).
          <Button variant="ghost" size="sm" onClick={() => refetch()} aria-label="Retry approvals fetch">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </CardContent>
      </Card>
    );
  }

  const hasItems = pending.items.length > 0;
  if (!hasItems && !showEmpty) {
    // Collapse to a slim healthy line; expandable so the operator can verify freshness
    return (
      <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
        <CardContent className="flex items-center justify-between gap-2 p-3">
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            No pending HITL approvals — policy engine clear.
          </p>
          <div className="flex items-center gap-1.5">
            <span className="hidden text-[10px] text-muted-foreground sm:inline">
              checked {dataUpdatedAt ? ago(new Date(dataUpdatedAt).toISOString()) : "—"}
            </span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShowEmpty(true)} aria-label="Show approvals detail">
              <ClipboardCheck className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(hasItems && "border-amber-500/30 bg-amber-500/[0.04]")}>
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <ClipboardCheck className={cn("h-4 w-4", hasItems ? "text-amber-500" : "text-primary")} />
            HITL approvals
            <Badge variant={hasItems ? "default" : "secondary"} className="h-4 px-1.5 text-[10px]">
              {pending.items.length}
            </Badge>
          </p>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh approvals">
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
          </Button>
        </div>

        {pending.note && (
          <p className="mb-2 rounded-md border border-muted bg-muted/30 px-2.5 py-1.5 font-mono text-[11px] text-muted-foreground">{pending.note}</p>
        )}

        {!hasItems ? (
          <p className="py-2 text-xs text-muted-foreground">
            The tower policy engine has no requests awaiting an operator decision. Mutating tool calls flagged by policy_preview surface here when the
            engine needs a human.
          </p>
        ) : (
          <ul className="space-y-2">
            {pending.items.map((it, i) => (
              <motion.li
                key={it.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: i * 0.04 }}
                className="rounded-lg border border-amber-500/30 bg-background/60 p-3"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <p className="flex flex-wrap items-center gap-1.5">
                      <span className="font-mono text-xs font-semibold text-amber-600 dark:text-amber-400">{it.id}</span>
                      {it.tool && <MetricBadge>{it.tool}</MetricBadge>}
                      {it.requestedAt && (
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {ago(it.requestedAt)}
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">{it.summary}</p>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button size="sm" className="h-7 px-2.5 text-xs" disabled={decide.isPending}>
                          <ShieldCheck className="mr-1 h-3 w-3" />
                          Approve
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Approve {it.id}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Grant the requested action on the tower. The decision is journaled in the Operations Journal for audit.
                            {it.summary ? ` Request: ${it.summary}` : ""}
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => decide.mutate({ requestId: it.id, decision: "APPROVED" })}>
                            Approve
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs text-red-500 hover:text-red-500" disabled={decide.isPending}>
                          <XCircle className="mr-1 h-3 w-3" />
                          Reject
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Reject {it.id}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Deny the requested action. The decision is journaled in the Operations Journal for audit.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction className="bg-red-600 text-white hover:bg-red-700" onClick={() => decide.mutate({ requestId: it.id, decision: "REJECTED" })}>
                            Reject
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </motion.li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
