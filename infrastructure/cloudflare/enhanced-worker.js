// infrastructure/cloudflare/enhanced-worker.js
// Enhanced Cloudflare Worker for SupremeAI 2.0 Edge Computing

/**
 * Enhanced Cloudflare Worker implementing:
 * 1. Multi-layer edge caching
 * 2. Request/response transformation
 * 3. Rate limiting at edge
 * 4. Geographic routing
 * 5. Request deduplication
 * 6. Multi-node backend auto-failover with KV-backed circuit state
 *    (Feature 4, old plan — backend primary node down হলে Cloudflare-level
 *     secondary node-এ স্বয়ংক্রিয় failover)
 *
 * ── BUGFIXES (2026-09) ──────────────────────────────────────────────────
 * 1. `caches.default.putToCache(...)` বিদ্যমান নেই — প্রতিটি successful
 *    GET /api/* miss এখানেই throw করত এবং ক্লায়েন্ট 500 পেত। এখন
 *    `caches.default.put()` (AI পাথের মতোই) ব্যবহার হয়।
 * 2. AI cache key-তে `sha256Hash(...)` এর আগে `await` ছিল না — কী-তে
 *    "[object Promise]" ঢুকে যেত; cache কখনো কাজ করত না।
 * 3. Default route-এ `fetch(request)` নিজেকেই আবার কল করত (recursive
 *    loop / origin-এ না যাওয়া) — এখন origin proxy হয়।
 * 4. `DUPLICATE_DB`/`CACHE_METADATA`/`SUPREME_KV` কোডে ব্যবহৃত কিন্তু
 *    wrangler.toml-এ ডিক্লেয়ার ছিল না — এখন ডিক্লেয়ার করা হয়েছে।
 * ─────────────────────────────────────────────────────────────────────────
 */

// Configuration
const CONFIG = {
  // Cache TTL values (in seconds)
  CACHE_TTL: {
    STATIC_ASSETS: 31536000,   // 1 year
    API_RESPONSES: 300,        // 5 minutes
    AI_RESPONSES: 60,          // 1 minute
    RATE_LIMIT_WINDOW: 60,     // 1 minute
  },

  // Rate limiting (requests per window)
  RATE_LIMIT: {
    DEFAULT: 100,              // 100 requests per minute per IP
    AUTHENTICATED: 1000,       // 1000 requests per minute for authenticated users
  },

  // Cache keys prefixes
  CACHE_PREFIXES: {
    API: "supremeai:api:",
    AI: "supremeai:ai:",
    RATE_LIMIT: "supremeai:ratelimit:",
    DEDUP: "supremeai:dedup:",
  }
};

// ─────────────────────────────────────────────────────────────────────────
// Feature 4 (old plan): Multi-node failover configuration
// Node list env var থেকে আসে (Zero-Hardcoding) — wrangler.toml [vars]:
//   RENDER_URL          → priority 1 (primary)
//   BACKUP_RENDER_URL   → priority 2 (secondary, optional)
//   TERTIARY_RENDER_URL → priority 3 (optional)
// KV-ভিত্তিক circuit state: failed node ২ মিনিটের জন্য OPEN থাকে, তারপর
// TTL শেষে auto HALF-OPEN (আবার try হয়)।
// ─────────────────────────────────────────────────────────────────────────
const FAILOVER = {
  HEALTH_CACHE_KEY: "supremeai:node_health_v1",
  CIRCUIT_OPEN_TTL: 120,     // 2 min circuit open (per plan)
  NODE_TIMEOUT_MS: 8000,     // 8s per-node timeout (per plan)
};

/**
 * Build the ordered backend node list from environment (never hardcode URLs).
 */
function getBackendNodes(env) {
  const nodes = [];
  const candidates = [
    { url: env.RENDER_URL, priority: 1, name: "primary" },
    { url: env.BACKUP_RENDER_URL, priority: 2, name: "backup" },
    { url: env.TERTIARY_RENDER_URL, priority: 3, name: "tertiary" },
  ];
  for (const c of candidates) {
    if (c.url && /^https?:\/\//.test(c.url)) {
      nodes.push({ ...c, url: c.url.replace(/\/+$/, "") });
    }
  }
  return nodes.sort((a, b) => a.priority - b.priority);
}

/** Read last known-bad nodes (circuit OPEN state) from KV. */
async function getFailedNodes(env) {
  if (!env.SUPREME_KV) return new Set();
  try {
    const cached = await env.SUPREME_KV.get(FAILOVER.HEALTH_CACHE_KEY);
    return cached ? new Set(JSON.parse(cached)) : new Set();
  } catch (_) {
    return new Set(); // Corrupt state → treat all nodes as healthy
  }
}

/** Persist the failed-node set with TTL (HALF-OPEN recovery after TTL). */
function persistFailedNodes(env, ctx, failedNodes) {
  if (!env.SUPREME_KV || !ctx) return;
  ctx.waitUntil(
    env.SUPREME_KV.put(
      FAILOVER.HEALTH_CACHE_KEY,
      JSON.stringify([...failedNodes]),
      { expirationTtl: FAILOVER.CIRCUIT_OPEN_TTL }
    )
  );
}

/**
 * Main fetch handler
 */
export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
      const country = request.headers.get('CF-IPCountry') || 'unknown';

      // Log request for analytics (sampling to avoid overload)
      if (Math.random() < 0.1) { // 10% sampling
        console.log(`[EDGE] ${request.method} ${url.pathname} from ${ip} (${country})`);
      }

      // Route to appropriate handler based on path
      if (url.pathname.startsWith('/api/')) {
        return await handleApiRequest(request, env, ctx);
      } else if (url.pathname.startsWith('/ai/')) {
        return await handleAiRequest(request, env, ctx);
      } else if (url.pathname.startsWith('/cdn/')) {
        return await handleStaticAssets(request, env, ctx);
      } else if (url.pathname.startsWith('/health')) {
        return await handleHealthCheck(request, env, ctx);
      } else {
        // BUGFIX 3: আগে `fetch(request)` ছিল — worker নিজেকেই কল করত।
        // এখন default traffic-ও failover সহ origin-এ যায়।
        return await proxyToOrigin(request, env, ctx);
      }
    } catch (error) {
      console.error('[EDGE] Error in worker:', error);
      return new Response('Internal Server Error', {
        status: 500,
        headers: { 'Content-Type': 'text/plain' }
      });
    }
  },

  async scheduled(event, env, ctx) {
    // 🛡️ Keep-Alive Ping for Render Free Tier (Zero Cold Start)
    const backendUrl = env.RENDER_URL || '';
    const urlsToPing = [
      `${backendUrl}/api/v1/health`
    ];

    const promises = urlsToPing.map(url => {
      // ক্যাশ-বাস্টিং টাইমস্ট্যাম্প + আসল ব্রাউজার User-Agent
      const bustUrl = `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`;
      return fetch(bustUrl, {
        cf: { cacheTtl: 0, cacheEverything: false },
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
          'Cache-Control': 'no-cache, no-store',
          'Pragma': 'no-cache'
        }
      })
        .then(res => console.log(`Pinged ${bustUrl} - Status: ${res.status}`))
        .catch(err => console.error(`Failed to ping ${bustUrl}:`, err));
    });

    ctx.waitUntil(Promise.allSettled(promises));
  }
};

/**
 * Handle API requests with caching, rate limiting and multi-node failover
 */
async function handleApiRequest(request, env, ctx) {
  const url = new URL(request.url);

  // Skip caching for non-GET requests
  if (request.method !== 'GET') {
    return await proxyToOrigin(request, env, ctx);
  }

  // Check rate limit
  const rateLimitResult = await checkRateLimit(
    request,
    env,
    `${CONFIG.CACHE_PREFIXES.RATE_LIMIT}api:`,
    CONFIG.RATE_LIMIT.DEFAULT
  );

  if (!rateLimitResult.allowed) {
    return new Response('Rate limit exceeded', {
      status: 429,
      headers: {
        'Content-Type': 'text/plain',
        'Retry-After': String(rateLimitResult.resetIn)
      }
    });
  }

  // Generate cache key
  const cacheKey = `${CONFIG.CACHE_PREFIXES.API}${await sha256Hash(request.url)}`;

  // Try to get from cache
  const cachedResponse = await caches.default.match(
    new Request(`https://cache.cloudflare.com/${cacheKey}`),
    { cacheName: 'api-cache' }
  );

  if (cachedResponse) {
    // Add cache hit header
    const newHeaders = new Headers(cachedResponse.headers);
    newHeaders.set('X-Cache-Status', 'HIT');
    newHeaders.set('X-Cache-Layer', 'EDGE');

    return new Response(cachedResponse.body, {
      status: cachedResponse.status,
      headers: newHeaders
    });
  }

  // Fetch from origin (with failover)
  const originResponse = await proxyToOrigin(request, env, ctx);

  // Cache successful responses
  if (originResponse.ok) {
    const responseToCache = new Response(originResponse.clone().body, originResponse);
    responseToCache.headers.set('X-Cache-Status', 'MISS');
    responseToCache.headers.set('X-Cache-Layer', 'ORIGIN');

    // BUGFIX 1: `putToCache` নামে কোনো Cache API method নেই — এটা প্রতিবার
    // throw করত ফলে GET /api/* সব 500 হতো। এখন সঠিক `caches.default.put()`।
    ctx.waitUntil(
      caches.default.put(
        new Request(`https://cache.cloudflare.com/${cacheKey}`),
        responseToCache.clone(),
        { cacheName: 'api-cache' }
      )
    );

    // Keep KV expiration metadata in sync (matches AI path behavior)
    ctx.waitUntil(
      setCacheExpiration(
        `https://cache.cloudflare.com/${cacheKey}`,
        env,
        CONFIG.CACHE_TTL.API_RESPONSES
      )
    );
  }

  return originResponse;
}

/**
 * Handle AI requests with specialized caching and deduplication
 */
async function handleAiRequest(request, env, ctx) {
  // Only cache POST requests with cacheable content-type
  if (request.method !== 'POST') {
    return await proxyToOrigin(request, env, ctx);
  }

  // Check rate limit (stricter for AI endpoints)
  const rateLimitResult = await checkRateLimit(
    request,
    env,
    `${CONFIG.CACHE_PREFIXES.RATE_LIMIT}ai:`,
    Math.floor(CONFIG.RATE_LIMIT.DEFAULT / 2) // Half the rate limit for AI
  );

  if (!rateLimitResult.allowed) {
    return new Response('AI service rate limit exceeded', {
      status: 429,
      headers: {
        'Content-Type': 'text/plain',
        'Retry-After': String(rateLimitResult.resetIn)
      }
    });
  }

  // Get request body for cache key generation
  let requestBody = '';
  try {
    const clone = request.clone();
    requestBody = await clone.text();
  } catch (e) {
    // If we can't read the body, fall back to URL-only caching
    requestBody = '';
  }

  // Create cache key from method, URL, and body hash
  const bodyHash = requestBody ? await sha256Hash(requestBody) : 'no-body';
  // BUGFIX 2: sha256Hash async — await ছাড়া কী-তে "[object Promise]" যেত
  const cacheKey = `${CONFIG.CACHE_PREFIXES.AI}${await sha256Hash(`${request.method}:${request.url}:${bodyHash}`)}`;

  // Check for duplicate requests (deduplication)
  const dedupKey = `${CONFIG.CACHE_PREFIXES.DEDUP}${cacheKey}`;
  const isDuplicate = await checkAndSetDuplicate(env, dedupKey, 5); // 5 second dedup window

  if (isDuplicate) {
    // Return cached response if available
    const cachedResponse = await caches.default.match(
      new Request(`https://cache.cloudflare.com/${cacheKey}`),
      { cacheName: 'ai-cache' }
    );

    if (cachedResponse) {
      const newHeaders = new Headers(cachedResponse.headers);
      newHeaders.set('X-Cache-Status', 'HIT');
      newHeaders.set('X-Deduplicated', 'true');

      return new Response(cachedResponse.body, {
        status: cachedResponse.status,
        headers: newHeaders
      });
    }

    // If no cached response, ask client to retry shortly
    return new Response('Please wait...', {
      status: 202,
      headers: {
        'Content-Type': 'text/plain',
        'Retry-After': '2'
      }
    });
  }

  // Try to get from cache
  const cachedResponse = await caches.default.match(
    new Request(`https://cache.cloudflare.com/${cacheKey}`),
    { cacheName: 'ai-cache' }
  );

  if (cachedResponse) {
    const newHeaders = new Headers(cachedResponse.headers);
    newHeaders.set('X-Cache-Status', 'HIT');
    newHeaders.set('X-Cache-Layer', 'EDGE');
    newHeaders.set('X-Deduplicated', 'false');

    return new Response(cachedResponse.body, {
      status: cachedResponse.status,
      headers: newHeaders
    });
  }

  // Fetch from origin (with failover)
  const originResponse = await proxyToOrigin(request, env, ctx);

  // Cache successful AI responses (shorter TTL)
  if (originResponse.ok) {
    const responseToCache = new Response(originResponse.body, originResponse);
    responseToCache.headers.set('X-Cache-Status', 'MISS');
    responseToCache.headers.set('X-Cache-Layer', 'ORIGIN');
    responseToCache.headers.set('X-Deduplicated', 'false');

    ctx.waitUntil(
      caches.default.put(
        new Request(`https://cache.cloudflare.com/${cacheKey}`),
        responseToCache.clone(),
        { cacheName: 'ai-cache' }
      )
    );

    // Set expiration
    ctx.waitUntil(
      setCacheExpiration(
        `https://cache.cloudflare.com/${cacheKey}`,
        env,
        CONFIG.CACHE_TTL.AI_RESPONSES
      )
    );
  }

  return originResponse;
}

/**
 * Handle static assets with aggressive caching
 */
async function handleStaticAssets(request, env, ctx) {
  // Only cache GET requests for static assets
  if (request.method !== 'GET') {
    return await proxyToOrigin(request, env, ctx);
  }

  const url = new URL(request.url);
  const cacheKey = `${CONFIG.CACHE_PREFIXES.API}${url.pathname}`;

  // Try cache first
  const cachedResponse = await caches.default.match(
    new Request(`https://cache.cloudflare.com/${cacheKey}`),
    { cacheName: 'static-assets' }
  );

  if (cachedResponse) {
    const newHeaders = new Headers(cachedResponse.headers);
    newHeaders.set('X-Cache-Status', 'HIT');
    newHeaders.set('X-Asset-Type', 'STATIC');

    return new Response(cachedResponse.body, {
      status: cachedResponse.status,
      headers: newHeaders
    });
  }

  // Fetch from origin (R2 bucket or origin server)
  const originResponse = await fetch(request);

  // Cache static assets aggressively
  if (originResponse.ok) {
    const responseToCache = new Response(originResponse.body, originResponse);
    responseToCache.headers.set('X-Cache-Status', 'MISS');
    responseToCache.headers.set('X-Asset-Type', 'STATIC');

    ctx.waitUntil(
      caches.default.put(
        new Request(`https://cache.cloudflare.com/${cacheKey}`),
        responseToCache.clone(),
        { cacheName: 'static-assets' }
      )
    );

    // Very long TTL for static assets
    ctx.waitUntil(
      setCacheExpiration(
        `https://cache.cloudflare.com/${cacheKey}`,
        env,
        CONFIG.CACHE_TTL.STATIC_ASSETS
      )
    );
  }

  return originResponse;
}

/**
 * Health check endpoint
 */
async function handleHealthCheck(request, env, ctx) {
  return new Response(JSON.stringify({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'SupremeAI 2.0 Edge Worker',
    version: '2.1.0',
    failover_nodes: getBackendNodes(env).map(n => ({ name: n.name, priority: n.priority })),
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Proxy request to the highest-priority healthy backend node.
 *
 * Feature 4 (old plan): Cloudflare Worker → Backend Auto-Failover Circuit
 * Breaker। প্রতিটি node সাজানো priority অনুযায়ী try হয়; 5xx/network error
 * হলে node-টি KV-সংরক্ষিত OPEN circuit-এ যায় (২ মিনিট), পরের node try হয়।
 * TTL শেষে সেট auto-expire হয় — এটাই HALF-OPEN recovery।
 */
async function proxyToOrigin(request, env, ctx) {
  const nodes = getBackendNodes(env);

  if (nodes.length === 0) {
    return new Response(
      JSON.stringify({ error: 'No backend nodes configured (set RENDER_URL in wrangler.toml [vars])' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }

  // POST/PUT ইত্যাদির body একবারই পড়া যায় — আগেই বাফার করে রাখি,
  // যাতে প্রতিটি node-attempt-এ একই body পাঠানো যায়।
  let bodyBuffer = null;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    try {
      bodyBuffer = await request.arrayBuffer();
    } catch (_) {
      bodyBuffer = null;
    }
  }

  const failedNodes = await getFailedNodes(env);

  for (const node of nodes) {
    if (failedNodes.has(node.url)) continue; // circuit OPEN — skip

    const url = new URL(request.url);
    const targetUrl = url.pathname + url.search
      ? `${node.url}${url.pathname}${url.search}`
      : node.url;

    try {
      const response = await fetch(
        new Request(targetUrl, {
          method: request.method,
          headers: request.headers,
          body: bodyBuffer,
          redirect: 'follow',
        }),
        { signal: AbortSignal.timeout(FAILOVER.NODE_TIMEOUT_MS) }
      );

      if (response.ok || response.status < 500) {
        // 4xx ক্লায়েন্ট-এরর মানে node জীবিত — circuit healthy রাখো।
        if (failedNodes.has(node.url)) {
          failedNodes.delete(node.url);
          persistFailedNodes(env, ctx, failedNodes);
        }
        const headers = new Headers(response.headers);
        headers.set('X-Served-By', node.name);
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers,
        });
      }

      // 5xx — এই node ব্যর্থ, circuit খুলে পরের node-এ যাওয়া হবে।
      console.error(`[FAILOVER] Node ${node.name} (${node.url}) returned ${response.status}`);
      failedNodes.add(node.url);
      persistFailedNodes(env, ctx, failedNodes);
    } catch (err) {
      // Network/timeout failure — circuit খোলো, পরের node try করো।
      console.error(`[FAILOVER] Node ${node.name} (${node.url}) failed: ${err && err.message}`);
      failedNodes.add(node.url);
      persistFailedNodes(env, ctx, failedNodes);
    }
  }

  return new Response(
    JSON.stringify({ error: 'All backend nodes unavailable. Please retry.' }),
    {
      status: 503,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': String(FAILOVER.CIRCUIT_OPEN_TTL),
      },
    }
  );
}

/**
 * Check rate limit for an identifier using atomic Native Rate Limiting
 */
async function checkRateLimit(request, env, prefix, limit) {
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';

  if (env.API_RATE_LIMITER) {
    const { success } = await env.API_RATE_LIMITER.limit({ key: `${prefix}${ip}` });
    return {
      allowed: success,
      resetIn: 60 // Fixed period based on the binding configuration
    };
  }

  // Graceful fallback if binding is not configured
  return { allowed: true, resetIn: 60 };
}

/**
 * Check and set duplicate request marker
 */
async function checkAndSetDuplicate(env, key, ttlSeconds) {
  if (!env.DUPLICATE_DB) {
    return false; // KV binding absent — dedup disabled (was a hard TypeError before)
  }
  const exists = await env.DUPLICATE_DB.get(key);

  if (exists) {
    return true; // Duplicate detected
  }

  // Set the deduplication key
  await env.DUPLICATE_DB.put(key, '1', {
    expiration: Math.floor(Date.now() / 1000) + ttlSeconds
  });

  return false; // Not a duplicate
}

/**
 * Helper to put response in cache with expiration
 */
async function putInCache(request, response, options = {}) {
  const cache = await caches.open(options.cacheName || 'default');
  return await cache.put(request, response);
}

/**
 * Helper to set cache expiration using cache tags or custom metadata
 */
async function setCacheExpiration(cacheKey, env, ttlSeconds) {
  // In Cloudflare Workers, we can't directly set TTL on cache objects
  // Instead, we rely on cache-control headers or use KV for metadata
  // This is a simplified implementation

  try {
    if (!env.CACHE_METADATA) return;
    // Store expiration timestamp in KV
    const expiryTime = Math.floor(Date.now() / 1000) + ttlSeconds;
    await env.CACHE_METADATA.put(
      `exp:${cacheKey}`,
      String(expiryTime),
      { expiration: ttlSeconds }
    );
  } catch (e) {
    console.warn('Failed to set cache expiration metadata:', e);
  }
}

/**
 * SHA256 hash utility
 * (আগের কোডে "async function sha256Hash(...)" লেখা ছিল, যা ইনভ্যালিড JS সিনট্যাক্স
 *  এবং পুরো worker.js ফাইলটাকে ডিপ্লয়মেন্টের সময় parse error দিয়ে ফেল করাতো)
 */
async function sha256Hash(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
