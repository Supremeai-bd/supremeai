// Architectural Fix: In-memory circuit breaker state
const circuitBreakerState = {
  brokenUntil: 0, // Timestamp until which the circuit is open
  failureCount: 0,
  lastFailureTime: 0,
};

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

addEventListener('scheduled', event => {
  event.waitUntil(checkHealthAndStore())
})

function getKV() {
  if (typeof env !== 'undefined' && env.SUPREMEAI_KV) return env.SUPREMEAI_KV;
  if (typeof SUPREMEAI_KV !== 'undefined') return SUPREMEAI_KV;
  if (typeof globalThis !== 'undefined' && globalThis.SUPREMEAI_KV) return globalThis.SUPREMEAI_KV;
  return null;
}

function getBackends() {
  // বাংলা মন্তব্য: ইউজার ব্যাকএন্ড এবং অ্যাডমিন ব্যাকএন্ড উভয় ইউআরএল এক্সট্র্যাক্ট করা
  const gcp_url = typeof env !== 'undefined' ? (env.USER_BACKEND_URL || env.GCP_CLOUD_RUN_URL) : (typeof GCP_CLOUD_RUN_URL !== 'undefined' ? GCP_CLOUD_RUN_URL : '');
  const admin_url = typeof env !== 'undefined' ? env.ADMIN_BACKEND_URL : (typeof ADMIN_BACKEND_URL !== 'undefined' ? ADMIN_BACKEND_URL : '');

  const gcp_weight = typeof env !== 'undefined' ? env.GCP_WEIGHT : (typeof GCP_WEIGHT !== 'undefined' ? GCP_WEIGHT : '50');
  const gcp_region = typeof env !== 'undefined' ? env.GCP_REGION : (typeof GCP_REGION !== 'undefined' ? GCP_REGION : 'us-central1');

  const list = [];
  if (gcp_url) {
    list.push({
      name: 'gcp-cloud-run',
      url: gcp_url,
      health: `${gcp_url.replace(/\/$/, '')}/api/v1/health`,
      region: gcp_region,
      timeout: 5000,
      retries: 3,
      weight: parseInt(gcp_weight || '50', 10),
    });
  }
  if (admin_url) {
    list.push({
      name: 'admin-backend',
      url: admin_url,
      health: `${admin_url.replace(/\/$/, '')}/health`,
      region: gcp_region,
      timeout: 5000,
      retries: 3,
      weight: parseInt(gcp_weight || '50', 10),
    });
  }
  return list;
}

const FALLBACK_HTML = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>SupremeAI - Core Offline</title><style>body{background:#07090f;color:#fff;font-family:monospace;text-align:center;padding:50px}h1{color:#00f3ff;text-transform:uppercase;letter-spacing:2px}p{color:#bc13fe}.loader{margin:20px auto;border:2px solid #333;border-top:2px solid #00f3ff;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite}@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style></head><body><h1>⚡ SupremeAI Core Offline</h1><p>The neural network is currently running a self-healing protocol.</p><div class="loader"></div><p>Please wait a moment and try again.</p></body></html>`;

async function handleRequest(request) {
  const url = new URL(request.url)
  const backends = getBackends()

  if (backends.length === 0) {
    return new Response(FALLBACK_HTML, { status: 503, headers: { 'Content-Type': 'text/html' } })
  }

  // Caching Layer for public APIs
  if (request.method === 'GET' && url.pathname.includes('/api/v1/public/')) {
    const cache = caches.default;
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
  }

  // Circuit breaker state
  const kv = getKV();
  let localState = { ...circuitBreakerState };
  if (kv) {
    try {
      const cached = await kv.get('SUPREMEAI_CIRCUIT_BREAKER_V2', { type: 'json' });
      if (cached) {
        localState = cached;
      }
    } catch (e) {
      console.error("KV read error for circuit breaker:", e);
    }
  }

  if (Date.now() < localState.brokenUntil) {
    console.error('Circuit Breaker is open. Returning emergency fallback response.');
    return new Response(FALLBACK_HTML, { status: 503, headers: { 'Content-Type': 'text/html' } });
  }

  const healthyBackends = await getHealthyBackendsFromKV(backends)
  if (healthyBackends.length === 0) {
    console.warn('All backends reported as unhealthy. Attempting to route to a backend as a last resort.');
    const backend = weightedPick(backends); 
    return forwardRequest(request, backend, url);
  }

  const backend = weightedPick(healthyBackends)
  const target = new URL(url.pathname + url.search, backend.url)

  try {
    const response = await fetch(target, {
      method: request.method,
      headers: omitWranglerHeaders(request.headers),
      body: request.method !== 'GET' ? await request.text() : null,
      signal: AbortSignal.timeout(backend.timeout),
    })

    const finalResponse = new Response(response.body, {
      status: response.status,
      headers: omitHopByHopHeaders(new Headers(response.headers)),
    })

    // Store in Cache if successful and public
    if (request.method === 'GET' && url.pathname.includes('/api/v1/public/') && response.status === 200) {
      const cache = caches.default;
      const responseToCache = finalResponse.clone();
      responseToCache.headers.set('Cache-Control', 's-maxage=60'); // 1 minute edge cache
      request.waitUntil(cache.put(request, responseToCache));
    }

    return finalResponse;
  } catch (err) {
    return new Response(FALLBACK_HTML, { status: 502, headers: { 'Content-Type': 'text/html' } })
  }
}

async function forwardRequest(request, backend, originalUrl) {
  const target = new URL(originalUrl.pathname + originalUrl.search, backend.url);

  try {
    const response = await fetch(target, {
      method: request.method,
      headers: omitWranglerHeaders(request.headers),
      body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.text() : null,
      signal: AbortSignal.timeout(backend.timeout),
    });

    return new Response(response.body, {
      status: response.status,
      headers: omitHopByHopHeaders(new Headers(response.headers)),
    });
  } catch (err) {
    return new Response(`Last-resort routing to backend ${backend.name} failed: ${err.message}`, { status: 502 });
  }
}

async function getHealthyBackendsFromKV(backends) {
  try {
    const kv = typeof SUPREMEAI_KV !== 'undefined' ? SUPREMEAI_KV : null;
    if (kv) {
      const cached = await kv.get('healthy_backends');
      if (cached) {
        const healthyNames = JSON.parse(cached);
        const filtered = backends.filter(b => healthyNames.includes(b.name));
        if (filtered.length > 0) {
          return filtered;
        }
      }
    }
  } catch (e) {
    console.error('KV read error:', e);
  }
  // Fallback to direct health check if KV is empty or fails
  const directlyChecked = await getHealthyBackends(backends);
  if (directlyChecked.length === 0 && backends.length > 0) {
    // All backends are unhealthy, trip the circuit breaker
    let localState = { ...circuitBreakerState };
    const kv = getKV();
    if (kv) {
      try {
        const cached = await kv.get('SUPREMEAI_CIRCUIT_BREAKER_V2', { type: 'json' });
        if (cached) {
          localState = cached;
        }
      } catch (e) {
        console.error("KV read error during state mutation:", e);
      }
    }
    localState.failureCount++;
    localState.lastFailureTime = Date.now();
    // If it fails 3 times in a row, open the circuit for 1 minute
    if (localState.failureCount >= 3) {
      console.error('All backends unhealthy after direct check. Tripping circuit breaker for 60 seconds.');
      localState.brokenUntil = Date.now() + 60000; // Open for 60 seconds
      localState.failureCount = 0; // Reset count
    }
    Object.assign(circuitBreakerState, localState);
    if (kv) {
      try {
        // বাংলা মন্তব্য: P1 Fix — অন্যান্য Isolates-এর সাথে ব্রেকার স্টেট সিঙ্ক করতে KV-তে লিখা হচ্ছে।
        await kv.put('SUPREMEAI_CIRCUIT_BREAKER_V2', JSON.stringify(localState), { expirationTtl: 300 });
      } catch (e) {
        console.error("KV write error during state mutation:", e);
      }
    }
  }
  return directlyChecked;
}

async function checkHealthAndStore() {
  const backends = getBackends()
  if (backends.length === 0) return

  const healthyBackends = await getHealthyBackends(backends)
  const healthyNames = healthyBackends.map(b => b.name)

  const kv = getKV();
  if (kv) {
    // আর্কিটেকচারাল ফিক্স #2: Add a TTL to prevent using stale data if the cron fails
    await kv.put('healthy_backends', JSON.stringify(healthyNames), {
      expirationTtl: 60 // Expire after 60 seconds
    });
    console.log('Saved healthy backends to KV:', healthyNames)
  }
}

async function getHealthyBackends(backends) {
  const results = await Promise.allSettled(
    backends.map(async backend => {
      for (let attempt = 0; attempt < backend.retries; attempt++) {
        try {
          const res = await fetch(backend.health, { signal: AbortSignal.timeout(backend.timeout) })
          if (res.ok) return backend
        } catch (_) {
          if (attempt === backend.retries - 1) return null
          await new Promise(r => setTimeout(r, 200 * (attempt + 1)))
        }
      }
      return null
    })
  )
  return results.filter(r => r.status === 'fulfilled' && r.value).map(r => r.value)
}

function weightedPick(backends) {
  const total = backends.reduce((sum, b) => sum + (b.weight || 0), 0)
  if (total === 0) return backends[Math.floor(Math.random() * backends.length)]
  let r = Math.random() * total
  for (const b of backends) {
    r -= b.weight || 0
    if (r <= 0) return b
  }
  return backends[backends.length - 1]
}

function omitWranglerHeaders(headers) {
  const allowlist = ['content-type', 'authorization', 'x-telegram-bot-token']
  const out = new Headers()
  headers.forEach((v, k) => { if (allowlist.includes(k.toLowerCase()) || !k.startsWith('cf-')) out.set(k, v) })
  return out
}

function omitHopByHopHeaders(headers) {
  const block = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade'])
  const out = new Headers()
  headers.forEach((v, k) => { if (!block.has(k.toLowerCase())) out.set(k, v) })
  return out
}
