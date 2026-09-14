# M0-F: ai_memory Phase C — Execution Evidence & Code Follow-ups

Roadmap item M0.6 (`docs/plans/UNIFIED_NEXT_ROADMAP_2026-09-15.md`), completing the checkpoint left open by PR #303 ("Execution on Supabase + sign-off is still pending").

## 1. Phase C SQL executed on Supabase ✅

`backend/database/supabase/ai_memory_phase_c.sql` (idempotent, whole file) was executed against the **live** Supabase Postgres.

**Live-drift discovery (this is why the file needed two reconciliation patches):**

| Attempt | Result | Root cause |
|---|---|---|
| 1 | `operator does not exist: text = uuid` | Legacy bootstrap table had `user_id uuid`; Part 3's `ADD COLUMN IF NOT EXISTS user_id TEXT` is a no-op on existing columns, so Part 6's `auth.uid()::text = user_id` exploded |
| 2 | `cannot alter type of a column used in a policy definition` | Legacy RLS policy `ai_memory_select` referenced `user_id` |
| 3 | **EXECUTED OK** | Part 3b added (see below) |

**Patch shipped in this PR — `Part 3b` (guarded, idempotent):**
1. If `user_id` is `uuid`: drop all policies on the table (Part 6 recreates the canonical four immediately after, same implicit transaction batch), then `ALTER COLUMN user_id TYPE text USING user_id::text` — a lossless cast on production rows.
2. Otherwise: no-op with a NOTICE.

## 2. Verification SQL evidence (captured after execution) ✅

| Check | Result |
|---|---|
| `user_id` data_type | **text** (converted from uuid; `uuid::text` lossless) |
| RLS policies | `ai_memory_select_own`, `ai_memory_insert_own`, `ai_memory_update_own`, `ai_memory_delete_own` (4/4 canonical) |
| RPCs | `match_ai_memory` (both arities incl. `p_user_id`), `fn_ai_memory_touch_updated_at`, `fn_ai_memory_retention_cleanup` |
| HNSW index | `ix_ai_memory_embedding_hnsw` present (`m=16, ef_construction=64`) |
| `embedding` typmod | 384 (dimension enforced) |
| Row count | **588 preserved** (no data loss during uuid→text) |

## 3. Code follow-ups (PR #303 §10 items) ✅

| # | File | Gap | Fix |
|---|---|---|---|
| 1 | `services/memory_service.py` (`get_embedding`) | Hardcoded 1536-d hash fallback → poisoned the vector(384) contract | `pg_dim=384` + `hash_vectorize(size=384)` |
| 2 | `core/ai_memory/vector_store.py` (`upsert_batch`) | Writer discarded `session_id`/`content`/`user_id`/`importance` into the `metadata` JSONB only — row-level queries, RLS scoping and retention never saw them; **and** AutoRAG's deterministic string ids (`"user:session:<sha>"`) fail `id uuid` so nothing ever persisted (the exception block swallowed it) | Promote the four fields to first-class columns (`metadata` kept for recall fallback); add `_coerce_uuid()` — invalid ids become deterministic `uuid5(NAMESPACE_URL, id)` so upsert-dedupe semantics survive |
| 3 | `core/startup/agents.py` | `fn_ai_memory_retention_cleanup` existed but nothing invoked it | New env-gated supervisor agent `ai-memory-retention` (daily cycle via `ENABLE_AI_MEMORY_RETENTION=true`, interval `AI_MEMORY_RETENTION_INTERVAL_SECONDS`, default 86400s) calling the RPC through the service-role client |

## 4. Live AutoRAG store→recall round-trip ✅

Executed with the real `FreeTierOptimizedVectorStore` against live Supabase (synthetic user, deleted afterwards):

1. `upsert_batch(payloads=[{content, user_id, session_id, importance}])` → **HTTP 201 Created** — PostgREST log shows the columns actually sent: `id, user_id, session_id, content, importance_score, embedding, metadata, created_at` (proof the promotion works; pre-fix only `id, embedding, metadata, created_at` were sent and the insert would have failed on `id uuid` anyway)
2. `similarity_search(user_id="m0f-evidence-user")` → **1 row recalled** via the `match_memories` RPC (HTTP 200) with content + user_id intact
3. Cleanup DELETE → HTTP 200 (no evidence residue left behind)

## 5. Test evidence ✅

- `pytest tests/models/test_ai_memory_schema_contract.py tests/test_auto_rag_injector.py` → **20/20 passed**
- ruff (CI-identical select/ignore set) + `ruff format --check` → clean

## Sign-off

Checkpoint M0.6 is **closed**: SQL executed, verification captured, code gaps fixed with live round-trip evidence. The retention agent is dormant until `ENABLE_AI_MEMORY_RETENTION=true` (opt-in, consistent with every other infrastructure agent).
