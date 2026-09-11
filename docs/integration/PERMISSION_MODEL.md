# SupremeAI Connection Permission Model

## Principle

Zero-friction means minimal user effort, not automatic authority. A connection URL identifies a capability; it does not authorize actions.

## Effective authority

```text
Effective authority =
  actor role
  ∩ tenant policy
  ∩ connection role
  ∩ capability action policy
  ∩ risk / approval policy
  ∩ provider-granted scope
```

The narrowest applicable boundary wins.

## Roles

| Role | Default use | Meaning |
|---|---|---|
| `user` | Customer connection | Read, search, compose and other explicitly allowed low-risk actions |
| `admin` | Tenant administrator | Broader tenant-scoped management, still subject to risk and approval |
| `system` | Platform automation | Reserved for governed internal automation; never granted by a URL |

Roles are labels for policy evaluation, not unconditional bypasses.

## One-line operations

Default connection:

```yaml
connect: https://example.com/mcp
```

Optional administrator change:

```yaml
connection_role: admin
```

The backend must verify that the actor may make this change. A role change may still require provider consent, re-authentication, human approval or a narrower action allow-list.

## Safe defaults

- deny by default when capability risk is unknown;
- prefer read-only access during discovery;
- do not inherit admin authority from the connector owner unless tenant policy explicitly says so;
- keep provider scopes no broader than the requested capability set;
- revoke immediately for future invocations when a connection is disabled;
- retain an immutable audit record of grants, changes and revocations.

## Sensitive actions

Deletes, external messages, financial actions, data exports, credential changes, code execution and tenant administration require their own policy decision. `admin` does not automatically remove human approval or safety checks.

## Revocation

Revocation should be as simple as:

```yaml
connection_status: revoked
```

Revocation blocks future use, invalidates cached authorization, and records who revoked it and why. Existing provider tokens must also be revoked or expired according to provider support.
