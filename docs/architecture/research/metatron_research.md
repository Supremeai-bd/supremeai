# Metatron Security Sandbox Research (issue #4058)

> **Priority:** P3 — research only, no implementation
> **Date:** 2026-10-06
> **Roadmap v2 section:** Phase 2 → §2.2 Integration Matrix (row #13: Metatron)

## Mission

Research Metatron as an isolated security sandbox scanner. Determine if it fills a gap SupremeAI's native security tooling cannot.

## What is Metatron?

Metatron is an isolated security analysis framework designed for running security scanners in sandboxed environments. It provides:
- Isolated execution containers for untrusted security tools
- Network-egress-controlled sandbox for scanner traffic
- Result aggregation + severity scoring
- Plugin architecture for multiple scanner types

## SupremeAI's Current Security Stack (verified on main)

| Component | File | Purpose |
|---|---|---|
| Code Vulnerability Scanner | `backend/agents/code_vulnerability_scanner_agent.py` | AI-driven code vulnerability scanning |
| Docker Sandbox | `sandbox/docker_sandbox.py` | Native Docker-based code execution isolation |
| SSRF Protection | `backend/core/security/ssrf_protection.py` (historical, now consolidated) | SSRF guard for outbound requests |
| PII Redaction | Structured logging gate (#3415) | JWT/email/phone/API key/bearer/credit card patterns |
| Auth Middleware | `backend/core/security/auth_middleware.py` | JWT decode, public paths, Bearer, query token, cookies, CSRF |
| Workload Admission | `backend/core/admission/` (#3513) | 5-dimension: agent_count, parallelism, prompt_tokens, retry_count, queue_depth |
| Security Audit Script | `scripts/devops/zero_knowledge_secret_audit.py` | Zero-knowledge secret presence audit |
| Auto Secret Rotate | `scripts/security/auto_secret_rotate.py` | Automated secret rotation |
| Headless Agent Registry | `backend/tools/headless_agent_registry.py` | Agent registration + security context |
| SyncGuard Agent | `backend/agents/syncguard/syncguard_agent.py` | Sync guard for concurrent operations |

**Total native security components: 10+** — SupremeAI already has a comprehensive security stack.

## Gap Analysis

| Capability | Metatron | SupremeAI Native | Gap? |
|---|---|---|---|
| Isolated scanner execution | ✅ Container-per-scan | ✅ `sandbox/docker_sandbox.py` | ❌ No gap |
| Network egress control | ✅ Network policy per scan | ⚠️ SSRF guard exists but not per-scan | Minor gap |
| Multi-scanner aggregation | ✅ Plugin architecture | ❌ No multi-scanner aggregation | Minor gap |
| Severity scoring | ✅ Built-in | ⚠️ Per-scanner, not aggregated | Minor gap |
| Untrusted tool isolation | ✅ Purpose-built | ✅ Docker sandbox | ❌ No gap |

**Conclusion:** No critical gap. Minor gaps in multi-scanner aggregation + per-scan network policy, but these are not blockers for current operations.

## Benchmark (Metatron vs native)

Not run — Metatron would require a separate deployment (Docker + network policy config) for a formal benchmark. The architectural comparison above is sufficient evidence at P3 priority.

## Security Review

| Risk | Metatron | Native |
|---|---|---|
| Supply chain | New dependency (Metatron framework + plugins) | Zero new deps |
| Attack surface | Metatron itself is an attack surface (sandbox escape risk) | Native sandbox already hardened |
| Operational burden | Metatron deployment + maintenance + version drift | Zero |

## Maintenance Cost

- Metatron: High (Docker deployment + plugin updates + network policy maintenance)
- Native: Zero (already integrated)

## Decision: **REFERENCE ONLY** (not Adopt)

**Rationale:** SupremeAI already has a comprehensive native security stack (10+ components). Metatron's isolated scanner execution is already covered by `sandbox/docker_sandbox.py`. The minor gaps (multi-scanner aggregation, per-scan network policy) are not sufficient justification for adopting a new heavy dependency at P3 priority.

If a future security task genuinely needs multi-scanner aggregation, open a NEW issue referencing this research. Do NOT adopt Metatron without a new audit proving the native scanner cannot meet the requirement.

## Bengali Note

Metatron = শুধু research। SupremeAI-তে ইতিমধ্যে ১০+ native security component আছে। Metatron-এর isolated scanner execution `sandbox/docker_sandbox.py` দ্বারা আচ্ছাদিত। নতুন heavy dependency যোগ করার প্রয়োজন নেই।
