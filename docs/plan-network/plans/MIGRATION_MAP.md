---
id: migration-map
subject: "SupremeAI Plan Migration Map — 188 files → 12 plans"
document_role: migration
planning_authority: Architecture Governance / Planning Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes: ["docs/plans/phases/plan_inventory_report.md"]
superseded_by: []
target_scope: combined_ecosystem
---

# SupremeAI Plan Migration Map — ভূমিকা নির্ধারণ

> **ইকোসিস্টেম দর্শন:** প্রতিটা ফাইল গাছের কোনো না কোনো অংশ — কেউ বর্জন নয়।
> এই ম্যাপ ফাইলগুলোকে "মুছে ফেলার" তালিকা নয়, বরং "প্রতিটার ভূমিকা নির্ধারণের" ম্যাপ।
> কেউ ক্যানোনিকাল শাখা, কেউ মার্জ হওয়া শাখা, কেউ আর্কাইভ রেফারেন্স (মাটিতে মিশে শিকড়ের খোরাক)।
> কেউ শুকনো ডাল — আলাদা করা দরকার, কিন্তু মুছলে ইতিহাস হারায়।
>
> দর্শন: [ECOSYSTEM_PHILOSOPHY.md](../ECOSYSTEM_PHILOSOPHY.md) ·
> এক্সিকিউশন: [P12 Codebase Cleanup](./governance/codebase-cleanup.md)

**Starting point:** `docs/plans/plan_inventory_report.md` (generated 2026-09-19
by `scripts/governance/lint_plans.py`) — 185 documents, 13 content-derived families.

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Plan documents | 188 | 12 canonical (+ ভূমিকা নির্ধারিত legacy) |
| "Master" / "final" / "v2" ভিন্ন দৃষ্টিকোণ | many | একত্রিত (প্রতিযোগী না, পরিপূরক) |
| Documentation index | 1 × 305 KB master file | 1 × registry table |
| Relationship visibility | none | full graph + matrix |
| Domains | 13 ad-hoc families | 9 explicit domains |

---

## Family → canonical plan mapping

| # | Legacy family | Docs | → Domain | Canonical plan(s) | Note |
|---|---------------|------|----------|-------------------|------|
| 1 | control-tower-mcp | 41 | MCP | [P03](./mcp/mcp-architecture.md) | Largest family. Single canonical MCP doc; 40 legacy files archived with `superseded_by: P03`. |
| 2 | execution-phases | 28 | split | [P11](./governance/testing-quality.md) + [P12](./governance/codebase-cleanup.md) | Split: phase trackers → Governance/Quality; reconciliation/disposition → Cleanup. |
| 3 | free-tier-federation | 25 | Infrastructure | [P08](./infrastructure/infrastructure-optimization.md) | Consolidate into Infra Optimization. |
| 4 | frontend-product-ux | 16 | Experience | [P07](./experience/frontend-evolution.md) | All UX/UI/dashboard/onboarding → Frontend Evolution. |
| 5 | unified-architecture | 10 | split | [P02](./intelligence/provider-abstraction.md) + [P09](./observability/observability.md) | Split: provider/vendor neutrality → P02; runtime observability → P09. |
| 6 | browser-automation | 9 | Automation | [P06](./automation/browser-automation.md) | Single canonical doc. |
| 7 | ci-cd-pipeline | 7 | split | [P08](./infrastructure/infrastructure-optimization.md) + [P11](./governance/testing-quality.md) | Split: pipeline infra → P08; quality gate → P11. |
| 8 | intelligence-evolution | 6 | Intelligence | [P02](./intelligence/provider-abstraction.md) + [P04](./agents/agent-orchestration.md) + [P05](./intelligence/memory-knowledge-engine.md) | Split across provider, agents, memory. |
| 9 | dynamic-configuration | 5 | Infrastructure | [P08](./infrastructure/infrastructure-optimization.md) | Folds in (zero-hardcode config is an infra concern). |
| 10 | production-readiness | 3 | split | [P09](./observability/observability.md) + [P10](./governance/deployment-safety.md) | Split: monitoring → P09; safe rollout → P10. |
| 11 | security-defense | 1 | Security | [P01](./security/security-guardian.md) | ⚠️ Underdeveloped — only 1 doc for the most critical domain. P01 must be hardened. |
| 12 | deployment-render | 1 | Governance | [P10](./governance/deployment-safety.md) | Folds into Deployment Safety. |
| 13 | unclassified | 33 | split | [P12](./governance/codebase-cleanup.md) | Triage individually during Cleanup; most will archive. |
| | **Total** | **185** | | **12 canonical** | |

---

## ভূমিকা নির্ধারণ নিয়ম (Disposition — কেউ বর্জন নয়)

প্রতিটা legacy ফাইলের জন্য ঠিক একটা ভূমিকা নির্ধারণ করো। কাউকে "মুছবে না" — প্রতিটার
গাছে জায়গা আছে:

| ভূমিকা | অর্থ | গন্তব্য | গাছের অংশ |
|---|---|---|---|
| **retain-canonical** | এই ফাইলটাই নতুন canonical doc (এডিট করে) | `docs/plans/<domain>/<name>.md` | আজকের মূল শাখা |
| **merge** | কনটেন্ট canonical প্ল্যানে মিশে গেছে; জ্ঞান হিসেবে থাকে | canonical plan-এ "Legacy documents superseded" টেবিলে রেকর্ড | ছোট শাখা বড় শাখায় জুড়ে গেছে |
| **archive-reference** | পুরনো কনটেন্ট; ইতিহাস হিসেবে থাকে | `docs/archive/plans/<original-path>` + `superseded_by` frontmatter | পুরনো পাতা — মাটিতে মিশে শিকড়ের খোরাক |
| **archive-dry-branch** | শুকনো ডাল — গাছ থেকে আলাদা করা দরকার, কিন্তু মুছলে ইতিহাস হারায় | `docs/archive/plans/<original-path>` + `superseded_by` + `role: historical` | শুকনো ডাল |
| **split** | কনটেন্ট ≥2 canonical প্ল্যানে বিতরণ | archive original; প্রতিটা canonical plan-এর টেবিলে রেকর্ড | একটা শাখা কয়েক ডালে ভাগ |

> **নিয়ম: কোনো legacy ফাইল সাইলেন্টলি মুছবে না।** প্রতিটা archival `superseded_by`
> সেট করে যাতে `git log` এবং `lint_plans.py` provenance ট্রেস করতে পারে।
> এমনকি শুকনো ডালও আর্কাইভে থাকবে — ইতিহাস গাছের বার্ষিক রিং।

---

## Migration order (do not parallelize)

The cleanup itself follows the dependency graph — clean foundations first.

1. **P01 Security** — harden the 1 existing doc into the canonical guardian. (blocker: underdeveloped)
2. **P03 MCP** — collapse the 41-doc family into one canonical doc + 40 archives.
3. **P08 Infrastructure** — consolidate 25+5+7 = 37 docs.
4. **P02 / P04 / P05 Intelligence** — split the 6+10 = 16 intelligence/unified docs.
5. **P06 Automation, P07 Experience** — straightforward 1:1 family → plan.
6. **P09 / P10 Observability + Deployment** — split production-readiness.
7. **P11 Testing & Quality** — already Verifying; just link evidence.
8. **P12 Codebase Cleanup** — triage the 33 unclassified files last.

Each step is a separate PR that updates PLAN_REGISTRY.md, PLAN_GRAPH.md, and
PLAN_MATRIX.md in the same commit.

---

## Verification of the migration

The migration is complete when `scripts/governance/lint_plans.py` reports:

```text
Documents scanned: 12 canonical (+ N archived)
With valid frontmatter: 12/12
Findings: 0 errors / 0 warnings
Registry ↔ filesystem parity: PASS
Graph ↔ registry parity: PASS
Stable plans with un-Stable dependencies: 0
Blocked plans without documented blocker: 0
```

Until that output is clean, P12 stays Proposed and the migration is not done.
