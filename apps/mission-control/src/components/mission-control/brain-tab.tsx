"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Brain, CloudDownload, CloudUpload, Lightbulb, Pin, PinOff, Plus, Search, Sparkles, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { MemoryNoteData } from "@/lib/mission-types";
import { callTowerTool } from "@/lib/tower-gateway";
import { MetricBadge, SectionHeader, ago, Tip } from "./widgets";

const KIND_META: Record<string, { label: string; cls: string }> = {
  fact: { label: "Fact", cls: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  decision: { label: "Decision", cls: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  lesson: { label: "Lesson", cls: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
  insight: { label: "Insight", cls: "bg-violet-500/10 text-violet-600 dark:text-violet-400" },
  sync: { label: "Sync", cls: "bg-teal-500/10 text-teal-600 dark:text-teal-400" },
};

interface MemoryResponse {
  notes: MemoryNoteData[];
  stats: Record<string, number>;
  total: number;
}

export function BrainTab() {
  const qc = useQueryClient();
  const [q, setQ] = React.useState("");
  const [kind, setKind] = React.useState("all");
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [form, setForm] = React.useState({ title: "", content: "", kind: "fact", tags: "" });

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["memory", q, kind],
    queryFn: async (): Promise<MemoryResponse> => {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (kind !== "all") params.set("kind", kind);
      const res = await fetch(`/api/memory?${params}`, { cache: "no-store" });
      return res.json();
    },
    refetchInterval: 60_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["memory"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const createMutation = useMutation({
    mutationFn: async (payload: typeof form) => {
      const res = await fetch("/api/memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error ?? `HTTP ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      toast.success("Memory etched into the brain");
      setDialogOpen(false);
      setForm({ title: "", content: "", kind: "fact", tags: "" });
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  const pinMutation = useMutation({
    mutationFn: async ({ id, pinned }: { id: string; pinned: boolean }) => {
      await fetch("/api/memory", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id, pinned }) });
    },
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await fetch(`/api/memory?id=${id}`, { method: "DELETE" });
    },
    onSuccess: () => {
      toast.success("Memory forgotten");
      invalidate();
    },
  });

  const [towerPushing, setTowerPushing] = React.useState<string | null>(null);
  const pushToTower = React.useCallback(
    async (n: MemoryNoteData) => {
      setTowerPushing(n.id);
      const res = await callTowerTool("memory_remember_fact", {
        fact: `${n.title} — ${n.content}`.slice(0, 2000),
        tags: n.tags.join(",") || n.kind,
      });
      setTowerPushing(null);
      if (res.ok) toast.success(`Mirrored to tower brain (${res.durationMs}ms)`);
      else toast.error(`Tower mirror failed: ${(res.error ?? "tower unreachable").slice(0, 90)}`);
    },
    [],
  );

  const [pulling, setPulling] = React.useState(false);
  const pullFromTower = React.useCallback(async () => {
    setPulling(true);
    try {
      const res = await callTowerTool("memory_get_recent_episodes", { limit: 10 });
      const payload = res.result as unknown;
      let items: Record<string, unknown>[] = [];
      if (Array.isArray(payload)) items = payload as Record<string, unknown>[];
      else if (payload && typeof payload === "object") {
        const rec = payload as Record<string, unknown>;
        const list = rec.episodes ?? rec.items ?? rec.memories ?? rec.results;
        if (Array.isArray(list)) items = list as Record<string, unknown>[];
      }
      let imported = 0;
      for (const it of items.slice(0, 10)) {
        const content = String(it.content ?? it.observation ?? it.fact ?? it.summary ?? it.text ?? JSON.stringify(it)).slice(0, 4000);
        const title = String(it.title ?? it.task ?? it.name ?? content.split("\n")[0] ?? "Tower memory").slice(0, 120);
        if (!content.trim()) continue;
        await fetch("/api/memory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, content, kind: "insight", tags: "tower,episodic", pinned: false }),
        });
        imported++;
      }
      if (res.ok && imported > 0) {
        toast.success(`Pulled ${imported} tower episode(s) into local brain`);
        invalidate();
      } else if (res.ok) {
        toast.info("Tower returned no new episodes");
      } else {
        toast.error(`Tower pull failed: ${(res.error ?? "tower unreachable").slice(0, 90)}`);
      }
    } finally {
      setPulling(false);
    }
  }, []);

  const notes = data?.notes ?? [];
  const stats = data?.stats ?? {};

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Brain & Memory"
        desc="Long-term memory: facts, decisions, lessons — the system learns from every operation"
        right={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={pullFromTower} disabled={pulling}>
              <CloudDownload className={`mr-1.5 h-3.5 w-3.5 ${pulling ? "animate-pulse" : ""}`} />
              {pulling ? "Pulling…" : "Pull from Tower"}
            </Button>
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <Plus className="mr-1.5 h-3.5 w-3.5" /> Remember
            </Button>
          </div>
        }
      />

      {/* Stats strip */}
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="gap-1.5">
          <Brain className="h-3.5 w-3.5 text-primary" /> {data?.total ?? 0} memories
        </Badge>
        {Object.entries(stats).map(([k, v]) => (
          <MetricBadge key={k}>{KIND_META[k]?.label ?? k}: {v}</MetricBadge>
        ))}
      </div>

      {/* Search */}
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search memory…" className="pl-9" aria-label="Search memory" />
        </div>
        <Select value={kind} onValueChange={setKind}>
          <SelectTrigger className="w-full sm:w-40" aria-label="Filter by kind">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All kinds</SelectItem>
            {Object.entries(KIND_META).map(([k, m]) => (
              <SelectItem key={k} value={k}>{m.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh memory">
          <Sparkles className={`h-4 w-4 ${isFetching ? "animate-pulse" : ""}`} />
        </Button>
      </div>

      {/* Notes */}
      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}
        </div>
      ) : notes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <Lightbulb className="h-10 w-10 text-muted-foreground/40" />
            <p className="max-w-sm text-sm text-muted-foreground">
              The brain is empty. Every fact, decision and lesson you record here makes the system smarter — memory that compounds.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid max-h-[520px] gap-3 overflow-y-auto pr-1 md:grid-cols-2">
          {notes.map((n, i) => (
            <motion.div key={n.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18, delay: Math.min(i * 0.02, 0.3) }}>
              <Card className={`h-full transition-all ${n.pinned ? "border-primary/50 shadow-[0_0_16px_-6px] shadow-primary/30" : "hover:border-primary/30"}`}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="line-clamp-1 text-sm">{n.title}</CardTitle>
                    <div className="flex shrink-0 items-center gap-0.5">
                      <Tip label="Mirror to tower brain (memory_remember_fact)">
                        <Button variant="ghost" size="icon" className="h-7 w-7" disabled={towerPushing === n.id} onClick={() => pushToTower(n)} aria-label="Push to tower">
                          <CloudUpload className={`h-3.5 w-3.5 ${towerPushing === n.id ? "animate-pulse text-primary" : ""}`} />
                        </Button>
                      </Tip>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => pinMutation.mutate({ id: n.id, pinned: !n.pinned })} aria-label={n.pinned ? "Unpin" : "Pin"}>
                        {n.pinned ? <PinOff className="h-3.5 w-3.5 text-primary" /> : <Pin className="h-3.5 w-3.5" />}
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-red-500" onClick={() => deleteMutation.mutate(n.id)} aria-label="Delete memory">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${KIND_META[n.kind]?.cls ?? "bg-muted text-muted-foreground"}`}>
                      {KIND_META[n.kind]?.label ?? n.kind}
                    </span>
                    {n.tags.map((t) => (
                      <MetricBadge key={t}>#{t}</MetricBadge>
                    ))}
                    <span className="ml-auto text-[10px] text-muted-foreground/60">{n.source} · {ago(n.createdAt)}</span>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <ScrollArea className="max-h-24">
                    <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">{n.content}</p>
                  </ScrollArea>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Add dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Etch a memory</DialogTitle>
            <DialogDescription>
              Long-term facts, decisions and lessons — searchable forever, mirrored to the tower brain on demand.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} aria-label="Memory title" />
            <div className="grid grid-cols-2 gap-2">
              <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v })}>
                <SelectTrigger aria-label="Memory kind"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(KIND_META).map(([k, m]) => (
                    <SelectItem key={k} value={k}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input placeholder="tags, comma, separated" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} aria-label="Memory tags" />
            </div>
            <Textarea placeholder="What should the system remember?" rows={4} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} aria-label="Memory content" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button
              disabled={!form.title.trim() || !form.content.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate(form)}
            >
              <Brain className="mr-2 h-4 w-4" /> Remember
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
