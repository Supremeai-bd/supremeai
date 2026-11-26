/**
 * Session principal resolution (fail-closed auth for /sse + /mcp follow-ups).
 *
 * বাংলা মন্তব্য: আগে http_server.ts-এ তিন জায়গায় `?? "admin"` fallback ছিল এবং
 * auto-register হওয়া যেকোনো guest client রেকর্ড থাকলেই `authenticated: true`
 * ধরা হতো। ফলে ক্রেডেনশিয়াল ছাড়া caller-ও "authenticated" হিসেবে চিহ্নিত হতো,
 * আর guest রেকর্ড তৈরি ব্যর্থ হলে সরাসরি admin + global-admin পেত (fail-open)।
 * এই pure ফাংশনটি সেই সিদ্ধান্তকে এক জায়গায় আনে:
 *   ১. role-এর শেষ fallback সবসময় "viewer" (কখনো admin নয়)।
 *   ২. authenticated = শুধু আসল ক্রেডেনশিয়াল — যাচাইকৃত slot অথবা Bearer token।
 *      guest/auto-registered client রেকর্ড কখনো নিজে থেকে authentication নয়।
 *   ৩. global-admin শুধু authenticated admin অথবা env-admin key-ধারী পায়।
 * Pure — কোনো network/clock/env নেই, তাই অফলাইনে টেস্টযোগ্য।
 */
import type { UserRole } from "../policy/auth.context.js";

export interface SessionPrincipalInput {
  /** Role from a live-verified slot credential (assertSlotAuthorization). */
  slotRole?: UserRole;
  /** True only when a slot credential is bound AND verified for this session. */
  slotVerified: boolean;
  /** Role of the registry record tied to the session (may be a guest record). */
  clientRole?: UserRole;
  /** Role resolved from the request's Bearer token; null = no valid credential. */
  bearerRole: UserRole | null;
  /** True only for the env MCP_ADMIN_KEY holder (resolveCaller). */
  isEnvGlobalAdmin: boolean;
}

export interface SessionPrincipal {
  role: UserRole;
  authenticated: boolean;
  isGlobalAdmin: boolean;
}

/** বাংলা মন্তব্য: role-এর শেষ ডিফল্ট — fail-closed, কখনো privileged নয়। */
export const SESSION_FALLBACK_ROLE: UserRole = "viewer";

export function resolveSessionPrincipal(input: SessionPrincipalInput): SessionPrincipal {
  const authenticated = input.slotVerified || input.bearerRole !== null;
  const role: UserRole = input.slotRole ?? input.clientRole ?? input.bearerRole ?? SESSION_FALLBACK_ROLE;
  // বাংলা মন্তব্য: unauthenticated caller-এর রেকর্ডে admin role থাকলেও (যেমন DB-তে
  // guest রেকর্ড upgrade) global-admin দেওয়া হয় না — আগে ক্রেডেনশিয়াল লাগবে।
  const isGlobalAdmin = input.isEnvGlobalAdmin || (authenticated && role === "admin");
  return { role, authenticated, isGlobalAdmin };
}
