"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Save, Settings2, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { SettingsData } from "@/lib/mission-types";
import { SectionHeader } from "./widgets";

export function SettingsTab() {
  const qc = useQueryClient();
  const [draft, setDraft] = React.useState<SettingsData | null>(null);

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

  const update = <K extends keyof SettingsData>(k: K, v: SettingsData[K]) => setDraft({ ...draft, [k]: v });

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
              value={draft.towerKeyMasked}
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
