"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { EyeOff, FlaskConical, Plus, Save, Settings2, ShieldCheck, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { DashboardData, SettingsData } from "@/lib/mission-types";
import { SectionHeader, MetricBadge } from "./widgets";

export function SettingsTab() {
  const qc = useQueryClient();
  // Draft is a superset: rotate-only secret fields (towerKey / githubToken) exist
  // only after the user types a new value — masked server-returned values are never sent back.
  type SettingsDraft = SettingsData & { towerKey?: string; githubToken?: string };
  const [draft, setDraft] = React.useState<SettingsDraft | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: async (): Promise<SettingsData> => {
      const res = await fetch("/api/settings", { cache: "no-store" });
      return res.json();
    },
  });

  React.useEffect(() => {
    if (data && !draft) setDraft(data);
  }, [data, draft]);

  const saveMutation = useMutation({
    mutationFn: async (d: SettingsData) => {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(d),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      toast.success("Settings saved — dynamic config applied instantly");
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading || !draft) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const update = <K extends keyof SettingsDraft>(k: K, v: SettingsDraft[K]) => setDraft({ ...draft, [k]: v });

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <SectionHeader title="Settings" desc="Dynamic by Design — change behavior without touching code" />

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Settings2 className="h-4 w-4 text-primary" />
            Control Tower & Repo
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="towerUrl">Tower URL</Label>
            <Input id="towerUrl" value={draft.towerUrl} onChange={(e) => update("towerUrl", e.target.value)} className="font-mono text-xs" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="towerKey">Tower Admin Key</Label>
            <Input
              id="towerKey"
              value={draft.towerKey ?? draft.towerKeyMasked}
              onChange={(e) => update("towerKey", e.target.value)}
              className="font-mono text-xs"
              placeholder="paste new key to rotate"
            />
            <p className="text-[11px] text-muted-foreground">
              <ShieldCheck className="mr-1 inline h-3 w-3" /> Masked server-side. Paste a fresh key only to rotate.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="repo">GitHub Repo</Label>
              <Input id="repo" value={draft.githubRepo} onChange={(e) => update("githubRepo", e.target.value)} className="font-mono text-xs" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="branch">Watch Branch</Label>
              <Input id="branch" value={draft.watchBranch} onChange={(e) => update("watchBranch", e.target.value)} className="font-mono text-xs" />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="githubToken">GitHub Token (PAT)</Label>
            <Input
              id="githubToken"
              value={draft.githubToken ?? draft.githubTokenMasked}
              onChange={(e) => update("githubToken", e.target.value)}
              className="font-mono text-xs"
              placeholder={draft.githubTokenMasked || "paste new token to rotate"}
            />
            <p className="text-[11px] text-muted-foreground">
              <ShieldCheck className="mr-1 inline h-3 w-3" /> Powers the Git Sync Center (PRs, CI, auto-merge sync). Masked server-side; paste a fresh token only to rotate.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="renderAccount">Render Account ID (tower resource)</Label>
            <Input
              id="renderAccount"
              value={draft.renderAccountId}
              onChange={(e) => update("renderAccountId", e.target.value)}
              className="font-mono text-xs"
              placeholder="render-primary"
            />
            <p className="text-[11px] text-muted-foreground">
              Used by the Render Fleet panel (render_list_services / deploy tools).
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base">Behavior</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Auto-wake tower</p>
              <p className="text-xs text-muted-foreground">Ping /health when Render free tier sleeps</p>
            </div>
            <Switch checked={draft.autoWake} onCheckedChange={(v) => update("autoWake", v)} aria-label="Toggle auto wake" />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Auto-sync stale PRs</p>
              <p className="text-xs text-muted-foreground">Merge main into clean PRs that fell behind</p>
            </div>
            <Switch checked={draft.autoSyncPrs} onCheckedChange={(v) => update("autoSyncPrs", v)} aria-label="Toggle auto sync" />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Service watchdog</p>
              <p className="text-xs text-muted-foreground">Alert on service status transitions (down / degraded / recovered)</p>
            </div>
            <Switch checked={draft.watchdogEnabled} onCheckedChange={(v) => update("watchdogEnabled", v)} aria-label="Toggle service watchdog" />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>Watchdog notify channel</Label>
              <div className="flex gap-2">
                <Select
                  value={draft.watchdogNotifyChannel}
                  onValueChange={(v) => update("watchdogNotifyChannel", v as SettingsData["watchdogNotifyChannel"])}
                >
                  <SelectTrigger aria-label="Watchdog notify channel">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None — activity stream only</SelectItem>
                    <SelectItem value="telegram">Telegram (tower notify_send_telegram)</SelectItem>
                    <SelectItem value="discord">Discord (tower notify_send_discord)</SelectItem>
                  </SelectContent>
                </Select>
                <NotifyTestButton channel={draft.watchdogNotifyChannel} />
              </div>
              <p className="text-[11px] text-muted-foreground">
                Tower env must have TELEGRAM_CHAT_ID / webhook configured.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="cooldown">Alert cooldown (minutes)</Label>
              <Input
                id="cooldown"
                type="number"
                min={0}
                max={240}
                value={draft.watchdogCooldownMin}
                onChange={(e) => update("watchdogCooldownMin", Number(e.target.value) || 15)}
              />
              <p className="text-[11px] text-muted-foreground">Per-provider suppression window (0–240).</p>
            </div>
          </div>
          <WatchdogOverridesEditor value={draft.watchdogOverrides} onChange={(json) => update("watchdogOverrides", json)} />
          <WatchdogDrill armed={draft.watchdogEnabled} />
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="refresh">Refresh interval (seconds)</Label>
              <Input
                id="refresh"
                type="number"
                min={10}
                max={600}
                value={draft.refreshIntervalSec}
                onChange={(e) => update("refreshIntervalSec", Number(e.target.value) || 30)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="retention">Journal retention (days)</Label>
              <Input
                id="retention"
                type="number"
                min={1}
                max={365}
                value={draft.journalRetentionDays}
                onChange={(e) => update("journalRetentionDays", Number(e.target.value) || 14)}
              />
              <p className="text-[11px] text-muted-foreground">
                Older journal rows are pruned automatically (1–365).
              </p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>Console theme</Label>
              <Select value={draft.theme} onValueChange={(v) => update("theme", v as SettingsData["theme"])}>
                <SelectTrigger aria-label="Theme"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="dark">Dark (mission deck)</SelectItem>
                  <SelectItem value="light">Light</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => saveMutation.mutate(draft)} disabled={saveMutation.isPending}>
          <Save className="mr-2 h-4 w-4" />
          {saveMutation.isPending ? "Saving…" : "Save settings"}
        </Button>
      </div>
    </div>
  );
}

/* ── Per-provider watchdog overrides editor (Dynamic by Design) ─────── */
interface OverrideRow {
  provider: string;
  enabled: boolean;
  cooldownMin: number | null; // null = inherit global
  channel: "inherit" | "none" | "telegram" | "discord";
}

function parseOverrideRows(json: string): OverrideRow[] {
  try {
    const obj = JSON.parse(json) as Record<string, Record<string, unknown>>;
    return Object.entries(obj ?? {}).map(([provider, o]) => ({
      provider,
      enabled: o.enabled !== false,
      cooldownMin: typeof o.cooldownMin === "number" ? o.cooldownMin : null,
      channel: (typeof o.channel === "string" ? o.channel : "inherit") as OverrideRow["channel"],
    }));
  } catch (err) {
    console.warn('[settings] watchdog overrides JSON parse failed, using empty rows:', err);
    return [];
  }
}

function rowsToOverridesJson(rows: OverrideRow[]): string {
  const out: Record<string, Record<string, unknown>> = {};
  for (const r of rows) {
    const o: Record<string, unknown> = {};
    // Always persist `enabled` explicitly — a brand-new all-default row must
    // still survive serialization round-trips (client↔API↔client).
    o.enabled = r.enabled;
    if (r.cooldownMin != null) o.cooldownMin = r.cooldownMin;
    if (r.channel !== "inherit") o.channel = r.channel;
    out[r.provider.trim().toLowerCase()] = o;
  }
  return JSON.stringify(out);
}

function WatchdogOverridesEditor({ value, onChange }: { value: string; onChange: (json: string) => void }) {
  const [adding, setAdding] = React.useState(false);
  const [newProvider, setNewProvider] = React.useState("");
  const rows = React.useMemo(() => parseOverrideRows(value), [value]);

  // Live provider names come free from the shared dashboard query (deduped by react-query)
  const { data: dash } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async (): Promise<DashboardData> => {
      const res = await fetch("/api/dashboard", { cache: "no-store" });
      return res.json();
    },
    enabled: adding && rows.length === 0,
    staleTime: 60_000,
  });
  const knownProviders = (dash?.services ?? []).map((s) => s.provider).filter((p) => !rows.some((r) => r.provider === p.toLowerCase()));

  const setRows = (next: OverrideRow[]) => onChange(rowsToOverridesJson(next));

  const addProvider = (name: string) => {
    const p = name.trim().toLowerCase();
    if (!p || rows.some((r) => r.provider === p)) return;
    setRows([...rows, { provider: p, enabled: true, cooldownMin: null, channel: "inherit" }]);
    setNewProvider("");
  };

  return (
    <div className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <EyeOff className="h-4 w-4 text-primary" />
        <p className="text-sm font-medium">Per-provider overrides</p>
        {rows.length > 0 && <MetricBadge>{rows.length} custom</MetricBadge>}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto h-7 px-2 text-xs"
          onClick={() => setAdding((v) => !v)}
          aria-expanded={adding}
          aria-label="Add provider override"
        >
          <Plus className="mr-1 h-3.5 w-3.5" /> Add
        </Button>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        Mute noisy providers, or give them their own cooldown / notify channel. Everything else inherits the global watchdog config above.
      </p>

      {adding && (
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <Input
            value={newProvider}
            onChange={(e) => setNewProvider(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") addProvider(newProvider);
            }}
            placeholder="provider name — e.g. cloudflare"
            className="h-8 text-xs"
            list="provider-suggestions"
            aria-label="New provider name"
          />
          <datalist id="provider-suggestions">
            {knownProviders.slice(0, 24).map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
          <Button size="sm" className="h-8 shrink-0 text-xs" onClick={() => addProvider(newProvider)} disabled={!newProvider.trim()}>
            Add override
          </Button>
        </div>
      )}

      {rows.length > 0 && (
        <ul className="mt-3 space-y-2">
          {rows.map((r, i) => (
            <li key={r.provider} className="grid grid-cols-2 items-center gap-2 rounded-md border bg-muted/10 p-2 sm:grid-cols-[1fr_auto_auto_auto]">
              <p className="flex min-w-0 items-center gap-1.5 text-xs font-medium">
                {!r.enabled && <EyeOff className="h-3.5 w-3.5 shrink-0 text-amber-500" aria-label="muted" />}
                <span className="truncate font-mono" title={r.provider}>
                  {r.provider}
                </span>
                {!r.enabled && <span className="shrink-0 text-[10px] uppercase tracking-wide text-amber-500">muted</span>}
              </p>
              <div className="flex items-center justify-end gap-1.5 sm:justify-center">
                <span className="text-[10px] text-muted-foreground">on</span>
                <Switch
                  checked={r.enabled}
                  onCheckedChange={(v) => setRows(rows.map((x, j) => (j === i ? { ...x, enabled: v } : x)))}
                  aria-label={`Watchdog enabled for ${r.provider}`}
                />
              </div>
              <Input
                type="number"
                min={0}
                max={240}
                value={r.cooldownMin ?? ""}
                onChange={(e) => {
                  const raw = e.target.value;
                  const n = raw === "" ? null : Math.max(0, Math.min(240, Number(raw) || 0));
                  setRows(rows.map((x, j) => (j === i ? { ...x, cooldownMin: n } : x)));
                }}
                placeholder="∞"
                className="h-7 w-16 text-xs"
                aria-label={`Cooldown override for ${r.provider}`}
              />
              <div className="flex items-center gap-1.5">
                <Select
                  value={r.channel}
                  onValueChange={(v) => setRows(rows.map((x, j) => (j === i ? { ...x, channel: v as OverrideRow["channel"] } : x)))}
                >
                  <SelectTrigger className="h-7 w-[110px] text-xs" aria-label={`Notify channel for ${r.provider}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">inherit</SelectItem>
                    <SelectItem value="none">none</SelectItem>
                    <SelectItem value="telegram">telegram</SelectItem>
                    <SelectItem value="discord">discord</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => setRows(rows.filter((_, j) => j !== i))}
                  aria-label={`Remove override for ${r.provider}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {rows.some((r) => !r.enabled) && (
        <p className="mt-2 text-[11px] text-amber-500">
          Muted providers are skipped entirely — transitions are neither journaled nor broadcast.
        </p>
      )}
    </div>
  );
}

/* ── Watchdog drill — synthetic DOWN transition to verify the alert path ── */
function WatchdogDrill({ armed }: { armed: boolean }) {
  const qc = useQueryClient();
  const [provider, setProvider] = React.useState("");
  const [running, setRunning] = React.useState(false);

  // Reuse the shared dashboard cache for the live provider list (no extra tower call)
  const { data: dash } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async (): Promise<DashboardData> => {
      const res = await fetch("/api/dashboard", { cache: "no-store" });
      return res.json();
    },
    staleTime: 60_000,
    retry: 1,
  });
  const providers = (dash?.services ?? []).map((s) => s.provider);

  const runDrill = async () => {
    if (!provider) return;
    setRunning(true);
    try {
      const res = await fetch("/api/watchdog/drill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider }),
      });
      const data = (await res.json()) as {
        ok?: boolean;
        error?: string;
        drill?: { notified: boolean | null; channel: string; error?: string };
      };
      if (res.ok && data.ok) {
        const d = data.drill!;
        if (d.notified === true) toast.success(`Drill complete — journaled ✓ · notify sent via ${d.channel} ✓`);
        else if (d.notified === false) toast.warning(`Drill journaled ✓ · notify via ${d.channel} failed: ${(d.error ?? "tower rejected").slice(0, 100)}`);
        else toast.success(`Drill complete — journaled ✓ (channel: ${d.channel} — journal/stream only)`);
        qc.invalidateQueries({ queryKey: ["watchdog-history"] });
        qc.invalidateQueries({ queryKey: ["journal"] });
      } else {
        toast.error(`Drill failed: ${(data.error ?? `HTTP ${res.status}`).slice(0, 140)}`);
      }
    } catch (err) {
      toast.error(`Drill failed: ${String(err).slice(0, 140)}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-lg border border-dashed p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 shrink-0 text-violet-500" />
          <Label className="text-sm font-medium">Watchdog drill</Label>
        </div>
        <Select value={provider} onValueChange={setProvider} disabled={providers.length === 0}>
          <SelectTrigger className="h-9 flex-1 text-xs" aria-label="Provider for watchdog drill">
            <SelectValue placeholder={providers.length === 0 ? "Load dashboard first…" : "Pick a provider"} />
          </SelectTrigger>
          <SelectContent className="max-h-64">
            {providers.map((p) => (
              <SelectItem key={p} value={p} className="text-xs">
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          className="h-9 shrink-0 border-violet-500/40 text-xs text-violet-600 hover:bg-violet-500/10 hover:text-violet-600 dark:text-violet-400"
          onClick={runDrill}
          disabled={!provider || running || !armed}
          aria-label="Run watchdog drill"
        >
          {running ? "Firing…" : "Run drill"}
        </Button>
      </div>
      <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
        Fires a clearly-labeled synthetic DOWN transition through the full path — journal entry, activity stream, notify channel — without touching real statuses. Bypasses cooldown; respects mute overrides.
        {!armed && <span className="ml-1 text-amber-500">Arm the watchdog first.</span>}
      </p>
    </div>
  );
}

/* ── Notify channel test button (send-and-see-result) ────────────── */
function NotifyTestButton({ channel }: { channel: SettingsData["watchdogNotifyChannel"] }) {
  const [testing, setTesting] = React.useState(false);

  const sendTest = async () => {
    setTesting(true);
    try {
      const res = await fetch("/api/tower/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool: channel === "discord" ? "notify_send_discord" : "notify_send_telegram",
          args: { message: `✅ SupremeAI Mission Control test alert — ${channel} channel OK at ${new Date().toISOString().slice(11, 19)} UTC` },
        }),
      });
      const data = (await res.json()) as { ok?: boolean; error?: string };
      if (res.ok && data.ok !== false) toast.success(`Test alert sent via ${channel} ✓`);
      else toast.error(`Test failed: ${(data.error ?? "tower rejected").slice(0, 120)}`);
    } catch (err) {
      toast.error(`Test failed: ${String(err).slice(0, 120)}`);
    } finally {
      setTesting(false);
    }
  };

  if (channel === "none") {
    return (
      <Button variant="outline" size="sm" className="h-9 shrink-0 text-xs opacity-40" disabled aria-label="Select a channel to enable test">
        Test
      </Button>
    );
  }
  return (
    <Button variant="outline" size="sm" className="h-9 shrink-0 text-xs" onClick={sendTest} disabled={testing} aria-label={`Send test alert via ${channel}`}>
      {testing ? "Sending…" : "Test"}
    </Button>
  );
}
