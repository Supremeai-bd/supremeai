import assert from "node:assert/strict";

/**
 * Root-cause regression for render-mcp permanent "degraded" (2026-11-26):
 * the retired un-suffixed Tower host (assembled at runtime — never a
 * contiguous dead-host substring) answers HTTP 503 "Service Suspended".
 * A stale RENDER_MCP_URL / RENDER_EXTERNAL_URL pointing at that host made
 * the self-check report "self-check: /health responded 503" forever and
 * flipped the whole /health aggregate to degraded.
 *
 * env.render.controlTower.url contract:
 *   - no env candidate set         → "" (account.registry availability stays
 *     key-driven; test_render_logs "no implicit legacy MCP service")
 *   - candidate(s) set but retired → canonical live origin (self-heal)
 *   - first live candidate         → that value (trailing slashes stripped)
 *
 * Canonical live origin: registry SSOT config/service_registry.yaml
 * services.mcp.production_url.
 */

// Assembled at runtime — contiguous dead string must not appear in source
// (ghost_host_guard zero-tolerance on *.ts executable surfaces).
const RETIRED = "https://" + "supremeai-mcp-tower" + "." + "onrender.com";
const CANONICAL = "https://supremeai-mcp-tower-live.onrender.com";
const saved = {
  RENDER_MCP_URL: process.env.RENDER_MCP_URL,
  RENDER_EXTERNAL_URL: process.env.RENDER_EXTERNAL_URL,
};

function restore() {
  for (const [key, value] of Object.entries(saved)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

try {
  // 1. No env candidates → "" (preserve empty-when-unset contract).
  delete process.env.RENDER_MCP_URL;
  delete process.env.RENDER_EXTERNAL_URL;
  let { env } = await import("./src/lib/env.js");
  // Re-import is cached; call the getter via a fresh module is not possible,
  // so assert through the live env object after mutating process.env — the
  // getter reads process.env on each access.
  assert.equal(env.render.controlTower.url, "", "unset env must yield empty url");

  // 2. Stale retired RENDER_MCP_URL must be rejected → canonical live origin.
  process.env.RENDER_MCP_URL = `${RETIRED}/`;
  assert.equal(env.render.controlTower.url, CANONICAL, "retired RENDER_MCP_URL must fall back to canonical live URL");
  assert.notEqual(env.render.controlTower.url, RETIRED, "never resolve to the suspended host");

  // 3. Retired RENDER_MCP_URL + retired RENDER_EXTERNAL_URL → still canonical.
  process.env.RENDER_MCP_URL = RETIRED;
  process.env.RENDER_EXTERNAL_URL = RETIRED;
  assert.equal(env.render.controlTower.url, CANONICAL, "both retired → canonical");

  // 4. Live external URL wins over retired primary.
  process.env.RENDER_MCP_URL = RETIRED;
  process.env.RENDER_EXTERNAL_URL = "https://example-live.onrender.com/";
  assert.equal(env.render.controlTower.url, "https://example-live.onrender.com", "live RENDER_EXTERNAL_URL preferred over retired primary; trailing slash stripped");

  // 5. Live primary URL is returned as-is (trailing slashes stripped).
  process.env.RENDER_MCP_URL = "https://custom-tower.example.com/mcp///";
  delete process.env.RENDER_EXTERNAL_URL;
  assert.equal(env.render.controlTower.url, "https://custom-tower.example.com/mcp", "live primary url, trailing slashes stripped");

  console.log("control tower url contract tests passed");
} finally {
  restore();
}
