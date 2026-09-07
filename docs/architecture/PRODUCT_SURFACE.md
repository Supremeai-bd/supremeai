# SupremeAI Product Surface

## Product promise

SupremeAI is a tenant-owned, governed AI workspace. Users see outcomes and opted-in tools; administrators govern access; platform developers operate the control plane.

## Portals

### User workspace

Default navigation is intentionally small:

- Ask: start a task or conversation.
- Projects: organize ongoing work.
- Files: use documents and artifacts.
- Activity: review recent work and outcomes.
- Settings: choose optional tools and personal preferences.

Optional tools are enabled by the tenant/user policy, not only by hiding or showing a frontend tab. Development tools, terminal access, infrastructure controls, swarm, evolution, provider internals, and MCP controls are never default user navigation.

### Tenant Admin console

Tenant admins manage their own tenant only:

- Members and roles
- Capability activation
- Approvals and policies
- Integrations
- Usage and limits
- Audit and security events
- Tenant health

### Platform/Developer console

Platform operators manage the SupremeAI platform:

- MCP/control plane
- Circles and capability registry
- Providers and adapters
- Runtime, workers, queues, and infrastructure
- Evolution and platform diagnostics

## Route ownership

- `/workspace/*` is the outcome-oriented user surface.
- `/tenant-admin/*` is tenant-scoped administration and requires tenant-admin permissions.
- `/platform/*` is platform/developer operation and requires platform permissions.
- `/api/v1/capabilities/*` is the governed execution boundary; it is not a substitute for portal authorization.
- Compatibility routes may remain during migration, but new mutations must declare their owning portal and use the capability gateway.

## Runtime ownership

```text
User/Admin/Agent
  -> Chat or Dashboard
  -> CapabilityRequest
  -> Central discovery and policy
  -> MCP/control interface
  -> Circle adapter
  -> Backend engine/provider
  -> Verification
  -> Audit and reusable experience
```

## Product rules

1. UI visibility is not authorization.
2. Every consequential action has a tenant, actor, correlation ID, policy decision, and audit context.
3. Backend policy remains authoritative over frontend role or module state.
4. Existing compatibility routes may remain, but new user-facing features must use canonical portals and capability contracts.
5. New features require a clear product owner, Circle owner, verification strategy, and failure behavior before implementation.
6. Platform complexity is progressive disclosure, not a default user experience.
