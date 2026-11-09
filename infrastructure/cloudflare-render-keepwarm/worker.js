/**
 * SupremeAI Render Keepwarm Mesh — Cloudflare Worker
 * 
 * Runs on a 5-minute cron schedule to keep all 7 Render production services alive,
 * eliminating the 50-90s cold start latency on the Free tier.
 */

const TARGET_SERVICES = [
  { name: "MCP Control Tower", url: "https://supremeai-mcp-tower.onrender.com/health" },
  { name: "Primary Core Node", url: "https://supremeai-primary-node-5xso.onrender.com/health/live" },
  { name: "Browser Scraper Node", url: "https://supremeai-scraper-node.onrender.com/health" },
  { name: "Async Worker Node", url: "https://supremeai-worker-node.onrender.com/health" },
  { name: "API Gateway", url: "https://supremeai-api-ulw0.onrender.com/healthz" },
  { name: "Tiny AI Brain", url: "https://supremeai-tiny-brain.onrender.com/health" }
];

export default {
  // Scheduled Cron Event (every 5 minutes)
  async scheduled(event, env, ctx) {
    const startedAt = Date.now();
    
    const results = await Promise.allSettled(
      TARGET_SERVICES.map(async (target) => {
        try {
          const res = await fetch(target.url, {
            method: "GET",
            headers: {
              "User-Agent": "SupremeAI-Keepwarm-Mesh/1.0 (+https://supremeai.org)",
              "Accept": "application/json, text/plain, */*"
            },
            signal: AbortSignal.timeout(15000)
          });
          return {
            name: target.name,
            url: target.url,
            status: res.status,
            ok: res.ok
          };
        } catch (err) {
          return {
            name: target.name,
            url: target.url,
            error: err.message || String(err)
          };
        }
      })
    );

    const elapsedMs = Date.now() - startedAt;
    console.log(`[Keepwarm Mesh] Executed in ${elapsedMs}ms:`, JSON.stringify(results));
  },

  // HTTP Gateway for manual health check or status probing
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const deployedCommit = env?.CF_COMMIT_SHA || env?.RELEASE_SHA || env?.COMMIT_SHA || env?.GITHUB_SHA || "unknown";
    const expectedCommit = env?.EXPECTED_COMMIT_SHA || deployedCommit;
    const isConfigured = deployedCommit !== "unknown";

    if (url.pathname === "/health" || url.pathname === "/healthz") {
      return new Response(JSON.stringify({
        status: "healthy",
        service: "supremeai-render-keepwarm-mesh",
        commit: deployedCommit,
        build: {
          deployed_commit: deployedCommit,
          expected_commit: expectedCommit,
          fresh: isConfigured && deployedCommit === expectedCommit,
          reason: isConfigured ? "configured" : "not_configured"
        }
      }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
      });
    }
    if (url.pathname === "/release") {
      return new Response(JSON.stringify({
        service: "supremeai-render-keepwarm-mesh",
        release: deployedCommit,
        commit: deployedCommit,
        build: {
          deployed_commit: deployedCommit,
          expected_commit: expectedCommit,
          fresh: isConfigured && deployedCommit === expectedCommit,
          reason: isConfigured ? "configured" : "not_configured"
        }
      }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
      });
    }
    return new Response(
      JSON.stringify({
        status: "active",
        service: "supremeai-render-keepwarm-mesh",
        commit: deployedCommit,
        monitored_nodes: TARGET_SERVICES.length,
        schedule: "*/5 * * * *"
      }, null, 2),
      {
        headers: { "Content-Type": "application/json" }
      }
    );
  }
};
