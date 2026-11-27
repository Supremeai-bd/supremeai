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

const DEFAULT_ALERT_INGEST_URL = "https://supremeai-studio.pages.dev/api/internal/alerts";

// বাংলা: জরুরি সার্ভিস বন্ধ হলে Studio অ্যালার্ট হাবে জানায় (admin → Services & Health → Alerts)।
// একই সার্ভিসের জন্য হাব ৬ ঘণ্টায় একবারই চ্যানেলে পাঠায় (dedupeKey)। টোকেন না থাকলে চুপচাপ বাদ।
async function reportRequiredDown(outcome, env, fetchImpl = fetch) {
  const token = env?.ALERT_INGEST_TOKEN;
  if (!token || !outcome.requiredDown) return 0;
  const url = env?.ALERT_INGEST_URL || DEFAULT_ALERT_INGEST_URL;
  const down = outcome.nodes.filter((node, i) => TARGET_SERVICES[i].required && !node.ok);
  let sent = 0;
  for (const node of down) {
    try {
      const res = await fetchImpl(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          severity: "critical",
          source: "keep-warm",
          title: `${node.name} is down`,
          body: `${node.url} → ${node.status ? `HTTP ${node.status}` : node.error || "no response"} after ${node.latency_ms} ms`,
          dedupeKey: `keepwarm-down:${node.name}`
        }),
        signal: AbortSignal.timeout(8000)
      });
      if (res.ok) sent += 1;
    } catch (err) {
      console.log(JSON.stringify({ alert_error: err.message || String(err) }));
    }
  }
  return sent;
}

export default {
  // বাংলা: সময়সূচির একমাত্র উৎস wrangler.toml।
  async scheduled(event, env, ctx) {
    const outcome = await pingServices();
    console.log(JSON.stringify({ cron: event.cron, scheduledTime: event.scheduledTime, ...outcome }));
    if (outcome.requiredDown) {
      await reportRequiredDown(outcome, env);
      throw new Error("Required Render keepwarm target unavailable");
    }
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
