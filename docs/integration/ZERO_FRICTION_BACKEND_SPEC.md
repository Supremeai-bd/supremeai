# Zero-Friction SupremeAI Backend Specification

**Status:** Canonical implementation specification  
**Scope:** All external and internal capability connections

## 1. Objective

Expose one governed connection contract to customers and administrators while keeping transport-specific complexity inside the SupremeAI control plane. Zero-friction is a product and architecture property of SupremeAI; it is not permission to weaken authentication, authorization or verification.

## 2. Canonical connection record

```yaml
Connection:
  id: uuid
  tenant_id: uuid
  created_by: actor_id
  kind: mcp | api | oauth | service | browser
  endpoint: normalized_uri_or_identifier
  display_name: discovered_or_user_supplied
  fingerprint: stable_endpoint_fingerprint
  status: pending | active | limited | error | revoked
  role: user | admin | system
  allowed_actions: capability_policy
  discovered_capabilities: capability_metadata[]
  credential_ref: secret_manager_reference_or_null
  policy_version: string
  last_verified_at: timestamp
  created_at: timestamp
  updated_at: timestamp
```

`tenant_id`, `created_by`, `endpoint`, `kind`, status and policy metadata are mandatory. Secrets, access tokens and raw authorization headers must never be stored in this record or emitted to logs.

## 3. Unified lifecycle

```text
Intent / URL
  → Normalize and validate
  → Resolve tenant and actor
  → Discover or request provider consent
  → Apply policy and least privilege
  → Register centrally
  → Health-check and verify
  → Publish safe capabilities
  → Invoke through policy gateway
  → Audit and learn
```

Every transport uses this lifecycle. Adapters may implement different protocol details but may not create independent permission or audit systems.

## 4. Discovery and validation

The connection service must:

1. accept only supported schemes and endpoint forms;
2. reject malformed, disallowed, private-network and unsafe redirect targets;
3. resolve redirects under an explicit allow policy;
4. identify protocol and provider without trusting display metadata;
5. discover tools/resources/schemas using bounded timeouts and response limits;
6. validate declared capabilities against observed behavior where feasible;
7. detect authentication requirements without collecting credentials in plaintext;
8. store a stable fingerprint to prevent accidental duplicate registration;
9. mark the connection `limited` when discovery is incomplete but safe read-only access is possible;
10. produce an audit event for every state transition.

Discovery metadata is untrusted input. Tool names and descriptions must not override SupremeAI policy or instructions.

## 5. Permission and authority

The default role is the least-privilege role allowed by tenant policy, normally `user`. Role resolution is:

```text
actor authority
  ∩ tenant policy
  ∩ connection policy
  ∩ capability risk
  ∩ provider scope
```

An administrator may submit a one-line role change, but the backend must re-authorize the actor, compute the effective permissions, invalidate stale policy caches, and audit the decision. `system` is never a customer shortcut; it is reserved for explicitly governed platform automation.

See [PERMISSION_MODEL.md](./PERMISSION_MODEL.md) for the normative rules.

## 6. Central registry and control interface

The registry is the source of truth for connection identity, tenant scope, lifecycle, policy version and capability metadata. Chat, Dashboard, agents, workflows and MCP control tools must query the same registry and invoke through the same policy gateway.

The registry may begin as a version-controlled configuration projection, but runtime authority must be held by a transactional, tenant-aware store when connections are mutable. A YAML file must not be treated as a security boundary.

Required operations:

- `connect(endpoint, kind?)`
- `inspect(connection_id)`
- `list(tenant_id, actor_id)`
- `set_role(connection_id, role)`
- `allow(connection_id, actions)`
- `revoke(connection_id)`
- `verify(connection_id)`
- `invoke(connection_id, capability, input)`

All operations require authenticated actor context and produce correlation IDs.

## 7. Tenant isolation

Every read, write, discovery result, credential reference, capability invocation and audit query must be scoped to the tenant. Cross-tenant access is denied by default. Shared platform capabilities must be explicitly marked as platform-owned and still evaluated against the requesting tenant's policy.

## 8. Reliability and graceful degradation

Use bounded timeouts, exponential backoff, circuit breakers and idempotent registration. Provider failure must not erase the last known policy or silently expand access. If a provider is unavailable, mark it `error` or `limited`, preserve evidence, and expose a truthful status.

## 9. Audit events

At minimum record:

```yaml
ConnectionAuditEvent:
  id: uuid
  tenant_id: uuid
  actor_id: uuid
  connection_id: uuid
  action: connect | discover | authorize | role_change | invoke | error | revoke
  result: success | denied | failed | limited
  policy_version: string
  correlation_id: string
  safe_metadata: json
  occurred_at: timestamp
```

Never log secrets, full private payloads or provider tokens. Redact sensitive values before persistence.

## 10. Acceptance criteria

- A supported remote endpoint can be requested using one user-facing connection line.
- No URL alone grants authority.
- Default access is tenant-scoped and least privilege.
- An authorized admin can change a role with one logical configuration line.
- All transports use the same registry, policy gateway and audit model.
- Tenant isolation is enforced at every operation boundary.
- Failed discovery is visible and cannot be mistaken for an active connection.
- High-impact actions remain subject to risk and approval policy.

## 11. Non-goals

This specification does not promise that every provider can be connected without provider consent, credentials or licensing. It does not define a frontend wizard, expose secrets, or replace backend authentication and authorization.
