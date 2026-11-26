/**
 * Session principal contract tests — fail-closed auth for /sse + /mcp follow-ups.
 *
 * বাংলা মন্তব্য: লাইভ Tower-এ ক্রেডেনশিয়াল ছাড়া একটি সেশন initialize-এর পর
 * follow-up রিকোয়েস্টে `callerAuthenticated: true` দেখিয়েছিল, কারণ auto-register
 * হওয়া guest রেকর্ডকেই authentication ধরা হতো; আর guest রেকর্ড না থাকলে
 * `?? "admin"` fallback সরাসরি admin + global-admin দিত। এই টেস্টগুলো pure
 * resolveSessionPrincipal()-এর চুক্তি পিন করে:
 *   ১. কোনো ক্রেডেনশিয়াল নেই → viewer, authenticated=false, global-admin=false।
 *   ২. guest রেকর্ড থাকলেও (যেকোনো role) → authenticated=false।
 *   ৩. DB-তে admin-এ upgrade হওয়া guest → role admin হলেও global-admin নয়।
 *   ৪. যাচাইকৃত slot → slot role, authenticated=true।
 *   ৫. Bearer token → token role, authenticated=true; admin token → global-admin।
 *   ৬. env MCP_ADMIN_KEY ধারী → সবসময় global-admin।
 *   ৭. role-এর শেষ fallback কখনো admin নয় (রিগ্রেশন গার্ড)।
 *   ৮. bridge verified-submitter লেবেল শুধু authenticated কনটেক্সটে।
 *
 * Run: npm run test:session-principal   (wired into test:unit + test:tower-ci)
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { resolveSessionPrincipal, SESSION_FALLBACK_ROLE } from "./src/lib/session_principal.js";
import { accessModeFor } from "./src/policy/mcp-access.js";
import { RequestContextStore } from "./src/policy/auth.context.js";
import { BRIDGE_VERIFIED_SUBMITTER_LABEL, isVerifiedBridgeSubmitter } from "./src/tools/bridge.tools.js";

// ১. সম্পূর্ণ anonymous (guest রেকর্ড তৈরি ব্যর্থ হলেও) — fail-closed viewer
{
  const p = resolveSessionPrincipal({ slotVerified: false, bearerRole: null, isEnvGlobalAdmin: false });
  assert.deepEqual(p, { role: "viewer", authenticated: false, isGlobalAdmin: false });
  assert.equal(accessModeFor(p.role, p.authenticated), "public_viewer");
}

// ২. auto-registered guest রেকর্ড — authentication নয়
{
  const p = resolveSessionPrincipal({ slotVerified: false, clientRole: "viewer", bearerRole: null, isEnvGlobalAdmin: false });
  assert.equal(p.authenticated, false);
  assert.equal(accessModeFor(p.role, p.authenticated), "public_viewer");
}

// ৩. guest রেকর্ড DB-তে admin/agent-এ upgrade — ক্রেডেনশিয়াল ছাড়া privilege নেই
for (const clientRole of ["agent", "admin", "supremeadmin"] as const) {
  const p = resolveSessionPrincipal({ slotVerified: false, clientRole, bearerRole: null, isEnvGlobalAdmin: false });
  assert.equal(p.authenticated, false, `${clientRole} guest must stay unauthenticated`);
  assert.equal(p.isGlobalAdmin, false, `${clientRole} guest must not become global admin`);
  assert.equal(accessModeFor(p.role, p.authenticated), "public_viewer");
}

// ৪. যাচাইকৃত slot — slot role জেতে
{
  const p = resolveSessionPrincipal({ slotRole: "agent", slotVerified: true, clientRole: "viewer", bearerRole: null, isEnvGlobalAdmin: false });
  assert.deepEqual(p, { role: "agent", authenticated: true, isGlobalAdmin: false });
  assert.equal(accessModeFor(p.role, p.authenticated), "agent");
}

// ৫. Bearer token — registry client বা env key
{
  const agent = resolveSessionPrincipal({ slotVerified: false, clientRole: "agent", bearerRole: "agent", isEnvGlobalAdmin: false });
  assert.deepEqual(agent, { role: "agent", authenticated: true, isGlobalAdmin: false });
  const envAgent = resolveSessionPrincipal({ slotVerified: false, bearerRole: "agent", isEnvGlobalAdmin: false });
  assert.deepEqual(envAgent, { role: "agent", authenticated: true, isGlobalAdmin: false });
  const admin = resolveSessionPrincipal({ slotVerified: false, bearerRole: "admin", isEnvGlobalAdmin: false });
  assert.equal(admin.isGlobalAdmin, true);
}

// ৬. env MCP_ADMIN_KEY — সবসময় global admin
{
  const p = resolveSessionPrincipal({ slotVerified: false, bearerRole: "admin", isEnvGlobalAdmin: true });
  assert.deepEqual(p, { role: "admin", authenticated: true, isGlobalAdmin: true });
}

// ৭. রিগ্রেশন গার্ড — fallback কখনো privileged নয়, http_server.ts-এ `?? "admin"` ফিরে আসবে না
{
  assert.equal(SESSION_FALLBACK_ROLE, "viewer");
  const src = readFileSync(join(import.meta.dirname ?? ".", "src", "http_server.ts"), "utf8");
  assert.equal(/\?\?\s*"admin"/.test(src), false, 'http_server.ts must not fall back to "admin"');
  assert.equal(/Boolean\([^)]*refreshedClient\s*\|\|/.test(src), false, "guest record must not count as authentication");
}

// ৮. bridge লেবেল — CI guard (tiny_brain_pr_guard.py) একই স্ট্রিং পড়ে
{
  assert.equal(BRIDGE_VERIFIED_SUBMITTER_LABEL, "bridge:verified-submitter");
  assert.equal(isVerifiedBridgeSubmitter(), false, "no context → unverified");
  const guest = resolveSessionPrincipal({ slotVerified: false, clientRole: "viewer", bearerRole: null, isEnvGlobalAdmin: false });
  RequestContextStore.run({ role: guest.role, authenticated: guest.authenticated }, () => {
    assert.equal(isVerifiedBridgeSubmitter(), false, "guest session must not earn the verified label");
  });
  const slot = resolveSessionPrincipal({ slotRole: "agent", slotVerified: true, bearerRole: null, isEnvGlobalAdmin: false });
  RequestContextStore.run({ role: slot.role, authenticated: slot.authenticated }, () => {
    assert.equal(isVerifiedBridgeSubmitter(), true, "verified slot earns the label");
  });
}

console.log("Session principal fail-closed tests passed (8 groups)");
