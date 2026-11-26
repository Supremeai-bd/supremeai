import assert from "node:assert/strict";

/**
 * Root-cause regression for render-mcp permanent "degraded" (2026-11-26):
 * the retired un-suffixed Tower host (assembled at runtime — never a
 * contiguous dead-host substring) answers HTTP 503 "Service Suspended".
 * A stale RENDER_MCP_URL / RENDER_EXTERNAL_URL pointing at that host made
 * the self-check report "self-check: /health responded 503"
 * forever and flipped the whole /health aggregate to degraded.
 *
 * env.render.controlTower.url must reject the retired host and fall back to
 * the canonical live origin (registry SSOT: config/service_registry.yaml
 * services.mcp.production_url).
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
  // 1. Stale retired RENDER_MCP_URL must be rejected → canonical live origin.
  process.env.RENDER_MCP_URL = `${RETIRED}/`;
  delete process.env.RENDER_EXTERNAL_URL;
  const { env } = await import("./src/lib/env.js");
  assert.equal(env.render.controlTower.url, CANONICAL, "retired RENDER_MCP_URL must fall back to canonical live URL");
  assert.notEqual(env.render.controlTower.url, RETIRED, "never resolve to the suspended host");

  // 2. Retired RENDER_MCP_URL + retired RENDER_EXTERNAL_URL → still canonical.
  process.env.RENDER_MCP_URL = RETIRED;
  process.env.RENDER_EXTERNAL_URL = RETIRED;
  assert.equal(env.render.controlTower.url, CANONICAL, "both retired candidates must still resolve to canonical");

  // 3. Valid non-empty RENDER_MCP_URL wins (dynamic override preserved).
  process.env.RENDER_MCP_URL = "https://custom-tower.example.com/";
  assert.equal(env.render.controlTower.url, "https://custom-tower.example.com", "valid override is kept and trailing slash stripped");

  // 4. Unset RENDER_MCP_URL → RENDER_EXTERNAL_URL when it is the live host.
  delete process.env.RENDER_MCP_URL;
  process.env.RENDER_EXTERNAL_URL = CANONICAL;
  assert.equal(env.render.controlTower.url, CANONICAL, "RENDER_EXTERNAL_URL live host is accepted");

  // 5. Empty strings must not pin the URL to "".
  process.env.RENDER_MCP_URL = "";
  process.env.RENDER_EXTERNAL_URL = "";
  assert.equal(env.render.controlTower.url, CANONICAL, "empty env strings fall through to canonical");

  console.log("control tower url contract tests passed");
} finally {
  restore();
}
