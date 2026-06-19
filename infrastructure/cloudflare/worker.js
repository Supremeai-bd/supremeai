export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return Response.json({
        status: 'ok',
        mesh: ['gcp', 'railway', 'render'],
        strategy: 'weighted-active-active'
      });
    }

    const providers = [
      { name: 'gcp', url: env.GCP_CLOUD_RUN_URL, weight: 40 },
      { name: 'railway', url: env.RAILWAY_URL, weight: 35 },
      { name: 'render', url: env.RENDER_URL, weight: 25 }
    ].filter((provider) => provider.url);

    if (providers.length === 0) {
      return Response.json({ error: 'No upstream providers configured' }, { status: 503 });
    }

    const totalWeight = providers.reduce((sum, provider) => sum + provider.weight, 0);
    let pick = Math.random() * totalWeight;
    let selected = providers[0];
    for (const provider of providers) {
      pick -= provider.weight;
      if (pick <= 0) {
        selected = provider;
        break;
      }
    }

    const upstream = new URL(url.pathname + url.search, selected.url);
    const headers = new Headers(request.headers);
    headers.set('x-supremeai-origin', selected.name);
    headers.set('x-forwarded-host', url.host);

    const upstreamRequest = new Request(upstream, {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body
    });

    const response = await fetch(upstreamRequest);
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set('x-supremeai-origin', selected.name);
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders
    });
  }
};
