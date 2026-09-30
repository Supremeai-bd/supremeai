// ── Upstash multi-account fallback chain (shared) ───────────────────────────
// The fleet's canonical Upstash PRIMARY repeatedly hits its 500k/day command
// ceiling (issue #1402 "Redis" note; live incidents). Liveness and health data
// MUST survive a quota-dead account, so every Redis-facing surface walks the
// vault-provisioned account chain (primary → secondary → tertiary →
// quaternary → quinary; injected by infisical_bootstrap AND mirrored into
// Render service env for vault-independence).
//
// Extracted from registry/agent_heartbeat.ts (issue #1402) so the read-only
// health adapter (adapters/redis) can also report fleet-wide Redis capability
// instead of failing on the primary alone (false DOWN while the chain serves).

import { env } from "./env.js";

export type RedisAccountConfig = {
  label: string;
  restUrl?: string;
  restToken?: string;
  tcpUrl?: string;
};

const CHAIN_ENV_SUFFIXES: Array<[string, string, string]> = [
  ["secondary", "UPSTASH_REDIS_SECONDARY_REST_URL", "UPSTASH_REDIS_SECONDARY_REST_TOKEN"],
  ["tertiary", "UPSTASH_REDIS_TERTIARY_REST_URL", "UPSTASH_REDIS_TERTIARY_REST_TOKEN"],
  ["quaternary", "UPSTASH_REDIS_QUATERNARY_REST_URL", "UPSTASH_REDIS_QUATERNARY_REST_TOKEN"],
  ["quinary", "UPSTASH_REDIS_QUINARY_REST_URL", "UPSTASH_REDIS_QUINARY_REST_TOKEN"],
];

/** Ordered account chain from env (labels match the dashboard's chain). */
export function buildAccountChain(): RedisAccountConfig[] {
  const chain: RedisAccountConfig[] = [];
  const restUrl = env.redis.restUrl;
  const restToken = env.redis.restToken;
  const tcpUrl = env.redis.url;
  if (restUrl && restToken) {
    chain.push({ label: process.env.REDIS_ACCOUNT_LABEL || "primary", restUrl, restToken });
  } else if (tcpUrl) {
    chain.push({ label: process.env.REDIS_ACCOUNT_LABEL || "primary", tcpUrl });
  }
  for (const [label, urlKey, tokenKey] of CHAIN_ENV_SUFFIXES) {
    const url = process.env[urlKey];
    const token = process.env[tokenKey];
    if (url && token) chain.push({ label, restUrl: url, restToken: token });
  }
  return chain;
}

// ── দৈনিক-কোটা cooldown registry (#2613 — #2452 free-tier permanent fix) ────
// বাংলা মন্তব্য: Upstash free tier-এর দৈনিক কোটা শেষ হলে REST API HTTP 400 +
// "max requests limit ..." মার্কার-সহ body দেয়। এই shared registry মার্কার দেখা
// মাত্রই ওই account-কে পরবর্তী UTC মধ্যরাত + ৬০s পর্যন্ত cooldown-এ ফেলে —
// ফলে tower-এর সব Redis-পথ (heartbeat read/write, orchestrator dispatch)
// exhausted account-এ একটিও wasted request না পাঠিয়ে সরাসরি পরের account-এ
// read-shift করে। UTC মধ্যরাতে কোটা রিসেট হলে account স্বয়ংক্রিয়ভাবে ফিরে আসে।
export const QUOTA_EXCEEDED_MARKER = "max requests limit";

const quotaCooldownUntil = new Map<string, number>();

/** পরবর্তী UTC মধ্যরাত + ৬০s grace (ms epoch) — Upstash দৈনিক রিসেটের আনুমানিক সময়। */
export function nextUtcResetEpochMs(nowMs: number = Date.now()): number {
  const d = new Date(nowMs);
  const nextMidnight = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1, 0, 0, 0, 0);
  return nextMidnight + 60_000;
}

/** ওই account-কে কোটা cooldown-এ ফেলে (R2)। আগের cooldown-এর চেয়ে দীর্ঘ হলে তবেই update। */
export function markAccountQuotaExhausted(label: string, untilMs: number = nextUtcResetEpochMs()): void {
  const prev = quotaCooldownUntil.get(label) ?? 0;
  if (untilMs > prev) {
    quotaCooldownUntil.set(label, untilMs);
    console.warn(
      `[redis-chain] Upstash account "${label}" দৈনিক কোটা শেষ — ` +
        `cooldown until ${new Date(untilMs).toISOString()} (স্বয়ংক্রিয় read-shift চালু)।`,
    );
  }
}

/** Account কি এই মুহূর্তে কোটা cooldown-এ? (মেয়াদ শেষ হলে entry পরিষ্কার হয়) */
export function isAccountQuotaExhausted(label: string, nowMs: number = Date.now()): boolean {
  const until = quotaCooldownUntil.get(label);
  if (until === undefined) return false;
  if (nowMs >= until) {
    quotaCooldownUntil.delete(label);
    return false;
  }
  return true;
}

/**
 * Cooldown-মুক্ত account-দের chain (R2)। সব account cooldown-এ থাকলে পুরো
 * chain ফিরিয়ে দাও — সময়-হিসাবে ভুল হলেও fleet-wide blackout এড়াতে
 * (graceful degradation, AGENTS.md invariant #3)।
 */
export function activeAccountChain(nowMs: number = Date.now()): RedisAccountConfig[] {
  const chain = buildAccountChain();
  const active = chain.filter((account) => !isAccountQuotaExhausted(account.label, nowMs));
  return active.length > 0 ? active : chain;
}

/** REST response-এ কোটা-ত্রুটির মার্কার আছে কি না (status + body উভয় থেকে)। */
export function responseIndicatesQuotaExhaustion(status: number, body: string): boolean {
  if (body && body.includes(QUOTA_EXCEEDED_MARKER)) return true;
  return status === 400 && body.includes("max requests limit");
}

/** পর্যবেক্ষণের জন্য cooldown snapshot (invariant #5 — fleet observability)। */
export function quotaChainStatus(nowMs: number = Date.now()): { label: string; cooldownUntil: string | null }[] {
  return buildAccountChain().map((account) => {
    const until = quotaCooldownUntil.get(account.label);
    return {
      label: account.label,
      cooldownUntil: until && nowMs < until ? new Date(until).toISOString() : null,
    };
  });
}
