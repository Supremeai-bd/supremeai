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

function findGapBaselinePath(): string | null {
  for (const c of CANDIDATE_GAP_PATHS) {
    if (existsSync(c)) return c;
  }
  return null;
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
        const findings = Array.isArray(data.findings) ? data.findings : [];
        const n = limit ?? 20;
        const sample = findings.slice(0, n);
        const summary = {
          available: true,
          source: p,
          generatedAt: data.generated_at ?? data.generatedAt ?? null,
          totalFindings: findings.length,
          returned: sample.length,
          counts: data.stats ?? data.counts ?? null,
          findings: sample,
          note: "Frozen/unreachable modules from deployment-derived entrypoints. Modules may leave freely; adding requires deliberate commit. This is static analysis, not runtime health.",
        };
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
