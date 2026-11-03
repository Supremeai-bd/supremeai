"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, Bot, Megaphone, PowerOff, Send, ShieldCheck, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { callTowerTool } from "@/lib/tower-gateway";
import { WatchdogHistory } from "./watchdog-history";
import { JsonViewer, SectionHeader, StatusDot, ago } from "./widgets";

interface AutonomyState {
  status: "live" | "sleeping" | "unreachable";
  enabled: boolean | null;
  raw: unknown;
}

interface PendingRequest {
  id?: string;
  requestId?: string;
  action?: string;
  risk?: string;
  reason?: string;
  requestedBy?: string;
  createdAt?: string;
  /* tower shape: { id, context: { provider, action }, state, createdAtMs, expiresAtMs } */
  context?: { provider?: string; action?: string } | null;
  state?: string;
  createdAtMs?: number;
  expiresAtMs?: number;
  [k: string]: unknown;
}

function pickId(p: PendingRequest): string {
  return String(p.id ?? p.requestId ?? Math.random().toString(36).slice(2));
}

/** Normalize the tower's pending-policy shapes into display fields. */
function normalizePending(p: PendingRequest): {
  label: string;
  state: string;
  createdAgo: string | null;
  expiresIn: string | null;
  expired: boolean;
} {
  const provider = p.context?.provider ?? "";
  const action = p.context?.action ?? p.action ?? p.title;
  const label = action
    ? provider
      ? `${provider}:${action}`
      : String(action)
    : "Unknown action";
  const createdIso = p.createdAtMs ? new Date(p.createdAtMs).toISOString() : p.createdAt ?? null;
  const expiresMs = typeof p.expiresAtMs === "number" ? p.expiresAtMs : null;
  const now = Date.now();
  const expired = expiresMs != null && expiresMs <= now;
  let expiresIn: string | null = null;
  if (expiresMs != null) {
    if (expired) expiresIn = "expired";
    else {
      const mins = Math.max(1, Math.round((expiresMs - now) / 60_000));
      expiresIn = mins >= 60 ? `expires in ${Math.floor(mins / 60)}h ${mins % 60}m` : `expires in ${mins}m`;
    }
  }
  return {
    label,
    state: String(p.state ?? "PENDING"),
    createdAgo: createdIso ? ago(createdIso) : null,
    expiresIn,
    expired,
  };
}

export function AutonomyTab() {
  const { data: autonomy, isLoading: loadingAuto, refetch: refetchAuto } = useQuery({
    queryKey: ["autonomy"],
    queryFn: async (): Promise<AutonomyState> => {
      const r = await callTowerTool("autonomy_status", {});
      const payload = r.result as Record<string, unknown> | string | null;
      let enabled: boolean | null = null;
      if (typeof payload === "string") {
        // Tower returns plain text like "Autonomy is currently ENABLED ✅"
        if (/disabled/i.test(payload)) enabled = false;
        else if (/enabled/i.test(payload)) enabled = true;
      } else if (payload && typeof payload === "object") {
        enabled = Boolean(payload.enabled ?? payload.autonomous ?? payload.is_enabled ?? payload.value);
      }
      return { status: r.ok ? "live" : r.error?.includes("503") ? "sleeping" : "unreachable", enabled, raw: r.result };
    },
    refetchInterval: 90_000,
  });

  const { data: pending, isLoading: loadingPending, refetch: refetchPending } = useQuery({
    queryKey: ["pending-approvals"],
    queryFn: async (): Promise<PendingRequest[]> => {
      const r = await callTowerTool("policy_list_pending", {});
      const payload = r.result as { requests?: PendingRequest[]; items?: PendingRequest[] } | Record<string, unknown> | null;
      const list = (payload?.requests ?? payload?.items ?? (Array.isArray(payload) ? payload : [])) as PendingRequest[];
      return Array.isArray(list) ? list : [];
    },
    refetchInterval: 60_000,
  });

  const act = useMutation({
    mutationFn: async ({ tool, args }: { tool: string; args: Record<string, unknown> }) => callTowerTool(tool, args),
    onSuccess: (r, vars) => {
      if (r.ok) toast.success(`${vars.tool} executed (${r.durationMs}ms)`);
      else toast.error(`${vars.tool} failed: ${r.error ?? "unknown"}`);
      refetchAuto();
      refetchPending();
    },
  });

  // Tower schema: policy_approve { requestId, decision: "APPROVED" | "REJECTED" }
  const approve = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "APPROVED" | "REJECTED" }) =>
      callTowerTool("policy_approve", { requestId: id, decision }),
    onSuccess: (r, vars) => {
      if (r.ok) toast.success(vars.decision === "APPROVED" ? "Request approved" : "Request rejected");
      else toast.error(`policy_approve failed: ${(r.error ?? "unknown").slice(0, 90)}`);
      refetchPending();
    },
    onError: (e) => toast.error(String(e)),
  });

  const enabled = autonomy?.enabled;

  return (
    <div className="space-y-5">
      <SectionHeader title="Autonomy & HITL" desc="Autonomous remediation control + pending human-in-the-loop approvals" />

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Autonomy control */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="h-4 w-4 text-primary" />
              Autonomous Remediation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingAuto ? (
              <Skeleton className="h-28 w-full" />
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-4">
                  <StatusDot status={autonomy?.status === "live" ? (enabled === false ? "sleeping" : "healthy") : autonomy?.status ?? "unknown"} className="h-3 w-3" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold">
                      {autonomy?.status !== "live" ? "Tower unreachable" : enabled === null ? "State unknown" : enabled ? "Autonomy ENABLED" : "Autonomy DISABLED"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {enabled === false
                        ? "Remediations are paused — the tower will only observe."
                        : "The tower can self-heal services within governed policy limits."}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={autonomy?.status !== "live" || act.isPending}
                    onClick={() => act.mutate({ tool: "autonomy_enable", args: {} })}
                  >
                    <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Enable
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="destructive" disabled={autonomy?.status !== "live" || act.isPending}>
                        <PowerOff className="mr-1.5 h-3.5 w-3.5" /> Kill Switch
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle className="flex items-center gap-2">
                          <AlertTriangle className="h-5 w-5 text-red-500" /> Engage kill switch?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                          This instantly disables ALL autonomous remediations on the tower. You must re-enable manually. Use in emergencies only.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          className="bg-red-600 hover:bg-red-700"
                          onClick={() => act.mutate({ tool: "autonomy_kill_switch", args: {} })}
                        >
                          Kill autonomy
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>

                {autonomy?.raw != null && <JsonViewer data={autonomy.raw} maxHeight={160} />}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pending approvals */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-4 w-4 text-primary" />
              Pending Approvals
              {pending && pending.length > 0 && <Badge variant="destructive">{pending.length}</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[300px] px-4 pb-4">
              {loadingPending ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
                </div>
              ) : (pending?.length ?? 0) === 0 ? (
                <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
                  <CheckCircle2 className="h-8 w-8 opacity-40" />
                  <p className="text-xs">Nothing awaiting approval — HITL queue is clear</p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {pending!.map((raw) => {
                    const p = normalizePending(raw);
                    return (
                      <li key={pickId(raw)} className="rounded-lg border p-3 transition-colors hover:bg-muted/20">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="flex items-center gap-1.5 truncate text-xs font-semibold">
                              {p.label}
                              <Badge variant="outline" className="h-4 px-1 text-[9px] uppercase tracking-wide text-muted-foreground">{p.state}</Badge>
                            </p>
                            <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">
                              REQ {pickId(raw)}
                              {raw.risk ? ` · risk: ${String(raw.risk)}` : ""}
                              {p.createdAgo ? ` · raised ${p.createdAgo}` : ""}
                              {p.expiresIn ? ` · ${p.expiresIn}` : ""}
                            </p>
                          </div>
                          <div className="flex shrink-0 gap-1">
                            <Button size="icon" variant="outline" className="h-7 w-7 text-emerald-600" aria-label="Approve" onClick={() => approve.mutate({ id: pickId(raw), decision: "APPROVED" })} disabled={approve.isPending}>
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              size="icon"
                              variant="outline"
                              className="h-7 w-7 text-red-500"
                              aria-label="Reject"
                              onClick={() => approve.mutate({ id: pickId(raw), decision: "REJECTED" })}
                              disabled={approve.isPending}
                            >
                              <XCircle className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      <NotifyTest />

      <WatchdogHistory />
    </div>
  );
}

/* ── Notify test panel (telegram/discord via governed tower tools) ── */
function NotifyTest() {
  const [channel, setChannel] = React.useState("telegram");
  const [message, setMessage] = React.useState("");
  const [chatId, setChatId] = React.useState("");
  const [result, setResult] = React.useState<unknown>(null);

  const send = useMutation({
    mutationFn: async () => {
      const args: Record<string, unknown> = { message: message.trim() };
      if (channel === "telegram" && chatId.trim()) args.chatId = chatId.trim();
      return callTowerTool(channel === "telegram" ? "notify_send_telegram" : "notify_send_discord", args);
    },
    onSuccess: (r) => {
      setResult(r.result ?? r.error ?? null);
      if (r.ok) {
        toast.success(`Alert sent via ${channel} (${r.durationMs}ms)`);
        setMessage("");
      } else {
        toast.error(`Send failed: ${(r.error ?? "unknown").slice(0, 90)}`);
      }
    },
    onError: (e) => toast.error(String(e)),
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Megaphone className="h-4 w-4 text-primary" />
          Operator Alert — Test Broadcast
          <Badge variant="secondary" className="text-[10px]">notify_*</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid w-full max-w-[180px] gap-1.5">
            <Label htmlFor="notifyChannel">Channel</Label>
            <Select value={channel} onValueChange={setChannel}>
              <SelectTrigger id="notifyChannel" aria-label="Alert channel"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="telegram">Telegram</SelectItem>
                <SelectItem value="discord">Discord</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid flex-1 gap-1.5">
            <Label htmlFor="notifyMsg">Message</Label>
            <Input
              id="notifyMsg"
              placeholder="e.g. Mission Control deploy test ✅"
              maxLength={channel === "telegram" ? 4000 : 1900}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && message.trim() && !send.isPending) send.mutate();
              }}
            />
          </div>
          {channel === "telegram" && (
            <div className="grid w-full max-w-[170px] gap-1.5">
              <Label htmlFor="notifyChat">Chat ID</Label>
              <Input
                id="notifyChat"
                placeholder="override (optional)"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
              />
            </div>
          )}
          <Button disabled={!message.trim() || send.isPending} onClick={() => send.mutate()}>
            <Send className="mr-1.5 h-3.5 w-3.5" />
            {send.isPending ? "Sending…" : "Send alert"}
          </Button>
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Targets are configured on the tower (TELEGRAM_CHAT_ID / Discord webhook) — never stored in this console.
        </p>
        {result != null && <div className="mt-3"><JsonViewer data={result} maxHeight={140} /></div>}
      </CardContent>
    </Card>
  );
}
