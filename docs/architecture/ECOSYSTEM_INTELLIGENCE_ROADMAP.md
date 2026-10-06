# SupremeAI Ecosystem Intelligence Roadmap (v2)

> **Root-cause analysis against current `main` branch (`66a23f6`) — not a blind adoption of external repos.**
> **v2: incorporates 15-point feedback — Evidence Before Adoption, Evaluation Engine, Policy Engine, 3-tier routing.**

## Executive Summary

SupremeAI's strength is **not** building every capability itself — it is **orchestrating capabilities through governance + memory + routing + verification + learning**. This roadmap treats the 24 analyzed external repos as **governed providers** or **research sources**, not as core dependencies.

> **SupremeAI = Capability Aggregator + Orchestrator + Governance + Learning System**
> **External repos = governed providers (optional, replaceable, health-checked, policy-gated)**

### Core Principle: Evidence Before Adoption

```text
New Repo Found
      ↓
Do we already have it?  ──→ Yes → Extend existing, don't adopt
      ↓ No
Does it solve a real problem?  ──→ No → Reference only
      ↓ Yes
Benchmark (correctness, latency, cost, security)
      ↓
Security review
      ↓
Maintenance cost vs expected improvement
      ↓
Adopt / Adapt / Reference / Reject
```

This is the **core decision algorithm** for ecosystem intelligence. No repo enters SupremeAI without evidence.

---

## Current Architecture Inventory (verified @ `66a23f6`)

| Layer | Component | Status | File(s) |
|---|---|---|---|
| **Capability Router** | Provider Registry | ✅ Active | `backend/core/llm/provider_registry.py` |
| **Memory** | MemoryRepository + pgvector | ✅ Active | `backend/core/ai_memory/repository.py` |
| **Memory** | Adaptive Engine (experience DB) | ✅ Active | `backend/adaptive_engine/experience_db.py` |
| **Memory** | Episodic / Long-term / Consolidator | ✅ Active | `backend/memory/episodic_memory.py`, `long_term_memory.py`, `backend/evolution/memory_consolidator.py` |
| **Browser** | Native Playwright stack | ✅ Active (adapter retired #4044 → #4068) | `backend/core/playwright_manager.py` + 15 files (see `docs/architecture/retired_adapters.md`) |
| **Coding Agent** | Native coder fleet + MCP bridge | ✅ Active (adapter retired #4045 → #4068) | `scripts/agents/continuous_agent_loop.py`, `backend/external_agents/`, `backend/brain/mcp_client.py` |
| **MCP** | MCP Client + Gateway | ✅ Active | `backend/brain/mcp_client.py`, `backend/tools/mcp/` |
| **Scanner** | Rules Breaker (Team Leader pattern) | ✅ Active | `scripts/agents/rules_breaker.py` |
| **Learning** | Learning Pipeline + Experience | ✅ Active | `backend/evolution/learning_pipeline.py`, `backend/learning/experience.py` |
| **Deploy** | Render + Vercel + Deploy Train | ✅ Active | `scripts/deploy/` |
| **Mission Control** | Admin dashboard | ✅ Active | `apps/mission-control/` |
| **Integrations (retired)** | ~~mem0, e2b, graphiti~~ | ⛔ Retired + Deleted (#4057 → PR #4103) | native replacements (see `docs/architecture/retired_adapters.md`) |

### Key Gap Identified — Resolved (Phase 1.2 executed)
All five orphaned adapters have been **audited → decided → retired + deleted** (browser_use #4044 / openhands #4045 → executed #4068/PR #4069; mem0/e2b/graphiti #4057 → executed PR #4103). The pre-adoption gate stands: before adding ANY new external repo, the Capability Inventory must be checked and any revival requires a fresh audit (Rule 4 — Evidence Before Adoption).

---

## Architecture: Capability Router + Policy Engine

```
                    SUPREMEAI
                        │
             ┌──────────┴──────────┐
             │  Capability Router   │
             └──────────┬──────────┘
                        │
             ┌──────────┴──────────┐
             │ Capability Policy   │
             │ Engine              │
             │ (who/what/cost/sec) │
             └──────────┬──────────┘
                        │
       ┌────────────────┼─────────────────┐
       ↓                ↓                 ↓
   Internal         Governed           Research
   Capability       Provider           Source
       │                │                 │
   Native Agent     Cerebras           Agent-Reach
   Native Memory    Groq/Gemini        OpenViking
   Native Router    Strata/Colibrì     agentmemory
       │            DuckDB               │
       └────────────────┼─────────────────┘
                        ↓
              ┌─────────────────┐
              │  Evaluation     │
              │  Engine         │
              │ (correctness,   │
              │  latency, cost, │
              │  security,      │
              │  regression)    │
              └────────┬────────┘
                        ↓
                Verification Layer
                        ↓
                  Memory / Learning
                        ↓
                   Admin Policy
```

### Why Policy Engine?
The Router alone is insufficient. **Who can use which provider, for which task, with what cost limit and security level** — these are Policy Engine decisions, not routing decisions. This connects directly to agent-governance.

### Why Evaluation Engine?
Without a **Capability Evaluation Engine**, automatic routing becomes simplistic ("Cerebras fast → use Cerebras"). Quality scoring requires:
- Correctness (does the output solve the task?)
- Latency (how fast?)
- Cost (how much per call?)
- Reliability (uptime, error rate)
- Security (data exposure risk?)
- Tool-use success (can it use tools correctly?)
- Regression (did quality degrade?)

The Evaluation Engine feeds scores back to the Router and Policy Engine.

---

## 5-Phase Roadmap (v2)

### Phase 1: Capability Inventory + Orphan Audit (Week 1-2)
> **Goal:** Stop accumulating capabilities before cleaning up what exists.

#### 1.1 SupremeAI Capability Inventory
Create `docs/architecture/CAPABILITY_INVENTORY.md`:
- Every integration/adapter → status (active/orphaned/deprecated)
- Every provider → config flag + env var + health check
- Every external dependency → purpose + replaceability assessment

#### 1.2 Orphaned Adapter Audit (Audit → Decide → Revive/Retire)
> **Key v2 change:** Orphan does NOT automatically mean revive. Audit first.

```text
Existing orphaned adapter
      ↓
Current upstream version (is it still maintained?)
      ↓
Current API compatibility (does it still work?)
      ↓
Current SupremeAI use-case (do we still need it?)
      ↓
Benchmark against alternatives
      ↓
Security review
      ↓
Maintenance cost assessment
      ↓
Revive / Replace / Retire
```

| Adapter | Action | Rationale |
|---|---|---|
| ~~`browser_use_adapter.py`~~ | ✅ **Audit done → RETIRED + DELETED** (#4044, executed #4068/PR #4069) | Evidence overrode hypothesis: upstream dep never declared (probe always `False`), adapter only ever ran its zero-cost fallback; native Playwright stack supersedes. Full audit: `docs/architecture/audits/browser_use_audit.md` |
| ~~`openhands_adapter.py`~~ | ✅ **Audit done → RETIRED + DELETED** (#4045, executed #4068/PR #4069) | Evidence overrode hypothesis: dead sessions-API (conversations-migration), zero callers, native fleet superior. MCP-server path retained as live governed bridge |
| ~~`mem0_adapter.py`~~ | ✅ **Retired + Deleted** (#4057, executed PR #4103) | SupremeAI already has canonical MemoryRepository + pgvector; mem0 was redundant |
| ~~`e2b_adapter.py`~~ | ✅ **Retired + Deleted** (#4057, executed PR #4103) | SupremeAI's own `sandbox/docker_sandbox.py` covers sandbox execution; e2b was redundant |
| ~~`graphiti_adapter.py`~~ | ✅ **Retired + Deleted** (#4057, executed PR #4103) | SupremeAI's episodic + long-term memory covers this |

#### 1.3 Provider Health Dashboard
Wire all active providers into the existing `service_topology.py` health check with proper `CONFIGURED` / `REACHABLE` / `HEALTHY` states (leveraging #3226 fix).

---

### Phase 2: Governed Provider Revival + Policy Engine (Week 3-4)
> **Goal:** External repos = governed, policy-gated, health-checked providers.

#### 2.1 No New Provider Rule
```text
NO NEW PROVIDER
      ↓
Capability Inventory (do we have it?)
      ↓
Orphan adapter (can we revive it?)
      ↓
Can extend existing?
      ↓
Only then new provider
```

#### 2.2 Governed Provider Integration Matrix

> **v2 terminology:** "Use directly" → **"Governed Provider"** — SupremeAI never uses external repos as uncontrolled direct dependencies.

| # | Repo | Category | Action | Priority |
|---|---|---|---|---|
| 1 | **Browser Use** | ⛔ Rejected | Audit executed → **RETIRED + DELETED** (#4044 → #4068/PR #4069): upstream dep never declared; native Playwright stack supersedes (`docs/architecture/retired_adapters.md`) | ✅ Done |
| 2 | **OpenHands** | ⛔ Rejected | Audit executed → **RETIRED + DELETED** (#4045 → #4068/PR #4069): dead sessions-API, zero callers; native coder fleet + MCP-server bridge retained | ✅ Done |
| 3 | **OpenViking** | 🟢 Adapt concepts | Adopt hierarchical context tiers + memory/knowledge/skill unification | P1 |
| 4 | **Agent-Reach** | 🟢 Prototype | Build as Ecosystem Scout data acquisition layer | P1 |
| 5 | **Cerebras** | 🟢 Governed Provider | Add as speed-optimized LLM provider | P2 |
| 6 | **agentmemory** | 🟡 Adapt concepts | Adopt decision metadata model into learning memory | P2 |
| 7 | **DuckDB** | 🟢 Governed Provider | Add as analytics engine — **workload-driven** (only when daily analytics workload exceeds Postgres capability) | P3 |
| 8 | **Memanto** | 🟡 Adapt concepts | Memory governance: conflict detection, provenance, expiration, lifecycle | P3 |
| 9 | **Strata** | 🟡 Optional | Local inference provider (benchmark vs llama.cpp first) | P3 |
| 10 | **Colibrì** | 🟡 Optional | VRAM/RAM layer staging research | P3 |
| 11 | **Dify** | 🔵 Reference | Workflow UX / DAG / retry-state ideas | P3 |
| 12 | **Excalidraw** | 🟢 UI component | Mission Control visualization (if existing viz insufficient) | P3 |
| 13 | **Metatron** | 🟡 Security research | Isolated security sandbox scanner | P3 |
| 14 | **LibreChat** | 🔵 Reference | Chat UX ideas | P4 |
| 15 | **Anarlog** | 🟡 Future | Voice/meeting intelligence | P4 |
| 16 | **Screego** | 🟡 Peripheral | WebRTC screen sharing for agent-human pairing | P4 |
| 17 | **Node.js Best Practices** | 🔵 Reference | Security auditor knowledge source | P4 |
| 18 | **PocketBase** | 🔵 Optional | SupremeAI Local Edition backend | P4 |
| 19 | **Appwrite** | 🔵 Reference | Do NOT add (over-engineering risk) | — |
| 20 | **HackProduct** | 🔵 Reference | Weak recommendation — read only | — |
| 21 | **Supabase** | 🟠 Already core | No action | — |
| 22 | **Qdrant** | 🟠 Already covered | pgvector = primary, Qdrant = specialized if needed | — |
| 23 | **Vite** | 🟠 Already used | No action | — |
| 24 | **anthropic-tools** | 🔴 REJECT | Archived + deprecated | — |

#### 2.3 Governed Provider Pattern
```text
Agent
 ↓
Capability Request
 ↓
Policy Engine (who/what/cost/security)
 ↓
Router (which provider?)
 ↓
Governed Provider (Cerebras / LLM providers / routers)
 ↓
Evaluation Engine (correctness + latency + cost)
 ↓
Verification Layer
 ↓
Memory / Learning
```

---

### Phase 3: Memory + Learning Enhancement (Week 5-6)
> **Goal:** Evolve SupremeAI's memory from "storage" to "intelligence."

#### 3.1 Hierarchical Context Tiers (from OpenViking)
> **v2 change:** L0 is not just "memory" — it's **governance context**.

```
L0 = Immutable / Constitutional Context (always loaded)
     - AGENTS.md, AGENT_RULES.md, security policies, governance rules
     - NOT memory — governance context that constrains all behavior

L1 = Active Task Context (loaded on task assignment)
     - Task contract, touching files, role policy, skill bundle
     - Loaded when agent receives task

L2 = Retrieved Experience / Skills (loaded on demand, similarity-ranked)
     - Past decisions, learned patterns, successful approaches
     - Retrieved via vector similarity from experience DB
```

#### 3.2 Decision Metadata Model (from agentmemory)
> **v2 change:** 3 additional fields — `verification`, `policy_context`, `supersedes`.

```json
{
  "agent_type": "coder",
  "task_type": "ci_fix",
  "decision": "chose_provider_X",
  "why": "lowest_latency_for_task_type",
  "evidence": ["benchmark_run_123: 0.3s", "cost_log: $0.001"],
  "confidence": 0.85,
  "outcome": "success",
  "reusability": "high",
  "expiry": "2026-12-31",
  "policy_context": "cost_optimization_mode: true, max_cost_per_task: $0.05",
  "verification": "pytest passed, CI green, 0 regression",
  "supersedes": null
}
```

**Why `verification`?**
SupremeAI doesn't just want to know "what did the agent decide?" — it wants to know **"did the decision actually work?"** This is what separates a learning system from a memory system.

**Why `supersedes`?**
When a better decision supersedes an old one, the old decision is marked deprecated but not deleted (provenance chain).

#### 3.3 Memory Governance (from Memanto)
> **v2 change:** TTL is **policy-driven**, not hardcoded.

```text
Memory Policy Engine
   ↓
Inputs:
  - type (procedural / episodic / cache / decision)
  - importance score
  - confidence level
  - verification status
  - usage frequency (how often retrieved?)
  - freshness (how recent?)
  - risk level (what happens if stale?)
   ↓
Output: TTL (dynamic, per-entry)
```

**Not hardcoded:**
- ❌ procedural = permanent, episodic = 30d, cache = 1h
- ✅ Policy-driven: high-importance + high-confidence + verified = permanent; low-confidence + unverified + stale = short TTL

---

### Phase 4: Ecosystem Scout + Evidence Pipeline (Week 7-8)
> **Goal:** SupremeAI actively discovers, evaluates, and selectively adopts external innovation.

#### 4.1 Evidence-Based Discovery Pipeline
> **v2 change:** Gap Analysis + Capability Inventory step added.

```text
Daily Scout Cron (Agent-Reach)
  ↓
Raw findings from X, Reddit, YouTube, GitHub, Bilibili
  ↓
Deduplicate (fingerprint against existing inventory)
  ↓
Capability Inventory check (do we already have this?)
  ↓
Gap Analysis (is this a real gap in SupremeAI?)
  ↓
Benchmark / Evidence collection
  ↓
Recommendation (score: relevance × improvement × cost)
  ↓
Auditor Agent (Team Leader pattern — reviews, filters false-positives)
  ↓
GitHub Issue (only if score > threshold + auditor approves)
  ↓
Admin Decision Gate (if architectural)
```

#### 4.2 Hard Governance Rule
> **Discovery agents may discover. Auditor may recommend. Only governed issue-generation workflow may create issues.**

This prevents malicious/low-quality external information from causing automated issue spam.

#### 4.3 DuckDB Analytics Layer (workload-driven)
> **v2 change:** P2 → P3. Only adopt DuckDB when daily analytics workload exceeds Postgres capability.

```text
Supabase/Postgres (operational DB)
      ↓
Export/Event stream (when analytics volume grows)
      ↓
DuckDB (analytics engine — NOT operational DB)
      ↓
Daily ecosystem audit + cost + latency + regression reports
```

---

### Phase 5: Capability Evaluation Engine + Self-Evolution (Week 9-12)
> **Goal:** SupremeAI learns from its own operations and improves — with evidence, not assumptions.**

#### 5.1 Capability Evaluation Engine (THE MISSING COMPONENT)
> **v2 addition:** This is the roadmap's most important new section.

```text
Provider A
Provider B
Provider C
     ↓
Same benchmark tasks (representative workload)
     ↓
Correctness (does output solve the task?)
Latency (how fast?)
Cost (how much per call?)
Reliability (uptime, error rate)
Security (data exposure risk)
Tool-use success (can it use tools correctly?)
Regression (did quality degrade vs last benchmark?)
     ↓
Provider Score (weighted by task type)
     ↓
Router + Policy Engine
```

Without this, automatic routing is simplistic ("Cerebras fast → use Cerebras"). The Evaluation Engine makes routing **evidence-based**.

#### 5.2 3-Tier Auto-Routing
> **v2 addition:** Not all routing is automatic. Some requires admin governance.

| Tier | What | Who decides |
|---|---|---|
| **Automatic** | Latency weight, temporary provider health, cost optimization, retry/fallback | System (no human) |
| **Governed automatic** | Provider preference, model selection, benchmark-based routing | System (within admin-set policy bounds) |
| **Admin-only** | Constitutional changes, security-sensitive providers, permission escalation, new external capability adoption, architecture changes | Human (admin decision gate) |

This aligns with SupremeAI's **99.99% automatic / 0.01% admin boundary** principle.

#### 5.3 Learning Loop
```
Agent executes task
  ↓
Decision + Evidence + Outcome + Verification recorded
  ↓
Daily: learning_pipeline.py analyzes patterns
  ↓
Successful patterns → skill templates (L2)
Failed patterns → regression guards
Ambiguous patterns → Admin Decision
  ↓
Skill templates injected into next agent's context (L1)
  ↓
Verified improvement measurable in next run (Evaluation Engine)
```

---

## Architectural Decision Rules

### Rule 1: No New Core Dependencies
External repos are **governed providers** behind the Capability Router + Policy Engine. SupremeAI's core (memory, learning, governance, verification, orchestration) remains self-contained.

### Rule 2: Health-Checked + Replaceable + Policy-Gated
Every external provider has:
- Config flag (`SUPREMEAI_X_ENABLED`)
- Health check in `service_topology.py`
- Policy gate (who can use it, for what, at what cost)
- Fallback to native capability if unavailable
- Documented replacement path

### Rule 3: Team Leader Scanner Pattern
Scanners collect findings → write JSON report → auditor agent reviews → creates issues. No direct issue creation. (Implemented in #3973)

**Hard governance rule:** Discovery agents may discover. Auditor may recommend. Only governed issue-generation workflow may create issues.

### Rule 4: Evidence Before Adoption
> **v2 upgrade from "Memory Before Capability"**

Before adopting ANY external repo:
1. Do we already have this capability?
2. Does it solve a real problem (not theoretical)?
3. Benchmark: correctness, latency, cost, security
4. Maintenance cost vs expected improvement
5. Integration complexity
6. **Adopt / Adapt / Reference / Reject**

### Rule 5: Consolidation Over Expansion
- Supabase pgvector = canonical persistent memory (not Qdrant, not mem0)
- Provider Registry = single LLM routing point (not scattered config)
- Mission Control = single admin surface (not multiple dashboards)
- **How much capability improved per added complexity?** — this is the real metric

---

## Priority Execution Order (v2)

| Priority | Task | Source | Effort |
|---|---|---|---|
| 🥇 P1 | ~~Audit orphaned adapters (Browser Use + OpenHands) → decide revive/retire~~ ✅ **Done** — RETIRED + DELETED (#4044/#4045 → #4068/PR #4069) | Internal | Medium |
| 🥇 P1 | Adopt hierarchical context tiers (L0 governance / L1 task / L2 experience) | OpenViking | Medium |
| 🥇 P1 | Prototype Agent-Reach as Scout data layer | Agent-Reach | Medium |
| 🥇 P1 | **Build Capability Evaluation Engine** (correctness + latency + cost + security scoring) | Internal (NEW) | Large |
| 🥈 P2 | Add Cerebras as governed LLM provider | Cerebras | Small |
| 🥈 P2 | Adopt decision metadata model (with `verification` + `policy_context` + `supersedes`) | agentmemory | Medium |
| 🥈 P2 | Build Policy Engine layer (who/what/cost/security gate) | Internal (NEW) | Medium |
| 🥉 P3 | Memory governance (policy-driven TTL, conflict detection, provenance) | Memanto | Medium |
| 🥉 P3 | ~~Retire orphaned adapters (mem0, e2b, graphiti)~~ ✅ **Done** — executed PR #4103 (#4057) | Internal | Small |
| 🥉 P3 | DuckDB analytics (workload-driven — only when Postgres analytics insufficient) | DuckDB | Medium |
| 🥉 P3 | Security sandbox research | Metatron | Large |
| 🥉 P3 | Mission Control visualization | Excalidraw | Medium |
| P4 | Local inference benchmark (Strata vs Colibrì vs llama.cpp) | Strata/Colibrì | Medium |
| P4 | Chat UX research | LibreChat | Small |
| P4 | Local edition backend research | PocketBase | Small |
| ❌ | **REJECT: anthropic-tools** (archived/deprecated) | — | — |

---

## Success Metrics (v2)
> **v2 change:** Provider count is NOT a success metric. Improvement per complexity is.

| Metric | Current | Target | How |
|---|---|---|---|
| Orphaned adapters | 5 | 0 | Phase 1 audit + retire |
| **Capability improvement per added complexity** | — | measurable | Evaluation Engine tracks delta |
| Provider fallback success rate | unknown | >95% | Health checks + automatic fallback |
| Task success rate (agents) | unknown | >90% | Decision metadata + verification |
| Provider evaluation coverage | 0% | 100% of active providers | Evaluation Engine |
| Memory tier hierarchy | flat | L0/L1/L2 | Phase 3 |
| Learning loop completeness | partial | full (decision→verify→learn) | Phase 5 |
| Ecosystem scout frequency | none | daily | Phase 4 |
| Routing decisions: evidence-based | 0% | 100% | Evaluation Engine feeds Router |

---

## What This Roadmap Does NOT Do

1. **Does NOT add 24 repos as dependencies** — over-engineering prevention
2. **Does NOT replace SupremeAI's core** — external repos are governed providers, not brain
3. **Does NOT duplicate existing capabilities** — consolidation first, evidence before adoption
4. **Does NOT add without governance** — every provider is health-checked + policy-gated + replaceable
5. **Does NOT trust external reports blindly** — each repo verified against SupremeAI's actual codebase
6. **Does NOT blindly revive orphaned adapters** — audit first, decide second, revive third
7. **Does NOT use "provider count" as success metric** — improvement per complexity is the real measure
8. **Does NOT auto-route without evaluation** — Evaluation Engine feeds evidence to Router

---

## Ecosystem Intelligence Loop (THE CORE VALUE)

```
                 ECOSYSTEM
                     │
                     ▼
              Discovery / Scout
                     │
                     ▼
              Evidence Collector
                     │
                     ▼
              Capability Analyzer
                     │
                     ▼
          ┌────── Evaluation ──────┐
          │   Engine               │
          │ (correctness, cost,   │
          │  latency, security,    │
          │  regression)           │
          └──────────┬────────────┘
                     ▼
          ┌────── Gap Analysis ─────┐
          │                        │
          ▼                        ▼
       Existing?               New Gap?
          │                        │
          └──────────┬─────────────┘
                     ▼
              Recommendation
                     │
                     ▼
               Governance
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
       Adopt                  Reject
          │
          ▼
    Governed Provider
          │
          ▼
      Verification
          │
          ▼
        Memory
          │
          ▼
       Learning
          │
          └──────► Next Scout (loop continues)
```

SupremeAI evolves from "AI platform that builds things" to **"AI ecosystem intelligence system that observes, evaluates, learns, selectively adopts, verifies, and improves."**

---

*Generated: 2026-10-06 · v2 · Based on SupremeAI main @ `66a23f6` · Incorporates 15-point feedback analysis.*
