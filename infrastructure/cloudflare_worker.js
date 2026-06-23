addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

addEventListener('scheduled', event => {
  event.waitUntil(checkHealthAndStore())
})

function getBackends() {
  const gcp_url = typeof env !== 'undefined' ? env.GCP_CLOUD_RUN_URL : (typeof GCP_CLOUD_RUN_URL !== 'undefined' ? GCP_CLOUD_RUN_URL : '');
  const railway_url = typeof env !== 'undefined' ? env.RAILWAY_URL : (typeof RAILWAY_URL !== 'undefined' ? RAILWAY_URL : '');
  const render_url = typeof env !== 'undefined' ? env.RENDER_URL : (typeof RENDER_URL !== 'undefined' ? RENDER_URL : '');
  
  const gcp_weight = typeof env !== 'undefined' ? env.GCP_WEIGHT : (typeof GCP_WEIGHT !== 'undefined' ? GCP_WEIGHT : '50');
  const railway_weight = typeof env !== 'undefined' ? env.RAILWAY_WEIGHT : (typeof RAILWAY_WEIGHT !== 'undefined' ? RAILWAY_WEIGHT : '30');
  const render_weight = typeof env !== 'undefined' ? env.RENDER_WEIGHT : (typeof RENDER_WEIGHT !== 'undefined' ? RENDER_WEIGHT : '20');

  const gcp_region = typeof env !== 'undefined' ? env.GCP_REGION : (typeof GCP_REGION !== 'undefined' ? GCP_REGION : 'us-central1');

  return [
    {
      name: 'gcp-cloud-run',
      url: gcp_url,
      health: gcp_url ? `${gcp_url}/health` : '',
      region: gcp_region,
      timeout: 5000,
      retries: 3,
      weight: parseInt(gcp_weight || '50', 10),
    },
    {
      name: 'railway',
      url: railway_url,
      health: railway_url ? `${railway_url}/health` : '',
      region: 'us-east1',
      timeout: 5000,
      retries: 3,
      weight: parseInt(railway_weight || '30', 10),
    },
    {
      name: 'render',
      url: render_url,
      health: render_url ? `${render_url}/health` : '',
      region: 'us-east1',
      timeout: 5000,
      retries: 3,
      weight: parseInt(render_weight || '20', 10),
    },
  ].filter(b => b.url)
}

async function handleRequest(request) {
  const url = new URL(request.url)
  const backends = getBackends()

  if (backends.length === 0) {
    return new Response('No backends configured', { status: 503 })
  }

  const healthyBackends = await getHealthyBackendsFromKV(backends)
  if (healthyBackends.length === 0) {
    return new Response('All backends unhealthy', { status: 503 })
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

    return new Response(response.body, {
      status: response.status,
      headers: omitHopByHopHeaders(new Headers(response.headers)),
    })
  } catch (err) {
    return new Response(`Backend ${backend.name} error: ${err.message}`, { status: 502 })
  }
}

async function getHealthyBackendsFromKV(backends) {
  try {
    const kv = typeof SUPREMEAI_KV !== 'undefined' ? SUPREMEAI_KV : (typeof env !== 'undefined' && env.SUPREMEAI_KV ? env.SUPREMEAI_KV : null);
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
  return await getHealthyBackends(backends);
}

async function checkHealthAndStore() {
  const backends = getBackends()
  if (backends.length === 0) return

  const healthyBackends = await getHealthyBackends(backends)
  const healthyNames = healthyBackends.map(b => b.name)

  const kv = typeof SUPREMEAI_KV !== 'undefined' ? SUPREMEAI_KV : (typeof env !== 'undefined' && env.SUPREMEAI_KV ? env.SUPREMEAI_KV : null);
  if (kv) {
    await kv.put('healthy_backends', JSON.stringify(healthyNames))
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
