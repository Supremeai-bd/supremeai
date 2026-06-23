// ============================================================================
// file >> etag.ts
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> src
// ============================================================================
  const newHeaders = new Headers(response.headers);
  const etag = crypto.randomUUID().split('-')[0];
  newHeaders.set('ETag', etag);
  return new Response(response.body, {
    status: response.status,
    headers: newHeaders,
  });
}

export function checkETag(currentEtag: string, serverEtag: string): boolean {
  return currentEtag !== serverEtag;
}

export function generateETag(data: unknown): string {
  const str = typeof data === 'string' ? data : JSON.stringify(data);
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `${hash}`;
}