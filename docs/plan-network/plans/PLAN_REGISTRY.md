---
id: plan-registry
subject: "SupremeAI Plan Registry"
document_role: registry
planning_authority: Architecture Governance / Planning Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes: ["docs/DOCUMENTATION_MASTER_INDEX.md"]
superseded_by: []
target_scope: combined_ecosystem
---

# SupremeAI Plan Registry

> **এটি ইনডেক্স, মাস্টার প্ল্যান না।** প্রতিটা প্ল্যান একটা জীবন্ত গ্রাফের নোড।
> এই ফাইল প্রতিটা canonical প্ল্যান আর তার সম্পর্ক তালিকাভুক্ত করে।
> প্রতিটা প্ল্যান একে অপরের প্রতিযোগী না — একটা ইকোসিস্টেমের অংশ।
> দর্শন: [ECOSYSTEM_PHILOSOPHY.md](../ECOSYSTEM_PHILOSOPHY.md) ·
> গ্রাফ: [PLAN_GRAPH.md](./PLAN_GRAPH.md) · ম্যাট্রিক্স: [PLAN_MATRIX.md](./PLAN_MATRIX.md)

**Owner:** Planning Circle · **Last verified:** 2026-09-24 · **Total plans:** 12

---

## How to read this registry

Each row is **one canonical plan**. The relationship columns are the part that
was missing before — they make the network visible:

- **Depends On** — plans that must be Stable before this plan can ship.
- **Enables** — plans that become possible *because* this plan exists.
- **Verified By** — the evidence that proves this plan works.

> নিয়ম: **এক ধারণা → একটা canonical document → অনেক reference।**
> দুটো প্ল্যান একই টপিক কভার করলে তারা প্রতিযোগী না — পরিপূরক। একত্রিত করো,
> কিন্তু কাউকে মুছো না — আর্কাইভে ইতিহাস থাকবে।

---

## Registry

| ID | Plan | Domain | Status | Depends On | Enables | Verified By |
|----|------|--------|--------|------------|---------|-------------|
| [P01](./security/security-guardian.md) | Security Guardian | Security | Active | — | P02, P03, P04, P06, P08 | Security Audit + gitleaks + pentest |
| [P02](./intelligence/provider-abstraction.md) | Provider Abstraction | Intelligence | Active | P01 | P04 | Provider contract tests + failover sim |
| [P03](./mcp/mcp-architecture.md) | MCP Architecture | MCP | Stable | P01 | P04, P05, P06, P07 | MCP integration tests + federation e2e |
| [P04](./agents/agent-orchestration.md) | Agent Orchestration | Agents | Stable | P01, P02, P03 | P05, P07 | Agent integration tests + HITL review — **evidence (2026-09-25):** `pytest tests/agents/` 275 passed/16 skipped; M17 HITL dispatch+CAS+resume-token review complete (#1238 wave audit, PR #1286) |
| [P05](./intelligence/memory-knowledge-engine.md) | Memory & Knowledge Engine | Intelligence | Active | P03, P04 | — | Memory recall tests + consolidation audit |
| [P06](./automation/browser-automation.md) | Browser Automation | Automation | Implementing | P01, P03 | — | Runtime browser tests + sandbox escape checks |
| [P07](./experience/frontend-evolution.md) | Frontend Evolution | Experience | Active | P03, P04 | — | E2E / Playwright UI + a11y audit |
| [P08](./infrastructure/infrastructure-optimization.md) | Infrastructure Optimization | Infrastructure | Stable | P01 | P09, P10 | Resource pressure tests + build runtime checks — **evidence (2026-09-25):** `pytest tests/missions/test_mission_suite.py tests/core/test_zero_cost_phase1_queue.py` 100 passed; main CI build/runtime jobs green (runs 35967684674+) |
| [P09](./observability/observability.md) | Observability | Observability | Implementing | P08 | P10 | SLO dashboards + alert dry-runs |
| [P10](./governance/deployment-safety.md) | Deployment Safety | Governance | Active | P08, P09 | — | Deployment verification + canary metrics |
| [P11](./governance/testing-quality.md) | Testing & Quality | Governance | Verifying | P08 | — | CI green + coverage ≥ target + audit sign-off |
| [P12](./governance/codebase-cleanup.md) | Codebase Cleanup | Governance | Proposed | — | — | lint_plans.py clean + registry ↔ filesystem parity |

---

## Status legend

| Status | Meaning |
|--------|---------|
| **Proposed** | Idea written, not yet approved for execution. |
| **Active** | Approved; next milestone being scoped. |
| **Implementing** | Code is being written against an open milestone. |
| **Verifying** | PR merged; tests/audit in progress. |
| **Stable** | Evidence recorded; safe to depend on. |
| **Blocked** | Cannot proceed until a named blocker clears. |
| **Archived** | Superseded or retired; kept for history. |

See [PLAN_STATUS_LIFECYCLE.md](./PLAN_STATUS_LIFECYCLE.md) for the full state machine.

---

## নতুন প্ল্যান যোগ করা

**Impact Map প্রশ্নের উত্তর না দিয়ে নতুন প্ল্যান ডকুমেন্ট বানাবে না।**
See [IMPACT_MAP.md](./IMPACT_MAP.md). The short version:

1. Which **domain** does it belong to?
2. Which **existing plans** does it depend on?
3. Which plans does it **enable**?
4. Which **milestone** implements it?
5. What **verifies** it?

If a plan with the same purpose already exists, **extend that plan instead of
creating a new one.** একই টপিকে একাধিক প্ল্যান থাকলে তারা পরিপূরক — একত্রিত করে একটা canonical-এ নিয়ে এসো।

Use the canonical template: [`_templates/PLAN_TEMPLATE.md`](./_templates/PLAN_TEMPLATE.md).

---

## Migration status

The legacy `docs/plans/` tree contained **188 files** across 13 content-derived
families. The migration to this registry is tracked in
[MIGRATION_MAP.md](./MIGRATION_MAP.md). Legacy files are retained under
`docs/archive/plans/` with a `superseded_by` pointer to their canonical home.
