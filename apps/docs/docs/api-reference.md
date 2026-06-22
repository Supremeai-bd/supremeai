# SupremeAI 2.0 — API Reference

## Authentication

All admin endpoints require JWT Bearer token:
```
Authorization: Bearer <access_token>
```

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| GET | `/actuator/health` | Spring-compatible health probe |

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/login` | Admin password login (returns OTP challenge) |
| POST | `/api/admin/verify` | Verify TOTP and get JWT |
| POST | `/api/admin/firebase-login` | Firebase Auth login |
| POST | `/api/auth/sso/saml` | SAML 2.0 SSO |
| POST | `/api/auth/sso/oidc/discovery` | OIDC discovery |
| POST | `/api/auth/sso/oidc/{provider}/authorize` | OIDC authorize (okta/azure/google) |
| POST | `/api/auth/sso/oidc/{provider}/callback` | OIDC callback |
| GET | `/api/auth/sso/oidc/{provider}/logout` | OIDC logout |
| GET | `/api/auth/sso/metadata` | SAML SP metadata XML |

## Onboarding

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/onboarding/complete` | Complete onboarding (creates user, issues JWT) |
| GET | `/api/onboarding/status/{user_id}` | Get onboarding status |

## Tools

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tools/smell-check` | Run code smell analysis on a path |
| GET | `/api/tools/` | List registered tools |
| POST | `/api/tools/` | Register a tool |
| PATCH | `/api/tools/{id}` | Update a tool |
| DELETE | `/api/tools/{id}` | Archive a tool |

## Rate Limiting

| Method | Path | Description |
|--------|------|-------------|
| (middleware) | global | 120 req/min, burst=20 by default |
| (middleware) | `/api/tools/*` | Per-tenant Redis-backed quota |

## Admin

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/rules` | Get constitutional rules |
| POST | `/admin/rules` | Update constitutional rules |
| GET | `/admin/cloud-distribution` | Multi-cloud routing stats |
| GET | `/gcp/health` | GCP health check |
| GET | `/gcp/verification-queue/stats` | Firestore queue stats |
| GET | `/gcp/pubsub/stats` | Pub/Sub queue stats |

## Tenant Limits

| Method | Path | Description |
|--------|------|-------------|
| PATCH | `/api/tools/tenant-limits/{tenant_id}/tier` | Change billing tier |
| POST | `/api/tools/tenant-limits/{tenant_id}/override` | Admin override |
