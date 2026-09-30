import assert from "node:assert/strict";
import { approveClient, defaultClientScopes, getOrCreateGuestClient, listClients, registerClient, resolveClient, revokeClient, rotateClient } from "./src/policy/client-registry.js";

const created = registerClient("Customer AI", "viewer", defaultClientScopes("viewer"), undefined, "customer-ai", "streamable-http");
assert.equal(created.client.provider, "customer-ai");
assert.equal(created.client.protocol, "streamable-http");
assert.equal(created.client.role, "viewer");
assert.equal(created.client.status, "pending");
assert.equal(resolveClient(created.token), undefined);
assert.equal(approveClient(created.client.id)?.status, "active");
assert.equal(resolveClient(created.token)?.id, created.client.id);
assert.ok(created.client.scopes.includes("health:read"));
const rotated = rotateClient(created.client.id);
assert.ok(rotated?.token);
assert.equal(resolveClient(created.token), undefined);
assert.equal(resolveClient(rotated!.token)?.id, created.client.id);
assert.equal(revokeClient(created.client.id), true);
assert.equal(resolveClient(rotated!.token), undefined);

// ── #2588: guest auto-registration contract ─────────────────────────────
// Zero-manual-registration for no-auth AI clients + live protocol refresh.
const guestSse = getOrCreateGuestClient("guest_test_registry_1", "Test Guest (1.2.3.4)", "cursor", "sse");
assert.equal(guestSse.status, "active");
assert.equal(guestSse.role, "viewer");
assert.equal(guestSse.protocol, "sse");

// Reconnect over streamable-http → SAME record, protocol follows the latest transport.
const guestHttp = getOrCreateGuestClient("guest_test_registry_1", "Test Guest (1.2.3.4)", "cursor", "streamable-http");
assert.equal(guestHttp.id, guestSse.id);
assert.equal(guestHttp.protocol, "streamable-http");

// Name-based reuse path (#1787): different preferred id, same name → same record.
const guestByName = getOrCreateGuestClient("guest_some_other_id", "Test Guest (1.2.3.4)", "cursor", "sse");
assert.equal(guestByName.id, guestSse.id);
assert.equal(guestByName.protocol, "sse");

// A known provider label upgrades a previously-generic record on reuse.
const relabeled = getOrCreateGuestClient("guest_test_registry_1", "Test Guest (1.2.3.4)", "grok-lab", "sse");
assert.equal(relabeled.provider, "grok-lab");

// Same display name in the same tenant reuses the record (#1787 name-dedupe
// precedence over the #2030 auto-increment path) — guest names embed the IP,
// so an identical name is the SAME logical client reconnecting.
const guestA = getOrCreateGuestClient("guest_t2_a", "Second Guest", "generic", "stdio", "tenant_two");
const guestB = getOrCreateGuestClient("guest_t2_b", "Second Guest", "generic", "stdio", "tenant_two");
assert.equal(guestB.id, guestA.id);
assert.equal(guestB.name, "Second Guest");

// Guests are visible to tenant admins via listClients.
assert.ok(listClients("*").some((c) => c.id === guestSse.id));
assert.ok(listClients("tenant_two").some((c) => c.id === guestA.id));

console.log("client registry contract tests passed");
