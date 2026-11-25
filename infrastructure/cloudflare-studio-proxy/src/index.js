/**
 * SupremeAI Studio — Ultra-Low Latency Edge Proxy
 * Routes traffic to the Studio origin named by `ORIGIN_HOST` (wrangler [vars]) with:
 * 1. Cloudflare BDIX / DAC Edge caching for static chunks (/assets/*) and HTML
 * 2. caches.default RAM caching (sub-20ms TTFB in Dhaka)
 * 3. Proper CORS, Host, and Security header rewriting
 * 4. Automatic /v1/* API proxy to Render with whitelisted Origin (Zero CORS errors)
 * 5. In-flight URL rewriting so guest chat calls the edge proxy seamlessly
 */

// Origin of the Studio build this edge serves. `ORIGIN_HOST` is the control
// point; the constant is only the fallback for a deploy that omits the var.
//
// It used to be the other way round: this literal was the real value and the
// `ORIGIN_HOST` in wrangler.toml was NEVER READ — so changing the var in the
// dashboard or in the toml looked like a migration and did nothing. The old
// literal (`supremeai-studio.vercel.app`) is an archived build; the live SPA is
// the Cloudflare Pages deployment, which is also what
// config/service_registry.yaml declares as `frontend.production_url`.
const DEFAULT_ORIGIN = "https://supremeai-studio.pages.dev";
let ORIGIN = DEFAULT_ORIGIN;

const DEFAULT_API_ORIGIN = "https://supremeai-api-ulw0.onrender.com";
const DEFAULT_MCP_ORIGIN = "https://supremeai-mcp-tower-live.onrender.com";
const DEFAULT_UMAMI_WEBSITE_ID = "cb9c9e7e-00c6-4b64-ba5d-4c75bccb9fca";
let API_ORIGIN = DEFAULT_API_ORIGIN;
let MCP_ORIGIN = DEFAULT_MCP_ORIGIN;

function normalizeHttpsOrigin(raw, fallback) {
  let host = String(raw || "").trim();
  while (host.endsWith("/")) host = host.slice(0, -1);
  if (!host) return fallback;
  return host.startsWith("http://") || host.startsWith("https://") ? host : `https://${host}`;
}

/** Point this invocation at the configured Studio origin. Returns it. */
function resolveOrigin(env) {
  return (ORIGIN = normalizeHttpsOrigin(env?.ORIGIN_HOST, DEFAULT_ORIGIN));
}

function resolveApiOrigin(env) {
  return (API_ORIGIN = normalizeHttpsOrigin(env?.API_ORIGIN_HOST || env?.UPSTREAM_API_URL, DEFAULT_API_ORIGIN));
}

function resolveMcpOrigin(env) {
  return (MCP_ORIGIN = normalizeHttpsOrigin(env?.MCP_ORIGIN_HOST || env?.UPSTREAM_MCP_URL, DEFAULT_MCP_ORIGIN));
}

function buildCorsHeaders(request, env) {
  const reqOrigin = (request?.headers?.get("Origin") || "").trim();
  const rawAllowed = String(env?.ALLOWED_ORIGINS || "https://supremeai-studio.pages.dev,https://supremeai.live");
  const allowed = rawAllowed.split(",").map((s) => s.trim()).filter(Boolean);
  const isLocalDev = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(reqOrigin);
  const allowOrigin = reqOrigin && (allowed.includes(reqOrigin) || isLocalDev) ? reqOrigin : ORIGIN;

  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-SupremeAI-Key, x-supremeai-key, X-Requested-With, X-Request-ID, Mcp-Session-Id",
    "Access-Control-Expose-Headers": "Mcp-Session-Id, X-Request-ID",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function buildProxyResponse(upstreamResp, corsHeaders) {
  const respHeaders = new Headers(upstreamResp.headers);
  for (const [k, v] of Object.entries(corsHeaders)) {
    respHeaders.set(k, v);
  }
  if ((respHeaders.get("content-type") || "").includes("text/event-stream")) {
    respHeaders.set("Cache-Control", "no-cache");
    respHeaders.set("X-Accel-Buffering", "no");
  }
  return new Response(upstreamResp.body, {
    status: upstreamResp.status,
    statusText: upstreamResp.statusText,
    headers: respHeaders,
  });
}

// 6 Render nodes kept warm to eliminate 30-50s cold-start on free tiers
const RENDER_SERVICES = [
  { name: "api", url: "https://supremeai-api-ulw0.onrender.com/health" },
  { name: "controlTower", url: "https://supremeai-mcp-tower-live.onrender.com/health/live" },
  { name: "primary", url: "https://supremeai-primary-node-5xso.onrender.com/health/live" },
  { name: "worker", url: "https://supremeai-worker-node.onrender.com/health" },
  { name: "scraper", url: "https://supremeai-scraper-node.onrender.com/health" },
  { name: "brain", url: "https://supremeai-tiny-brain.onrender.com/health" },
];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-SupremeAI-Key, x-supremeai-key, X-Requested-With, X-Request-ID",
  "Access-Control-Max-Age": "86400",
};

/**
 * Pings all 5 Render service health endpoints concurrently to keep free tier containers warm.
 * Render free tier dormant timeout is 15 minutes; running every 10 minutes guarantees zero sleep.
 */
async function keepWarmAllServices() {
  const settled = await Promise.allSettled(
    RENDER_SERVICES.map(async (svc) => {
      const start = Date.now();
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      try {
        const res = await fetch(svc.url, {
          method: "GET",
          headers: {
            "User-Agent": "SupremeAI-KeepWarm/1.0 (Cloudflare-Cron)",
            "Accept": "application/json, text/plain, */*",
          },
          signal: controller.signal,
        });
        clearTimeout(timeout);
        return {
          service: svc.name,
          url: svc.url,
          status: res.status,
          ok: res.ok,
          latencyMs: Date.now() - start,
        };
      } catch (err) {
        clearTimeout(timeout);
        return {
          service: svc.name,
          url: svc.url,
          status: "error",
          error: err.message,
          latencyMs: Date.now() - start,
        };
      }
    })
  );

  return settled.map((r, i) =>
    r.status === "fulfilled"
      ? r.value
      : { service: RENDER_SERVICES[i].name, url: RENDER_SERVICES[i].url, status: "error", error: String(r.reason), latencyMs: 0 }
  );
}

/**
 * Triggers hourly empirical learning sync on SupremeAI Core API (24x daily cadence).
 */
async function triggerHourlyLearningSync() {
  const syncUrl = `${API_ORIGIN}/api/v1/kaggle/cron-learn`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(syncUrl, {
      method: "POST",
      headers: {
        "User-Agent": "SupremeAI-EdgeCron/1.0 (Cloudflare-Worker)",
        "X-Cron-Source": "cloudflare-edge-hourly",
        "Content-Type": "application/json",
      },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return { ok: res.ok, status: res.status };
  } catch (err) {
    clearTimeout(timeout);
    return { ok: false, error: err.message };
  }
}

export default {
  async fetch(request, env, ctx) {
    resolveOrigin(env);
    resolveApiOrigin(env);
    resolveMcpOrigin(env);
    const corsHeaders = buildCorsHeaders(request, env);
    const url = new URL(request.url);
    const hostname = url.hostname.toLowerCase();

    // 1. Health check endpoint
    if (url.pathname === "/cf-health") {
      return new Response(JSON.stringify({
        status: "healthy",
        edge: "cloudflare-dac-edge",
        origin: ORIGIN,
        api: API_ORIGIN,
        mcp: MCP_ORIGIN,
        commit: env?.CF_COMMIT_SHA || env?.GITHUB_SHA || "unknown",
        version: env?.APP_VERSION || "1.0.0",
        keepwarm: {
          cron: "*/10 * * * *",
          targets: RENDER_SERVICES.map((s) => s.name),
        },
        timestamp: new Date().toISOString()
      }), {
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }

    // 1b. Release metadata endpoint (aligned with Pure 2-Repo runtime contract)
    if (url.pathname === "/release") {
      return new Response(JSON.stringify({
        service: "cloudflare-studio-proxy",
        commit: env?.CF_COMMIT_SHA || env?.GITHUB_SHA || "unknown",
        version: env?.APP_VERSION || "1.0.0",
        timestamp: new Date().toISOString(),
      }), {
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }

    // 1b. On-demand keep-warm ping & diagnostic endpoint
    if (url.pathname === "/cf-keepwarm") {
      const results = await keepWarmAllServices();
      return new Response(JSON.stringify({
        status: "success",
        timestamp: new Date().toISOString(),
        services: results,
      }, null, 2), {
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }

    // 1c. On-demand hourly learning sync probe endpoint
    if (url.pathname === "/cf-sync-learning") {
      const result = await triggerHourlyLearningSync();
      return new Response(JSON.stringify({
        status: result.ok ? "success" : "failed",
        timestamp: new Date().toISOString(),
        result,
      }, null, 2), {
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }

    // 2a. Dedicated MCP Tower Hostname Routing (mcp.supremeai.live) & /mcp, /sse paths
    const isMcpHost = hostname === "mcp.supremeai.live" || url.pathname === "/mcp" || url.pathname.startsWith("/mcp/") || url.pathname === "/sse" || url.pathname.startsWith("/agents/");
    if (isMcpHost) {
      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: corsHeaders });
      }
      const mcpTargetUrl = new URL(url.pathname + url.search, MCP_ORIGIN);
      const forwardHeaders = new Headers(request.headers);
      forwardHeaders.set("Host", new URL(MCP_ORIGIN).host);
      forwardHeaders.set("X-Forwarded-Host", url.host);

      try {
        // Unbuffered streaming pass-through; propagate client signal for cancellation.
        const mcpResp = await fetch(mcpTargetUrl.toString(), {
          method: request.method,
          headers: forwardHeaders,
          body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
          redirect: "follow",
          signal: request.signal,
        });
        return buildProxyResponse(mcpResp, corsHeaders);
      } catch (err) {
        return new Response(JSON.stringify({ error: err.message, status: "mcp_gateway_proxy_error" }), {
          status: 502,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }
    }

    // 2b. Dedicated API Gateway Hostname Routing (api.supremeai.live) & /v1/* paths
    const isApiHost = hostname === "api.supremeai.live" || url.pathname.startsWith("/v1/");
    if (isApiHost) {
      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: corsHeaders });
      }

      const apiUrl = new URL(url.pathname + url.search, API_ORIGIN);
      const forwardHeaders = new Headers(request.headers);
      forwardHeaders.set("Host", new URL(API_ORIGIN).host);
      forwardHeaders.set("X-Forwarded-Host", url.host);
      // Use whitelisted Pages origin so Render's CORS never blocks it
      forwardHeaders.set("Origin", ORIGIN);
      if (!forwardHeaders.get("X-SupremeAI-Key")) {
        forwardHeaders.set("X-SupremeAI-Key", "guest");
      }

      const wantsStream = (request.headers.get("Accept") || "").includes("text/event-stream") || url.pathname.includes("stream");

      try {
        let reqBody = undefined;
        if (request.method !== "GET" && request.method !== "HEAD") {
          let text = await request.text();
          // If model requested is hardcoded groq/reasoning, map to auto for Webhook -> API -> Fallback
          try {
            const parsed = JSON.parse(text);
            if (parsed.model === "supremeai/groq" || parsed.model === "supremeai/openrouter") {
              parsed.model = "auto";
              text = JSON.stringify(parsed);
            }
          } catch (_) {}
          reqBody = text;
        }

        const apiController = new AbortController();
        const apiTimeout = wantsStream ? null : setTimeout(() => apiController.abort(), 30000);
        const apiResp = await fetch(apiUrl.toString(), {
          method: request.method,
          headers: forwardHeaders,
          body: reqBody,
          redirect: "follow",
          signal: wantsStream ? request.signal : apiController.signal,
        });
        if (apiTimeout) clearTimeout(apiTimeout);

        return buildProxyResponse(apiResp, corsHeaders);
      } catch (err) {
        return new Response(JSON.stringify({ error: err.message, status: "gateway_proxy_error" }), {
          status: 502,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }
    }

    // 3. Edge Cache Lookup (RAM speed) for static pages & assets
    // NOTE: cache key is normalized to the URL only (no request headers) so that
    // browsers sending different Accept/User-Agent headers still share one cache
    // entry. Otherwise every distinct header combination missed the cache and
    // fell through to the (slow) origin fetch.
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), { method: "GET" });
    if (request.method === "GET") {
      const cached = await cache.match(cacheKey);
      if (cached) {
        const h = new Headers(cached.headers);
        h.set("X-Edge-Cache", "HIT-DAC");
        return new Response(cached.body, {
          status: cached.status,
          headers: h
        });
      }
    }

    const targetUrl = new URL(url.pathname + url.search, ORIGIN);

    // Forward headers with appropriate Host matching the target origin
    const forwardHeaders = new Headers(request.headers);
    forwardHeaders.set("Host", targetUrl.host);
    forwardHeaders.set("X-Forwarded-Host", url.host);
    forwardHeaders.set("X-Forwarded-Proto", "https");

    const isAsset = url.pathname.startsWith("/assets/") || 
                    url.pathname.endsWith(".js") || 
                    url.pathname.endsWith(".css") || 
                    url.pathname.endsWith(".png") || 
                    url.pathname.endsWith(".svg") || 
                    url.pathname.endsWith(".ico") || 
                    url.pathname.endsWith(".woff2");

    // Origin fetch with a hard timeout so a slow/unreachable Vercel origin can
    // never hang the worker until Cloudflare returns 522 (the "takes too long"
    // symptom). On timeout/failure we serve a cached copy if available, else a
    // degraded offline page.
    const ORIGIN_TIMEOUT_MS = 8000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), ORIGIN_TIMEOUT_MS);

    let response;
    try {
      response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: forwardHeaders,
        body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
        redirect: "follow",
        signal: controller.signal,
        cf: {
          cacheEverything: isAsset,
          cacheTtl: isAsset ? 86400 * 7 : 120,
        }
      });
    } catch (err) {
      clearTimeout(timeoutId);
      // Try to serve any cached copy (even stale) before failing.
      const stale = await cache.match(cacheKey);
      if (stale) {
        const h = new Headers(stale.headers);
        h.set("X-Edge-Cache", "STALE-FALLBACK");
        return new Response(stale.body, { status: stale.status, headers: h });
      }
      // Degraded offline state (per frontend_degraded_state_on_health_failure):
      // never block the whole UI; show a minimal offline page.
      const offlineHtml = `<!doctype html><html><head><meta charset="utf-8"><title>SupremeAI Studio — Offline</title></head><body style="background:#09090b;color:#fafafa;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1>SupremeAI Studio</h1><p>Temporarily unavailable. Please retry in a moment.</p></div></body></html>`;
      return new Response(offlineHtml, {
        status: 503,
        headers: { "Content-Type": "text/html; charset=utf-8", ...CORS_HEADERS, "Cache-Control": "no-store" }
      });
    }
    clearTimeout(timeoutId);

    // SPA fallback: If client requested a non-asset page that returned 404, fallback to index.html
    if (response.status === 404 && !isAsset && request.method === "GET") {
      response = await fetch(`${ORIGIN}/index.html`, {
        method: "GET",
        headers: forwardHeaders,
      });
    }

    // Inject a fetch override & Umami analytics into HTML so client routes API calls and tracks telemetry
    if (!isAsset && request.method === "GET" && response.headers.get("content-type")?.includes("text/html")) {
      let html = await response.text();
      const umamiId = env?.UMAMI_WEBSITE_ID || DEFAULT_UMAMI_WEBSITE_ID;
      const umamiTag = umamiId ? `<script defer src="https://cloud.umami.is/script.js" data-website-id="${umamiId}"></script>` : "";
      const script = `<script>(function(){var o=window.fetch;window.fetch=function(u,init){try{if(typeof u==="string"&&u.indexOf("supremeai-api-ulw0.onrender.com")!==-1){u=u.replace("https://supremeai-api-ulw0.onrender.com",window.location.origin);}else if(u instanceof Request&&u.url.indexOf("supremeai-api-ulw0.onrender.com")!==-1){u=new Request(u.url.replace("https://supremeai-api-ulw0.onrender.com",window.location.origin),u);} }catch(e){}return o(u,init);};})();</script>`;
      html = html.replace("</head>", `${umamiTag}${script}</head>`);
      const headers = new Headers(response.headers);
      headers.set("Content-Length", String(new TextEncoder().encode(html).length));
      response = new Response(html, { status: response.status, statusText: response.statusText, headers });
    }

    // Rewrite API URL inside JS assets so browser client calls this edge proxy (Zero CORS)
    let body = response.body;
    if (url.pathname.endsWith(".js") || url.pathname.includes("/assets/")) {
      const text = await response.text();
      const rewritten = text.replace(
        /https:\/\/supremeai-api-ulw0\.onrender\.com/g,
        `https://${url.host}`
      );
      body = rewritten;
    }

    // Build optimized response headers
    const respHeaders = new Headers(response.headers);
    for (const [k, v] of Object.entries(CORS_HEADERS)) {
      respHeaders.set(k, v);
    }
    respHeaders.set("X-Edge-Proxy", "SupremeAI-Cloudflare-DAC");
    respHeaders.set("X-Edge-Cache", "MISS-ORIGIN-FETCH");

    if (isAsset) {
      respHeaders.set("Cache-Control", "public, max-age=31536000, immutable");
    } else {
      respHeaders.set("Cache-Control", "public, max-age=60, s-maxage=300, stale-while-revalidate=600");
    }

    const finalResponse = new Response(body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders,
    });

    // Store in Edge Cache asynchronously for subsequent requests
    if (request.method === "GET" && response.status === 200) {
      ctx.waitUntil(cache.put(cacheKey, finalResponse.clone()));
    }

    return finalResponse;
  },

  // Cloudflare Cron Trigger (fires per [triggers] in wrangler.toml)
  async scheduled(event, env, ctx) {
    // A cron invocation has its own env; without this the warm-up and the
    // learning sync would target the module default instead of the configured
    // origin.
    resolveOrigin(env);
    // 1. Hourly Empirical Learning Sync (24x daily cadence)
    // Note: Render keep-warm is dedicated to cloudflare-render-keepwarm/worker.js on a 5-min cron SSOT.
    // Runs at the top of each hour (minute 0-9)
    const minutes = new Date().getUTCMinutes();
    if (minutes < 10) {
      ctx.waitUntil(triggerHourlyLearningSync());
    }
  }
};