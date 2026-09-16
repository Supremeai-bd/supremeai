"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { BookOpen, ChevronDown, Code2, Copy, ExternalLink, FileText, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { callTowerTool } from "@/lib/tower-gateway";
import { MetricBadge } from "./widgets";
import { cn } from "@/lib/utils";

/**
 * Docs Sources — the tower's curated documentation registry (docs_list /
 * docs_search). Lazy + collapsed by default so it never costs a tower call
 * unless the operator opens it.
 */

interface DocSource {
  name: string;
  url: string;
  description: string;
  category: string;
  relevance?: number;
}

function normalizeSources(payload: unknown): DocSource[] {
  let list: unknown[] = [];
  if (Array.isArray(payload)) list = payload;
  else if (payload && typeof payload === "object") {
    const rec = payload as Record<string, unknown>;
    const inner = rec.sources ?? rec.items ?? rec.docs ?? rec.results;
    if (Array.isArray(inner)) list = inner;
  }
  return list
    .map((it) => {
      const r = (it ?? {}) as Record<string, unknown>;
      return {
        name: String(r.name ?? r.title ?? "unknown"),
        url: String(r.url ?? r.link ?? "#"),
        description: String(r.description ?? r.desc ?? "").slice(0, 140),
        category: String(r.category ?? r.cat ?? "general"),
        relevance: typeof r.relevance === "number" ? r.relevance : undefined,
      };
    })
    .filter((d) => d.name !== "unknown" || d.url !== "#");
}

export function DocsSources() {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState("");
  const [reading, setReading] = React.useState<DocSource | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["docs-sources", q],
    queryFn: async () => {
      const r = q.trim()
        ? await callTowerTool("docs_search", { query: q.trim() }, { silent: true })
        : await callTowerTool("docs_list", {}, { silent: true });
      return r;
    },
    enabled: open,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const sources = React.useMemo(() => normalizeSources(data?.result), [data]);
  const categories = [...new Set(sources.map((s) => s.category))];

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="min-w-0">
        <CollapsibleTrigger asChild>
          <button className="flex w-full items-center gap-2 p-4 text-left" aria-expanded={open}>
            <BookOpen className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">Docs Sources</span>
            <span className="text-xs text-muted-foreground">tower documentation registry — list & search</span>
            {sources.length > 0 && <Badge variant="secondary" className="text-[10px]">{sources.length} sources</Badge>}
            <ChevronDown className={cn("ml-auto h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search docs sources — deploy, database, edge…"
                  className="pl-9 h-8"
                  aria-label="Search docs sources"
                />
              </div>
              {categories.length > 0 && (
                <div className="flex flex-wrap items-center gap-1">
                  {categories.slice(0, 6).map((c) => (
                    <Badge key={c} variant="outline" className="text-[10px] capitalize">{c}</Badge>
                  ))}
                </div>
              )}
              <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh docs sources">
                <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
              </Button>
            </div>

            {isLoading ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-16 animate-pulse rounded-lg bg-muted/40" />
                ))}
              </div>
            ) : isError || !data?.ok ? (
              <p className="py-4 text-xs text-muted-foreground">Docs registry unavailable ({(data?.error ?? "tower unreachable").slice(0, 80)}).</p>
            ) : sources.length === 0 ? (
              <p className="py-4 text-xs text-muted-foreground">No docs sources match “{q}”.</p>
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {sources.map((s, i) => (
                  <li key={`${s.name}-${i}`}>
                    <div
                      className={cn(
                        "group flex h-full items-start gap-2 rounded-lg border p-3 transition-colors",
                        reading?.url === s.url ? "border-primary/40 bg-primary/5" : "hover:border-primary/40 hover:bg-primary/5",
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="flex items-center gap-1.5 text-xs font-semibold">
                          <span className="truncate">{s.name}</span>
                          <MetricBadge>{s.category}</MetricBadge>
                          {s.relevance != null && <MetricBadge tone={s.relevance >= 0.5 ? "good" : "default"}>{Math.round(s.relevance * 100)}%</MetricBadge>}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{s.description || s.url}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-0.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground/70 hover:text-primary"
                          onClick={() => setReading(s)}
                          aria-label={`Read ${s.name} inline`}
                          title="Read inline (docs_fetch)"
                        >
                          <BookOpen className="h-3.5 w-3.5" />
                        </Button>
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/50 transition-colors hover:bg-muted hover:text-primary"
                          aria-label={`Open ${s.name} in new tab`}
                          title="Open original"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>

      <DocReader doc={reading} onClose={() => setReading(null)} />
    </Collapsible>
  );
}

/* ── Inline doc reader — fetches full page content via docs_fetch ─── */

function extractDocText(payload: unknown): { text: string; title: string | null; sourceHtml: string | null } {
  // Tower may return a plain string, {content}, {text}, {docs}, or nested JSON.
  let raw = payload;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const rec = raw as Record<string, unknown>;
    raw = rec.content ?? rec.text ?? rec.body ?? rec.docs ?? rec.result ?? rec.data ?? raw;
  }
  if (typeof raw === "string") {
    // Sometimes the string itself is JSON — try to unwrap once.
    if (raw.trimStart().startsWith("{") || raw.trimStart().startsWith("[")) {
      try {
        const inner = extractDocText(JSON.parse(raw));
        return { text: inner.text, title: inner.title, sourceHtml: inner.sourceHtml };
      } catch {
        /* keep as plain text */
      }
    }
    // docs_fetch often returns raw page HTML — extract readable text + title.
    if (/<html[\s>]|<head[\s>]|<body[\s>]|<div[\s>]|<meta[\s>]/i.test(raw)) {
      const titleMatch = raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
      const title = titleMatch ? decodeEntities(titleMatch[1]).trim().slice(0, 140) : null;
      return { text: htmlToText(raw), title, sourceHtml: raw };
    }
    return { text: raw, title: null, sourceHtml: null };
  }
  if (raw == null) return { text: "", title: null, sourceHtml: null };
  return { text: JSON.stringify(raw, null, 2), title: null, sourceHtml: null };
}

function decodeEntities(s: string): string {
  return s
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#x27;|&#39;|&apos;/gi, "'")
    .replace(/&lrm;|&rlm;/gi, "")
    .replace(/&#(\d+);/g, (_m, d) => { try { return String.fromCodePoint(Number(d)); } catch { return " "; } })
    .replace(/&#x([0-9a-f]+);/gi, (_m, h) => { try { return String.fromCodePoint(parseInt(h, 16)); } catch { return " "; } });
}

/**
 * HTML → readable markdown-ish text. docs_fetch returns raw page HTML, so the
 * reader converts it: headings become markdown, lists become bullets, links
 * become markdown links — then the markdown renderer takes over. Raw source
 * stays available via the Raw toggle.
 */
export function htmlToText(html: string): string {
  if (!/<[a-z!/][\s\S]*>/i.test(html)) return html;
  let t = html
    .replace(/<!doctype[^>]*>/gi, " ")
    .replace(/<\?xml[^>]*>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<svg[\s\S]*?<\/svg>/gi, " ")
    .replace(/<head[\s\S]*?<\/head>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<!--[\s\S]*$/g, " ") // truncated unterminated comment (fetch cap)
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<hr\s*\/?>/gi, "\n---\n")
    .replace(/<a [^>]*href=["']([^"']*)["'][^>]*>([\s\S]*?)<\/a>/gi, (_m, href, label) => {
      const txt = label.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
      if (!txt) return " ";
      return `[${txt}](${href})`;
    })
    .replace(/<h([1-6])[^>]*>/gi, (_m, l) => "\n\n" + "#".repeat(Number(l)) + " ")
    .replace(/<li[^>]*>/gi, "\n- ")
    .replace(/<p[^>]*>/gi, "\n\n")
    .replace(/<dt[^>]*>/gi, "\n\n")
    .replace(/<dd[^>]*>/gi, "\n- ")
    .replace(/<pre[^>]*>/gi, "\n\n```\n")
    .replace(/<\/pre>/gi, "\n```\n\n")
    .replace(/<td[^>]*>/gi, " | ")
    .replace(/<th[^>]*>/gi, " | ")
    .replace(/<\/tr>/gi, " |\n")
    .replace(/<\/?[a-z][^>]*>/gi, " ");
  t = decodeEntities(t);
  t = t
    .replace(/[ \t]+/g, " ")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/^[ \t]+|[ \t]+$/gm, "")
    .replace(/<[a-z!/-]*$/i, ""); // trailing tag fragment from truncated fetch
  return t.trim();
}

/** Heuristic: does this look like markdown worth rendering? */
function looksLikeMarkdown(text: string): boolean {
  if (text.length < 24) return false;
  return /(^|\n)#{1,6}\s+|\n\s*[-*+]\s+|^\s*\d+\.\s+|```|\*\*[^*\n]+\*\*|(^|\n)\|.+|\]\([^)\s]{4,}\)/m.test(text);
}

/** Styled markdown components — compact mission-deck typography. */
const MD_COMPONENTS = {
  h1: (p: React.ComponentPropsWithoutRef<"h1">) => <h1 className="mb-2 mt-4 border-b pb-1 text-base font-bold first:mt-0" {...p} />,
  h2: (p: React.ComponentPropsWithoutRef<"h2">) => <h2 className="mb-1.5 mt-4 text-sm font-bold" {...p} />,
  h3: (p: React.ComponentPropsWithoutRef<"h3">) => <h3 className="mb-1 mt-3 text-[13px] font-semibold" {...p} />,
  h4: (p: React.ComponentPropsWithoutRef<"h4">) => <h4 className="mb-1 mt-2 text-xs font-semibold" {...p} />,
  p: (p: React.ComponentPropsWithoutRef<"p">) => <p className="my-1.5 text-[12.5px] leading-relaxed" {...p} />,
  ul: (p: React.ComponentPropsWithoutRef<"ul">) => <ul className="my-1.5 list-disc space-y-0.5 pl-5 text-[12.5px] leading-relaxed" {...p} />,
  ol: (p: React.ComponentPropsWithoutRef<"ol">) => <ol className="my-1.5 list-decimal space-y-0.5 pl-5 text-[12.5px] leading-relaxed" {...p} />,
  li: (p: React.ComponentPropsWithoutRef<"li">) => <li className="pl-0.5" {...p} />,
  a: (p: React.ComponentPropsWithoutRef<"a">) => <a className="text-primary underline underline-offset-2 hover:opacity-80" target="_blank" rel="noreferrer" {...p} />,
  blockquote: (p: React.ComponentPropsWithoutRef<"blockquote">) => <blockquote className="my-2 border-l-2 border-primary/40 pl-3 text-[12.5px] italic text-muted-foreground" {...p} />,
  code: (p: React.ComponentPropsWithoutRef<"code">) => {
    const inline = !String(p.className ?? "").includes("language-");
    return inline ? (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-primary/90" {...p} />
    ) : (
      <code className="font-mono text-[11px]" {...p} />
    );
  },
  pre: (p: React.ComponentPropsWithoutRef<"pre">) => <pre className="my-2 overflow-auto rounded-md border bg-zinc-950/95 p-2.5 text-emerald-300/90" {...p} />,
  table: (p: React.ComponentPropsWithoutRef<"table">) => <table className="my-2 w-full border-collapse text-[11.5px]" {...p} />,
  th: (p: React.ComponentPropsWithoutRef<"th">) => <th className="border bg-muted/50 px-2 py-1 text-left font-semibold" {...p} />,
  td: (p: React.ComponentPropsWithoutRef<"td">) => <td className="border px-2 py-1 align-top" {...p} />,
  hr: () => <hr className="my-3 border-border" />,
};

function DocReader({ doc, onClose }: { doc: DocSource | null; onClose: () => void }) {
  const [rawMode, setRawMode] = React.useState(false);
  // Fetch only while a doc is selected; one-shot (no polling), fresh per open.
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["doc-fetch", doc?.url],
    queryFn: () => callTowerTool("docs_fetch", { url: doc!.url }),
    enabled: !!doc,
    staleTime: 10 * 60_000,
    retry: false,
  });

  const extracted = React.useMemo(() => (data?.result !== undefined ? extractDocText(data.result) : null), [data]);
  const words = extracted ? extracted.text.trim().split(/\s+/).filter(Boolean).length : 0;
  const isMd = looksLikeMarkdown(extracted?.text ?? "");
  const hasSource = !!extracted?.sourceHtml;
  // Tower docs_fetch caps the payload (~5KB, mostly <head>) — surface that.
  const truncated = !!extracted?.sourceHtml && extracted.sourceHtml.length >= 4_800;
  const renderMd = isMd && !rawMode;

  const copyDoc = async () => {
    if (!extracted?.text) return;
    try {
      await navigator.clipboard.writeText(extracted.text);
      toast.success("Doc content copied to clipboard");
    } catch {
      toast.error("Clipboard unavailable in this context");
    }
  };

  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 sm:max-w-2xl">
        <DialogHeader className="min-w-0 pr-8">
          <DialogTitle className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
            <FileText className="h-4 w-4 shrink-0 text-primary" />
            <span className="truncate">{extracted?.title ?? doc?.name ?? "Document"}</span>
            {words > 0 && <MetricBadge>{words.toLocaleString()} words</MetricBadge>}
            {words > 0 && (
              <MetricBadge tone={isMd ? "good" : "default"}>
                {isMd ? "markdown" : "plain text"}
              </MetricBadge>
            )}
            {truncated && (
              <MetricBadge tone="warn" >excerpt — tower fetch cap</MetricBadge>
            )}
          </DialogTitle>
          <DialogDescription className="truncate text-[11px]">{doc?.url}</DialogDescription>
        </DialogHeader>

        <ScrollArea className="min-h-0 flex-1 rounded-md border bg-muted/20">
          <div className="p-4">
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="h-3 animate-pulse rounded bg-muted/60" style={{ width: `${72 + ((i * 13) % 28)}%` }} />
                ))}
                <p className="pt-2 text-[11px] text-muted-foreground">Fetching via tower docs_fetch…</p>
              </div>
            ) : isError || !data?.ok ? (
              <p className="text-xs text-muted-foreground">
                Could not fetch this page ({(data?.error ?? (error as Error)?.message ?? "tower unreachable").slice(0, 120)}).
              </p>
            ) : renderMd ? (
              <div className="max-w-none break-words text-foreground/90">
                <ReactMarkdown components={MD_COMPONENTS}>{extracted?.text}</ReactMarkdown>
              </div>
            ) : rawMode && extracted?.sourceHtml ? (
              <pre className="whitespace-pre-wrap break-words font-mono text-[10.5px] leading-relaxed text-muted-foreground/80">{extracted.sourceHtml.slice(0, 20_000)}</pre>
            ) : (
              <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-foreground/90">{extracted?.text}</pre>
            )}
          </div>
        </ScrollArea>

        <div className="flex items-center gap-2 pt-3">
          <span className="min-w-0 flex-1 truncate text-[10px] uppercase tracking-wide text-muted-foreground/60">
            tower tool · docs_fetch · silent off (journaled)
          </span>
          {hasSource && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => setRawMode((r) => !r)}
              aria-pressed={rawMode}
              aria-label={rawMode ? "Switch to rendered view" : "Switch to raw source view"}
            >
              <Code2 className="h-3 w-3" />
              {rawMode ? "Rendered" : "Raw source"}
            </Button>
          )}
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={copyDoc} disabled={!extracted?.text}>
            <Copy className="mr-1 h-3 w-3" /> Copy
          </Button>
          {doc && (
            <a href={doc.url} target="_blank" rel="noreferrer">
              <Button variant="outline" size="sm" className="h-7 text-xs">
                <ExternalLink className="mr-1 h-3 w-3" /> Original
              </Button>
            </a>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
