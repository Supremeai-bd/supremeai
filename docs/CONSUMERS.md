# API Consumers

This document tracks known consumers of the SupremeAI API surface.

## Internal Consumers

| Consumer | Endpoint Pattern | Auth Method | Notes |
|---|---|---|---|
| VS Code Extension | `/api/v1/*` | JWT (user token) | Desktop client hub |
| Tauri Desktop App | `/api/v1/*` | JWT (user token) | Desktop workstation |
| Capacitor Mobile App | `/api/v1/*` | JWT (user token) | Mobile client |
| MCP Control Tower | `/api/v1/mcp/*` | Service key (`sk-supreme-*`) | Infrastructure orchestration |
| Browser Service | `/api/v1/browser/*` | Service key | Headless automation |

## External Consumers

| Consumer | Endpoint Pattern | Auth Method | Notes |
|---|---|---|---|
| GitHub Webhooks | `/api/webhooks/github` | HMAC signature | PR review events |
| Render Deploy Hooks | `/healthz` | None (public) | Health checks |

## Webhook Endpoints (public, signature-verified)

- `/api/webhooks/github` — HMAC-verified via `_verify_signature()`
- `/api/v1/pr-review/webhook` — HMAC-verified

## Notes

- Core JWT authentication requires `iss=supremeai`, `aud=supremeai-api`, `exp`, and `jti`.
- Previously issued JWTs without these required claims are rejected; sign in again after rollout.
- Service keys use the `sk-supreme-` prefix and are verified via `keygen.verify_key()`
- Guest tokens are short-lived (300s TTL) and quota-limited
- Living Engine domain execution uses the LLM gateway; unavailable providers or empty/failed responses produce `success=false`, not synthetic offline results.
- Living Engine results include `reflection` on success and failure. If feedback itself fails, this field reports `status=unavailable` and `error_type` without changing the execution outcome.
- Generated-code execution remains disabled unless the existing local-development codegen gate is explicitly enabled.
