"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Network, Search, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { callTowerTool } from "@/lib/tower-gateway";
import { MetricBadge } from "./widgets";

/* ── Tower memory payloads (defensive) ─────────────────────────────── */

interface GraphEntity {
  name: string;
  entityType?: string;
  observations?: string[];
}
interface GraphRelation {
  from?: string;
  source?: string;
  to?: string;
  target?: string;
  relationType?: string;
}
interface GraphData {
  entities: GraphEntity[];
  relations: GraphRelation[];
}

function normalizeGraph(payload: unknown): GraphData {
  const rec = (payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {}) ?? {};
  const entities = (rec.entities ?? rec.nodes ?? []) as GraphEntity[];
  const relations = (rec.relations ?? rec.edges ?? []) as GraphRelation[];
  return {
    entities: Array.isArray(entities) ? entities.filter((e) => e && e.name) : [],
    relations: Array.isArray(relations) ? relations : [],
  };
}

const TYPE_COLORS: Record<string, string> = {
  service: "#10b981",
  concept: "#8b5cf6",
  person: "#f59e0b",
  tool: "#14b8a6",
  decision: "#f97316",
  system: "#22d3ee",
  default: "#64748b",
};

/* ── Interactive graph SVG ─────────────────────────────────────────── */

function GraphView({ graph }: { graph: GraphData }) {
  const [hover, setHover] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<GraphEntity | null>(null);

  const W = 560;
  const H = 340;
  const CX = W / 2;
  const CY = H / 2;
  const R = Math.min(W, H) / 2 - 58;

  const shown = graph.entities.slice(0, 22);
  const positions = (() => {
    const map = new Map<string, { x: number; y: number }>();
    shown.forEach((e, i) => {
      const angle = (2 * Math.PI * i) / Math.max(shown.length, 1) - Math.PI / 2;
      map.set(e.name, { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) });
    });
    return map;
  })();

  const nodeR = (e: GraphEntity) => 7 + Math.min((e.observations?.length ?? 0) * 1.2, 7);
  const relFrom = (r: GraphRelation) => r.from ?? r.source ?? "";
  const relTo = (r: GraphRelation) => r.to ?? r.target ?? "";

  const related = (name: string) =>
    graph.relations.filter((r) => relFrom(r) === name || relTo(r) === name).length;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg border bg-muted/20" role="img" aria-label="Knowledge graph">
        {/* edges */}
        {graph.relations.slice(0, 120).map((r, i) => {
          const a = positions.get(relFrom(r));
          const b = positions.get(relTo(r));
          if (!a || !b) return null;
          const active = hover && (relFrom(r) === hover || relTo(r) === hover);
          return (
            <line
              key={i}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={active ? "hsl(var(--primary))" : "currentColor"}
              className="text-border"
              strokeWidth={active ? 1.8 : 0.8}
              strokeOpacity={active ? 0.9 : hover ? 0.12 : 0.45}
            />
          );
        })}
        {/* nodes */}
        {shown.map((e) => {
          const p = positions.get(e.name);
          if (!p) return null;
          const color = TYPE_COLORS[(e.entityType ?? "default").toLowerCase()] ?? TYPE_COLORS.default;
          const dim = hover && hover !== e.name && related(hover) > 0 && !graph.relations.some((r) => (relFrom(r) === hover && relTo(r) === e.name) || (relTo(r) === hover && relFrom(r) === e.name));
          return (
            <g
              key={e.name}
              transform={`translate(${p.x},${p.y})`}
              className="cursor-pointer"
              opacity={dim ? 0.25 : 1}
              onMouseEnter={() => setHover(e.name)}
              onMouseLeave={() => setHover(null)}
              onClick={() => setSelected(e)}
            >
              <circle r={nodeR(e) + 4} fill={color} opacity={hover === e.name ? 0.25 : 0} />
              <circle r={nodeR(e)} fill={color} fillOpacity={0.85} stroke="hsl(var(--background))" strokeWidth={1.5} />
              <text y={nodeR(e) + 11} textAnchor="middle" className="fill-foreground" style={{ fontSize: 8.5, fontWeight: 600 }}>
                {e.name.length > 16 ? `${e.name.slice(0, 15)}…` : e.name}
              </text>
            </g>
          );
        })}
        {graph.entities.length > 22 && (
          <text x={W - 10} y={H - 10} textAnchor="end" className="fill-muted-foreground" style={{ fontSize: 9 }}>
            +{graph.entities.length - 22} more entities
          </text>
        )}
      </svg>

      {/* Selected entity detail */}
      {selected && (
        <div className="mt-3 rounded-lg border bg-muted/30 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-bold">{selected.name}</p>
            <button onClick={() => setSelected(null)} className="text-[10px] text-muted-foreground hover:text-foreground">close</button>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <MetricBadge>{selected.entityType ?? "entity"}</MetricBadge>
            <MetricBadge tone="good">{related(selected.name)} relations</MetricBadge>
            <MetricBadge>{selected.observations?.length ?? 0} observations</MetricBadge>
          </div>
          <ScrollArea className="mt-2 max-h-24">
            <ul className="space-y-1 text-[11px] text-muted-foreground">
              {(selected.observations ?? []).map((o, i) => (
                <li key={i} className="leading-relaxed">• {o}</li>
              ))}
              {(selected.observations?.length ?? 0) === 0 && <li>No observations recorded.</li>}
            </ul>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

/* ── Search result rows ───────────────────────────────────────────── */

function resultRows(payload: unknown): { title: string; score?: number; text: string }[] {
  const rec = (payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {}) ?? {};
  const list = (rec.results ?? rec.matches ?? rec.items ?? (Array.isArray(payload) ? payload : [])) as Record<string, unknown>[];
  if (!Array.isArray(list)) return [];
  return list.slice(0, 8).map((r) => ({
    title: String(r.name ?? r.title ?? r.id ?? r.entity ?? "result"),
    score: typeof r.score === "number" ? r.score : typeof r.similarity === "number" ? r.similarity : undefined,
    text: String(r.text ?? r.content ?? r.observation ?? r.fact ?? r.snippet ?? JSON.stringify(r)).slice(0, 260),
  }));
}

/* ── Section component ────────────────────────────────────────────── */

export function KnowledgeGraphPanel() {
  const [nodeQ, setNodeQ] = React.useState("");
  const [semQ, setSemQ] = React.useState("");

  const graph = useQuery({
    queryKey: ["kg-graph"],
    queryFn: async (): Promise<GraphData> => {
      const r = await callTowerTool("memory_read_graph", {});
      return normalizeGraph(r.result);
    },
    staleTime: 60_000,
    retry: 1,
  });

  const nodes = useQuery({
    queryKey: ["kg-nodes", nodeQ],
    enabled: nodeQ.trim().length > 1,
    queryFn: async () => {
      const r = await callTowerTool("memory_search_nodes", { query: nodeQ.trim() });
      return resultRows(r.result);
    },
    retry: 1,
  });

  const semantic = useQuery({
    queryKey: ["kg-semantic", semQ],
    enabled: semQ.trim().length > 1,
    queryFn: async () => {
      const r = await callTowerTool("memory_search_semantic", { query: semQ.trim(), k: 6 });
      return resultRows(r.result);
    },
    retry: 1,
  });

  const graphData = graph.data ?? { entities: [], relations: [] };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <Network className="h-4 w-4 text-primary" />
          Knowledge Graph & Semantic Search
          {graphData.entities.length > 0 && (
            <Badge variant="secondary" className="text-[10px]">
              {graphData.entities.length} entities · {graphData.relations.length} relations
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-5">
          {/* Graph */}
          <div className="lg:col-span-3">
            {graph.isLoading ? (
              <Skeleton className="h-[340px] w-full" />
            ) : graphData.entities.length === 0 ? (
              <div className="flex h-[340px] flex-col items-center justify-center gap-2 rounded-lg border bg-muted/20 text-center text-muted-foreground">
                <Network className="h-8 w-8 opacity-40" />
                <p className="max-w-xs text-xs">
                  The knowledge graph is empty. Tower memory tools (memory_create_entities / memory_add_observations) populate it — entities appear here live.
                </p>
              </div>
            ) : (
              <GraphView graph={graphData} />
            )}
          </div>

          {/* Searches */}
          <div className="space-y-4 lg:col-span-2">
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                <Search className="h-3 w-3" /> Node search
              </p>
              <Input
                value={nodeQ}
                onChange={(e) => setNodeQ(e.target.value)}
                placeholder="entity name… (memory_search_nodes)"
                className="h-8 text-xs"
                aria-label="Search knowledge graph nodes"
              />
              {nodeQ.trim().length > 1 && (
                <ScrollArea className="mt-2 max-h-36 rounded-lg border">
                  {nodes.isLoading ? (
                    <div className="space-y-1.5 p-2.5">
                      <Skeleton className="h-8 w-full" />
                      <Skeleton className="h-8 w-full" />
                    </div>
                  ) : (nodes.data?.length ?? 0) === 0 ? (
                    <p className="p-2.5 text-[11px] text-muted-foreground">No nodes matched.</p>
                  ) : (
                    <ul className="divide-y divide-border/60">
                      {nodes.data!.map((r, i) => (
                        <li key={i} className="px-2.5 py-1.5">
                          <p className="truncate text-[11px] font-semibold">{r.title}</p>
                          <p className="line-clamp-2 text-[10px] text-muted-foreground">{r.text}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </ScrollArea>
              )}
            </div>

            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                <Sparkles className="h-3 w-3" /> Semantic search
              </p>
              <div className="flex gap-2">
                <Input
                  value={semQ}
                  onChange={(e) => setSemQ(e.target.value)}
                  placeholder="meaning-based search… (memory_search_semantic)"
                  className="h-8 text-xs"
                  aria-label="Semantic search over tower vector memory"
                />
                <Button size="sm" variant="outline" className="h-8 shrink-0 px-2" onClick={() => semantic.refetch()} disabled={semQ.trim().length < 2} aria-label="Run semantic search">
                  Go
                </Button>
              </div>
              {semQ.trim().length > 1 && (semantic.isFetching || semantic.data) && (
                <ScrollArea className="mt-2 max-h-36 rounded-lg border">
                  {semantic.isFetching ? (
                    <div className="space-y-1.5 p-2.5">
                      <Skeleton className="h-8 w-full" />
                      <Skeleton className="h-8 w-full" />
                    </div>
                  ) : (semantic.data?.length ?? 0) === 0 ? (
                    <p className="p-2.5 text-[11px] text-muted-foreground">No semantic matches.</p>
                  ) : (
                    <ul className="divide-y divide-border/60">
                      {semantic.data!.map((r, i) => (
                        <li key={i} className="px-2.5 py-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-[11px] font-semibold">{r.title}</p>
                            {r.score != null && <MetricBadge tone={r.score > 0.7 ? "good" : "default"}>{r.score.toFixed(2)}</MetricBadge>}
                          </div>
                          <p className="line-clamp-2 text-[10px] text-muted-foreground">{r.text}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </ScrollArea>
              )}
            </div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] leading-relaxed text-muted-foreground/70"
            >
              Graph + vector memory live in the tower&apos;s Python memory sidecar (Supabase/pgvector + Qdrant) — zero local cost, one governed surface.
            </motion.p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
