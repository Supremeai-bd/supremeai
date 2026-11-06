import assert from "node:assert/strict";
import { aggregateStatus, confidenceFor, fact } from "./src/diagnostics/evidence.js";

const passFacts = [fact("github", "pass", { sha: "abc" }), fact("render", "pass", { sha: "abc" })];
assert.equal(aggregateStatus([{ name: "release", status: "pass", confidence: confidenceFor("pass", passFacts), facts: passFacts, explanation: "matched" }]), "healthy");

const unknownFacts = [fact("runtime", "unknown", undefined, "endpoint unavailable")];
assert.equal(aggregateStatus([{ name: "runtime", status: "unknown", confidence: confidenceFor("unknown", unknownFacts), facts: unknownFacts, explanation: "not proven" }]), "unknown");

const failedFacts = [fact("github", "pass", { sha: "abc" }), fact("render", "fail", { sha: "old" })];
assert.equal(aggregateStatus([{ name: "release", status: "fail", confidence: confidenceFor("fail", failedFacts), facts: failedFacts, explanation: "mismatch" }]), "critical");

console.log("intelligent foundation contract tests passed");
