import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import {
  findGapBaselinePath,
  normalizeArchitectureGapReport,
  registerArchitectureGapTools,
} from "./src/tools/architecture.tools.js";
import {
  CANONICAL_TOPOLOGY_DEFAULTS,
  loadAuthoritativeServices,
} from "./src/diagnostics/service_manifest.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");

// বাংলা মন্তব্য: ১) বাস্তব `docs/generated/architecture_gap_map.json` ও `architecture_gap_baseline.json`-এ Hollow-Zero রিগ্রেশন পরীক্ষা।
const resolvedGapPath = findGapBaselinePath();
assert.ok(resolvedGapPath, "Expected architecture gap JSON artifact to exist in repo");

const liveRaw = JSON.parse(readFileSync(resolvedGapPath, "utf-8")) as Record<string, unknown>;
const liveNormalized = normalizeArchitectureGapReport(liveRaw, resolvedGapPath, 15);
assert.equal(liveNormalized.available, true);
assert.ok(
  liveNormalized.totalFindings > 0,
  `architecture.gaps must not return hollow zero on populated artifact (got ${liveNormalized.totalFindings})`,
);
assert.equal(liveNormalized.returned, 15);
assert.ok(liveNormalized.counts !== null, "counts summary must be populated from modern schema");
assert.equal(typeof liveNormalized.counts?.modules, "number");
assert.equal(typeof liveNormalized.counts?.unreachable, "number");
assert.equal(liveNormalized.counts?.danglingCount, 0);

// বাংলা মন্তব্য: ২) ফ্যালব্যাক `scripts/ops/architecture_gap_baseline.json` স্কিমা পরীক্ষা।
const baselinePath = path.join(REPO_ROOT, "scripts", "ops", "architecture_gap_baseline.json");
const baselineRaw = JSON.parse(readFileSync(baselinePath, "utf-8")) as Record<string, unknown>;
const baselineNormalized = normalizeArchitectureGapReport(baselineRaw, baselinePath, 10);
assert.ok(baselineNormalized.totalFindings > 0);
assert.equal(baselineNormalized.returned, 10);
assert.equal(baselineNormalized.counts?.unreachable, baselineRaw._count);

// বাংলা মন্তব্য: ৩) লিগ্যাসি `{ findings, counts }` ব্যাকওয়ার্ড-কম্প্যাটিবিলিটি পরীক্ষা।
const legacyNormalized = normalizeArchitectureGapReport(
  {
    generated_at: "2026-11-26T00:00:00Z",
    findings: [{ module: "legacy.dead" }, { module: "legacy.unused" }],
    counts: { unreachable: 2 },
  },
  "/tmp/legacy.json",
  1,
);
assert.equal(legacyNormalized.totalFindings, 2);
assert.equal(legacyNormalized.returned, 1);
assert.deepEqual(legacyNormalized.counts, { unreachable: 2 });

// বাংলা মন্তব্য: ৪) ইন-মেমরি MCP ট্রান্সপোর্টে `architecture.gaps` টুল এন্ড-টু-এন্ড যাচাই।
const server = new McpServer({ name: "test-arch-gaps", version: "1.0.1" });
registerArchitectureGapTools(server);
const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
await server.connect(serverTransport);
const client = new Client({ name: "test-arch-client", version: "1.0.0" });
await client.connect(clientTransport);

const res = await client.callTool({ name: "architecture.gaps", arguments: { limit: 5 } });
const contentList = Array.isArray(res.content) ? res.content : [];
const textBlock = contentList[0] as { type?: string; text?: string } | undefined;
assert.ok(textBlock?.text, "MCP tool must return JSON text payload");
const parsedToolPayload = JSON.parse(textBlock.text) as {
  available: boolean;
  totalFindings: number;
  returned: number;
  counts: Record<string, unknown> | null;
};
assert.equal(parsedToolPayload.available, true);
assert.ok(parsedToolPayload.totalFindings > 0);
assert.equal(parsedToolPayload.returned, 5);
assert.ok(parsedToolPayload.counts !== null);
await client.close();

// বাংলা মন্তব্য: ৫) ফ্রন্টএন্ড ক্যানোনিকাল হেলথ ও রিলিজ পাথ (SPA HTML fallback `/release` বর্জন) যাচাই।
assert.equal(CANONICAL_TOPOLOGY_DEFAULTS.frontend?.healthPath, "/api/health");
assert.equal(CANONICAL_TOPOLOGY_DEFAULTS.frontend?.readinessPath, "/api/health");
assert.equal(CANONICAL_TOPOLOGY_DEFAULTS.frontend?.releasePath, "/api/releases/latest");

const authoritative = loadAuthoritativeServices();
assert.equal(authoritative.frontend?.healthPath, "/api/health");
assert.equal(authoritative.frontend?.readinessPath, "/api/health");
assert.equal(authoritative.frontend?.releasePath, "/api/releases/latest");

console.log("[architecture-gaps & frontend-manifest] PASS — schema normalization + manifest paths verified");
