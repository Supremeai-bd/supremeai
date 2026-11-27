import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, readFileSync } from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../../..");

const CANDIDATE_GAP_PATHS = [
  path.join(REPO_ROOT, "docs", "generated", "architecture_gap_map.json"),
  path.join(process.cwd(), "docs", "generated", "architecture_gap_map.json"),
  path.join(__dirname, "../../../../docs/generated", "architecture_gap_map.json"),
  "/app/docs/generated/architecture_gap_map.json",
  // Fallback: frozen baseline (manually curated)
  path.join(REPO_ROOT, "scripts", "ops", "architecture_gap_baseline.json"),
  path.join(process.cwd(), "scripts", "ops", "architecture_gap_baseline.json"),
];

export function findGapBaselinePath(): string | null {
  for (const c of CANDIDATE_GAP_PATHS) {
    if (existsSync(c)) return c;
  }
  return null;
}

export interface ArchitectureGapFinding {
  kind: "dangling_reference" | "unreachable_module" | "legacy_finding";
  module?: string;
  [key: string]: unknown;
}

export interface ArchitectureGapSummary {
  available: boolean;
  source: string;
  generatedAt: unknown;
  generatedBy: unknown;
  totalFindings: number;
  returned: number;
  counts: Record<string, unknown> | null;
  findings: unknown[];
  note: string;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/**
 * বাংলা মন্তব্য: `architecture_gap_guardian.py` এখন `unreachable_modules`, `reachability` ও `gaps`
 * কী-তে ডেটা জেনারেট করে; আগে শুধু পুরোনো `findings`/`counts` খোঁজায় লাইভে মিথ্যা শূন্য (`totalFindings: 0`)
 * রিটার্ন হচ্ছিল। এখানে নতুন ও লিগ্যাসি উভয় স্কিমা নির্ভুলভাবে নরমালাইজ করা হয়েছে।
 */
export function normalizeArchitectureGapReport(
  data: Record<string, unknown>,
  source: string,
  limit = 20,
): ArchitectureGapSummary {
  const n = Math.max(1, Math.min(50, limit));
  const legacyFindings = Array.isArray(data.findings) ? data.findings : null;

  const graph = asRecord(data.graph);
  const entrypoints = asRecord(data.entrypoints);
  const reachability = asRecord(data.reachability);
  const gaps = asRecord(data.gaps);

  const danglingRaw = Array.isArray(gaps?.dangling_references) ? gaps.dangling_references : [];
  const unreachableRaw = Array.isArray(data.unreachable_modules) ? data.unreachable_modules : [];
  const unattributedRaw = Array.isArray(data.reachable_but_unattributed)
    ? data.reachable_but_unattributed
    : [];

  let allFindings: unknown[];
  if (legacyFindings !== null) {
    allFindings = legacyFindings;
  } else {
    const danglingFindings: ArchitectureGapFinding[] = danglingRaw.map((item) => {
      const rec = asRecord(item);
      return rec
        ? { kind: "dangling_reference", ...rec }
        : { kind: "dangling_reference", module: String(item) };
    });
    const unreachableFindings: ArchitectureGapFinding[] = unreachableRaw.map((mod) => ({
      kind: "unreachable_module",
      module: String(mod),
    }));
    allFindings = [...danglingFindings, ...unreachableFindings];
  }

  const legacyCounts = asRecord(data.stats) ?? asRecord(data.counts);
  const hasModernMetadata =
    graph !== null ||
    entrypoints !== null ||
    reachability !== null ||
    gaps !== null ||
    Array.isArray(data.unreachable_modules) ||
    typeof data._count === "number";

  const derivedCounts: Record<string, unknown> | null = hasModernMetadata
    ? {
        modules: graph?.modules ?? null,
        edges: graph?.edges ?? null,
        entrypointsFound:
          entrypoints?.found ??
          (Array.isArray(data._entrypoints) ? data._entrypoints.length : null),
        entrypointsMissing: entrypoints?.missing ?? null,
        reachable: reachability?.reachable ?? null,
        unreachable:
          reachability?.unreachable ??
          (typeof data._count === "number" ? data._count : unreachableRaw.length),
        reachablePct: reachability?.reachable_pct ?? null,
        danglingCount:
          typeof gaps?.dangling_count === "number" ? gaps.dangling_count : danglingRaw.length,
        unverifiedCount: gaps?.unverified_count ?? null,
        stringHintCount: gaps?.string_hint_count ?? null,
        unresolvedServices: gaps?.unresolved_services ?? null,
        reachableButUnattributed: Array.isArray(data.reachable_but_unattributed)
          ? unattributedRaw.length
          : null,
      }
    : null;

  const sample = allFindings.slice(0, n);
  return {
    available: true,
    source,
    generatedAt: data.generated_at ?? data.generatedAt ?? null,
    generatedBy: data.generated_by ?? data._derived_from ?? null,
    totalFindings: allFindings.length,
    returned: sample.length,
    counts: legacyCounts ?? derivedCounts,
    findings: sample,
    note: "Frozen/unreachable modules from deployment-derived entrypoints. Modules may leave freely; adding requires deliberate commit. This is static analysis, not runtime health.",
  };
}

export function registerArchitectureGapTools(server: McpServer): void {
  server.tool(
    "architecture.gaps",
    "Read the latest architecture gap baseline (dead/unreachable modules, floating modules) produced by architecture_gap_guardian. Returns counts + sample findings. Data is from CI artifact, not a live scan.",
    {
      limit: z.number().int().min(1).max(50).optional().describe("Max findings to return (default 20)"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ limit }) => {
      const p = findGapBaselinePath();
      if (!p) {
        return {
          isError: true,
          content: [{ type: "text", text: JSON.stringify({ available: false, reason: "architecture_gap_baseline.json not found on disk", hint: "Run scripts/ci/architecture_gap_guardian.py in CI first." }, null, 2) }],
        };
      }
      try {
        const raw = readFileSync(p, "utf-8");
        const data = JSON.parse(raw) as Record<string, unknown>;
        const summary = normalizeArchitectureGapReport(data, p, limit ?? 20);
        return { content: [{ type: "text", text: JSON.stringify(summary, null, 2) }] };
      } catch (err) {
        return {
          isError: true,
          content: [{ type: "text", text: JSON.stringify({ available: false, reason: (err as Error).message }, null, 2) }],
        };
      }
    }
  );
}
