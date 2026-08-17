# THREAT-MODEL-001: Authentication System

**Date:** 2026-07-08

**System Component:** User & Admin Authentication

**Analyst:** Gemini Code Assist

## Overview

This document outlines potential security threats to the SupremeAI 2.0 authentication system, which includes user login, admin login, and API token validation. We use the STRIDE methodology for threat modeling.

## System Description

- **Admin Auth:** Uses Firebase Authentication + Firestore record check + TOTP for Multi-Factor Authentication (MFA).
- **User Auth:** Primarily handled by Firebase Auth.
- **API Auth:** Uses JWTs with role claims (`admin`, `user`) and a Redis-based blacklist for token revocation. A legacy API token with constant-time comparison is used as a fallback.
- **Service-to-Service Auth:** Internal webhooks (like Cloud Scheduler invoking the Orchestrator) are protected using Google Cloud IAM native OIDC token verification. Public traffic is strictly blocked on these routes.
- **Fake Logins:** A `FAKE_USERS` dictionary exists for non-production environments.

---

## Threat Analysis (STRIDE)

### 1. Spoofing (Pretending to be someone else)

- **Threat:** An attacker impersonates a legitimate user or admin.
- **Attack Vector:**
  - Stealing credentials (password, JWT, API key).
  - Bypassing authentication checks.
  - Exploiting the `FAKE_USERS` system in a misconfigured production environment.
- **Mitigation:**
  - **Current:** Use of Firebase Auth handles password hashing and secure login. Admin access requires TOTP (MFA), which significantly reduces risk. JWTs have short expiry times. Internal endpoints (e.g., `/orchestrator/tick`) are bypassed by custom JWT logic and exclusively verified by Google Cloud IAM at the infrastructure layer.
  - **Recommendation:** Ensure the check for `settings.env.lower() == "production"` is robust and cannot be easily bypassed by manipulating environment variables at runtime. Consider removing the `FAKE_USERS` code entirely and using a dedicated test database instead.

### 2. Tampering (Modifying data)

- **Threat:** An attacker modifies an authentication token to gain higher privileges.
- **Attack Vector:** Modifying the payload of a JWT (e.g., changing `{"role": "user"}` to `{"role": "admin"}`) before it is signed, or if the signature validation is weak.
- **Mitigation:**
  - **Current:** JWTs are signed with a strong secret using the HS256 algorithm. The server validates the signature on every request, so any tampering with the payload will invalidate the token.
  - **Recommendation:** The `jwt_secret` must be long, complex, and stored securely as an environment variable, never in code. The `core/config.py` file's validation for a secure JWT secret is a good practice and should be enforced everywhere.

### 3. Information Disclosure (Exposing sensitive data)

- **Threat:** The system leaks sensitive information like passwords, secrets, or session tokens.
- **Attack Vector:**
  - Hardcoded secrets in source code (e.g., old `test-token`).
  - Leaking secrets through logs (e.g., old TOTP secret logging).
  - Exposing secrets via API endpoints (e.g., old `/config` endpoint).
- **Mitigation:**
  - **Current:** The `supremeai-comprehensive-analysis.md` shows that many of these issues have been fixed. Secrets are loaded from environment variables, and the `/config` endpoint now masks sensitive values.
  - **Recommendation:** Perform regular automated secret scanning on the codebase. Consolidate the two `config.py` files to ensure consistent security validation logic is applied across the entire application.
