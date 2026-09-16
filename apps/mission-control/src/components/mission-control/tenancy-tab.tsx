"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  BadgeCheck,
  Building2,
  Copy,
  KeyRound,
  PauseCircle,
  PlayCircle,
  ShieldAlert,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ToolCallResult } from "@/lib/mission-types";
import { callTowerTool } from "@/lib/tower-gateway";
import { JsonViewer, MetricBadge, SectionHeader, Tip } from "./widgets";

/* ── Tower payload helpers (defensive: tower shapes vary) ─────────── */

function extractList(payload: unknown, keys: string[]): Record<string, unknown>[] {
  if (Array.isArray(payload)) return payload as Record<string, unknown>[];
  if (payload && typeof payload === "object") {
    const rec = payload as Record<string, unknown>;
    for (const k of keys) {
      const v = rec[k];
      if (Array.isArray(v)) return v as Record<string, unknown>[];
    }
    // last resort: first array-valued field
    for (const v of Object.values(rec)) {
      if (Array.isArray(v)) return v as Record<string, unknown>[];
    }
  }
  return [];
}

function str(v: unknown, fallback = "—"): string {
  return v == null || v === "" ? fallback : String(v);
}

const STATUS_TONE: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  approved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  suspended: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  pending: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
  revoked: "bg-red-500/10 text-red-600 dark:text-red-400",
};

function StatusPill({ status }: { status: string }) {
  const s = status.toLowerCase();
  return (
    <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${STATUS_TONE[s] ?? "bg-muted text-muted-foreground"}`}>
      {s || "unknown"}
    </span>
  );
}

/* ── Token reveal dialog (rotate / register results) ──────────────── */

function TokenDialog({ token, title, onClose }: { token: string | null; title: string; onClose: () => void }) {
  const copy = async () => {
    if (!token) return;
    await navigator.clipboard.writeText(token).catch(() => {});
    toast.success("Token copied to clipboard");
  };
  return (
    <Dialog open={Boolean(token)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Shown once — copy it now. The old token (if any) stopped working immediately.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2">
          <code className="min-w-0 flex-1 break-all rounded-md border bg-muted/50 p-2.5 font-mono text-[11px]">{token}</code>
          <Button size="icon" variant="outline" onClick={copy} aria-label="Copy token">
            <Copy className="h-4 w-4" />
          </Button>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function tokenFrom(result: unknown): string | null {
  if (!result) return null;
  const scan = (o: unknown, depth = 0): string | null => {
    if (depth > 4 || o == null) return null;
    if (typeof o === "string") return /token|sk-|key/i.test(o) && o.length > 8 ? o : null;
    if (Array.isArray(o)) return null;
    if (typeof o === "object") {
      const rec = o as Record<string, unknown>;
      for (const k of ["token", "adminToken", "clientToken", "secret", "apiKey", "value"]) {
        const hit = scan(rec[k], depth + 1);
        if (hit) return hit;
      }
      for (const v of Object.values(rec)) {
        const hit = scan(v, depth + 1);
        if (hit) return hit;
      }
    }
    return null;
  };
  return scan(result);
}

/* ── Main tab ─────────────────────────────────────────────────────── */

interface TenancyTabProps {
  onToolError?: (msg: string) => void;
}

export function TenancyTab({ onToolError }: TenancyTabProps = {}) {
  const qc = useQueryClient();

  const tenants = useQuery({
    queryKey: ["tenants"],
    queryFn: async () => {
      const r = await callTowerTool("tenant_list", {}, { silent: true });
      if (!r.ok && r.error?.includes("not configured")) onToolError?.(r.error);
      return extractList(r.result, ["tenants", "items", "data", "results"]);
    },
    refetchInterval: 120_000,
    retry: 1,
  });

  const clients = useQuery({
    queryKey: ["clients"],
    queryFn: async () => {
      const r = await callTowerTool("client_list", {}, { silent: true });
      if (!r.ok && r.error?.includes("not configured")) onToolError?.(r.error);
      return extractList(r.result, ["clients", "items", "data", "results"]);
    },
    refetchInterval: 120_000,
    retry: 1,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tenants"] });
    qc.invalidateQueries({ queryKey: ["clients"] });
  };

  const act = useMutation({
    mutationFn: async ({ tool, args }: { tool: string; args: Record<string, unknown> }): Promise<ToolCallResult> =>
      callTowerTool(tool, args),
    onSuccess: (r, vars) => {
      if (r.ok) toast.success(`${vars.tool} ✓ (${r.durationMs}ms)`);
      else toast.error(`${vars.tool} failed: ${(r.error ?? "unknown").slice(0, 90)}`);
      invalidate();
    },
  });

  const [tokenReveal, setTokenReveal] = React.useState<{ token: string; title: string } | null>(null);

  const rotateTenant = useMutation({
    mutationFn: async (tenantId: string) => callTowerTool("tenant_rotate_admin_token", { tenantId }),
    onSuccess: (r) => {
      invalidate();
      const t = tokenFrom(r.result);
      if (r.ok && t) setTokenReveal({ token: t, title: "New tenant admin token" });
      else if (r.ok) toast.success("Admin token rotated (value hidden by tower)");
      else toast.error(`Rotate failed: ${(r.error ?? "unknown").slice(0, 90)}`);
    },
  });

  const rotateClient = useMutation({
    mutationFn: async (clientId: string) => callTowerTool("client_rotate_token", { clientId }),
    onSuccess: (r) => {
      invalidate();
      const t = tokenFrom(r.result);
      if (r.ok && t) setTokenReveal({ token: t, title: "New client token" });
      else if (r.ok) toast.success("Client token rotated");
      else toast.error(`Rotate failed: ${(r.error ?? "unknown").slice(0, 90)}`);
    },
  });

  /* register dialog state */
  const [regOpen, setRegOpen] = React.useState(false);
  const [reg, setReg] = React.useState({ name: "", provider: "claude", role: "agent", protocol: "mcp", expiresInDays: "" });
  const register = useMutation({
    mutationFn: async () => {
      const args: Record<string, unknown> = { name: reg.name.trim(), provider: reg.provider, role: reg.role, protocol: reg.protocol };
      if (reg.expiresInDays.trim()) args.expiresInDays = Number(reg.expiresInDays);
      return callTowerTool("client_register", args);
    },
    onSuccess: (r) => {
      setRegOpen(false);
      setReg({ name: "", provider: "claude", role: "agent", protocol: "mcp", expiresInDays: "" });
      invalidate();
      const t = tokenFrom(r.result);
      if (r.ok && t) setTokenReveal({ token: t, title: "Client registered — access token" });
      else if (r.ok) toast.success("Client registered");
      else toast.error(`Register failed: ${(r.error ?? "unknown").slice(0, 90)}`);
    },
  });

  /* create-tenant dialog state */
  const [tenantOpen, setTenantOpen] = React.useState(false);
  const [tn, setTn] = React.useState({ name: "", ownerEmail: "", type: "customer", plan: "free" });
  const createTenant = useMutation({
    mutationFn: async () =>
      callTowerTool("tenant_create", {
        name: tn.name.trim(),
        ownerEmail: tn.ownerEmail.trim(),
        type: tn.type,
        plan: tn.plan.trim() || "free",
      }),
    onSuccess: (r) => {
      setTenantOpen(false);
      setTn({ name: "", ownerEmail: "", type: "customer", plan: "free" });
      invalidate();
      const t = tokenFrom(r.result);
      if (r.ok && t) setTokenReveal({ token: t, title: "Tenant created — admin token" });
      else if (r.ok) toast.success("Tenant created");
      else toast.error(`Tenant create failed: ${(r.error ?? "unknown").slice(0, 90)}`);
    },
  });

  const tenantRows = tenants.data ?? [];
  const clientRows = clients.data ?? [];
  const suspended = tenantRows.filter((t) => String(t.status ?? "").toLowerCase() === "suspended").length;
  const pendingClients = clientRows.filter((c) => String(c.status ?? "").toLowerCase() === "pending").length;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Tenancy & Clients"
        desc="Multi-tenant governance — every AI client registered, scoped and revocable"
        right={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setTenantOpen(true)}>
              <Building2 className="mr-1.5 h-3.5 w-3.5" /> Create tenant
            </Button>
            <Button size="sm" onClick={() => setRegOpen(true)}>
              <UserPlus className="mr-1.5 h-3.5 w-3.5" /> Register client
            </Button>
          </div>
        }
      />

      {/* KPI strip */}
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="gap-1.5">
          <Building2 className="h-3.5 w-3.5 text-primary" /> {tenantRows.length} tenants
        </Badge>
        {suspended > 0 && <MetricBadge tone="warn">{suspended} suspended</MetricBadge>}
        <Badge variant="secondary" className="gap-1.5">
          <UsersRound className="h-3.5 w-3.5 text-primary" /> {clientRows.length} clients
        </Badge>
        {pendingClients > 0 && <MetricBadge tone="warn">{pendingClients} pending approval</MetricBadge>}
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        {/* Tenants */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Building2 className="h-4 w-4 text-primary" />
              Tenants
              <Badge variant="secondary" className="text-[10px]">{tenantRows.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {tenants.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : tenantRows.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
                <Building2 className="h-8 w-8 opacity-40" />
                <p className="max-w-xs text-xs">
                  {tenants.isError
                    ? "tenant_list unavailable — tower unreachable or not configured."
                    : "No tenants yet — hit “Create tenant” above to spin one up in seconds."}
                </p>
              </div>
            ) : (
              <ScrollArea className="max-h-[380px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tenant</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tenantRows.map((t, i) => {
                      const id = str(t.tenantId ?? t.id ?? t.tenant_id, "");
                      const name = str(t.name ?? t.tenantName, id || "tenant");
                      const status = String(t.status ?? "unknown").toLowerCase();
                      return (
                        <motion.tr
                          key={id || i}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ duration: 0.15, delay: Math.min(i * 0.03, 0.3) }}
                          className="transition-colors hover:bg-primary/5"
                        >
                          <TableCell className="max-w-[180px]">
                            <p className="truncate text-xs font-semibold">{name}</p>
                            <p className="truncate font-mono text-[10px] text-muted-foreground">{str(t.tenantId ?? t.id ?? t.tenant_id, "")}</p>
                          </TableCell>
                          <TableCell><MetricBadge>{str(t.plan ?? t.tier, "free")}</MetricBadge></TableCell>
                          <TableCell><StatusPill status={status} /></TableCell>
                          <TableCell>
                            <div className="flex justify-end gap-1">
                              <Tip label={status === "suspended" ? "Activate tenant" : "Suspend tenant"}>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7"
                                  aria-label={status === "suspended" ? "Activate tenant" : "Suspend tenant"}
                                  disabled={act.isPending || !id}
                                  onClick={() =>
                                    act.mutate({
                                      tool: status === "suspended" ? "tenant_activate" : "tenant_suspend",
                                      args: { tenantId: id },
                                    })
                                  }
                                >
                                  {status === "suspended" ? <PlayCircle className="h-3.5 w-3.5 text-emerald-500" /> : <PauseCircle className="h-3.5 w-3.5 text-amber-500" />}
                                </Button>
                              </Tip>
                              <Tip label="Rotate admin token">
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7"
                                  aria-label="Rotate admin token"
                                  disabled={rotateTenant.isPending || !id}
                                  onClick={() => rotateTenant.mutate(id)}
                                >
                                  <KeyRound className="h-3.5 w-3.5" />
                                </Button>
                              </Tip>
                            </div>
                          </TableCell>
                        </motion.tr>
                      );
                    })}
                  </TableBody>
                </Table>
              </ScrollArea>
            )}
          </CardContent>
        </Card>

        {/* Clients */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <UsersRound className="h-4 w-4 text-primary" />
              AI Clients
              <Badge variant="secondary" className="text-[10px]">{clientRows.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {clients.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : clientRows.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
                <UsersRound className="h-8 w-8 opacity-40" />
                <p className="max-w-xs text-xs">
                  {clients.isError
                    ? "client_list unavailable — tower unreachable or not configured."
                    : "No AI clients registered yet — register Claude, Cursor, Gemini, ChatGPT or a custom agent."}
                </p>
              </div>
            ) : (
              <ScrollArea className="max-h-[380px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Client</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {clientRows.map((c, i) => {
                      const id = str(c.clientId ?? c.id ?? c.client_id, "");
                      const name = str(c.name ?? c.clientName, id || "client");
                      const provider = String(c.provider ?? "custom").toLowerCase();
                      const role = String(c.role ?? "viewer").toLowerCase();
                      const status = String(c.status ?? "unknown").toLowerCase();
                      return (
                        <motion.tr
                          key={id || i}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ duration: 0.15, delay: Math.min(i * 0.03, 0.3) }}
                          className="transition-colors hover:bg-primary/5"
                        >
                          <TableCell className="max-w-[170px]">
                            <p className="truncate text-xs font-semibold">{name}</p>
                            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{provider}</p>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={role}
                              onValueChange={(v) => {
                                if (v !== role) act.mutate({ tool: "client_set_role", args: { clientId: id, role: v } });
                              }}
                            >
                              <SelectTrigger className="h-7 w-[104px] text-[11px]" aria-label={`Role for ${name}`}>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="viewer">viewer</SelectItem>
                                <SelectItem value="agent">agent</SelectItem>
                                <SelectItem value="admin">admin</SelectItem>
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell><StatusPill status={status} /></TableCell>
                          <TableCell>
                            <div className="flex justify-end gap-1">
                              {status === "pending" && (
                                <Tip label="Approve client">
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-7 w-7 text-emerald-600"
                                    aria-label="Approve client"
                                    disabled={act.isPending || !id}
                                    onClick={() => act.mutate({ tool: "client_approve", args: { clientId: id } })}
                                  >
                                    <BadgeCheck className="h-3.5 w-3.5" />
                                  </Button>
                                </Tip>
                              )}
                              <Tip label="Rotate token">
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7"
                                  aria-label="Rotate client token"
                                  disabled={rotateClient.isPending || !id}
                                  onClick={() => rotateClient.mutate(id)}
                                >
                                  <KeyRound className="h-3.5 w-3.5" />
                                </Button>
                              </Tip>
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground hover:text-red-500" aria-label="Revoke client" disabled={!id}>
                                    <ShieldAlert className="h-3.5 w-3.5" />
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>Revoke {name}?</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      The client&apos;s token stops working immediately. This cannot be undone — the client must be registered again.
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => act.mutate({ tool: "client_revoke", args: { clientId: id } })}>
                                      Revoke access
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            </div>
                          </TableCell>
                        </motion.tr>
                      );
                    })}
                  </TableBody>
                </Table>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Raw tenancy payloads for operators */}
      <details className="group">
        <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Raw tower payloads
        </summary>
        <div className="mt-2 grid gap-3 lg:grid-cols-2">
          <JsonViewer data={tenantRows} maxHeight={180} />
          <JsonViewer data={clientRows} maxHeight={180} />
        </div>
      </details>

      {/* Register client dialog */}
      <Dialog open={regOpen} onOpenChange={setRegOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Register AI client</DialogTitle>
            <DialogDescription>
              Enroll a new AI agent into a tenant — it gets a scoped token and governed tool access.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-2">
              <Label htmlFor="clientName">Client name</Label>
              <Input
                id="clientName"
                placeholder="e.g. niloy-claude-code"
                value={reg.name}
                onChange={(e) => setReg({ ...reg, name: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-2">
                <Label>Provider</Label>
                <Select value={reg.provider} onValueChange={(v) => setReg({ ...reg, provider: v })}>
                  <SelectTrigger aria-label="Provider"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["claude", "cursor", "gemini", "chatgpt", "vscode", "custom"].map((p) => (
                      <SelectItem key={p} value={p}>{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Role</Label>
                <Select value={reg.role} onValueChange={(v) => setReg({ ...reg, role: v })}>
                  <SelectTrigger aria-label="Role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["viewer", "agent", "admin"].map((r) => (
                      <SelectItem key={r} value={r}>{r}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-2">
                <Label>Protocol</Label>
                <Select value={reg.protocol} onValueChange={(v) => setReg({ ...reg, protocol: v })}>
                  <SelectTrigger aria-label="Protocol"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["mcp", "http", "websocket"].map((p) => (
                      <SelectItem key={p} value={p}>{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="expDays">Expires in days</Label>
                <Input
                  id="expDays"
                  type="number"
                  min={1}
                  placeholder="optional"
                  value={reg.expiresInDays}
                  onChange={(e) => setReg({ ...reg, expiresInDays: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRegOpen(false)}>Cancel</Button>
            <Button disabled={!reg.name.trim() || register.isPending} onClick={() => register.mutate()}>
              <UserPlus className="mr-2 h-4 w-4" />
              {register.isPending ? "Registering…" : "Register"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create tenant dialog */}
      <Dialog open={tenantOpen} onOpenChange={setTenantOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create tenant</DialogTitle>
            <DialogDescription>
              Spin up an isolated tenant with its own admin token — internal team or external customer.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-2">
              <Label htmlFor="tenantName">Tenant name</Label>
              <Input
                id="tenantName"
                placeholder="e.g. Saiful's Startup"
                value={tn.name}
                onChange={(e) => setTn({ ...tn, name: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tenantEmail">Owner email</Label>
              <Input
                id="tenantEmail"
                type="email"
                placeholder="owner@example.com"
                value={tn.ownerEmail}
                onChange={(e) => setTn({ ...tn, ownerEmail: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-2">
                <Label>Type</Label>
                <Select value={tn.type} onValueChange={(v) => setTn({ ...tn, type: v })}>
                  <SelectTrigger aria-label="Tenant type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="customer">customer</SelectItem>
                    <SelectItem value="admin">admin (internal)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="tenantPlan">Plan</Label>
                <Input
                  id="tenantPlan"
                  placeholder="free"
                  value={tn.plan}
                  onChange={(e) => setTn({ ...tn, plan: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTenantOpen(false)}>Cancel</Button>
            <Button
              disabled={!tn.name.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(tn.ownerEmail.trim()) || createTenant.isPending}
              onClick={() => createTenant.mutate()}
            >
              <Building2 className="mr-2 h-4 w-4" />
              {createTenant.isPending ? "Creating…" : "Create tenant"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Token reveal */}
      <TokenDialog token={tokenReveal?.token ?? null} title={tokenReveal?.title ?? ""} onClose={() => setTokenReveal(null)} />
    </div>
  );
}
