---
id: plan-matrix
subject: "SupremeAI Plan Matrix"
document_role: matrix
planning_authority: Architecture Governance / Planning Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes: []
superseded_by: []
target_scope: combined_ecosystem
---

# SupremeAI Plan Matrix

> A flat dependency view. Where [PLAN_GRAPH.md](./PLAN_GRAPH.md) shows shape,
> this matrix shows *who depends on whom* at a glance. No plan is isolated.

---

## Dependency matrix

| Plan | Domain | Depends On | Enables | Verify By | Status |
|------|--------|------------|---------|-----------|--------|
| [P01](./security/security-guardian.md) | Security | *(foundation)* | P02, P03, P04, P06, P08 | Security Audit + gitleaks + pentest | 🟦 Active |
| [P02](./intelligence/provider-abstraction.md) | Intelligence | P01 | P04 | Provider contract tests + failover sim | 🟦 Active |
| [P03](./mcp/mcp-architecture.md) | MCP | P01 | P04, P05, P06, P07 | MCP integration tests + federation e2e | 🟩 Stable |
| [P04](./agents/agent-orchestration.md) | Agents | P01, P02, P03 | P05, P07 | Agent integration tests + HITL review | 🟦 Active |
| [P05](./intelligence/memory-knowledge-engine.md) | Intelligence | P03, P04 | — | Memory recall tests + consolidation audit | 🟦 Active |
| [P06](./automation/browser-automation.md) | Automation | P01, P03 | — | Runtime browser tests + sandbox escape checks | 🟪 Implementing |
| [P07](./experience/frontend-evolution.md) | Experience | P03, P04 | — | E2E / Playwright UI + a11y audit | 🟦 Active |
| [P08](./infrastructure/infrastructure-optimization.md) | Infrastructure | P01 | P09, P10 | Resource pressure tests + build runtime checks | 🟦 Active |
| [P09](./observability/observability.md) | Observability | P08 | P10 | SLO dashboards + alert dry-runs | 🟪 Implementing |
| [P10](./governance/deployment-safety.md) | Governance | P08, P09 | — | Deployment verification + canary metrics | 🟦 Active |
| [P11](./governance/testing-quality.md) | Governance | P08 | — | CI green + coverage ≥ target + audit sign-off | 🟨 Verifying |
| [P12](./governance/codebase-cleanup.md) | Governance | — | — | lint_plans.py clean + registry ↔ filesystem parity | ⬜ Proposed |

---

## Reverse-dependency matrix (who needs me?)

Read this table to answer *"if I change plan X, what else might break?"*

| Plan | Dependents (plans that depend ON this) |
|------|----------------------------------------|
| P01 Security Guardian | P02, P03, P04, P06, P08 — **the whole network** |
| P02 Provider Abstraction | P04 |
| P03 MCP Architecture | P04, P05, P06, P07 |
| P04 Agent Orchestration | P05, P07 |
| P05 Memory & Knowledge | — |
| P06 Browser Automation | — |
| P07 Frontend Evolution | — |
| P08 Infrastructure Optimization | P09, P10, P11 |
| P09 Observability | P10 |
| P10 Deployment Safety | — |
| P11 Testing & Quality | — |
| P12 Codebase Cleanup | — |

> **P01 and P03 are the two highest-blast-radius plans.** Any change to them
> requires a regression pass across every dependent plan's verification suite.

---

## Status rollup by domain

| Domain | Plans | Stable | Active | Implementing | Verifying | Proposed |
|--------|-------|--------|--------|--------------|-----------|----------|
| Security | 1 | 0 | 1 | 0 | 0 | 0 |
| Intelligence | 3 | 0 | 3 | 0 | 0 | 0 |
| MCP | 1 | 1 | 0 | 0 | 0 | 0 |
| Agents | 1 | 0 | 1 | 0 | 0 | 0 |
| Automation | 1 | 0 | 0 | 1 | 0 | 0 |
| Experience | 1 | 0 | 1 | 0 | 0 | 0 |
| Infrastructure | 1 | 0 | 1 | 0 | 0 | 0 |
| Observability | 1 | 0 | 0 | 1 | 0 | 0 |
| Governance | 3 | 0 | 1 | 0 | 1 | 1 |
| **Total** | **12** | **1** | **8** | **2** | **1** | **1** |

> Only **1 of 12** plans is Stable. The network's biggest risk is that P01
> (Security) is Active, not Stable — yet everything depends on it. Promoting
> P01 to Stable is the single highest-leverage governance action available.
