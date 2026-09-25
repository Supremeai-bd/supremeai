---
id: security-guardian
subject: "Security Guardian"
document_role: architecture
planning_authority: "Security Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-25
supersedes:
  - "docs/plans/features/antihacking_security_defense_framework.md"
  - "docs/security/GITHUB_TOKEN_CANONICALIZATION_PLAN.md"
superseded_by: []
target_scope: supremeai_internal
plan_id: P01
domain: security
depends_on: []
enables: ["P02", "P03", "P04", "P06", "P08"]
implemented_by: "Milestone: Security Hardening"
verified_by: "Security Audit + gitleaks + pentest"
related_to: ["P10", "P11"]
---

# Plan: Security Guardian

> **Status:** `Active` · **Owner:** Security Circle · **ID:** `P01`

## Purpose
Establish the trust boundary every other domain relies on: secrets
canonicalization, provider-neutral auth, audit trail, and a living threat
model. P01 is the foundation of the network — five other plans cannot reach
Stable until this one does.

## Depends On
*(foundational — no upstream dependencies)*

> ⚠️ Foundational plans carry the highest blast radius. Every change here is a
> regression risk for P02, P03, P04, P06, P08.

## Enables
- [P02 — Provider Abstraction](../intelligence/provider-abstraction.md) — provider auth flows through here
- [P03 — MCP Architecture](../mcp/mcp-architecture.md) — tool execution needs a sandboxed trust boundary
- [P04 — Agent Orchestration](../agents/agent-orchestration.md) — HITL + capability scoping
- [P06 — Browser Automation](../automation/browser-automation.md) — sandbox escape prevention
- [P08 — Infrastructure Optimization](../infrastructure/infrastructure-optimization.md) — secret rotation, Infisical

## Related
- [P10 — Deployment Safety](../governance/deployment-safety.md) — pre-push verification gate
- [P11 — Testing & Quality](../governance/testing-quality.md) — security test suite

## Source of Truth
This document is the canonical definition of SupremeAI's security posture.
Other documents must reference it (`See: Security Guardian`) rather than
duplicate it.

## Architecture

### Current state
- `secrets_registry.yaml` (48 KB) enumerates every secret; `gitleaks.toml` + `.pre-commit-config.yaml` enforce pre-commit scanning.
- GitHub token canonicalization plan exists but is **not yet fully implemented**.
- The `security-defense` family had only **1 doc** — underdeveloped relative to its criticality.
- `docs/audit_reports/` contains 47 audit files across rounds 14–19.

### Target state
- Single provider-neutral auth gateway (with P02).
- Every secret rotation automated via Infisical.
- Continuous `gitleaks` + `semgrep` in CI, not just pre-commit.
- A living threat model refreshed each release.

### Non-goals
- This plan does **not** define agent capability scoping (that's P04).
- This plan does **not** define deployment rollback (that's P10).

## Execution

See GitHub milestone: **Security Hardening**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| Token canonicalization | 🟦 Active | Security | `docs/security/GITHUB_TOKEN_CANONICALIZATION_PLAN.md` |
| Infisical rollout | 🟪 Implementing | Infra | `docs/plans/infrastructure/infisical_enterprise_secret_management_guide.md` |
| Continuous secret scanning | ⬜ Proposed | Security | *(new issue)* |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| gitleaks pre-commit | audit | ✅ | `.pre-commit-config.yaml` |
| gitleaks in CI | audit | ✅ | `.github/workflows/scheduled-deep-audit.yml` (gitleaks v8.18.2, nightly schedule + manual; critical/high findings fail the job) — verified on run `36114000424` (Heavy Analysis ✅, 2026-09-25) |
| Token canonicalization e2e | integration | ❌ | `docs/security/...` in progress |
| Pentest round 19 | audit | ✅ | `docs/audit_reports/round19_comments/` |
| Threat model refresh | review | ❌ | *(no current model)* |

> P01 cannot reach **Stable** until gitleaks-in-CI, token canonicalization, and
> the threat model are all ✅.
>
> **Stable-promotion blocker record (issue #1294, verified 2026-09-25):**
> - gitleaks-in-CI — ✅ **closed** (evidence above; was stale ⚠️ — wired in
>   `scheduled-deep-audit.yml`, green on run `36114000424`).
> - token canonicalization e2e — ❌ **open blocker**: no integration test
>   asserting canonical token handling end-to-end was found in
>   `backend/core/security/` / `backend/tests/` (grep 2026-09-25);
>   `docs/security/GITHUB_TOKEN_CANONICALIZATION_PLAN.md` remains a plan, not
>   a verified implementation.
> - threat model refresh — ❌ **open blocker**: no threat-model document exists
>   anywhere under `docs/` (verified 2026-09-25).
> 
> **Registry decision: P01 stays `Active`** — honest state per the
> UNVERIFIED != PASS doctrine; promotion waits until both open blockers close
> with evidence links.

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/features/antihacking_security_defense_framework.md` | archive | folded into this canonical doc |
| `docs/security/GITHUB_TOKEN_CANONICALIZATION_PLAN.md` | archive | becomes a milestone under this plan |
| `docs/audit_reports/round*_comments/` | retain | evidence — stays in place, linked from here |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P01 | Planning Circle |
| 2026-09-25 | Stable-gate evidence audit (issue #1294): gitleaks row ⚠️→✅ (wired + green, run 36114000424); blocker record added — promotion deferred, P01 stays Active | Security Circle (agent, evidence-linked) |
