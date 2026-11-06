import assert from "node:assert/strict";
import { compareCommitEvidence, resolveTarget } from "./src/tools/diagnostic.tools.js";

const pass = compareCommitEvidence("abc", "abc", "abc");
assert.equal(pass.status, "pass");

const mismatch = compareCommitEvidence("abc", "old", "old");
assert.equal(mismatch.status, "fail");
assert.equal(mismatch.details.deploymentMatches, false);

const unknown = compareCommitEvidence("abc", null, null);
assert.equal(unknown.status, "unknown");

assert.equal(resolveTarget("does-not-exist"), null);
console.log("system diagnose contract tests passed");
