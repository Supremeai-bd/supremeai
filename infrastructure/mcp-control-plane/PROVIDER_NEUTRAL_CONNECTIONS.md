# Provider-neutral MCP connections

SupremeAI exposes one provider-neutral MCP endpoint. Customers may connect any MCP-compatible AI client; the server does not assume Claude, Cursor, or a specific vendor.

## Admin flow

1. Create a client in the admin dashboard or `POST /clients`.
2. Set a descriptive `provider` value such as `generic`, `claude`, `cursor`, `openai`, `gemini`, or an internal client name.
3. Choose a protocol supported by the client: `streamable-http`, `sse`, `stdio`, or `custom`.
4. Start with `viewer` and read-only scopes.
5. Share the one-time bearer token through a secure channel.
6. Promote to `agent` or `admin` only when the customer explicitly needs those capabilities.
7. Revoke, rotate, expire, and audit every client from the admin control plane.

Provider labels are metadata only. Authorization is determined by the issued token, role, scopes, tenant policy, approval policy, and service health—not by the provider name supplied by a client.

## Client contract

Any MCP-compatible client should connect to the same endpoint with:

```text
Authorization: Bearer <admin-issued-token>
```

The default role is viewer. Write, destructive, and administrative operations require explicit role and scope grants plus the normal approval policy.
