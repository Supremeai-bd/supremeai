---
id: verification-production-checks
subject: "Verification — Production Checks"
document_role: verification
planning_authority: "Quality Circle + Infra Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-24
supersedes: []
superseded_by: []
target_scope: supremeai_internal
---

# Verification — Production Checks

> **Layer 5 — Verification (runtime).** The thing that turns "it passed CI"
> into "it works in production." Owned jointly by Quality and Infra.

---

## SLOs (target)

| SLO | Target | Source plan | Dashboard |
|-----|--------|-------------|-----------|
| Control-tower availability | 99.5% (free-tier realistic) | [P03](../plans/mcp/mcp-architecture.md) | Grafana |
| Agent loop P95 latency | < 8 s | [P04](../plans/agents/agent-orchestration.md) | Grafana |
| Memory recall accuracy | > 90% | [P05](../plans/intelligence/memory-knowledge-engine.md) | recall test |
| Frontend TTI | < 3 s | [P07](../plans/experience/frontend-evolution.md) | Playwright |
| Canary rollback time | < 60 s | [P10](../plans/governance/deployment-safety.md) | deploy log |
| CI green on main | 100% | [P11](../plans/governance/testing-quality.md) | CI |

> ⚠️ The legacy repo had 6 `unverified-claim` findings around "99.9% uptime".
> Those claims are **not** current guarantees. This table records realistic
> free-tier targets; promotion beyond them requires [P08](../plans/infrastructure/infrastructure-optimization.md)
> to move off free-tier.

---

## Runtime verification hooks

| Hook | Trigger | Action | Feeds |
|------|---------|--------|-------|
| Pre-push gate | `git push` | gitleaks + semgrep + tests + build check | [P10](../plans/governance/deployment-safety.md) |
| Canary metric gate | deploy | auto-rollback on SLO breach | [P10](../plans/governance/deployment-safety.md) |
| Registry parity check | PR touching `docs/plans/` | `lint_plans.py --check-graph` | [P12](../plans/governance/codebase-cleanup.md) |
| Coverage gate | PR touching `backend/` or `frontend/` | block if coverage drops below target | [P11](../plans/governance/testing-quality.md) |
| a11y gate | PR touching `frontend/` | axe scan in Playwright | [P07](../plans/experience/frontend-evolution.md) |

---

## Evidence linking rule

Every plan's Verification table must link to **runnable** evidence:

- ✅ Good: `[CI run #1234](https://github.com/.../actions/runs/1234)`
- ✅ Good: `[audit round 19](../audit_reports/round19_comments/)`
- ✅ Good: `[Grafana dashboard](https://grafana.../d/mcp-tower)`
- ❌ Bad: "tested manually"
- ❌ Bad: "works on my machine"
- ❌ Bad: a claim with no link

`lint_plans.py` flags unlinked claims as `unverified-claim` warnings (the same
check that found the 6 uptime claims in the legacy inventory).
