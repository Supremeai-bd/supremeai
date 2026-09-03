# Bootstrap Brain & Decision Logic — Implementation Plan (v2)

**Goal:** `SUPREMEAI_BOOTSTRAP_BRAIN_AND_DECISION_LOGIC_PLAN.md`-এর বাকি অংশ বর্তমান `CascadeMemoryService` + `DynamicPlanningEngine` স্ট্যাকের উপর বাস্তবায়ন করা।

> [!IMPORTANT]
> **Key Architectural Shift (v2):** `methodology` (reuse/adapt/generate_new_code) decision এখন থেকে Discovery-**পরে** হবে, আগে নয়। `generate_new_code` আর default থাকবে না — সেটা শেষের **fallback**।

> [!NOTE]
> **Zero New Infrastructure Policy:** নতুন কোনো টেবিল বা ডেটাবেস তৈরি হবে না। সব বিদ্যমান `ai_memory` + `metadata` JSONB ব্যবহার করবে।

---

## What is Already Done (Skip)

| Component | File | Status |
|---|---|---|
| Vector Memory Store | `services/memory_service.py` | ✅ Done |
| Intent Deciphering + Memory Recall | `services/intent_deciphering.py` | ✅ Done |
| DAG-based Planner | `services/dynamic_planner.py` | ✅ Done |
| Living Engine Orchestrator | `services/living_engine.py` | ✅ Done |
| Memory Consolidation Node (DAG step) | `services/dynamic_planner.py` | ✅ Done |
| Self-Correction + Lesson Logging | `services/self_correction.py` | ✅ Done |
| Knowledge Seed Pipeline | `scripts/sync_knowledge.py` | ✅ Done (partial) |

---

## New Architecture: Discovery-First DAG

বর্তমান flow (v1):
```
Intent → Classify → [Action Nodes] → Verify → Memorize
                       ↑
               methodology ইতিমধ্যেই fixed
```

নতুন flow (v2) — Discovery হবে **before** methodology decision:
```
USER INTENT
    ↓
INTENT DECIPHERING (existing)
    ↓
EPISTEMIC PROBE (existing)
    ↓
CAPABILITY DISCOVERY [NEW – L1/L2/L3 Tiered]
    ↓
RESOURCE DISCOVERY [internal accounts/MCPs]
    ↓
COST / RISK / LATENCY EVALUATION
    ↓
┌──────────────────────────────────┐
│  METHODOLOGY DECISION (post-disc)│
│                                  │
│  reuse                           │
│  adapt                           │
│  compose                         │
│  delegate                        │
│  generate_new_code (last resort) │
│  ask_admin (destructive only)    │
└──────────────────────────────────┘
    ↓
EXECUTE (domain adapter)
    ↓
VERIFY
    ↓
MEMORIZE + METRICS
```

---

## Proposed Changes

### Component 1 — Brain Seed Data (Plan Phase 1)

**লক্ষ্য:** ১৫০+ কোর ডিসিশন প্যাটার্ন `ai_memory`-তে সীড করা।

---

#### [NEW] `backend/data/brain_seed_v1.json`

৬টি ক্যাটাগরিতে ~১৫০ রেকর্ড (ইংরেজিতে — ভেক্টর সার্চ পারফরম্যান্সের জন্য):

| `brain_domain` | রেকর্ড সংখ্যা | Plan Section |
|---|---|---|
| `decision_pattern` | ~40 | 3-A |
| `meta_question` | ~20 | 3-F (18 questions) |
| `tool_selection_rule` | ~25 | 3-D |
| `failure_recovery` | ~30 | 3-E |
| `capability_knowledge` | ~20 | 3-B |
| `implementation_source` | ~15 | 3-G |

**`metadata` schema:**
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

---

#### [NEW] `backend/scripts/seed_bootstrap_brain.py`

`sync_knowledge.py`-এর স্ট্রাকচার ফলো করে `brain_seed_v1.json` থেকে রিড করে `CascadeMemoryService.store_memory()` দিয়ে `ai_memory`-তে ইনজেক্ট করবে।
- `task_type = "bootstrap_brain"` সেট করবে — পরে filter করে দেখা যাবে
- ইডেম্পোটেন্ট: `source == "bootstrap_brain_seed_v1"` চেক করে ডুপ্লিকেট skip করবে

---

### Component 2 — Tiered Discovery Service (Core New Work)

**লক্ষ্য:** `discover_reusable_implementation` capability-টি সব `dev` task-এ সর্বদা available থাকবে, কিন্তু tiered execution দিয়ে cost ও latency নিয়ন্ত্রণ করবে।

---

#### [NEW] `backend/brain/discovery_service.py`

```python
class TieredDiscoveryService:
    """
    3-level tiered reusable implementation discovery.
    
    L1 — Cheap: ai_memory/cache search (in-process, <5ms)
    L2 — Medium: internal implementation registry / docs corpus search
    L3 — Expensive: external GitHub / web / OSS search (only if L1+L2 miss)
    """

    async def discover(
        self, 
        goal: str, 
        domain: str,
        complexity: str,
        allow_l3: bool = False,  # gated by complexity/confidence
    ) -> DiscoveryResult:
        
        # L1: ai_memory vector search (existing CascadeMemoryService)
        result = await self._l1_memory_search(goal)
        if result.confidence >= 0.8:
            return result  # fast path exit
        
        # L2: Internal docs/ corpus + scripts/ + services/ grep
        result = await self._l2_internal_registry_search(goal)
        if result.confidence >= 0.7:
            return result
        
        # L3: External discovery (GitHub/PyPI/web) — only if explicitly needed
        if allow_l3 and complexity in ("high", "novel"):
            result = await self._l3_external_discovery(goal)
        
        return result


@dataclass
class DiscoveryResult:
    found: bool
    confidence: float
    level: str            # "L1" | "L2" | "L3" | "none"
    source_type: str      # "memory" | "internal" | "github" | "none"
    source_ref: str
    suggested_action: str  # "reuse" | "adapt" | "compose" | "generate_new_code"
    candidates: list[dict]
```

**L3 allow logic — `allow_l3` কখন `True` হবে:**
```python
allow_l3 = (
    complexity in ("high", "novel") and
    intent.confidence_score < 0.7 and  # L1/L2-এ confidence কম
    not intent.latent_constraints.get("offline_only")
)
```

---

#### [MODIFY] [`dynamic_planner.py`](file:///f:/supremeai/backend/services/dynamic_planner.py)

`plan_task()` মেথডে ২টি পরিবর্তন:

**পরিবর্তন ১:** `discovery_node` সব dev task-এ add হবে `probe_node`-এর পর:

```python
discovery_node = TaskNode(
    id=f"{dag_id}_step1b_discover",
    name="Tiered Reusable Implementation Scout",
    capability="discover_reusable_implementation",
    description=(
        "L1→L2→L3 tiered search: ai_memory → internal registry → "
        "external OSS. Sets methodology for downstream nodes."
    ),
    input_params={
        "goal": intent.ultimate_goal,
        "domain": intent.domain,
        "complexity": intent.complexity,
    },
    dependencies=[probe_node.id],
)
```

**পরিবর্তন ২:** `_build_action_nodes()` এখন `discovery_result`-এর `suggested_action`-এর উপর ভিত্তি করে method সিলেক্ট করবে, আগের `intent.suggested_methodology` নয়:

```python
def _build_action_nodes(
    self, dag_id, intent, parent_id, discovery_result=None
) -> list[TaskNode]:
    # methodology এখন discovery_result থেকে আসে (post-discovery decision)
    methodology = (
        discovery_result.suggested_action 
        if discovery_result else "generate_new_code"  # safe fallback only
    )
    ...
```

---

#### [MODIFY] [`living_engine.py`](file:///f:/supremeai/backend/services/living_engine.py)

`discover_reusable_implementation` capability হ্যান্ডেল করার routing যোগ করা। Discovery result context-এ সেট হবে যাতে পরের node `_build_action_nodes()` সঠিক methodology পায়।

---

### Component 3 — Advisor Contract (Plan Section 4)

**লক্ষ্য:** LLM কল সর্বদা constrained advisory প্রম্পটে হবে — LLM decision authority পাবে না।

---

#### [NEW] `backend/brain/advisor_contract.py`

```python
class AdvisorContract:
    """
    Structured prompt builder for third-party LLM advisory calls.
    Follows Plan Section 4 contract format exactly.
    """
    
    @staticmethod
    def build_prompt(
        goal: str,
        capabilities: list[str],
        constraints: list[str],
        discovery_result: DiscoveryResult,
    ) -> str:
        return f"""
ROLE: You are a planning/reasoning advisor for SupremeAI.
      You provide structured recommendations ONLY.
      You do NOT execute, decide, or override SupremeAI policies.

USER GOAL: {goal}

AVAILABLE CAPABILITIES: {capabilities}
DISCOVERY RESULT: level={discovery_result.level}, action={discovery_result.suggested_action}
CONSTRAINTS: {constraints}

QUESTIONS TO ANSWER:
1. Is there a reusable or composable approach not yet considered?
2. What are the risks of the proposed path?
3. What should be validated after execution?
4. What lesson should be stored in ai_memory?

OUTPUT FORMAT: JSON with fields:
  recommendations, risks, validation_steps, lesson_candidate
  Clearly distinguish: facts | assumptions | uncertainties
"""
```

---

### Component 4 — Brain Quality Metrics (Plan Section 10)

#### [MODIFY] [`living_engine.py`](file:///f:/supremeai/backend/services/living_engine.py)

`SolutionResult` dataclass-এ নতুন ফিল্ড:

```python
@dataclass
class SolutionResult:
    ...  # existing fields
    
    # NEW: Brain quality metrics
    discovery_level: str = "none"          # "L1" | "L2" | "L3" | "none"
    methodology_decision: str = "unknown"  # "reuse" | "adapt" | "generate_new_code" | ...
    brain_coverage_score: float = 0.0      # % of task solved via existing capabilities
    new_code_ratio: float = 1.0            # 1.0 = 100% new code, 0.0 = 100% reuse
```

Memory consolidation node-এ এই মেট্রিক্স `ai_memory` metadata-তে persist হবে।

---

## Implementation Order

```
Step 1  →  brain_seed_v1.json তৈরি করা (~150 records)
Step 2  →  seed_bootstrap_brain.py তৈরি ও রান করা
Step 3  →  brain/discovery_service.py তৈরি করা (L1/L2/L3 tiered)
Step 4  →  dynamic_planner.py রিফ্যাক্টর করা (discovery node + post-disc methodology)
Step 5  →  living_engine.py-তে discovery capability routing যোগ করা
Step 6  →  brain/advisor_contract.py তৈরি করা
Step 7  →  SolutionResult-এ metrics fields যোগ করা
Step 8  →  টেস্ট রান ও ভেরিফিকেশন
```

---

## Verification Plan

### Automated Tests

```bash
# Seed verification
cd backend && python scripts/seed_bootstrap_brain.py --dry-run
cd backend && python scripts/seed_bootstrap_brain.py

# Existing memory tests must still pass
cd backend && pytest tests/core/test_memory_service.py -v
cd backend && pytest tests/memory/ -v

# New discovery service unit tests
cd backend && pytest tests/brain/test_discovery_service.py -v
```

### Manual Verification Checklist

- [ ] `seed_bootstrap_brain.py` রান — Supabase `ai_memory`-তে `task_type='bootstrap_brain'` রেকর্ড আছে
- [ ] নতুন dev task দিলে DAG-এ `step1b_discover` node লগে দেখা যায়
- [ ] L1 hit হলে (ai_memory confidence ≥ 0.8) `methodology = "reuse"` বা `"adapt"` সিলেক্ট হয়
- [ ] L3 কেবল `complexity = "high"` এবং L1/L2 miss হলে ট্রিগার হয়
- [ ] `SolutionResult.discovery_level` সঠিক ভ্যালু রিটার্ন করে
- [ ] `generate_new_code` শুধু সত্যিকারের "nothing found" কেসে ব্যবহৃত হয়
