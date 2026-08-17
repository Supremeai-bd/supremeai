# Authentication API

## Overview

The Authentication API provides endpoints for user authentication, session management, and credential verification. All sensitive operations are protected by the AutonoGuard Engine with JIT OTP enforcement.

## Endpoints

### POST `/api/v1/auth/login`

Authenticate a user and receive an access token.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `email` | string | Yes | User email address | `user@example.com` |
| `password` | string | Yes | User password | `securePassword123` |

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "usr_123",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

**Response (401):**

```json
{
  "error": "Invalid credentials",
  "code": "AUTH_INVALID_CREDENTIALS"
}
```

### POST `/api/v1/auth/logout`

Invalidate the current session.

**Headers:**
- `Authorization: Bearer {access_token}`

**Response (200):**

```json
{
  "message": "Successfully logged out"
}
```

### POST `/api/v1/auth/refresh`

Refresh an expired access token using a refresh token.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `refresh_token` | string | Yes | The refresh token received during login | `rt_abc123...` |

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### POST `/api/v1/auth/register`

Register a new user account.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `email` | string | Yes | User email address | `newuser@example.com` |
| `password` | string | Yes | User password (min 8 chars) | `securePassword123` |
| `name` | string | Yes | Full name | `Jane Doe` |

**Response (201):**

```json
{
  "id": "usr_456",
  "email": "newuser@example.com",
  "name": "Jane Doe",
  "created_at": "2026-07-26T06:00:00Z"
}
```

## Security

- All authentication endpoints are rate-limited (10 requests/minute per IP)
- JWT tokens are stored in HTTPOnly cookies (never localStorage)
- Sensitive operations (billing, admin, payments) require JIT OTP verification
- IP churn detection triggers re-authentication if >5 IPs detected in 1 hour
