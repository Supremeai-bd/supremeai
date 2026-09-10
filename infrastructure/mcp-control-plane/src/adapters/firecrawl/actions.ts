import { env } from "../../lib/env.js";
import { httpRequest } from "../../lib/http.js";

/**
 * Firecrawl — web scraping для документации, гайдов, стиль-гайдов.
 * https://api.firecrawl.dev/v1/scrape
 */

export async function scrapeUrl(
  url: string,
  opts: { formats?: string[]; onlyMainContent?: boolean; maxTokens?: number } = {}
): Promise<unknown> {
  const keys = env.firecrawl.apiKeys;
  if (keys.length === 0) throw new Error("FIRECRAWL_API_KEY is not configured.");

  const key = keys[0];
  const formats = opts.formats ?? ["markdown"];
  const onlyMainContent = opts.onlyMainContent ?? true;
  const maxTokens = opts.maxTokens ?? 8000;

  const res = await httpRequest("https://api.firecrawl.dev/v1/scrape", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: { url, formats, onlyMainContent },
    timeoutMs: 30_000,
    retries: 1,
  });

  if (!res.ok) {
    throw new Error(`Firecrawl scrape failed (${res.status}): ${JSON.stringify(res.data).slice(0, 300)}`);
  }

  const data = res.data as any;
  // Firecrawl v1 returns { success: true, data: { markdown: "...", html: "..." } }
  const content: string = data?.data?.markdown
    ?? data?.data?.["content"]
    ?? data?.markdown
    ?? JSON.stringify(data).slice(0, 1000);

  const trimmed = content.length > maxTokens * 4 ? content.slice(0, maxTokens * 4) : content;
  return {
    url,
    success: true,
    source: "firecrawl",
    formats,
    truncated: trimmed.length < content.length,
    content: trimmed,
  };
}