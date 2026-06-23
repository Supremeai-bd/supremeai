---
name: environment-config-audit
description: >-
  Audit environment configurations across dev/staging/prod for 
  security risks, missing variables, and cross-environment consistency.
domain: devops
subdomain: infrastructure
tags: [config, security, audit, env, docker]
frameworks:
  - NIST-CSF: DE.CM-01
  - MITRE-ATT&CK: T1071
  - CIS: 5.1
version: "1.0"
author: supreme-ai
auto_generate: true
---

## When to Use
- PR changes `.env*`, `docker-compose*`, `config/` files
- New environment setup required
- Security audit requested

## Prerequisites
- Access to all environment configs
- `python-dotenv`, `deepdiff` installed

## Workflow
1. Load all `.env.{environment}` files
2. Cross-diff environments
3. Risk-score each difference
4. Auto-fix safe issues
5. Flag critical for human review

## Verification
- Zero CRITICAL issues
- All required variables present per environment
- No secrets in non-prod environments

## Rationalizations
| Excuse | Rebuttal |
|--------|----------|
| "This is just dev" | Dev secrets leak to prod via copy-paste |
| "I'll fix later" | Auto-fix exists - no excuse |
| "It's just a comment" | Comments don't need API keys |
