# SupremeAI Plan Network Patch

A drop-in `docs/` overlay that reorganizes the **188-file documentation jungle**
in [`SaifulHaqueNiloy/supremeai`](https://github.com/SaifulHaqueNiloy/supremeai)
into a clean **Plan Network**: 5 layers, 9 domains, 12 canonical plans, and —
the part that was missing — a **relationship layer** (`depends_on / enables /
implemented_by / verified_by`) made visible through a single registry, a mermaid
graph, and a dependency matrix.

> **188 scattered plans → 12 canonical plans → 1 relationship layer.**

---

## What's in this patch

```text
supremeai-docs-patch/
├── README.md                          ← you are here (how to apply)
└── docs/
    ├── README.md                      ← new documentation entry point
    ├── vision/
    │   └── principles.md              ← Layer 1: vision + 7 principles
    ├── architecture/
    │   ├── system.md                  ← Layer 2: 5-layer model + system map
    │   └── domains.md                 ← Layer 2: the 9 domains
    ├── plans/
    │   ├── PLAN_REGISTRY.md           ← THE index (12 plans, one row each)
    │   ├── PLAN_GRAPH.md              ← mermaid dependency graph (3 views)
    │   ├── PLAN_MATRIX.md             ← dependency + reverse-dependency matrix
    │   ├── PLAN_STATUS_LIFECYCLE.md   ← 7-state lifecycle state machine
    │   ├── IMPACT_MAP.md              ← new-plan intake checklist + decision tree
    │   ├── MIGRATION_MAP.md           ← 188 files → 12 plans (family→domain)
    │   ├── _templates/
    │   │   └── PLAN_TEMPLATE.md       ← canonical plan template w/ relationship header
    │   ├── security/security-guardian.md              ← P01
    │   ├── intelligence/provider-abstraction.md       ← P02
    │   ├── intelligence/memory-knowledge-engine.md    ← P05
    │   ├── mcp/mcp-architecture.md                    ← P03
    │   ├── agents/agent-orchestration.md              ← P04
    │   ├── automation/browser-automation.md           ← P06
    │   ├── experience/frontend-evolution.md           ← P07
    │   ├── infrastructure/infrastructure-optimization.md ← P08
    │   ├── observability/observability.md             ← P09
    │   ├── governance/deployment-safety.md            ← P10
    │   ├── governance/testing-quality.md              ← P11
    │   └── governance/codebase-cleanup.md             ← P12
    ├── execution/
    │   └── github-mapping.md          ← Layer 4: plan → milestone → issue
    └── verification/
        ├── audits.md                  ← Layer 5: audit surfaces
        └── production-checks.md       ← Layer 5: SLOs + runtime hooks
```

**25 files total.** Every plan file uses the canonical relationship header:

```md
# Plan: <Name>
Status: <state>   Owner: <Circle>   ID: Pxx
## Purpose
## Depends On      ← the missing piece
## Enables         ← the missing piece
## Related
## Source of Truth
## Execution       → GitHub milestone
## Verification    ← evidence table
## Legacy documents superseded
```

---

## What this patch changes vs. preserves

### Preserved (compatible with existing repo)
- The existing frontmatter schema: `id / subject / document_role /
  planning_authority / status / evidence_state / disposition / last_verified /
  supersedes / superseded_by / target_scope`.
- The 3-tier scope taxonomy: `supremeai_internal / combined_ecosystem /
  user_project`.
- The existing `PLAN_LIFECYCLE_POLICY.md` single-plan execution discipline
  (extended, not replaced — see `PLAN_STATUS_LIFECYCLE.md`).
- All audit evidence under `docs/audit_reports/` (retained, linked, not moved).
- The `scripts/governance/lint_plans.py` inventory approach (extended).

### Added (the missing relationship layer)
- **Relationship frontmatter fields**: `plan_id / domain / depends_on / enables
  / implemented_by / verified_by / related_to`.
- **`PLAN_REGISTRY.md`** — one human-readable index table (replaces the 305 KB
  `DOCUMENTATION_MASTER_INDEX.md` as the entry point).
- **`PLAN_GRAPH.md`** — mermaid dependency graph (full graph + execution flow +
  domain cluster view).
- **`PLAN_MATRIX.md`** — flat dependency + reverse-dependency matrix.
- **`IMPACT_MAP.md`** — new-plan intake checklist + decision tree (prevents the
  jungle from regrowing).
- **`MIGRATION_MAP.md`** — maps the 13 legacy families → 9 domains → 12 plans,
  with disposition rules and migration order.
- **`PLAN_TEMPLATE.md`** — canonical template with the relationship header.
- **12 canonical plan files** (P01–P12), each listing the legacy files it
  supersedes.
- **Layer 1/2/4/5 files** — vision, architecture, execution, verification.

### Superseded (archived, not deleted)
- `docs/DOCUMENTATION_MASTER_INDEX.md` → `PLAN_REGISTRY.md` (+ this `README.md`).
- `docs/plans/PLAN_LIFECYCLE_POLICY.md` → `PLAN_STATUS_LIFECYCLE.md`.
- `docs/plans/phases/plan_inventory_report.md` → `MIGRATION_MAP.md`.
- `docs/plans/phases/plan_reconciliation_register.md` → `PLAN_REGISTRY.md`.
- The 4 "master plan" docs in `docs/plans/architecture/` → split across P02/P03/P09.
- The 2 competing frontend master plans → `experience/frontend-evolution.md`.
- ~170 more legacy plan files → archived with `superseded_by` pointers (see
  each canonical plan's "Legacy documents superseded" table).

---

## How to apply this patch

This is an **additive** patch. It does not delete anything — it adds the
network layer and points at legacy files for archival.

### Option A — apply as a single PR (recommended)

```bash
# from the root of your supremeai clone
git checkout -b docs/plan-network

# copy the patch's docs/ over your docs/ (additive — won't overwrite yet)
cp -r /path/to/supremeai-docs-patch/docs/* docs/

# mark the legacy master index as superseded (don't delete — archive)
git mv docs/DOCUMENTATION_MASTER_INDEX.md docs/archive/DOCUMENTATION_MASTER_INDEX.md

# commit
git add docs/
git commit -m "docs: introduce Plan Network (5 layers, 9 domains, 12 plans)

- add relationship layer (depends_on/enables/implemented_by/verified_by)
- add PLAN_REGISTRY, PLAN_GRAPH, PLAN_MATRIX, PLAN_STATUS_LIFECYCLE
- add IMPACT_MAP (new-plan intake) + MIGRATION_MAP (188 -> 12)
- add 12 canonical plans P01-P12 with relationship headers
- supersede DOCUMENTATION_MASTER_INDEX (305KB) with the registry
- see docs/plans/MIGRATION_MAP.md for the family->domain mapping"

git push -u origin docs/plan-network
```

### Option B — apply incrementally (per P12's migration order)

Follow [docs/plans/MIGRATION_MAP.md](./docs/plans/MIGRATION_MAP.md). Each step
is its own PR:

1. PR 1: add the network scaffolding (registry, graph, matrix, lifecycle,
   impact map, migration map, template) — no canonical plans yet.
2. PR 2: P01 Security + archive its 2 legacy docs.
3. PR 3: P03 MCP + archive its 40 legacy docs.
4. … and so on per the migration order.
5. Final PR: P12 cleanup — archive the 33 unclassified files.

This is slower but lower-risk for a 188-file repo.

---

## Verifying the patch

After applying, extend `scripts/governance/lint_plans.py` with three checks
(the patch's `PLAN_STATUS_LIFECYCLE.md` and `MIGRATION_MAP.md` specify them):

```text
1. registry ↔ filesystem parity
   every plan_id in PLAN_REGISTRY.md has a file; every plan file has a row.

2. graph ↔ registry parity
   every depends_on/enables edge in PLAN_GRAPH.md matches the registry.

3. stable-gate
   no plan with status:stable has an un-Stable dependency or missing evidence.
```

The migration is complete when the lint output is:

```text
Documents scanned: 12 canonical (+ N archived)
Findings: 0 errors / 0 warnings
Registry ↔ filesystem parity: PASS
Graph ↔ registry parity: PASS
Stable plans with un-Stable dependencies: 0
```

---

## The 12 canonical plans at a glance

| ID | Plan | Domain | Status | Depends On |
|----|------|--------|--------|------------|
| P01 | Security Guardian | Security | Active | — |
| P02 | Provider Abstraction | Intelligence | Active | P01 |
| P03 | MCP Architecture | MCP | **Stable** | P01 |
| P04 | Agent Orchestration | Agents | Active | P01, P02, P03 |
| P05 | Memory & Knowledge Engine | Intelligence | Active | P03, P04 |
| P06 | Browser Automation | Automation | Implementing | P01, P03 |
| P07 | Frontend Evolution | Experience | Active | P03, P04 |
| P08 | Infrastructure Optimization | Infrastructure | Active | P01 |
| P09 | Observability | Observability | Implementing | P08 |
| P10 | Deployment Safety | Governance | Active | P08, P09 |
| P11 | Testing & Quality | Governance | Verifying | P08 |
| P12 | Codebase Cleanup | Governance | Proposed | — |

See [docs/plans/PLAN_REGISTRY.md](./docs/plans/PLAN_REGISTRY.md) for the full
table with `Enables` and `Verified By` columns.

---

## Interactive preview

An interactive visualization of this entire network (graph, registry, matrix,
lifecycle, migration, impact-map generator) ships alongside this patch as a
Next.js page. Run it locally and open the **Preview Panel** to explore the
network visually — click any plan node to see its full relationship header.
