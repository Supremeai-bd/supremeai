import assert from "node:assert/strict";
import { defaultClientScopes, registerClient, resolveClient, revokeClient, rotateClient } from "./src/policy/client-registry.js";

const created = registerClient("Claude Desktop", "viewer", defaultClientScopes("viewer"));
assert.equal(created.client.role, "viewer");
assert.equal(resolveClient(created.token)?.id, created.client.id);
assert.ok(created.client.scopes.includes("health:read"));
const rotated = rotateClient(created.client.id);
assert.ok(rotated?.token);
assert.equal(resolveClient(created.token), undefined);
assert.equal(resolveClient(rotated!.token)?.id, created.client.id);
assert.equal(revokeClient(created.client.id), true);
assert.equal(resolveClient(rotated!.token), undefined);
console.log("client registry contract tests passed");
