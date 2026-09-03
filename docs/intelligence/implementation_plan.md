# docs/intelligence — Implementation Plan

> **Source Plan:** [`SUPREME_AI_INTELLIGENCE_MASTER.md`](file:///f:/supremeai/docs/intelligence/SUPREME_AI_INTELLIGENCE_MASTER.md)  
> **Goal:** 5-Pillar Cognitive Intelligence + Continuous Self-Evolution Lifecycle সম্পূর্ণ করা।

---

## Component Status Overview

| Component | File | Status |
|---|---|---|
| Intent Deciphering Service | `services/intent_deciphering.py` | ✅ Done |
| Dynamic Planning Engine | `services/dynamic_planner.py` | ✅ Done |
| Living Engine Orchestrator | `services/living_engine.py` | ✅ Done |
| DevAdapter | `adapters/dev_adapter.py` | ✅ Done |
| BusinessAdapter | `adapters/business_adapter.py` | ✅ Done |
| UXAdapter | `adapters/ux_adapter.py` | ✅ Done |
| PatternRecognizer | `learning/pattern_recognizer.py` | ✅ Done |
| EvolutionModule (Genetic Algo) | `core/evolution_module.py` | ✅ Done |
| CascadeMemoryService (Eternal Brain) | `services/memory_service.py` | ✅ Done |
| TokenJuice Compressor | `engine/compression/token_juice.py` | ✅ Exists |
| Hierarchical Memory Tree | `memory/hierarchical_tree.py` | ✅ Exists |
| RedTeam / Adversarial Reasoning | — | 🔴 Missing |
| Meta-Evolution (Self-Code Rewrite) | — | 🔴 Missing |
| Swarm Consensus Engine | — | 🔴 Missing |
| FitnessEngine wire-up | — | ⚠️ Partial |
| TokenJuice → LLM Gateway integration | — | ⚠️ Not wired |

---

## 🚧 Pending Tasks

### Step 1 — TokenJuice → LLM Gateway Integration
- **কাজ:** প্রতিটি LLM call-এর আগে context কে `TokenJuice.compress()` দিয়ে 70-85% compress করা
- **ফাইল:** `backend/core/llm/llm_gateway.py` → `acompletion()` method-এ integrate
- **টেস্ট:** `pytest tests/core/llm/test_llm_gateway.py -v` → token count কমেছে verify

### Step 2 — FitnessEngine → Evolution Learning Wire-up
- **কাজ:** Successful LLM call → `EvolutionModule.learn_from_success()` call করা
- **ফাইল:** `backend/core/llm/llm_gateway.py` → `learn_from_success()` await যোগ
- **Flag:** `ENABLE_EVOLUTION_LEARNING=true` env var দিয়ে গেট করা
- **টেস্ট:** `pytest tests/core/test_evolution_module.py`

### Step 3 — Red Team Adapter (Adversarial Validation)
- **কাজ:** একটি নতুন adapter যা generate করা output-কে adversarially challenge করে vulnerability খোঁজে
- **ফাইল:** `backend/adapters/red_team_adapter.py` (new)
- **Integration:** `living_engine.py`-এর execution loop-এ optional step হিসেবে
- **টেস্ট:** `pytest tests/adapters/test_red_team_adapter.py`

### Step 4 — Swarm Consensus Engine
- **কাজ:** Dev + Business + UX + RedTeam adapter-এর output → weighted voting consensus
- **ফাইল:** `backend/core/swarm_consensus.py` (new)
- **Algorithm:** Weighted majority vote, confidence-weighted
- **Integration:** `living_engine.py` → `SolutionResult` generation-এ
- **টেস্ট:** `pytest tests/core/test_swarm_consensus.py`

### Step 5 — Meta-Evolution (Self-Code Rewrite Module)
- **কাজ:** System নিজেই নিজের agent/adapter code-এ improvement suggest করতে পারবে (sandboxed)
- **ফাইল:** `backend/core/meta_evolution.py` (new)
- **Safety:** সরাসরি code write করবে না — `brain/promotion_candidate.py`-তে candidate রাখবে HITL approval-এর জন্য
- **টেস্ট:** Candidate generation test (actual self-write নয়)

### Step 6 — Multi-Model Parallel Swarm Routing
- **কাজ:** একই query Gemini + Groq + OpenRouter-এ parallel পাঠানো → fastest/best-quality response নেওয়া
- **ফাইল:** `backend/brain/parallel_cloud_router.py` (already exists, wire properly)
- **টেস্ট:** Latency comparison test

---

## Implementation Priority Order

```
Priority 1 (Token Cost Reduction):
  Step 1 → TokenJuice → LLM Gateway integration

Priority 2 (Self-Evolution):
  Step 2 → FitnessEngine wire-up

Priority 3 (Intelligence Quality):
  Step 3 → Red Team Adapter
  Step 4 → Swarm Consensus Engine

Priority 4 (Advanced):
  Step 5 → Meta-Evolution (sandboxed)
  Step 6 → Parallel Swarm Routing
```

## Verification Gate

```bash
# TokenJuice integration
cd backend && python -c "
from core.llm.llm_gateway import get_llm_gateway
import asyncio
gw = get_llm_gateway()
r = asyncio.run(gw.acompletion('hello', task_type='general'))
print('token_compressed:', r.get('token_usage'))
"

# Evolution learning
cd backend && pytest tests/core/test_evolution_module.py -v

# Full suite
cd backend && poetry run pytest tests/ -n auto -q --no-cov
```
