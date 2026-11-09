import assert from "node:assert/strict";
import { buildAccountRegistry, getAccountsForRole } from "./src/registry/account.registry.js";

console.log("Verifying Monorepo SSOT GitHub account resolution across roles...");

// 1. Admin sees primary repo + org monitor
const adminAccounts = getAccountsForRole("admin").filter((a) => a.provider === "github");
console.log("Admin GitHub accounts:", adminAccounts.map((a) => a.id));
assert.ok(adminAccounts.some((a) => a.id === "github-primary"));
assert.ok(adminAccounts.some((a) => a.id === "github-org-supremeai-bd"));
assert.ok(!adminAccounts.some((a) => a.id.includes("supremeai-studio")));

// 2. Agent sees primary repo (Supremeai-bd/supremeai), NOT org monitor or retired satellites
const agentAccounts = getAccountsForRole("agent").filter((a) => a.provider === "github");
console.log("Agent GitHub accounts:", agentAccounts.map((a) => a.id));
assert.equal(agentAccounts.length, 1);
assert.equal(agentAccounts[0].id, "github-primary");
assert.equal(agentAccounts[0].url, "https://api.github.com/repos/Supremeai-bd/supremeai");

// 3. Viewer sees primary repo (Supremeai-bd/supremeai)
const viewerAccounts = getAccountsForRole("viewer").filter((a) => a.provider === "github");
console.log("Viewer GitHub accounts:", viewerAccounts.map((a) => a.id));
assert.equal(viewerAccounts.length, 1);
assert.equal(viewerAccounts[0].id, "github-primary");
assert.equal(viewerAccounts[0].url, "https://api.github.com/repos/Supremeai-bd/supremeai");

console.log("✅ All role-based GitHub account resolutions point strictly to Supremeai-bd/supremeai!");
