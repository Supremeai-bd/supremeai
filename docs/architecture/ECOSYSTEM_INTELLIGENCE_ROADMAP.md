# SupremeAI Ecosystem Intelligence Roadmap

> **Root-cause analysis against current `main` branch (`9164498`) — not a blind adoption of external repos.**

## Executive Summary

SupremeAI's strength is **not** building every capability itself — it is **orchestrating capabilities through governance + memory + routing + verification + learning**. This roadmap treats the 24 analyzed external repos as **specialist providers** or **research sources**, not as core dependencies. The guiding principle:

> **SupremeAI = Capability Aggregator + Orchestrator + Governance + Learning System**
> **External repos = specialist capability providers (optional, replaceable, governed)**

---

## Current Architecture Inventory (verified @ `9164498`)

| Layer | Component | Status | File(s) |
|---|---|---|---|
| **Capability Router** | Provider Registry | ✅ Active | `backend/core/llm/provider_registry.py` |
| **Memory** | MemoryRepository + pgvector | ✅ Active | `backend/core/ai_memory/repository.py` |
| **Memory** | Adaptive Engine (experience DB) | ✅ Active | `backend/adaptive_engine/experience_db.py` |
| **Memory** | Episodic / Long-term / Consolidator | ✅ Active | `backend/memory/episodic_memory.py`, `long_term_memory.py`, `backend/evolution/memory_consolidator.py` |
| **Browser** | BrowserUse Adapter | ⚠️ Orphaned | `backend/integrations/browser_use_adapter.py` |
| **Coding Agent** | OpenHands Adapter | ⚠️ Orphaned | `backend/integrations/openhands_adapter.py` |
| **MCP** | MCP Client + Gateway | ✅ Active | `backend/brain/mcp_client.py`, `backend/tools/mcp/` |
| **Scanner** | Rules Breaker (Team Leader pattern) | ✅ Active (refactored) | `scripts/agents/rules_breaker.py` |
| **Learning** | Learning Pipeline + Experience | ✅ Active | `backend/evolution/learning_pipeline.py`, `backend/learning/experience.py` |
| **Deploy** | Render + Vercel + Deploy Train | ✅ Active | `scripts/deploy/` |
| **Mission Control** | Admin dashboard | ✅ Active | `apps/mission-control/` |
| **Integrations (orphaned)** | mem0, e2b, graphiti | ❌ Orphaned | `backend/integrations/` |

### Key Gap Identified
Three adapters are marked **orphaned** (`browser_use_adapter.py`, `openhands_adapter.py`, `mem0_adapter.py`). Before adding ANY new external repo, these must be either **revived as governed providers** or **formally retired**.

---

## 5-Phase Roadmap

### Phase 1: Capability Inventory + Orphan Cleanup (Week 1-2)
> **Goal:** Stop accumulating capabilities before cleaning up what exists.

#### 1.1 SupremeAI Capability Inventory
Create `docs/architecture/CAPABILITY_INVENTORY.md`:
- Every integration/adapter → status (active/orphaned/deprecated)
- Every provider → config flag + env var + health check
- Every external dependency → purpose + replaceability assessment

#### 1.2 Orphaned Adapter Audit
| Adapter | Action | Rationale |
|---|---|---|
| `browser_use_adapter.py` | **Revive** as governed browser provider | Browser Use is mature (117k+ stars), actively maintained, and SupremeAI's browser orchestration needs it |
| `openhands_adapter.py` | **Revive** as governed coding provider | OpenHands is the best autonomous coding execution engine; SupremeAI orchestrates, OpenHands executes |
| `mem0_adapter.py` | **Retire** | SupremeAI already has canonical MemoryRepository + pgvector; mem0 is redundant |
| `e2b_adapter.py` | **Retire** unless sandbox execution is needed | SupremeAI has its own sandbox; e2b is redundant if sandbox works |
| `graphiti_adapter.py` | **Retire** | SupremeAI's episodic + long-term memory covers this |

#### 1.3 Provider Health Dashboard
Wire all active providers into the existing `service_topology.py` health check with proper `CONFIGURED` / `REACHABLE` / `HEALTHY` states (leveraging #3226 fix).

---

### Phase 2: Provider Adapter Revival + Governance (Week 3-4)
> **Goal:** External repos = optional, governed, health-checked providers — not core dependencies.

#### 2.1 Capability Router Architecture
```
                    SUPREMEAI
                        │
             ┌──────────┴──────────┐
             │   Capability Router  │
             └──────────┬──────────┘
                        │
       ┌────────────────┼─────────────────┐
       ↓                ↓                 ↓
   Internal         External            Research
   Capability       Provider            Source
       │                │                 │
   Native Agent     OpenHands          Agent-Reach
   Native Memory    Browser Use        OpenViking
   Native Router    Cerebras           agentmemory
       │            Strata/Colibrì        │
       │            DuckDB               │
       └────────────────┼─────────────────┘
                        ↓
                Verification Layer
                        ↓
                  Memory / Learning
                        ↓
                   Admin Policy
```

#### 2.2 Provider Integration Matrix

| # | Repo | Category | Action | Priority |
|---|---|---|---|---|
| 1 | **Browser Use** | 🟢 Use directly | Revive adapter as governed browser provider. Escalation: HTTP → Playwright → Browser Use | P1 |
| 2 | **OpenHands** | 🟡 Use selectively | Revive adapter as coding execution provider. SupremeAI = orchestrator, OpenHands = executor | P1 |
| 3 | **Cerebras** | 🟢 Use directly | Add as speed-optimized LLM provider in provider_registry.py | P2 |
| 4 | **DuckDB** | 🟢 Use directly | Add as embedded analytics engine for CI/audit/cost analytics | P2 |
| 5 | **OpenViking** | 🟢 Research + adapt | Adopt hierarchical context tiers (L0/L1/L2) + memory/knowledge/skill unification into existing memory architecture | P1 |
| 6 | **Agent-Reach** | 🟢 Prototype | Build as Ecosystem Scout data acquisition layer (X, Reddit, YouTube, GitHub) | P1 |
| 7 | **agentmemory** | 🟡 Adapt ideas | Adopt decision metadata model (Decision/Why/Evidence/Confidence/Outcome/Expiry) into learning memory | P2 |
| 8 | **Memanto** | 🟡 Adapt ideas | Adopt memory governance: conflict detection, confidence, provenance, expiration, lifecycle | P3 |
| 9 | **Strata** | 🟡 Optional | Local inference provider (benchmark vs llama.cpp before adopting) | P3 |
| 10 | **Colibrì** | 🟡 Optional | VRAM/RAM layer staging research (benchmark vs Strata) | P3 |
| 11 | **Dify** | 🔵 Reference | Workflow UX / DAG representation / retry-state handling ideas | P3 |
| 12 | **Excalidraw** | 🟢 UI component | Mission Control architecture visualization (if existing viz insufficient) | P3 |
| 13 | **LibreChat** | 🔵 Reference | Chat UX ideas: model switching, provider fallback, conversation search, MCP UX | P3 |
| 14 | **Metatron** | 🟡 Security research | Isolated security sandbox scanner (PR → sandbox → findings → auditor → gate) | P3 |
| 15 | **Anarlog** | 🟡 Future | Voice/meeting intelligence (if product feature needed) | P4 |
| 16 | **Screego** | 🟡 Peripheral | WebRTC screen sharing for agent-human pairing/debugging | P4 |
| 17 | **Node.js Best Practices** | 🔵 Reference | Security auditor knowledge source (JWT revocation, brute-force, etc.) | P4 |
| 18 | **PocketBase** | 🔵 Optional | SupremeAI Local Edition backend (offline/low-resource/single-user) | P4 |
| 19 | **Appwrite** | 🔵 Reference | Alternative deployment target (do NOT add as dependency — over-engineering risk) | — |
| 20 | **HackProduct** | 🔵 Reference | Weak recommendation — read only, no integration | — |
| 21 | **Supabase** | 🟠 Already core | No action — already canonical database + pgvector | — |
| 22 | **Qdrant** | 🟠 Already covered | Already wired (archived context_manager). Production question: pgvector primary, Qdrant specialized? | — |
| 23 | **Vite** | 🟠 Already used | No action — frontend already Vite-based | — |
| 24 | **anthropic-tools** | 🔴 REJECT | Archived + deprecated. Do NOT use. Anthropic's current tool-use API is the replacement | — |

---

### Phase 3: Memory + Learning Enhancement (Week 5-6)
> **Goal:** Evolve SupremeAI's memory from "storage" to "intelligence."

#### 3.1 Hierarchical Context Tiers (from OpenViking)
```
L0: System/constitutional rules (always loaded)
L1: Task-specific context (loaded on task assignment)
L2: Episodic/skill memory (loaded on demand, similarity-ranked)
```
Adopt into existing `MemoryRepository` + `episodic_memory.py`.

#### 3.2 Decision Metadata Model (from agentmemory)
Every agent decision records:
```json
{
  "decision": "chose_provider_X",
  "why": "lowest_latency_for_task_type",
  "evidence": ["benchmark_run_123: 0.3s", "cost_log: $0.001"],
  "confidence": 0.85,
  "outcome": "success",
  "reusability": "high",
  "expiry": "2026-12-31"
}
```

#### 3.3 Memory Governance (from Memanto)
- **Conflict detection**: new memory conflicts with existing → flag for review
- **Provenance**: every memory entry records source agent + timestamp + confidence
- **Expiration**: memory entries have TTL based on type (procedural=permanent, episodic=30d, cache=1h)
- **Lifecycle**: creation → validation → active → deprecated → archived

---

### Phase 4: Ecosystem Scout + Research Pipeline (Week 7-8)
> **Goal:** SupremeAI actively discovers and evaluates external innovation.

#### 4.1 Agent-Reach Integration (Prototype)
```
Daily Scout Cron
  ↓
Agent-Reach CLI (X, Reddit, YouTube, GitHub, Bilibili)
  ↓
Raw findings → /tmp/ecosystem_scout_findings.json
  ↓
SupremeAI Auditor Agent (Team Leader pattern)
  ↓
Filter: false-positive? Already covered? Relevant?
  ↓
Score: relevance × complexity × cost × maintenance
  ↓
Generate GitHub Issue (if score > threshold)
  ↓
Admin Decision Gate (if architectural)
```

#### 4.2 DuckDB Analytics Layer
```sql
-- Daily ecosystem audit
SELECT 
  agent_name,
  COUNT(*) as decisions,
  AVG(confidence) as avg_confidence,
  SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) as successes,
  AVG(latency_ms) as avg_latency,
  SUM(cost_usd) as total_cost
FROM agent_decisions
WHERE date = CURRENT_DATE
GROUP BY agent_name;
```

---

### Phase 5: Self-Evolution + Continuous Improvement (Week 9-12)
> **Goal:** SupremeAI learns from its own operations and improves.

#### 5.1 Learning Loop
```
Agent executes task
  ↓
Decision + Evidence + Outcome recorded
  ↓
Daily: learning_pipeline.py analyzes patterns
  ↓
Successful patterns → skill templates
Failed patterns → regression guards
Ambiguous patterns → Admin Decision
  ↓
Skill templates injected into next agent's context (L1)
  ↓
Verified improvement measurable in next run
```

#### 5.2 Provider Benchmarking
Automated benchmark of all LLM providers:
```
Daily benchmark cron
  ↓
Send identical test prompt to each provider
  ↓
Record: latency, cost, quality score, availability
  ↓
DuckDB analytics → provider health dashboard
  ↓
Auto-adjust routing weights (Cerebras for speed, OpenAI for quality, local for cost)
```

---

## Architectural Decision Rules

### Rule 1: No New Core Dependencies
External repos are **providers** behind the Capability Router. SupremeAI's core (memory, learning, governance, verification, orchestration) remains self-contained.

### Rule 2: Health-Checked + Replaceable
Every external provider has:
- Config flag (`SUPREMEAI_X_ENABLED`)
- Health check in `service_topology.py`
- Fallback to native capability if unavailable
- Documented replacement path

### Rule 3: Team Leader Scanner Pattern
Scanners (rules_breaker, ecosystem_scout) collect findings → write JSON report → auditor agent reviews → creates issues. No direct issue creation. (Implemented in #3973)

### Rule 4: Memory Before Capability
Before adding a new capability, verify:
1. Is it already covered by an existing module?
2. Can an existing module be extended instead?
3. Does it duplicate any orphaned adapter?
4. Is there a plan to govern + monitor it?

### Rule 5: Consolidation Over Expansion
- Supabase pgvector = canonical persistent memory (not Qdrant, not mem0)
- Provider Registry = single LLM routing point (not scattered config)
- Mission Control = single admin surface (not multiple dashboards)

---

## Priority Execution Order

| Priority | Task | Source | Effort |
|---|---|---|---|
| 🥇 P1 | Revive Browser Use adapter (governed provider) | Browser Use | Medium |
| 🥇 P1 | Revive OpenHands adapter (governed provider) | OpenHands | Medium |
| 🥇 P1 | Adopt hierarchical context tiers (L0/L1/L2) | OpenViking | Medium |
| 🥇 P1 | Prototype Agent-Reach as Scout data layer | Agent-Reach | Medium |
| 🥈 P2 | Add Cerebras as LLM provider | Cerebras | Small |
| 🥈 P2 | Add DuckDB as analytics engine | DuckDB | Medium |
| 🥈 P2 | Adopt decision metadata model | agentmemory | Medium |
| 🥉 P3 | Memory governance (conflict/provenance/expiry) | Memanto | Medium |
| 🥉 P3 | Retire orphaned adapters (mem0, e2b, graphiti) | Internal | Small |
| 🥉 P3 | Security sandbox research | Metatron | Large |
| 🥉 P3 | Mission Control visualization | Excalidraw | Medium |
| P4 | Local inference benchmark (Strata vs Colibrì vs llama.cpp) | Strata/Colibrì | Medium |
| P4 | Chat UX research | LibreChat | Small |
| P4 | Local edition backend research | PocketBase | Small |
| ❌ | **REJECT: anthropic-tools** (archived/deprecated) | — | — |

---

## What This Roadmap Does NOT Do

1. **Does NOT add 24 repos as dependencies** — over-engineering prevention
2. **Does NOT replace SupremeAI's core** — external repos are providers, not brain
3. **Does NOT duplicate existing capabilities** — consolidation first
4. **Does NOT add without governance** — every provider is health-checked + replaceable
5. **Does NOT trust external reports blindly** — each repo verified against SupremeAI's actual codebase

---

## Success Metrics

| Metric | Current | Target | How |
|---|---|---|---|
| Orphaned adapters | 5 | 0 | Revive or retire in Phase 1 |
| Active governed providers | ~3 | ~8 | Phase 2 additions |
| Memory tiers | flat | L0/L1/L2 | Phase 3 |
| Learning loop | partial | full | Phase 5 |
| Ecosystem scout | none | daily | Phase 4 |
| Provider auto-routing | manual | automated | Phase 5 |

---

*Generated: 2026-10-06 · Based on SupremeAI main @ `9164498` · Analysis of 24 external repos against actual codebase architecture.*
