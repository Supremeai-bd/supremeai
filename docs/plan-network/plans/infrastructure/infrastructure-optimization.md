---
id: infrastructure-optimization
subject: "Infrastructure Optimization"
document_role: architecture
planning_authority: "Infra Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/infrastructure/free_tier_federation_master_plan_v4.md"
  - "docs/plans/infrastructure/free_tier_survival_and_resource_optimization_guide.md"
  - "docs/plans/architecture/dynamic_configuration_zero_hardcode_roadmap.md"
  - "docs/plans/infrastructure/CI_CD_PIPELINE_ARCHITECTURE.md"
  - "docs/plans/infrastructure/render_memory_leak_fix_roadmap.md"
superseded_by: []
target_scope: supremeai_internal
plan_id: P08
domain: infrastructure
depends_on: ["P01"]
enables: ["P09", "P10"]
implemented_by: "Milestone: Free-Tier Federation v4"
verified_by: "Resource pressure tests + build runtime checks"
related_to: ["P09"]
---

# Plan: Infrastructure Optimization

> **Status:** `Active` · **Owner:** Infra Circle · **ID:** `P08`

## Purpose
Free-tier federation, lean 512 MB survival, dynamic zero-hardcode configuration,
and the CI/CD pipeline architecture. SupremeAI runs on free-tier compute —
this plan is what makes that economically possible. Consolidates 37 legacy docs.

## Depends On
- [P01 — Security Guardian](../security/security-guardian.md) — *why: secret rotation + Infisical flow through here.*

## Enables
- [P09 — Observability](../observability/observability.md) — *how: metrics/log infrastructure is provisioned here.*
- [P10 — Deployment Safety](../governance/deployment-safety.md) — *how: the canary pipeline runs on this infra.*

## Related
- [P09 — Observability](../observability/observability.md) — *coupling: infra provisions the observability stack.*

## Source of Truth
This document defines infrastructure. Free-tier federation, zero-hardcode
config, CI/CD pipeline, and memory-leak remediation are sections/milestones
here, not separate plans.

## Architecture

### Current state
- Free-tier federation v4 designed; multi-account render deployment tracked.
- 512 MB survival guide exists; memory-leak fix roadmap in progress.
- Dynamic configuration roadmap written but not fully enforced (some hardcodes remain).
- CI/CD pipeline architecture documented.

### Target state
- One federated free-tier pool with automated failover.
- Zero hardcode values in the codebase (registry-driven config).
- CI/CD with build runtime optimization + cache.
- Memory leaks eliminated; pressure tests in CI.

### Non-goals
- This plan does **not** define observability tooling (that's P09).
- This plan does **not** define deployment rollback policy (that's P10).

## Execution

See GitHub milestone: **Free-Tier Federation v4**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| Federation v4 | 🟦 Active | Infra | `free_tier_federation_master_plan_v4.md` → fold |
| 512 MB survival | 🟪 Implementing | Infra | `free_tier_survival_..._guide.md` → fold |
| Zero-hardcode config | 🟦 Active | Infra | `dynamic_configuration_zero_hardcode_roadmap.md` → fold |
| CI/CD pipeline | 🟪 Implementing | Infra | `CI_CD_PIPELINE_ARCHITECTURE.md` → fold |
| Memory-leak fix | 🟪 Implementing | Infra | `render_memory_leak_fix_roadmap.md` → fold |
| Render 3-service GHCR | 🟦 Active | Infra | `render_3services_ghcr_deployment_roadmap_bn.md` → fold |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| 512 MB pressure test | perf | ⚠️ | tracked in legacy plan |
| Build runtime check | perf | ⚠️ | `ci_cd_render_build_runtime_optimization_plan_bn.md` |
| Zero-hardcode lint | lint | ❌ | not yet a CI rule |
| Federation failover | e2e | ⚠️ | partial |

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/infrastructure/free_tier_federation_master_plan_v4.md` | archive | canonical strategy folded here |
| `docs/plans/infrastructure/free_tier_survival_and_resource_optimization_guide.md` | archive | becomes "Survival" section |
| `docs/plans/architecture/dynamic_configuration_zero_hardcode_roadmap.md` | archive | becomes "Zero-hardcode" section |
| `docs/plans/infrastructure/CI_CD_PIPELINE_ARCHITECTURE.md` | archive | becomes "CI/CD" section |
| `docs/plans/infrastructure/render_memory_leak_fix_roadmap.md` | archive | becomes "Memory leak" milestone |
| `docs/plans/infrastructure/render_3services_ghcr_deployment_roadmap_bn.md` | archive | becomes "Render deploy" milestone |
| `docs/plans/infrastructure/render_4accounts_deployment_status_record.md` | retain | status record = evidence |
| `docs/archive/plans/infrastructure/production_upgrade_implementation_plan_v2.md` | archive-dry-branch | CP07 conflict (Istio/Kong impossible) → archived 2026-09-25 |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P08 | Planning Circle |
