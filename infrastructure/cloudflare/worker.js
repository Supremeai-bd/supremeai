export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Static Asset CDN from R2 bucket
    if (url.pathname.startsWith('/cdn/')) {
      const cacheKey = new Request(url.toString(), request);
      const cache = caches.default;

      let response = await cache.match(cacheKey);
      if (!response) {
        // Fetch from R2 bucket (assumed binding named STATIC_ASSETS)
        const objectName = url.pathname.replace('/cdn/', '');
        const object = await env.STATIC_ASSETS.get(objectName);

        if (object === null) {
          return new Response('Not Found', { status: 404 });
        }

        const headers = new Headers();
        object.writeHttpMetadata(headers);
        headers.set('etag', object.httpEtag);
        headers.set('Cache-Control', 'public, max-age=31536000'); // 1 year cache

        response = new Response(object.body, { headers });
        ctx.waitUntil(cache.put(cacheKey, response.clone()));
      }
      return response;
    }

    // Cache specific public API responses (e.g. repo list)
    if (request.method === 'GET' && url.pathname.startsWith('/api/repos')) {
      const cache = caches.default;
      let response = await cache.match(request);

      if (!response) {
        response = await fetch(request);
        if (response.ok) {
          response = new Response(response.body, response);
          response.headers.set('Cache-Control', 'public, max-age=300'); // 5 mins
          ctx.waitUntil(cache.put(request, response.clone()));
        }
      }
      return response;
    }

    // 🎯 Proxy /api/scraper/* to the standalone Scraper Microservice on Render
    // Decouples Playwright browser automation from the main backend.
    if (url.pathname.startsWith('/api/scraper/')) {
      const scraperUrl = env.SCRAPER_SERVICE_URL || 'https://supremeai-scraper.onrender.com';
      const targetUrl = scraperUrl + url.pathname.replace('/api/scraper', '');
      const proxyReq = new Request(targetUrl, {
        method: request.method,
        headers: { ...Object.fromEntries(request.headers), 'User-Agent': 'SupremeAI-Edge-Gateway/1.0' },
        body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
        redirect: 'follow'
      });
      return fetch(proxyReq);
    }

    // Default: proxy to backend origin
    const backendUrl = env.RENDER_URL || 'https://supremeai-backend-docker.onrender.com';
    const targetUrl = new URL(url.pathname + url.search, backendUrl);
    const proxyReq = new Request(targetUrl, {
      method: request.method,
      headers: { ...Object.fromEntries(request.headers), 'User-Agent': 'SupremeAI-Edge-Gateway/1.0' },
      body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
      redirect: 'follow'
    });
    return fetch(proxyReq);
  },

  async scheduled(event, env, ctx) {
    // 🛡️ Keep-Alive Ping for Render Free Tier (Zero Cold Start)
    const urlsToPing = [
      'https://supremeai-backend-docker.onrender.com/api/v1/health',
      'https://supremeai-backend-docker.onrender.com/api/v1/health',
      'https://supremeai-scraper.onrender.com/health'
    ];
    
    const promises = urlsToPing.map(url => 
      fetch(url, { headers: { 'User-Agent': 'Cloudflare-Worker-KeepAlive/1.0' } })
        .then(res => console.log(`Pinged ${url} - Status: ${res.status}`))
        .catch(err => console.error(`Failed to ping ${url}:`, err))
    );
    
    ctx.waitUntil(Promise.allSettled(promises));
  }
};
