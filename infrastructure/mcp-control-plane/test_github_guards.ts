import assert from "node:assert/strict";
import {
  assertAuthorizedRepo,
  assertSafeBranch,
  assertSafeFilePath,
} from "./src/tools/integrations.tools.js";

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

console.log("✅ All MCP Tower GitHub Security Guards PASSED!");
