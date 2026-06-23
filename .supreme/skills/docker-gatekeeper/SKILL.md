---
name: docker-gatekeeper
description: >-
  Multi-layer Docker image optimization, size check, and security compliance.
domain: devops
subdomain: infrastructure
tags: [docker, security, container, optimization]
frameworks:
  - CIS: Docker Benchmark 4.1
  - NIST-CSF: PR.IP-04
version: "1.0"
author: supreme-ai
auto_generate: true
---

## When to Use
- PR modifies any `Dockerfile`, `docker-compose*`, or container config files.
- Before deploying container images.

## Prerequisites
- Local docker service running or docker history access.
- `google-generativeai` package installed (for AI size autopsies).

## Workflow
1. Run static checks on Dockerfiles (`security_check.py`).
2. Run compliance checks (`compliance_check.py`).
3. Run docker image size analysis and generate report (`size_check.py`).
4. If image size exceeds limit, execute AI bloat analysis using Gemini.

## Verification
- Docker image size under threshold.
- No critical security issues found (e.g. running as root).
- Compliance checks passed.
