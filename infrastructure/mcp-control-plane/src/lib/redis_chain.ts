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
