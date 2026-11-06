import assert from "node:assert/strict";
import { resolveServiceIdentity, resolveServiceTarget } from "./src/diagnostics/service_manifest.js";

// 1. Canonical resolver returns identity for known service
const api = resolveServiceIdentity("api");
assert.ok(api, "api identity must resolve");
assert.equal(api!.logicalName, "api");
assert.ok(api!.runtimeUrl.startsWith("https://"), "runtime url must be present");
console.log("api identity verified:", api!.verified, api!.serviceId ? "id-present" : "no-id");

// 2. Unknown service returns null
const unknown = resolveServiceIdentity("definitely-not-a-service");
assert.equal(unknown, null, "unknown service must return null identity");

// 3. Service target resolution consistent
const t = resolveServiceTarget("core");
assert.ok(t, "core must resolve from registry");
assert.ok(t!.runtimeUrl, "core must have runtime url from registry");

// 4. Alias resolution
const gw = resolveServiceIdentity("backend-api");
assert.ok(gw, "backend-api alias must resolve");
assert.equal(gw!.logicalName, "api");

console.log("Phase 6 canonical wiring tests passed.");
