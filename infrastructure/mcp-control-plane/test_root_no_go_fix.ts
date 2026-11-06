import assert from "node:assert/strict";
import { classifyHttpProbe, aggregateRootStatus } from "./src/diagnostics/root-evidence.js";
import { evaluateCloudflareProbe } from "./src/diagnostics/cloudflare-evidence.js";
import { evaluateSchemaParity } from "./src/diagnostics/schema-parity.js";

assert.equal(classifyHttpProbe(200), "pass");
assert.equal(classifyHttpProbe(404), "fail");
assert.equal(classifyHttpProbe(503), "error");
assert.equal(aggregateRootStatus([{ status: "pass" }, { status: "unknown" }]), "unknown");

const cloudflare = evaluateCloudflareProbe({
  providerReachable: true,
  httpStatus: 404,
  body: { detail: "Not Found" },
});
assert.notEqual(cloudflare.status, "healthy");
assert.equal(cloudflare.checks.find((check) => check.source === "cloudflare.worker_route")?.status, "fail");

const schema = evaluateSchemaParity({
  expectedProjectRef: "expected",
  observedProjectRef: "expected",
  expectedTables: ["users"],
  observedTables: [],
});
assert.equal(schema.status, "fail");

const inconclusiveSchema = evaluateSchemaParity({
  expectedProjectRef: "expected",
  observedProjectRef: "expected",
  expectedTables: ["users"],
  observedTables: null,
});
assert.equal(inconclusiveSchema.status, "unknown");

console.log("root no-go remediation contract tests passed");
