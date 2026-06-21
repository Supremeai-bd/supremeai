# 🔐 Secrets Management Policy

This document defines the secrets storage, access, and rotation guidelines for SupremeAI 2.0.

## 🔑 Key Credentials & Tokens

### 1. Email Service Secrets
- **OAuth Refresh Tokens:** Gmail/Outlook OAuth credentials.
- **IMAP App Passwords:** Stored as fallbacks when OAuth is unavailable.

### 2. GitHub Integration Secrets
- **GitHub App Private Key:** Private `.pem` key used to generate installation access tokens.
- **Personal Access Tokens (PAT):** Fallback developer-level access tokens.

---

## 🛡️ Security Guidelines

- **No Raw Password Storage:** Credentials must never be saved in plain text database fields or committed to git repositories.
- **External Secrets Manager:** All tokens, app passwords, and private keys must be stored in secure secrets managers (e.g., HashiCorp Vault, AWS Secrets Manager, GitHub Secrets, or encrypted local environment).
- **Token Rotation Policy:** 
  - OAuth refresh tokens and app passwords must be rotated every **90 days**.
  - GitHub App keys and PATs should be audited and rotated annually or immediately upon suspected breach.
- **Governance & Approval Rules:**
  - AI is strictly prohibited from pushing changes directly to the `main` branch.
  - Changes must always flow through Pull Requests (PRs).
  - Explicit customer/admin approval is required before merging any AI-generated PR.
  - All automated commit actions must be logged for audit trails.
