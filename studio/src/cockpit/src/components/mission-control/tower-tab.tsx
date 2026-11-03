"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { CircleStop, Play, RadioTower, RefreshCw, Search, ShieldAlert, ShieldCheck, Wrench, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { McpToolInfo, ToolCallResult } from "@/lib/mission-types";
import { callTowerTool } from "@/lib/tower-gateway";
import { JsonViewer, MetricBadge, SectionHeader, StatusDot, Tip, ago } from "./widgets";
import { DocsSources } from "./docs-sources";

interface ToolsResponse {
  ok: boolean;
  tools: McpToolInfo[];
  error?: string;
}

/* ── Risk heuristics (Dynamic-by-Design: classify before invoke) ── */
const MUTATING_RE =
  /(create|delete|remove|rotate|revoke|suspend|send|register|trigger|deploy|approve|reject|update|kill|write|remember|ingest|clear|store|set_|reset|cancel|renew|rebuild|restart|start|stop|pause|resume|push|merge|close|open|grant|invite)/;

function isMutatingTool(name: string): boolean {
  return MUTATING_RE.test(name.toLowerCase());
}

function deriveProviderAction(name: string): { provider: string; action: string } {
  const parts = name.split("_");
  return { provider: parts[0] || "system", action: parts.slice(1).join("_") || name };
}

interface PolicyPreview {
  risk?: string;
  level?: string;
  decision?: string;
  allowed?: boolean;
  raw: unknown;
}

function normalizePolicy(raw: unknown): PolicyPreview {
  const obj = (raw && typeof raw === "object" ? (Array.isArray(raw) ? {} : (raw as Record<string, unknown>)) : {}) as Record<string, unknown>;
  const inner = (obj.result ?? obj.content ?? obj) as Record<string, unknown>;
  const pick = (...keys: string[]) => {
    for (const k of keys) {
      const v = (inner as Record<string, unknown>)?.[k] ?? obj[k];
      if (typeof v === "string") return v;
    }
    return undefined;
  };
  return {
    risk: pick("risk", "risk_level", "riskLevel", "level"),
    decision: pick("decision", "policy_decision", "verdict"),
    allowed: typeof inner.allowed === "boolean" ? inner.allowed : undefined,
    raw,
  };
}

export function TowerTab() {
  const qc = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [category, setCategory] = React.useState("all");
  const [selected, setSelected] = React.useState<McpToolInfo | null>(null);
  const [argsText, setArgsText] = React.useState("{}");
  const [result, setResult] = React.useState<ToolCallResult | null>(null);
  const [acknowledged, setAcknowledged] = React.useState(false);
  const [policy, setPolicy] = React.useState<PolicyPreview | null>(null);
  const [policyLoading, setPolicyLoading] = React.useState(false);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["tower-tools"],
    queryFn: async (): Promise<ToolsResponse> => {
      const res = await fetch("/api/tower/tools", { cache: "no-store" });
      return res.json();
    },
    refetchInterval: 120_000,
  });

  const tools = data?.tools ?? [];
  const categories = React.useMemo(() => ["all", ...Array.from(new Set(tools.map((t) => t.category))).sort()], [tools]);

  const filtered = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    return tools.filter(
      (t) =>
        (category === "all" || t.category === category) &&
        (!q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)),
    );
  }, [tools, search, category]);

  const callMutation = useMutation({
    mutationFn: async ({ tool, args }: { tool: string; args: Record<string, unknown> }) => {
      const res = await fetch("/api/tower/call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, args }),
      });
      return (await res.json()) as ToolCallResult;
    },
    onSuccess: (r) => {
      setResult(r);
      if (r.ok) toast.success(`${r.tool} → ${r.durationMs}ms`);
      else toast.error(`${r.tool} failed: ${r.error ?? "unknown"}`);
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(String(e)),
  });

  const openTool = (t: McpToolInfo) => {
    setSelected(t);
    setResult(null);
    setAcknowledged(false);
    setPolicy(null);
    // prefill with sensible defaults from schema properties
    try {
      const schema = t.inputSchema as { properties?: Record<string, { default?: unknown; type?: string }> };
      const prefill: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(schema?.properties ?? {})) {
        if (v.default !== undefined) prefill[k] = v.default;
        else if (v.type === "boolean") prefill[k] = false;
        else if (v.type === "number" || v.type === "integer") prefill[k] = 0;
        else if (v.type === "array") prefill[k] = [];
      }
      setArgsText(JSON.stringify(prefill, null, 2));
    } catch {
      setArgsText("{}");
    }
    // Mutating tools: ask the tower's policy engine for a risk preview (HITL support)
    if (isMutatingTool(t.name)) {
      setPolicyLoading(true);
      const { provider, action } = deriveProviderAction(t.name);
      callTowerTool("policy_preview", { provider, action }, { silent: true })
        .then((r) => setPolicy(r.ok ? normalizePolicy(r.result) : { raw: r.error ?? "preview unavailable" }))
        .catch(() => setPolicy({ raw: "preview unavailable" }))
        .finally(() => setPolicyLoading(false));
    }
  };

  const runTool = () => {
    if (!selected) return;
    if (isMutatingTool(selected.name) && !acknowledged) {
      toast.error("Acknowledge the mutation warning before invoking");
      return;
    }
    let args: Record<string, unknown>;
    try {
      args = JSON.parse(argsText || "{}");
    } catch {
      toast.error("Arguments are not valid JSON");
      return;
    }
    callMutation.mutate({ tool: selected.name, args });
  };

  const mutating = selected ? isMutatingTool(selected.name) : false;

  const towerLive = (data?.tools.length ?? 0) > 0;

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Tower Explorer"
        desc="Browse & invoke the governed capability surface of the central MCP Control Tower"
        right={
          <div className="flex items-center gap-2">
            <Badge variant={towerLive ? "default" : "secondary"} className="gap-1.5">
              <StatusDot status={towerLive ? "live" : "sleeping"} />
              {towerLive ? `${tools.length} tools` : "tower sleeping"}
            </Badge>
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* Controls */}
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={`Search ${tools.length || "…"} tools — health, memory, github, autonomy…`} className="pl-9" aria-label="Search tools" />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-full sm:w-44" aria-label="Filter by category">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            {categories.map((c) => (
              <SelectItem key={c} value={c}>{c === "all" ? "All categories" : c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tool grid */}
      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : isError || !data?.ok ? (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <RadioTower className="h-10 w-10 text-amber-500/70" />
            <p className="max-w-md text-sm text-muted-foreground">
              Tower unreachable ({data?.error ?? "cold start"}). Render free tier sleeps after ~15 idle minutes — the console auto-wakes it on demand.
            </p>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              <Zap className="mr-2 h-4 w-4" /> Retry link
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">{filtered.length} of {tools.length} tools</p>
          <div className="grid max-h-[560px] gap-3 overflow-y-auto pr-1 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((t, i) => (
              <motion.button
                key={t.name}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18, delay: Math.min(i * 0.008, 0.3) }}
                onClick={() => openTool(t)}
                className="group text-left"
              >
                <Card className="h-full transition-all group-hover:border-primary/50 group-hover:shadow-[0_0_20px_-8px] group-hover:shadow-primary/30">
                  <CardContent className="p-3 sm:p-4">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-mono text-[13px] font-semibold text-primary/90">{t.name}</p>
                      <Badge variant="secondary" className="shrink-0 text-[10px]">{t.category}</Badge>
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{t.description || "No description"}</p>
                    <p className="mt-2 flex items-center gap-1 text-[11px] text-primary/60 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100">
                      <Play className="h-3 w-3" /> click to invoke
                    </p>
                  </CardContent>
                </Card>
              </motion.button>
            ))}
          </div>
        </>
      )}

      {/* Runner dialog */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden sm:rounded-xl">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle className="flex flex-wrap items-center gap-2 font-mono text-base">
                  <Wrench className="h-4 w-4 text-primary" />
                  {selected.name}
                  <MetricBadge tone={mutating ? "warn" : "good"}>
                    {mutating ? <><ShieldAlert className="h-3 w-3" /> mutating</> : <><ShieldCheck className="h-3 w-3" /> read-only</>}
                  </MetricBadge>
                </DialogTitle>
                <DialogDescription className="line-clamp-3">{selected.description || "Governed tower tool"}</DialogDescription>
              </DialogHeader>

              <div className="space-y-3 overflow-y-auto pr-1" style={{ maxHeight: "55vh" }}>
                {mutating && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      Policy preview
                      {policyLoading && <span className="font-normal normal-case text-muted-foreground">consulting tower…</span>}
                    </p>
                    {policyLoading ? (
                      <div className="mt-2 h-4 w-40 animate-pulse rounded bg-amber-500/20" />
                    ) : policy ? (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        {policy.risk && <MetricBadge tone={/high|critical/i.test(policy.risk) ? "bad" : /medium|moderate/i.test(policy.risk) ? "warn" : "good"}>risk: {policy.risk}</MetricBadge>}
                        {policy.decision && <MetricBadge>decision: {policy.decision}</MetricBadge>}
                        {policy.allowed === false && <MetricBadge tone="bad">blocked by policy</MetricBadge>}
                        {policy.allowed === true && <MetricBadge tone="good">allowed</MetricBadge>}
                        {!policy.risk && !policy.decision && policy.allowed === undefined && (
                          <span className="text-[11px] text-muted-foreground">tower returned no explicit verdict — review arguments carefully</span>
                        )}
                      </div>
                    ) : (
                      <p className="mt-1 text-[11px] text-muted-foreground">preview unavailable — proceed with care</p>
                    )}
                  </div>
                )}

                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Arguments (JSON)</p>
                  <Textarea value={argsText} onChange={(e) => setArgsText(e.target.value)} rows={6} className="font-mono text-xs" spellCheck={false} aria-label="Tool arguments JSON" />
                </div>

                {mutating && (
                  <label className="flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-xs text-foreground/90 transition-colors hover:border-amber-500/40">
                    <input
                      type="checkbox"
                      checked={acknowledged}
                      onChange={(e) => setAcknowledged(e.target.checked)}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-amber-500"
                      aria-label="Acknowledge this tool may change tower state"
                    />
                    <span>
                      <span className="font-semibold">I understand</span> this tool can change tower state (create, rotate, deploy, send, or delete resources). Invoke deliberately.
                    </span>
                  </label>
                )}

                {callMutation.isPending && (
                  <div className="flex items-center gap-2 rounded-lg border p-3 text-sm text-muted-foreground">
                    <CircleStop className="h-4 w-4 animate-spin text-primary" />
                    Invoking through governed MCP gate…
                  </div>
                )}

                {result && (
                  <div>
                    <p className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Result
                      <MetricBadge tone={result.ok ? "good" : "bad"}>{result.ok ? "ok" : "error"}</MetricBadge>
                      <MetricBadge>{result.durationMs}ms</MetricBadge>
                    </p>
                    <JsonViewer data={result.error ? { error: result.error, result: result.result } : result.result} maxHeight={280} />
                  </div>
                )}
              </div>

              <DialogFooter className="gap-2">
                <Button variant="outline" onClick={() => setSelected(null)}>Close</Button>
                <Button
                  onClick={runTool}
                  disabled={callMutation.isPending || (mutating && !acknowledged)}
                  variant={mutating ? "destructive" : "default"}
                >
                  <Play className="mr-2 h-4 w-4" />
                  {mutating ? "Invoke (gated)" : "Invoke"}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <DocsSources />
    </div>
  );
}
