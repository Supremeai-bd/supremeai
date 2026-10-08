/**
 * Guard suite for issue #2510 — the Upstash REST admin token must never be
 * readable from client code / baked into the browser bundle.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  cachedFetch,
  batchGet,
  invalidatePattern,
  getCacheStats,
  resetCacheStats,
} from './cache.manager';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = join(HERE, '..');

/** Recursively collect .ts/.tsx source files under src/ (excluding tests). */
function collectSources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...collectSources(full));
    else if (/\.(ts|tsx)$/.test(entry.name) && !/\.(test|spec)\./.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

describe('#2510 source-scan guard — no client-side Upstash credential reads', () => {
  it('no frontend source reads UPSTASH env vars (any prefix)', () => {
    const offenders: string[] = [];
    for (const file of collectSources(SRC_ROOT)) {
      const text = readFileSync(file, 'utf-8');
      if (/UPSTASH_REDIS_REST_(URL|TOKEN)/.test(text)) {
        // The security note in vite-env.d.ts mentions the key name in a
        // comment — allow comment-only mentions, reject any *read*.
        const code = text
          .split('\n')
          .filter((line) => !line.trim().startsWith('//') && !line.trim().startsWith('*'))
          .join('\n');
        if (/UPSTASH_REDIS_REST_(URL|TOKEN)/.test(code)) offenders.push(file);
      }
    }
    expect(offenders, `files reading Upstash env in client code: ${offenders.join(', ')}`).toEqual(
      [],
    );
  });
});

describe('#2510 runtime contract — honest degradation, no fake cache', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    resetCacheStats();
  });

  it('cachedFetch falls back to a direct fetch when Redis is unavailable', async () => {
    const fetcher = vi.fn(async () => ({ ok: true, value: 42 }));
    const result = await cachedFetch('test-key-2510', fetcher);
    expect(result).toEqual({ ok: true, value: 42 });
    expect(fetcher).toHaveBeenCalledTimes(1); // direct passthrough, no fake hit
    expect(getCacheStats().errors).toBeGreaterThan(0); // the Redis attempt is honestly tracked
  });

  // বাংলা (#3162 কন্ট্রাক্ট-আপডেট): browser-side Redis ইচ্ছাকৃতভাবে নিষ্ক্রিয় —
  // batchGet এখন reject নয়, all-nulls graceful fallback দেয় (cache.manager.ts:219-223
  // কমেন্ট: "return করে (throw নয়), callers এখন graceful fallback পায়")।
  // পুরনো #2510 reject-কন্ট্রাক্ট ছিল — #3162 ডিজাইন-সিদ্ধান্তে বদলে গেছে; এই টেস্ট
  // সেই নতুন কন্ট্রাক্ট যাচাই করে (সোর্স-স্ক্যান গার্ড উপরে অক্ষত আছে)।
  it('batchGet degrades gracefully — all-nulls result, no fake cache (#3162 contract)', async () => {
    // বাংলা: no-op পথ getRedis-কে স্পর্শই করে না (cache.manager.ts:221-224) —
    // তাই error-stat বাড়ে না; চুক্তি হলো নীরব all-nulls graceful fallback।
    const result = await batchGet(['a', 'b']);
    expect(result).toEqual([null, null]);
  });

  it('invalidatePattern degrades gracefully — resolves as no-op, never fakes success (#3162 contract)', async () => {
    await expect(invalidatePattern('user:*')).resolves.toBeUndefined();
  });
});
