# SupremeAI Zero-Friction Integration Handbook

**Status:** Canonical design and operating guide  
**Audience:** SupremeAI customers, tenant administrators, agents and implementers

## What zero-friction means

Zero-friction belongs to **SupremeAI**, not to MCP alone. MCP, REST APIs, OAuth services and internal tools are different capability transports, but they enter SupremeAI through one governed connection path.

The user-facing promise is intentionally small:

```text
Connect a capability: https://example.com/mcp
```

SupremeAI then discovers the endpoint, registers it for the correct tenant, applies the least-privilege default, and makes approved capabilities available through the central control interface. Backend discovery, retries, credential handling, policy checks and audit logging remain behind the interface.

Zero-friction does not mean zero security. A URL never grants authority by itself. Credentials, provider consent, tenant policy and risk checks still apply.

## Customer path

For an already public, compatible endpoint, the customer supplies one connection line:

```yaml
connect: https://mcp.example.com/mcp
```

Expected behavior:

1. SupremeAI normalizes and validates the URL.
2. The endpoint is discovered and fingerprinted.
3. Supported tools/resources and required authentication are recorded.
4. The connection is registered under the authenticated tenant.
5. The customer receives the least-privilege role allowed by tenant policy.
6. Safe, read-only or otherwise permitted capabilities become queryable everywhere the customer is authorized.

If the provider requires OAuth or a secret, the user completes only that provider-required consent step. SupremeAI must not ask users to expose tokens in chat or configuration files.

## Administrator authority

Basic connection needs no extra permission line. An administrator changes the connection role only when broader authority is intentionally required:

```yaml
connection_role: admin
```

The role change is evaluated against tenant policy, risk and the administrator's own authority, then recorded in the audit trail. It does not bypass approval requirements for destructive, financial, privacy-sensitive or otherwise high-impact actions.

A safer explicit form is available when a tenant wants capability-level control:

```yaml
connection_role: user
allow: [read, search, draft]
```

## One model for every capability

The same SupremeAI entry point applies to:

| Capability | User-facing input | Internal transport |
|---|---|---|
| MCP server | URL | Streamable HTTP, SSE or local bridge |
| REST API | URL | HTTP adapter |
| OAuth service | Service URL or connector ID | OAuth authorization and token broker |
| Internal service | Service identifier or URL | Governed service adapter |
| Browser capability | Approved site URL | Browser worker |

The transport may differ. Tenant scope, policy, permission, risk, observability and lifecycle must not.

## What users should not need to know

Users should not need to understand registry tables, adapter classes, health probes, token rotation, retry policy, circuit breakers, audit event schemas or worker placement. Those are implementation concerns owned by the central SupremeAI control plane.

## Failure behavior

A failed connection becomes an observable lifecycle state, not a silent failure:

- `pending`: accepted and awaiting discovery or consent;
- `active`: discovered, policy-approved and usable;
- `limited`: connected but only a safe subset is available;
- `error`: discovery or provider access failed;
- `revoked`: disabled by the user, admin or policy.

SupremeAI retries transient failures with bounded backoff, preserves the last known safe metadata, and reports a short actionable status. It never reports a capability as active before validation succeeds.

## Security commitments

- Every connection is tenant-scoped and actor-scoped.
- URL validation prevents unsafe redirects, private-network abuse and unsupported protocols.
- Secrets are stored in a secret manager or provider-managed token broker, never in repository files or logs.
- Default access is least privilege; authority is never inferred from a URL.
- High-impact actions still require policy checks and human approval where configured.
- Connect, change, invoke, failure, revoke and delete events are auditable.
- Disconnecting revokes future use while preserving an audit record.

## Canonical principle

> Customers should experience SupremeAI as one simple system. Integration complexity may remain in the backend, but authority, policy, tenant boundaries and verification must remain centralized in SupremeAI.

See [ZERO_FRICTION_BACKEND_SPEC.md](./ZERO_FRICTION_BACKEND_SPEC.md), [PERMISSION_MODEL.md](./PERMISSION_MODEL.md), and [CONNECTION_EXAMPLES.md](./CONNECTION_EXAMPLES.md).

---

## Bengali quick explanation

ব্যবহারকারীর কাজ যতটা সম্ভব এক লাইনে থাকবে: capability-এর URL দিন। SupremeAI নিজে discovery, validation, tenant scope, default permission, audit এবং failure handling করবে। Full authority দরকার হলে admin শুধু role পরিবর্তন করবে; URL নিজে কখনও authority দেবে না।

"Zero-friction SupremeAI" মানে frontend/customer/admin-এর কাছে একটাই সহজ connection model—backend-এর নিরাপত্তা ও governance বাদ দেওয়া নয়।

---

**Related architecture:** [SUPREMEAI_CORE_CONSTITUTION.md](../architecture/SUPREMEAI_CORE_CONSTITUTION.md)

**Version:** 1.0
