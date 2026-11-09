/**
 * Cloudflare Pages Advanced Mode Worker for SupremeAI Studio.
 * Handles edge routing, CORS, API proxying to Render nodes, and static SPA serving.
 */

const API_GATEWAY_ORIGIN = "https://supremeai-api-ulw0.onrender.com";
const PRIMARY_CORE_ORIGIN = "https://supremeai-primary-node-5xso.onrender.com";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-Requested-With, X-SupremeAI-Key, x-supremeai-key, X-CSRF-Token",
  "Access-Control-Max-Age": "86400",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: CORS_HEADERS,
      });
    }

    // 2. Sovereign config endpoint (serve local static sovereign JSON)
    if (url.pathname === "/api/config" || url.pathname === "/api/config/") {
      return env.ASSETS.fetch(new Request(new URL("/api/config.json", request.url), request));
    }

    // 3. OpenAI-compatible API routes to SupremeAI API Gateway (Render)
    if (url.pathname.startsWith("/v1/")) {
      const targetUrl = new URL(url.pathname + url.search, API_GATEWAY_ORIGIN);
      const reqHeaders = new Headers(request.headers);
      reqHeaders.set("Host", "supremeai-api-ulw0.onrender.com");

      try {
        const upstreamResp = await fetch(targetUrl.toString(), {
          method: request.method,
          headers: reqHeaders,
          body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
          redirect: "follow",
        });

        const respHeaders = new Headers(upstreamResp.headers);
        for (const [key, val] of Object.entries(CORS_HEADERS)) {
          respHeaders.set(key, val);
        }

        return new Response(upstreamResp.body, {
          status: upstreamResp.status,
          statusText: upstreamResp.statusText,
          headers: respHeaders,
        });
      } catch (err) {
        return new Response(JSON.stringify({ detail: `Gateway proxy connection error: ${err.message}` }), {
          status: 502,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }
    }

    // 4. Core API routes to SupremeAI Primary Node (Render)
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/oauth/")) {
      const targetUrl = new URL(url.pathname + url.search, PRIMARY_CORE_ORIGIN);
      const reqHeaders = new Headers(request.headers);
      reqHeaders.set("Host", "supremeai-primary-node-5xso.onrender.com");

      try {
        const upstreamResp = await fetch(targetUrl.toString(), {
          method: request.method,
          headers: reqHeaders,
          body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
          redirect: "follow",
        });

        const respHeaders = new Headers(upstreamResp.headers);
        for (const [key, val] of Object.entries(CORS_HEADERS)) {
          respHeaders.set(key, val);
        }

        return new Response(upstreamResp.body, {
          status: upstreamResp.status,
          statusText: upstreamResp.statusText,
          headers: respHeaders,
        });
      } catch (err) {
        return new Response(JSON.stringify({ detail: `Core API proxy connection error: ${err.message}` }), {
          status: 502,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }
    }

    // 5. Static assets and SPA Fallback via env.ASSETS
    try {
      const assetResp = await env.ASSETS.fetch(request);
      if (assetResp.status === 404 && request.method === "GET" && !url.pathname.includes(".")) {
        return env.ASSETS.fetch(new Request(new URL("/index.html", request.url), request));
      }
      return assetResp;
    } catch {
      return env.ASSETS.fetch(new Request(new URL("/index.html", request.url), request));
    }
  },
};
