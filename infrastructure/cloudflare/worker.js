/**
 * SupremeAI 2.0 — Cloudflare Worker Load Balancer (Upgraded)
 * Traffic split: GCP(40%) + Railway(35%) + Render(25%)
 *
 * ── Setup ──────────────────────────────────────────────────────
 * Cloudflare Dashboard → Workers → Settings → Variables:
 *   GCP_CLOUD_RUN_URL  = https://supremeai-api-565236080752.us-central1.run.app
 *   RAILWAY_URL        = https://your-app.railway.app
 *   RENDER_URL         = https://your-app.onrender.com
 *
 * Endpoints:
 *   /lb-status  → backend health report
 *   /*          → proxied to selected backend
 * ────────────────────────────────────────────────────────────────
 */

const HEALTH_PATH = "/health";
const HEALTH_TIMEOUT_MS = 4000;

/** Build backend list from env, filter unconfigured ones */
function buildBackends(env) {
  return [
    { name: "gcp", url: env.GCP_CLOUD_RUN_URL, weight: 40, healthy: true },
    { name: "railway", url: env.RAILWAY_URL, weight: 35, healthy: true },
    { name: "render", url: env.RENDER_URL, weight: 25, healthy: true },
  ].filter((b) => b.url && b.url.startsWith("http"));
}

/** Weighted random pick from healthy backends, fallback to all if none healthy */
function pickBackend(backends) {
  const pool = backends.filter((b) => b.healthy);
  const active = pool.length > 0 ? pool : backends;
  const total = active.reduce((s, b) => s + b.weight, 0);
  let r = Math.random() * total;
  for (const b of active) {
    r -= b.weight;
    if (r <= 0) return b;
  }
  return active[active.length - 1];
}

/** Probe all backends for health (runs in background) */
async function probeHealth(backends) {
  await Promise.allSettled(
    backends.map(async (b) => {
      try {
        const res = await fetch(b.url + HEALTH_PATH, {
          method: "GET",
          signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
        });
        b.healthy = res.status < 500;
      } catch {
        b.healthy = false;
      }
    })
  );
}

/** Forward request to backend */
async function proxyRequest(backend, request) {
  const url = new URL(request.url);
  const target = new URL(url.pathname + url.search, backend.url).toString();

  const headers = new Headers(request.headers);
  headers.set("x-supremeai-origin", backend.name);
  headers.set("x-forwarded-host", url.host);

  const upReq = new Request(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    redirect: "follow",
  });

  const res = await fetch(upReq);
  const resHeaders = new Headers(res.headers);
  resHeaders.set("x-supremeai-node", backend.name);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: resHeaders });
}

// ─── Main Worker ─────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const backends = buildBackends(env);

    if (backends.length === 0) {
      return Response.json({ error: "No upstream providers configured" }, { status: 503 });
    }

    // Probe health in background (non-blocking)
    ctx.waitUntil(probeHealth(backends));

    const url = new URL(request.url);

    // ── Status endpoint ───────────────────────────────────────────
    if (url.pathname === "/lb-status") {
      return Response.json({
        status: "ok",
        strategy: "weighted-active-active",
        backends: backends.map(({ name, url: u, weight, healthy }) => ({ name, url: u, weight, healthy })),
        timestamp: new Date().toISOString(),
      });
    }

    // ── Proxy with fallback ───────────────────────────────────────
    const primary = pickBackend(backends);
    try {
      return await proxyRequest(primary, request);
    } catch (err) {
      // Try remaining backends
      const fallbacks = backends.filter((b) => b !== primary);
      for (const fb of fallbacks) {
        try {
          return await proxyRequest(fb, request);
        } catch {
          continue;
        }
      }
      return Response.json(
        { error: "All backends unavailable", detail: String(err) },
        { status: 503 }
      );
    }
  },
};
