// infrastructure/cloudflare/enhanced-worker.js
// Enhanced Cloudflare Worker for SupremeAI 2.0 Edge Computing

/**
 * Enhanced Cloudflare Worker implementing:
 * 1. Multi-layer edge caching
 * 2. Request/response transformation
 * 3. Rate limiting at edge
 * 4. Geographic routing
 * 5. Request deduplication
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
        // Default: proxy to proxy to origin
        return await fetch(request);
      }
    } catch (error) {
      console.error('[EDGE] Error in worker:', error);
      return new Response('Internal Server Error', { 
        status: 500,
        headers: { 'Content-Type': 'text/plain' }
      });
    }
  }
};

/**
 * Handle API requests with caching and rate limiting
 */
async function handleApiRequest(request, env, ctx) {
  const url = new URL(request.url);
  
  // Skip caching for non-GET requests
  if (request.method !== 'GET') {
    return await proxyToOrigin(request, env);
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
  const cacheKey = `${CONFIG.CACHE_PREFIXES.API}${crypto.SHA256(request.url)}`;
  
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
  
  // Fetch from origin
  const originResponse = await proxyToOrigin(request, env);
  
  // Cache successful responses
  if (originResponse.ok) {
    const responseToCache = new Response(originResponse.body, originResponse);
    responseToCache.headers.set('X-Cache-Status', 'MISS');
    responseToCache.headers.set('X-Cache-Layer', 'ORIGIN');
    
    ctx.waitUntil(
      caches.default.putToCache(
        cacheKey, 
        responseToCache, 
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
    return await proxyToOrigin(request, env);
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
  const bodyHash = requestBody ? await crypto.SHA256(requestBody) : 'no-body';
  const cacheKey = `${CONFIG.CACHE_PREFIXES.AI}${crypto.SHA256(`${request.method}:${request.url}:${bodyHash}`)}`;
  
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
  
  // Fetch from origin
  const originResponse = await proxyToOrigin(request, env);
  
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
    return await fetch(request);
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
    version: '2.0.0'
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

/**
 * Proxy request to origin server
 */
async function proxyToOrigin(request, env) {
  // In a real implementation, this would forward to your origin
  // For now, we'll simulate or use a default backend
  const originUrl = env.ORIGIN_URL || 'https://your-origin-server.com';
  
  const url = new URL(request.url);
  const originUrlObj = new URL(url.pathname + url.search, originUrl);
  
  const originRequest = new Request(originUrlObj.toString(), {
    method: request.method,
    headers: request.headers,
    body: request.body,
    redirect: 'follow'
  });
  
  return fetch(originRequest);
}

/**
 * Check rate limit for an identifier
 */
async function checkRateLimit(request, env, prefix, limit) {
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const key = `${prefix}${ip}`;
  
  // Get current count
  let count = await env.RATE_LIMIT_DB.get(key);
  count = parseInt(count) || 0;
  
  if (count >= limit) {
    // Get TTL for reset time
    const ttl = await env.RATE_LIMIT_DB.getExpiration(key);
    const resetIn = ttl ? Math.ceil(ttl / 1000) : 60; // Default to 60s if no TTL
    
    return {
      allowed: false,
      resetIn: resetIn
    };
  }
  
  // Increment counter
  const newCount = count + 1;
  await env.RATE_LIMIT_DB.put(key, String(newCount), {
    expiration: Math.floor(Date.now() / 1000) + 60 // Expire in 60 seconds
  });
  
  return {
    allowed: true,
    resetIn: 60 - (Date.now() % 60000) / 1000 // Seconds until minute boundary
  };
}

/**
 * Check and set duplicate request marker
 */
async function checkAndSetDuplicate(env, key, ttlSeconds) {
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
async function caches.default.put(request, response, options = {}) {
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
 */
async function crypto.SHA256(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}