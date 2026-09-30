import assert from "node:assert/strict";
import type { IncomingMessage } from "node:http";
import { autoRegisterGuestClient, detectProviderLabel } from "./src/policy/auto-register.js";
import { listClients } from "./src/policy/client-registry.js";

/**
 * #2588 — vendor-agnostic auto-registration contract tests.
 *
 * Architecture under test (founder guidance): the tower accepts ANY AI by
 * TRANSPORT protocol alone (sse / streamable-http); provider labels from the
 * User-Agent are cosmetic. Every no-auth connect must leave a database
 * record with zero manual registration, and the record must follow the
 * client's latest transport.
 */

function fakeReq(userAgent: string, ip = "203.0.113.7"): IncomingMessage {
  return {
    headers: { "user-agent": userAgent, "x-forwarded-for": ip },
    socket: { remoteAddress: ip },
  } as unknown as IncomingMessage;
}

// 1. Signature label detection is best-effort cosmetics, never acceptance.
assert.equal(detectProviderLabel("Mozilla/5.0 Grok/1.0 xAI").provider, "xai");
assert.equal(detectProviderLabel("claude-web/2.1").provider, "claude");
assert.equal(detectProviderLabel("GeminiSpark custom-app").provider, "gemini");
assert.equal(detectProviderLabel("cursor/0.42 vscode-extension").provider, "cursor");
assert.equal(detectProviderLabel("ChatGPT-User/1.0").provider, "chatgpt");
assert.equal(detectProviderLabel("VS Code MCP Client").provider, "vscode");
assert.equal(detectProviderLabel("totally-unknown-bot/9").provider, "generic");

// 2. Zero-manual-registration: xAI Grok over /sse gets a database record.
const grokSse = autoRegisterGuestClient(fakeReq("Mozilla/5.0 Grok/1.0 xAI"), "sse");
assert.ok(grokSse.id.startsWith("guest_xai_"), `unexpected guest id: ${grokSse.id}`);
assert.equal(grokSse.provider, "xai");
assert.equal(grokSse.protocol, "sse");
assert.equal(grokSse.status, "active");
assert.equal(grokSse.role, "viewer"); // guests start read-only; admins upgrade live

// 3. Idempotency: the same client reconnecting reuses its record.
const grokAgain = autoRegisterGuestClient(fakeReq("Mozilla/5.0 Grok/1.0 xAI"), "sse");
assert.equal(grokAgain.id, grokSse.id);

// 4. Cross-protocol reconnect: the registry follows the latest transport.
const grokHttp = autoRegisterGuestClient(fakeReq("Mozilla/5.0 Grok/1.0 xAI"), "streamable-http");
assert.equal(grokHttp.id, grokSse.id);
assert.equal(grokHttp.protocol, "streamable-http");

// 5. Unknown vendors register too (generic label) — protocol-driven acceptance.
const unknownAi = autoRegisterGuestClient(fakeReq("FutureAI-9000/0.1"), "streamable-http");
assert.equal(unknownAi.provider, "generic");
assert.ok(unknownAi.id.startsWith("guest_generic_"));
assert.equal(unknownAi.protocol, "streamable-http");
assert.equal(unknownAi.status, "active");

// 6. Same provider family + same IP (different UA version) still reuses; a
//    different IP gets a distinct record (per-IP guest identity preserved).
const grokNewerUa = autoRegisterGuestClient(fakeReq("Grok/2.0 xAI"), "sse");
assert.equal(grokNewerUa.id, grokSse.id);
const grokDifferentIp = autoRegisterGuestClient(fakeReq("Grok/2.0 xAI", "198.51.100.9"), "sse");
assert.notEqual(grokDifferentIp.id, grokSse.id);

// 7. Admin visibility: every auto-registered guest shows up in client_list.
const listed = listClients("*");
assert.ok(listed.some((c) => c.id === grokSse.id), "auto-registered guest missing from client_list");
assert.ok(listed.some((c) => c.id === unknownAi.id), "generic guest missing from client_list");

console.log("auto-register contract tests passed");
