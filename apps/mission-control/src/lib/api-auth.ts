/**
 * FE-10 (issue #503): shared, edge-runtime-safe API auth helpers.
 *
 * Mission Control's /api/* routes previously had NO authentication — anyone
 * who could reach the deployment could invoke arbitrary MCP tower tools with
 * the configured admin key (RCE-equivalent against every cloud provider the
 * tower governs).
 *
 * This module provides the primitives used by both:
 *   - src/middleware.ts                 (gate every /api/* request)
 *   - src/app/api/auth/unlock/route.ts  (exchange operator token for cookie)
 *
 * Edge runtime notes: uses WebCrypto only (no node:crypto), so the same code
 * runs in middleware, route handlers and node contexts.
 */

export const UNLOCK_COOKIE = "mc_unlock";
/** Unlock cookie lifetime in seconds (12h). */
export const UNLOCK_TTL_SECONDS = 12 * 60 * 60;

/** The configured operator token, or "" when not configured. */
export function getApiToken(): string {
  return process.env.MISSION_CONTROL_API_TOKEN || "";
}

/** Constant-time string comparison (length-independent early exit avoided). */
export function timingSafeEqualStr(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const len = Math.max(a.length, b.length);
  let diff = a.length === b.length ? 0 : 1;
  for (let i = 0; i < len; i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

async function hmacHex(secret: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Build the signed cookie value: "<expiresAtSecs>.<hmac>".
 * HMAC secret is the operator token itself — nothing secret is stored
 * server-side and the cookie cannot be forged without the token.
 */
export async function signUnlockCookie(token: string, nowSecs: number): Promise<string> {
  const exp = nowSecs + UNLOCK_TTL_SECONDS;
  const mac = await hmacHex(token, `mc-unlock:${exp}`);
  return `${exp}.${mac}`;
}

/** Verify a signed cookie value against the configured token. */
export async function verifyUnlockCookie(
  cookieValue: string | undefined,
  token: string,
): Promise<boolean> {
  if (!cookieValue || !token || !cookieValue.includes(".")) return false;
  const idx = cookieValue.indexOf(".");
  const expStr = cookieValue.slice(0, idx);
  const mac = cookieValue.slice(idx + 1);
  const exp = Number.parseInt(expStr, 10);
  if (!Number.isFinite(exp) || exp <= Math.floor(Date.now() / 1000)) return false;
  const expected = await hmacHex(token, `mc-unlock:${exp}`);
  return timingSafeEqualStr(mac, expected);
}
