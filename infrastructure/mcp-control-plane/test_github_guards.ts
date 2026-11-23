import assert from "node:assert/strict";
import {
  assertAuthorizedRepo,
  assertSafeBranch,
  assertSafeFilePath,
  assertApproved,
  requestWriteApproval,
} from "./src/tools/integrations.tools.js";
import { globalApprovalManager } from "./src/policy/approvals/lifecycle.js";
import {
  RequestContextStore,
  type RequestContext,
  type UserRole,
} from "./src/policy/auth.context.js";

console.log("=== Testing MCP Tower GitHub Security Guards ===");

// 1. Repo Allowlist Tests
assert.doesNotThrow(() => assertAuthorizedRepo("Supremeai-bd", "supremeai", "test"));
assert.doesNotThrow(() => assertAuthorizedRepo("supremeai-bd", "supremeai-public", "test"));

assert.throws(
  () => assertAuthorizedRepo("evil-corp", "supremeai", "test"),
  /Forbidden: Tool 'test' is restricted to Supremeai-bd organization repositories only/,
  "Must block unauthorized organization"
);
assert.throws(
  () => assertAuthorizedRepo("Supremeai-bd", "arbitrary-private-repo", "test"),
  /Forbidden: Tool 'test' is restricted to Supremeai-bd organization repositories only/,
  "Must block unauthorized repo name"
);

// 2. Protected Branch Guard Tests (No Direct Push to main / master)
assert.doesNotThrow(() => assertSafeBranch("agent/issue-123-fix", "test"));
assert.doesNotThrow(() => assertSafeBranch("feature/user-auth", "test"));
assert.doesNotThrow(() => assertSafeBranch("bot/sync-deps", "test"));

assert.throws(
  () => assertSafeBranch("main", "test"),
  /Direct push to protected branch 'main' is prohibited by SupremeAI Constitution/,
  "Must block direct push to main"
);
assert.throws(
  () => assertSafeBranch(undefined, "test"),
  /Direct push to protected branch 'main' is prohibited by SupremeAI Constitution/,
  "Must block undefined branch (default main)"
);
assert.throws(
  () => assertSafeBranch("master", "test"),
  /Direct push to protected branch 'master' is prohibited by SupremeAI Constitution/,
  "Must block direct push to master"
);
assert.throws(
  () => assertSafeBranch("refs/heads/main", "test"),
  /Direct push to protected branch 'refs\/heads\/main' is prohibited by SupremeAI Constitution/,
  "Must block refs/heads/main"
);

// 3. Sensitive Path Guard Tests
assert.doesNotThrow(() => assertSafeFilePath("src/index.ts", "test"));
assert.doesNotThrow(() => assertSafeFilePath("docs/README.md", "test"));
assert.doesNotThrow(() => assertSafeFilePath("gateway/service/app.py", "test"));

assert.throws(
  () => assertSafeFilePath(".env", "test"),
  /Direct write to sensitive path '.env' is blocked/,
  "Must block .env"
);
assert.throws(
  () => assertSafeFilePath("config/.env.production", "test"),
  /Direct write to sensitive path 'config\/.env.production' is blocked/,
  "Must block nested .env"
);
assert.throws(
  () => assertSafeFilePath("certs/private.key", "test"),
  /Direct write to sensitive path 'certs\/private.key' is blocked/,
  "Must block .key files"
);
assert.throws(
  () => assertSafeFilePath("keys/cert.pem", "test"),
  /Direct write to sensitive path 'keys\/cert.pem' is blocked/,
  "Must block .pem files"
);
assert.throws(
  () => assertSafeFilePath("secrets/credentials.json", "test"),
  /Direct write to sensitive path 'secrets\/credentials.json' is blocked/,
  "Must block credential files"
);
assert.throws(
  () => assertSafeFilePath(".git/config", "test"),
  /Direct write to sensitive path '.git\/config' is blocked/,
  "Must block .git path"
);


// ── 4. HITL Approval Gate (#757 follow-up) ──────────────────────────────────
// বাংলা মন্তব্য: allowlist ও ব্রাঞ্চ গার্ড "কোথায়" ঠিক করে; HITL ঠিক করে "মানুষ সম্মত কি না"।
console.log("=== Testing HITL Approval Gate ===");

// বাংলা মন্তব্য: requestWriteApproval async, তাই async context-এ চালাতে হবে
const runAs = <T>(role: UserRole, fn: () => Promise<T>): Promise<T> =>
  RequestContextStore.run({ role, authenticated: true } as RequestContext, fn);

async function hitlTests(): Promise<void> {
  // বাংলা মন্তব্য: HITL অনুমোদন-লিংক HMAC সাইনে MCP_ADMIN_KEY লাগে (signing.ts:32)
  process.env.MCP_ADMIN_KEY ||= "test-only-admin-key-for-hitl-signing";

// agent রোলের জন্য approval request তৈরি হয় (admin নয়)
const agentDecision = await runAs("agent", () =>
  requestWriteApproval("push_file", { repo: "supremeai-public", path: "docs/x.md" }),
);
assert.notEqual(agentDecision, null, "agent must receive an approval request");
assert.equal(typeof (agentDecision as any).request.id, "string", "request must carry an ID");

// admin নিজেই অনুমোদনকারী — তাই কোনো অতিরিক্ত request নয়
const adminDecision = await runAs("admin", () =>
  requestWriteApproval("push_file", { repo: "supremeai-public", path: "docs/x.md" }),
);
assert.equal(adminDecision, null, "admin must not be blocked by HITL");

// requestId ছাড়া → fail-closed
assert.throws(
  () => assertApproved(undefined, "github.push_file"),
  /requires human approval \(HITL\)/,
  "must reject a write with no approval request ID",
);

// PENDING request দিয়ে → fail-closed
const pendingId = (agentDecision as any).request.id;
assert.throws(
  () => assertApproved(pendingId, "github.push_file"),
  /is PENDING, not APPROVED/,
  "must reject a write whose request is still pending",
);

// অজানা/মিথ্যা requestId → fail-closed
assert.throws(
  () => assertApproved("REQ-forged-id", "github.push_file"),
  /not found or expired/,
  "must reject a forged approval request ID",
);

// admin অনুমোদনের পরেই কেবল অনুমতি
globalApprovalManager.resolveRequest(pendingId, "APPROVED");
assert.doesNotThrow(
  () => assertApproved(pendingId, "github.push_file"),
  "must allow a write whose request was genuinely approved",
);

// প্রত্যাখ্যাত request → fail-closed
const rejected = await runAs("agent", () =>
  requestWriteApproval("merge_pr", { pullNumber: 64 }),
);
globalApprovalManager.resolveRequest((rejected as any).request.id, "REJECTED");
assert.throws(
  () => assertApproved((rejected as any).request.id, "github.merge_pr"),
  /is REJECTED, not APPROVED/,
  "must reject a write whose approval was denied",
);

console.log("✅ All HITL Approval Gate tests PASSED!");
}

hitlTests().catch((e) => {
  console.error("HITL test suite failed:", e);
  process.exit(1);
});

console.log("✅ All MCP Tower GitHub Security Guards PASSED!");
