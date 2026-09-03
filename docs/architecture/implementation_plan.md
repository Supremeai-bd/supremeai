# docs/architecture — Implementation Plan

> **Covers:** Architecture plans, consolidation & cleanup, and structural decisions.
> **Source Plans:** `SUPREMEAI_CONSOLIDATION_AND_CLEANUP_PLAN.md`, `THEORY_OF_MIND_AND_DIGITAL_TWIN_DEEP_DIVE.md`, `SUPREME_SYSTEM_ARCHITECTURE.md`

---

## 1. `SUPREMEAI_CONSOLIDATION_AND_CLEANUP_PLAN.md`

**Goal:** Router sprawl (8 locations) + Agent sprawl (7 locations) + Route RBAC gaps (48 unguarded routes) দূর করা।

### Phase Status Overview

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Dead Code & Router Consolidation | ⚠️ Partial |
| Phase 2 | Agent & Evolution Consolidation | ⚠️ Partial |
| Phase 3 | Route RBAC Audit | 🔴 Not Started |
| Phase 4 | Test Coverage 38% → 80%+ | ⏸️ Deferred |
| Phase 5 | Documentation & Git Push | ✅ Done |
| Phase 6 | Intent Deciphering & Dynamic Planning | ✅ Done |
| Phase 7 | Tool Forge & Dual-Loop Verification | ✅ Done |

### 🚧 Pending Tasks

#### Phase 1 — Router Consolidation (Remaining Work)

**Target:** `backend/brain/` এর 8 router → `core/llm/advanced_model_router.py`-এ merge

```
Routers to audit & retire:
  backend/brain/api_router.py
  backend/brain/expert_router.py  
  backend/brain/gcp_router.py
  backend/brain/parallel_cloud_router.py
  backend/brain/performance_aware_router.py
  backend/brain/cognitive_router.py  ← already uses advanced_model_router?
```

- **Step 1a:** `grep -r "from brain.api_router\|from brain.expert_router" backend/` → caller graph তৈরি
- **Step 1b:** Dead router files (0 callers) → `git rm`
- **Step 1c:** Active routing logic → `advanced_model_router.py`-এ merge করা
- **টেস্ট:** `pytest tests/brain/ -v --no-cov`

#### Phase 2 — Agent Consolidation (Remaining Work)

**Target:** 7 locations → `backend/agents/` (core) + `backend/tools/ai_agents/` (tools)

- **Step 2a:** `backend/src/agents/syncguard/` → `backend/agents/syncguard/` (move)
- **Step 2b:** `backend/brain/autonomous_agent.py`, `crewai_agents.py`, `langgraph_agent.py` → `backend/agents/core/`
- **Step 2c:** Evolution systems: `backend/evolution/` + `backend/agents/evolution/` → `backend/core/evolution/`
- **টেস্ট:** `pytest tests/agents/ -v`

#### Phase 3 — Route RBAC Audit (🔴 Critical, Not Started)

**48 routes currently unguarded** — এটি সবচেয়ে গুরুত্বপূর্ণ pending item।

- **Step 3a:** `grep -r "router\.\(get\|post\|put\|delete\|patch\)" backend/api/routes/ | grep -v "Depends(" > unguarded_routes.txt`
- **Step 3b:** প্রতিটি route classify করা: Public / User-Protected / Admin-Only
- **Step 3c:** Admin-Only routes → `Depends(require_admin_token)` inject করা
- **Step 3d:** User-Protected routes → `Depends(get_current_user_token)` inject করা
- **টেস্ট:** `pytest tests/api/test_rbac_coverage.py`

---

## 2. `THEORY_OF_MIND_AND_DIGITAL_TWIN_DEEP_DIVE.md`

**Goal:** User Digital Twin + Theory of Mind layer activate করা

### ✅ Already Done
- `backend/brain/user_digital_twin.py` — ফাইলটি আছে (6257 bytes)

### 🚧 Pending Tasks

#### Step 1 — Digital Twin Service → API Endpoint
- **কাজ:** `user_digital_twin.py`-এর মেথডগুলো `/api/user/twin` endpoint-এ expose করা
- **ফাইল:** `backend/api/routes/user_twin.py` (new)

#### Step 2 — Twin → Intent Deciphering Integration
- **কাজ:** `IntentDecipheringService`-এ user twin recall যোগ করা — ইউজারের প্রেফারেন্স context-এ
- **ফাইল:** `backend/services/intent_deciphering.py` → `decipher_intent()` মেথড

---

## 3. `SYSTEM_DIAGRAMS_AND_FLOWS.md` / `SUPREME_SYSTEM_ARCHITECTURE.md`

### ✅ Already Done
- Single-service architecture deploy হয়েছে
- FastAPI + Supabase + pgvector stack production-ready

### 🚧 Pending Tasks

#### Step 1 — Architecture Diagram Auto-Generation
- **কাজ:** কোডবেস AST থেকে স্বয়ংক্রিয়ভাবে module dependency graph generate করা
- **ফাইল:** `backend/scripts/generate_architecture_diagram.py` (new)
- **Output:** `docs/architecture/current_architecture.mmd` (Mermaid format)

---

## Implementation Priority Order

```
Priority 1 (Critical Security):
  └── Phase 3: Route RBAC Audit → 48 unguarded routes fix করা

Priority 2 (Stability):
  ├── Phase 1: Dead router files remove করা
  └── Phase 2: Agent consolidation (src/agents/ → agents/)

Priority 3 (Feature):
  └── Digital Twin → Intent Deciphering integration
```

## Verification Gate

```bash
# RBAC coverage check
cd backend && grep -r "Depends(" api/routes/ | wc -l  # should increase

# Router consolidation check  
cd backend && python -c "from core.llm.advanced_model_router import *; print('OK')"

# Full test suite
cd backend && poetry run pytest tests/ -n auto -q --no-cov
```
