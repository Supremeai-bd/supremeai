# docs/ Root — Implementation Plan

> **Covers:** Root-level plan documents: `PRODUCTION_READINESS_PLAN_V3.md`, `SUPREMEAI_PRE_PRODUCTION_GO_LIVE_MASTER_TODO.md`, `FREE_TIER_STORAGE_PLAN.md`, `SPEC_KIT_ADOPTION.md`

---

## 1. `PRODUCTION_READINESS_PLAN_V3.md` — 13 Targeted Bug Fixes

**Goal:** 15 bugs + 10 perf issues + 10 dead-code + 4 capability gaps fix করা।

### Fix Status Tracker

| Fix | Description | Status |
| --- | --- | --- |
| #1 | `ArtifactType(str, str)` duplicate base | 🔴 Open |
| #2 | `stream_chat_sse` garbage stream | 🔴 Open |
| #3 | 7 missing `await` in tools/ | 🔴 Open |
| #4 | 9 broken imports | 🔴 Open |
| #5 | `time.sleep()` in async retry wrapper | 🔴 Open |
| #6 | WebSocket unbounded (no cap, no heartbeat) | 🔴 Open |
| #7 | `_pref_locks` dict memory leak | 🔴 Open |
| #8 | Per-request `httpx.AsyncClient` (no reuse) | 🔴 Open |
| #9 | Missing DB indexes on user tables | 🔴 Open |
| #10 | Dead file deletion (9 files) | 🔴 Open |
| #11 | `MaintenancePipeline.__new__` skips `__init__` | 🔴 Open |
| #12 | `EvolutionEngine.learn_from_success/failure` not wired | 🔴 Open |
| #13 | Ephemeral ChromaDB/Qdrant (learning lost on restart) | 🔴 Open |

### 🚧 Execution Plan (Priority Order)

#### Batch 1 — Critical Crashes (Fix #1, #2, #3, #4, #11)

These cause runtime errors or silent no-ops.

```bash
# Fix #1: ArtifactType
# File: backend/api/routes/artifacts.py:37
# Change: class ArtifactType(str, str): → class ArtifactType(str):

# Fix #2: stream_chat_sse
# File: backend/api/routes/stream_chat_sse.py:50-76
# Mirror: chat.py:221-232 async for chunk pattern

# Fix #3: 7 missing awaits
# Files: integrations/browser_use_adapter.py:116
#        tools/knowledge/pdf_to_sdk.py:92
#        tools/meta_architect.py:110,157
#        tools/media/presentation_generator.py:18
#        tools/media/music_generator.py:18
#        tools/media/threed_model_generator.py:18

# Fix #4: 9 broken imports (try/except with log)
# Key: scripts/sync_knowledge.py → from core.logging_config import logger

# Fix #11: MaintenancePipeline
# File: backend/core/maintenance_pipeline.py:213
# Change: __new__ → use app.state.evo_agent
```

- **টেস্ট:** `python -c "from api.routes.artifacts import ArtifactType; print('OK')"`

#### Batch 2 — Performance & Memory (Fix #5, #6, #7, #8)

```bash
# Fix #5: time.sleep → asyncio.sleep in supabase_client.py
# Fix #6: WebSocket MAX_CONNECTIONS=50, heartbeat 30s
# Fix #7: _pref_locks → LRUCache(maxsize=1000)
# Fix #8: github.py → use services.global_http_client
```

- **টেস্ট:** `pytest tests/api/routes/test_websocket*.py`

#### Batch 3 — Data Integrity (Fix #9, #13)

```bash
# Fix #9: DB index migration
# Migration: backend/alembic_migrations/versions/XXX_add_user_indexes.sql

# Fix #13: ChromaDB Persistent
# File: backend/adaptive_engine/experience_db.py
# Change: EphemeralClient() → PersistentClient(path=EXPERIENCE_DB_PATH)
```

#### Batch 4 — Self-Evolution (Fix #12) + Cleanup (Fix #10)

```bash
# Fix #12: Wire evolution learning
# File: backend/core/llm/llm_gateway.py → add learn_from_success after response

# Fix #10: git rm dead files
# backend/scripts/adhoc_archive/ (5 files)
# backend/services/morphic_refactor.py (0 bytes)
# backend/core/middleware/circuit_breaker_middleware.py (1 byte)
```

---

## 2. `FREE_TIER_STORAGE_PLAN.md`

**Goal:** Storage $0 রাখতে Supabase Storage + Cloudflare R2 (free tier) ব্যবহার।

### 🚧 Pending Tasks

#### Step 1 — Supabase Storage Integration Verify

- **কাজ:** `backend/services/storage/` → upload, download, delete endpoints working কিনা verify
- **টেস্ট:** `pytest tests/services/storage/ -v`

#### Step 2 — Cloudflare R2 Adapter

- **কাজ:** Large file (>50MB) → automatically R2-তে route করা
- **ফাইল:** `backend/services/storage/r2_adapter.py` (new)
- **টেস্ট:** Upload 100MB → verify R2 bucket

#### Step 3 — Storage Quota Guard

- **কাজ:** Per-user storage usage track করা + free tier limit (1GB) enforce করা
- **ফাইল:** `backend/middleware/storage_guard.py` (new)

---

## 3. `SPEC_KIT_ADOPTION.md`

**Goal:** Class B/C features-এর জন্য Spec-Driven Development (SDD) workflow enforce করা।

### ✅ Already Done

- `.specify/memory/constitution.md` — SDD constitution exists

### 🚧 Pending Tasks

#### Step 1 — Spec Kit Slash Commands

- **কাজ:** `/speckit.specify`, `/speckit.plan` commands → Antigravity IDE skills-এ register করা
- **ফাইল:** `.agents/skills/speckit-specify/SKILL.md` (new)

#### Step 2 — Feature Classification Checker

- **কাজ:** নতুন feature request এলে automatic Class A/B/C classification check
- **ফাইল:** `backend/scripts/classify_feature.py` (new)

---

## Overall Implementation Priority

```
CRITICAL (Do First):
  Production_V3: Batch 1 — Fix #1, #2, #3, #4, #11

HIGH (This Week):
  Production_V3: Batch 2 — Fix #5, #6, #7, #8

MEDIUM (Next Week):
  Production_V3: Batch 3 — Fix #9, #13
  Free Tier Storage: Step 1 (verify) + Step 2 (R2 adapter)

LOW (When Available):
  Production_V3: Batch 4 — Fix #12 + #10
  Spec Kit: Slash commands
```

## Verification Gate

```bash
# Full compile check
for f in $(find backend -name '*.py' -not -path '*/tests/*'); do
  python3 -c "compile(open('$f').read(), '$f', 'exec')" 2>&1
done | grep -v "^$" | head -5  # → 0 errors

# Import check
python3 -c "from core.app import app; print(f'{len(app.routes)} routes')"

# Test suite
cd backend && poetry run pytest -n auto --timeout=120 -q --no-cov
```
