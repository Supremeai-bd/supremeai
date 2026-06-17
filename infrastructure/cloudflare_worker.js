addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const serviceName = url.hostname

  const backends = [
    {
      name: 'gcp-cloud-run',
      url: env.GCP_CLOUD_RUN_URL,
      health: `${env.GCP_CLOUD_RUN_URL}/health`,
      region: env.GCP_REGION,
      timeout: 5000,
      retries: 3,
      weight: parseInt(env.GCP_WEIGHT || '50', 10),
    },
    {
      name: 'railway',
      url: env.RAILWAY_URL,
      health: `${env.RAILWAY_URL}/health`,
      region: 'us-east1',
      timeout: 5000,
      retries: 3,
      weight: parseInt(env.RAILWAY_WEIGHT || '30', 10),
    },
    {
      name: 'render',
      url: env.RENDER_URL,
      health: `${env.RENDER_URL}/health`,
      region: 'us-east1',
      timeout: 5000,
      retries: 3,
      weight: parseInt(env.RENDER_WEIGHT || '20', 10),
    },
  ].filter(b => b.url)

  if (backends.length === 0) {
    return new Response('No backends configured', { status: 503 })
  }

  const healthyBackends = await getHealthyBackends(backends)
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
