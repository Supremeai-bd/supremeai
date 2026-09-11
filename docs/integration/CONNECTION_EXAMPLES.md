# SupremeAI Connection Examples

These examples describe the user-facing contract. They are not a substitute for provider consent or secret management.

## Remote MCP server

```yaml
connect: https://mcp.example.com/mcp
```

Expected result: SupremeAI discovers the server, registers it for the current tenant, and exposes only policy-approved capabilities.

## REST API

```yaml
connect: https://api.example.com
kind: api
```

Expected result: the HTTP adapter discovers the declared API contract or uses a previously approved adapter profile. Authentication is handled through the secret broker.

## OAuth service

```yaml
connect: https://github.com
kind: oauth
```

Expected result: SupremeAI identifies the connector and opens the provider-required consent path. Tokens remain outside application configuration and logs.

## Local MCP bridge

```yaml
connect: stdio://my-local-mcp
kind: mcp
```

Expected result: a trusted local bridge is registered. Local process configuration remains an operator concern; tenant policy and audit remain SupremeAI concerns.

## Supabase or another data service

```yaml
connect: https://project.example.supabase.co
kind: service
```

Expected result: the service adapter validates the project endpoint and uses provider-managed credentials or an approved secret reference. Database access remains scoped by tenant and service policy.

## Custom tool endpoint

```yaml
connect: https://tools.example.com/manifest
kind: service
```

Expected result: SupremeAI validates the manifest, fingerprints the endpoint, applies safe defaults and publishes only verified tools.

## Administrator authority

```yaml
connection_role: admin
```

This changes the requested connection role only after actor authorization and policy evaluation. It does not grant system authority or bypass approval for high-impact actions.

## Revocation

```yaml
connection_status: revoked
```

Future invocations stop immediately and the audit trail is retained.

## Troubleshooting

| Status | Meaning | Next action |
|---|---|---|
| `pending` | Discovery or provider consent is incomplete | Complete required provider consent or wait for bounded discovery |
| `limited` | Only a safe subset is available | Inspect missing scope or provider capability |
| `error` | Endpoint, auth or protocol failed | Review the correlation ID and retry after correcting the cause |
| `revoked` | Access was intentionally disabled | Reconnect or ask an authorized admin |

Never paste access tokens into a connection line. If an endpoint is private, requires a VPN, or has no supported protocol, the backend must explain that limitation rather than pretending a URL-only connection is possible.
