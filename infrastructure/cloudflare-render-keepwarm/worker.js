/**
 * SupremeAI Render Keepwarm Mesh — Cloudflare Worker
 * 
 * Wrangler schedules lightweight liveness pings to reduce free-tier cold starts.
 */

const TARGET_SERVICES = [
  { required: true, name: "MCP Control Tower", url: "https://supremeai-mcp-tower-live.onrender.com/health/live" },
  { name: "Primary Core Node", url: "https://supremeai-primary-node-5xso.onrender.com/health/live" },
  { name: "Browser Scraper Node", url: "https://supremeai-scraper-node.onrender.com/health" },
  { name: "Async Worker Node", url: "https://supremeai-worker-node.onrender.com/health" },
  { required: true, name: "API Gateway", url: "https://supremeai-api-ulw0.onrender.com/healthz" },
  { name: "Tiny AI Brain", url: "https://supremeai-tiny-brain.onrender.com/health" }
];

function buildMetadata(env) {
  const commit = env?.CF_COMMIT_SHA || env?.RELEASE_SHA || env?.COMMIT_SHA || env?.GITHUB_SHA || "unknown";
  const expected = env?.EXPECTED_COMMIT_SHA || commit;
  return {
    service: "supremeai-render-keepwarm-mesh",
    commit,
    build: {
      deployed_commit: commit,
      expected_commit: expected,
      fresh: commit !== "unknown" && commit === expected,
      reason: commit !== "unknown" ? "configured" : "not_configured"
    }
  };
}

async function pingServices() {
  const startedAt = Date.now();
  const nodes = await Promise.all(
    TARGET_SERVICES.map(async (target) => {
      const nodeStart = Date.now();
      try {
        const res = await fetch(target.url, {
          method: "GET",
          headers: {
            "User-Agent": "SupremeAI-Keepwarm-Mesh/1.0 (+https://supremeai.org)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip"
          },
          signal: AbortSignal.timeout(15000)
        });
        return {
          name: target.name,
          url: target.url,
          status: res.status,
          latency_ms: Date.now() - nodeStart,
          ok: res.ok
        };
      } catch (err) {
        return {
          name: target.name,
          url: target.url,
          error: err.message || String(err),
          latency_ms: Date.now() - nodeStart,
          ok: false
        };
      }
    })
  );
  const requiredDown = nodes.some((node, i) => TARGET_SERVICES[i].required && !node.ok);
  return {
    elapsed_ms: Date.now() - startedAt,
    requiredDown,
    status: requiredDown ? "unavailable" : nodes.every(node => node.ok) ? "warmed" : "degraded",
    nodes
  };
}

export default {
  // বাংলা: সময়সূচির একমাত্র উৎস wrangler.toml।
  async scheduled(event, env, ctx) {
    const outcome = await pingServices();
    console.log(JSON.stringify({ cron: event.cron, scheduledTime: event.scheduledTime, ...outcome }));
    if (outcome.requiredDown) throw new Error("Required Render keepwarm target unavailable");
  },

  // HTTP Gateway for health check or status probing
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const meta = buildMetadata(env);

    if (url.pathname === "/health" || url.pathname === "/healthz") {
      return new Response(JSON.stringify({ status: "healthy", ...meta }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
      });
    }

    if (url.pathname === "/ping" || url.pathname === "/trigger") {
      const outcome = await pingServices();
      return new Response(
        JSON.stringify({
          status: outcome.status,
          ...meta,
          total_duration_ms: outcome.elapsed_ms,
          services: outcome.nodes
        }, null, 2),
        {
          status: outcome.requiredDown ? 503 : 200,
          headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
        }
      );
    }

    if (url.pathname === "/release") {
      return new Response(JSON.stringify({ status: "release", ...meta }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
      });
    }

    return new Response(
      JSON.stringify({
        status: "active",
        ...meta,
        monitored_nodes: TARGET_SERVICES.length,
        schedule: "*/10 * * * *"
      }, null, 2),
      {
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
      }
    );
  }
};
