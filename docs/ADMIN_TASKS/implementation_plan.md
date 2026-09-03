# Bootstrap Brain & Decision Logic — Implementation Plan (v3)

**Goal:** Implement SupremeAI's pre-seeded decision brain on the existing `CascadeMemoryService` + `DynamicPlanningEngine` stack.

> [!IMPORTANT]
> **Decision architecture:** methodology is decided **after discovery**, not before it. `generate_new_code` is a last resort, not the default.

> [!IMPORTANT]
> **Discovery architecture:** `discover_reusable_implementation` is **logically enabled for every `dev` task**, but it is **tiered** so expensive external discovery is not executed unnecessarily.

> [!NOTE]
> **No duplicate memory database:** reuse the existing `ai_memory` + `metadata` JSONB unless a future measured requirement proves a dedicated store is necessary.

---

## 1. Target Decision Flow

```text
USER INTENT
    ↓
INTENT DECIPHERING
    ↓
EPISTEMIC / CONTEXT PROBE
    ↓
REUSABLE CAPABILITY DISCOVERY  ← always available for dev
    │
    ├─ L1: memory / semantic cache
    ├─ L2: internal code + docs + existing capabilities
    └─ L3: external implementation discovery when justified
    ↓
RESOURCE / AUTHORIZATION DISCOVERY
    ↓
COST + RISK + LATENCY + QUALITY EVALUATION
    ↓
METHODOLOGY DECISION
    ├─ reuse
    ├─ compose
    ├─ adapt
    ├─ delegate
    ├─ generate_new_code
    └─ ask_admin / human approval when required
    ↓
EXECUTE
    ↓
VERIFY
    ↓
MEMORIZE CANDIDATE LESSON
    ↓
GOVERNED PROMOTION
```

The key principle is:

> **Discover broadly in logic; execute expensively only when evidence says it is worthwhile.**

---

## 2. Existing Components — Preserve and Reuse

| Component | Existing location | Direction |
| --- | --- | --- |
| Vector/semantic memory | `backend/services/memory_service.py` | Reuse |
| Intent + recall | `backend/services/intent_deciphering.py` | Reuse |
| DAG planner | `backend/services/dynamic_planner.py` | Extend |
| Living orchestrator | `backend/services/living_engine.py` | Extend |
| Memory consolidation | planner/living engine | Extend |
| Self-correction | `backend/services/self_correction.py` | Reuse/extend |
| Knowledge seeding | `backend/scripts/sync_knowledge.py` | Extend |

Do not create parallel memory/planner/orchestrator systems.

---

## 3. Bootstrap Brain Seed

Create a compact, high-value seed rather than a huge generic knowledge dump.

### Proposed seed domains

```text
decision_pattern
meta_question
tool_selection_rule
failure_recovery
capability_knowledge
implementation_source
```

Initial target: approximately 100–500 high-value patterns, adjusted to retrieval quality and existing storage capacity.

Each record should preserve provenance and verification state:

```json
{
  "brain_domain": "decision_pattern",
  "priority": "critical",
  "tier": "core",
  "tags": ["reuse", "discovery", "planner"],
  "confidence": 0.95,
  "status": "promoted",
  "version": "1.0",
  "source": "bootstrap_brain_seed_v1"
}
```

Use an idempotent seeding script and do not create duplicate records on repeated deployments.

---

## 4. Tiered Reusable Implementation Discovery

### Core rule

`discover_reusable_implementation` must be **available to every `dev` task**.

It must not mean “search GitHub/web on every request.” It means the planner always has the **opportunity to discover reuse**, with progressively more expensive tiers.

### L1 — cheapest

Search:

- `ai_memory`
- semantic cache
- previously verified capability results
- task fingerprints

Fast-path exit when a sufficiently trusted result exists.

### L2 — internal

Search:

- existing SupremeAI modules
- registered skills/tools
- MCP capability registry
- `docs/` planning corpus
- scripts and internal implementation index
- previously discovered external implementations already stored as trusted references

### L3 — external

Only when L1/L2 evidence is insufficient and external discovery has expected value.

Search candidates may include:

- GitHub/open source
- official SDK/reference implementations
- maintained package registries
- dedicated technical sources
- compatible APIs/services

Before reuse/adaptation, evaluate:

- provenance
- license compatibility
- security/vulnerabilities
- maintenance health
- compatibility
- dependency/resource weight
- operational cost
- privacy/data implications
- policy/terms constraints

Never blindly copy external code.

---

## 5. L3 Decision Policy

The previous plan's “high/novel + low confidence” condition is too restrictive because some medium-complexity tasks can have high reuse value.

Use an expected-value gate instead:

```text
L3 if:
  L1/L2 did not produce a sufficiently trusted solution
  AND external discovery is permitted
  AND expected_reuse_value > discovery_cost
  AND task is not offline-only
  AND request/security policy permits external lookup
```

`expected_reuse_value` should consider:

```text
estimated new-code effort avoided
+ future reuse potential
+ quality benefit
+ maintenance reduction
- discovery latency
- external-call cost
- security/review cost
```

For low-value/simple tasks, L3 may be skipped even though the discovery capability exists.

---

## 6. Methodology Decision

The action builder must consume the **post-discovery decision context**.

Priority:

```text
1. reuse
2. compose
3. adapt
4. delegate
5. generate_new_code
```

`generate_new_code` is selected only when existing capabilities, reusable implementations, composition, and authorized delegation are insufficient or inappropriate.

Never trust a model's claimed “50% existing” estimate without checking actual candidates.

---

## 7. Resource-as-Capability

After implementation discovery, inspect authorized resources available to the tenant/user.

Examples:

```text
GitHub repository / Actions
user-authorized SaaS/API
MCP server
browser-accessible service
existing provider account
```

The planner may use these resources when authorization, policy, privacy, and task scope permit.

Important:

```text
Capability ≠ Permission

A discovered capability is not automatically authorized.
```

Never use one tenant's private resource for another tenant.

---

## 8. Third-Party AI Advisor Contract

Third-party models may act as:

- planner advisor
- critic
- researcher
- implementation scout
- verifier

They do **not** become SupremeAI's policy authority.

The contract must require structured output separating:

```text
facts
assumptions
uncertainties
recommendations
risks
validation_steps
lesson_candidate
```

SupremeAI's own policy, authorization, evidence, and verification layers remain authoritative.

---

## 9. Brain Metrics

Persist metrics alongside execution lessons where the existing schema supports them:

```text
discovery_level
methodology_decision
brain_coverage_score
new_code_ratio
reuse_hit
external_discovery_used
validation_result
estimated_cost
actual_cost
```

Useful derived metrics:

```text
capability_reuse_rate
implementation_discovery_hit_rate
new_code_ratio
successful_adaptation_rate
delegation_success_rate
validation_success_rate
recovery_success_rate
lesson_reuse_rate
```

The objective is not maximum reuse at any cost. It is **minimum unnecessary new work while preserving security, correctness, and maintainability**.

---

## 10. Learning and Promotion

```text
execution result
    ↓
verification
    ↓
lesson candidate
    ↓
confidence/provenance evaluation
    ↓
quarantine if uncertain
    ↓
promote only when evidence is sufficient
```

A single model answer or failed experiment must not overwrite a trusted rule.

Promoted brain rules should be versioned and rollbackable.

---

## 11. Tests Required

### Discovery

- every dev DAG contains a discovery opportunity
- L1 hit exits before L2/L3
- L2 hit exits before L3
- L3 never executes when policy/offline constraints prohibit it
- low-value tasks can skip expensive L3
- external candidate evaluation records provenance/license/security state

### Methodology

- reuse selected for trusted internal match
- compose selected when multiple capabilities satisfy the goal
- adapt selected when a compatible implementation needs modification
- delegate selected when an authorized external capability is preferable
- generate_new_code only after appropriate discovery misses

### Resilience

- provider unavailable → fallback
- external search unavailable → continue with internal capabilities
- memory unavailable → safe degraded path
- user authorization revoked → capability immediately unavailable

### Multi-tenancy

- no cross-tenant memory retrieval
- no cross-tenant resource delegation
- no credential leakage in discovery results

---

## 12. Implementation Order

```text
1. Inventory existing memory/capability/planner interfaces
2. Add/verify bootstrap seed
3. Implement L1 discovery
4. Implement L2 internal discovery
5. Implement policy-gated L3 external discovery
6. Wire discovery into every dev DAG
7. Move methodology selection after discovery
8. Add resource/authorization discovery
9. Add advisor contract
10. Add metrics
11. Add verification/promotion rules
12. Load-test latency and cache/reuse behavior
```

### Final acceptance condition

A production-ready implementation must demonstrate that:

```text
same/similar problem
→ increasingly reuses validated knowledge/capabilities
→ performs less unnecessary discovery
→ generates less unnecessary code
→ remains safe when providers disappear
```
