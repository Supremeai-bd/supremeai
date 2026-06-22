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

    // Default: pass through to origin
    return fetch(request);
  },
};
