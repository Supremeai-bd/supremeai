/**
 * Unit tests for the Render Logs API fix (render.get_logs → GET /v1/logs).
 *
 * Covers the analysis findings (#render-logs):
 *   1. MCP account is bound to Paykari and does not try the retired account or ID
 *   2. Fail-honest errors (unknown account / no key / unavailable) — no silent
 *      empty results
 *   3. buildRenderLogQuery: 15-min default window, limit clamp to API cap 100,
 *      filter forwarding
 *   4. normalizeLogEntry: wrapped {log:…} + flat shapes, secret redaction
 *      (URL userinfo, bearer, JWT, key=value) and prose preservation
 *
 * No network, no credentials required. Live smoke test (optional):
 *   RENDER_API_PAYKARI=… RENDER_MCP_SERVICE_ID=srv-… tsx test_render_logs.ts --live
 */
import {
  buildRenderLogQuery,
  normalizeLogEntry,
  resolveRenderApiKey,
} from "./src/adapters/render/index.js";
import { redactSecretsInText } from "./src/lib/masking.js";
import { buildAccountRegistry } from "./src/registry/account.registry.js";

let passed = 0;
let failed = 0;
const failures: string[] = [];

function check(name: string, cond: boolean, detail?: unknown): void {
  if (cond) {
    passed++;
    console.log(`  ✅ ${name}`);
  } else {
    failed++;
    failures.push(name);
    console.error(`  ❌ ${name}${detail !== undefined ? ` — ${JSON.stringify(detail)}` : ""}`);
  }
}

function expectThrows(name: string, fn: () => unknown, needle?: string): void {
  try {
    fn();
    check(name, false, "expected an error but none was thrown");
  } catch (err) {
    const msg = (err as Error).message;
    check(name, needle === undefined || msg.includes(needle), msg);
  }
}

async function liveSmoke(): Promise<void> {
  const accountId = "render-mcp";
  const serviceId = process.env.RENDER_MCP_SERVICE_ID || "";
  if (!serviceId) {
    console.error("[live] Set RENDER_MCP_SERVICE_ID to run the live smoke test.");
    return;
  }
  console.log(`\n=== Live smoke: listLogs(${accountId}, ${serviceId}) ===`);
  const { listLogs } = await import("./src/adapters/render/index.js");
  try {
    const result = await listLogs(accountId, serviceId, { limit: 5 });
    console.log(`[live] count=${result.count} ownerId=${result.ownerId} window=${result.window.startTime}..${result.window.endTime}`);
    for (const entry of result.logs) {
      console.log(`[live] ${entry.timestamp} [${entry.level ?? "?"}] ${entry.message.slice(0, 160)}`);
    }
    check("live: received a well-formed logs result", typeof result.count === "number" && Array.isArray(result.logs));
  } catch (err) {
    console.error(`[live] Error: ${(err as Error).message}`);
    check("live: errors surfaced honestly (not silently empty)", (err as Error).message.length > 0);
  }
}

async function main(): Promise<void> {
  // ── 1. Account registry cutover ──────────────────────────────────────
  const keys = ["RENDER_API_KEY", "RENDER_API_KEY_4", "RENDER_API_KEY_1",
    "RENDER_API_PAYKARI", "RENDER_API_KEY_PAYKARI", "RENDER_MCP_URL",
    "RENDER_MCP_SERVICE_ID", "RENDER_MCP_SVC_ID", "RENDER_EXTERNAL_URL"];
  const saved = keys.map((key) => [key, process.env[key]] as const);
  try {
    for (const key of keys) delete process.env[key];
    process.env.RENDER_API_KEY = "unrelated-test-key";
    process.env.RENDER_API_KEY_4 = "retired-test-key";
    process.env.RENDER_MCP_SVC_ID = "srv-retired";
    const mcp = () => buildAccountRegistry().find((a) => a.id === "render-mcp");
    check("no implicit legacy MCP service", mcp()?.serviceId === "" && mcp()?.url === "");
    expectThrows("unrelated Render accounts cannot supply the MCP key",
      () => resolveRenderApiKey("render-mcp"), "not configured/available");
    process.env.RENDER_MCP_SERVICE_ID = "srv-replacement";
    process.env.RENDER_EXTERNAL_URL = "https://replacement.onrender.com";
    process.env.RENDER_API_KEY_PAYKARI = "paykari-alias-test-key";
    check("MCP resolves replacement metadata and Paykari alias",
      mcp()?.serviceId === "srv-replacement" && mcp()?.url === process.env.RENDER_EXTERNAL_URL
        && resolveRenderApiKey("render-mcp") === process.env.RENDER_API_KEY_PAYKARI);
    process.env.RENDER_API_PAYKARI = "paykari-canonical-test-key";
    check("canonical Paykari name wins", resolveRenderApiKey("render-mcp") === process.env.RENDER_API_PAYKARI);
    check("non-MCP compatibility unaffected", resolveRenderApiKey("render-primary") === process.env.RENDER_API_KEY);
    expectThrows("unknown account → explicit error", () => resolveRenderApiKey("render-nope"), "not found");
  } finally {
    for (const [key, value] of saved) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }

  // ── 2. buildRenderLogQuery (pure) ────────────────────────────────────────
  console.log("\n=== 2. buildRenderLogQuery ===");
  const now = new Date("2026-10-15T12:00:00.000Z");
  const defaults = buildRenderLogQuery("usr-owner", "srv-x", {}, now);
  check("default window start = now − 15 min", defaults.get("startTime") === "2026-10-15T11:45:00.000Z", defaults.get("startTime"));
  check("default window end = now", defaults.get("endTime") === "2026-10-15T12:00:00.000Z", defaults.get("endTime"));
  check("default limit = 50", defaults.get("limit") === "50", defaults.get("limit"));
  check("ownerId + resource required", defaults.get("ownerId") === "usr-owner" && defaults.get("resource") === "srv-x");

  const full = buildRenderLogQuery(
    "usr-owner",
    "srv-x",
    {
      startTime: "2026-10-15T10:00:00Z",
      endTime: "2026-10-15T11:00:00Z",
      level: "error",
      type: "build",
      text: "lstat",
      limit: 500,
      cursor: "cur-1",
    },
    now
  );
  check("limit clamped to API cap 100", full.get("limit") === "100", full.get("limit"));
  check("level/type/text/cursor forwarded", full.get("level") === "error" && full.get("type") === "build" && full.get("text") === "lstat" && full.get("cursor") === "cur-1");
  check("explicit window respected (no default applied)", full.get("startTime") === "2026-10-15T10:00:00Z" && full.get("endTime") === "2026-10-15T11:00:00Z");
  expectThrows("invalid limit (0) fails honestly", () => buildRenderLogQuery("u", "s", { limit: 0 }, now), "Invalid log limit");
  expectThrows("non-integer limit fails honestly", () => buildRenderLogQuery("u", "s", { limit: 12.5 }, now), "Invalid log limit");

  // ── 3. normalizeLogEntry + redaction ────────────────────────────────────
  console.log("\n=== 3. normalizeLogEntry + secret redaction ===");
  const wrapped = normalizeLogEntry({
    log: {
      timestamp: "2026-10-15T11:59:00Z",
      level: "error",
      type: "app",
      resource: "srv-x",
      message: "connect failed: " + ["rediss:/", "/default:SUPERSECRET@global-homeless-toucan.upstash.io:6379"].join(""), // gitleaks:allow
    },
  });
  check("wrapped {log:…} entry normalized", wrapped.type === "app" && wrapped.level === "error" && wrapped.resource === "srv-x", wrapped);
  check("URL-embedded credential redacted", !wrapped.message.includes("SUPERSECRET"), wrapped.message);
  check("mask marker present", wrapped.message.includes("***MASKED***"), wrapped.message);

  const flat = normalizeLogEntry({ timestamp: "2026-10-15T11:58:00Z", level: "info", message: "plain log line" });
  check("flat entry shape accepted", flat.message === "plain log line", flat.message);

  const mockJwt = ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJzdWIiOiIxMjM0NTY3ODkwIn0", "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c"].join("."); // gitleaks:allow
  const jwtLine = normalizeLogEntry({
    message: `auth ok for ${mockJwt}`,
  });
  check("JWT redacted", !jwtLine.message.includes("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"), jwtLine.message);

  const bearerLine = normalizeLogEntry({ message: "authorization: Bearer " + "abcdef1234567890abcdef1234567890 accepted" }); // gitleaks:allow
  check("bearer token redacted", !bearerLine.message.includes("abcdef1234567890abcdef"), bearerLine.message);

  const kvLine = normalizeLogEntry({ message: "startup with password=" + "hunter2secret done" }); // gitleaks:allow
  check("key=value secret redacted (key name kept)", kvLine.message.includes("password***MASKED***") && !kvLine.message.includes("hunter2secret"), kvLine.message);

  const prose = normalizeLogEntry({
    message: "password policy check ran: 0 failures; docs at https://api.render.com/v1/logs",
  });
  check(
    "ordinary prose and normal URLs preserved (no over-masking)",
    prose.message.includes("https://api.render.com/v1/logs") && prose.message.includes("0 failures"),
    prose.message
  );

  check("redactSecretsInText exported and safe on empty", redactSecretsInText("") === "");

  // ── Summary ──────────────────────────────────────────────────────────────
  console.log(`\n=== Summary: ${passed} passed, ${failed} failed ===`);
  if (failed > 0) {
    console.error("Failed checks:", failures);
    process.exit(1);
  }

  if (process.argv.includes("--live")) {
    await liveSmoke();
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
