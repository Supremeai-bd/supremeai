# AI Memory (Phase C) — Schema Audit & Canonical Supabase SQL Design

- **Task:** 7-b (production-readiness, branch `final-test/ai-memory-audit`, base `main@7bb4a98a`)
- **Principle:** audit-first — verify actual code usage → find duplicate/broken capability → reconcile → small measurable milestone → tests.
- **CHECKPOINT.md item closed by this work:** "Supabase `ai_memory` schema execution and privacy/retention sign-off" (CHECKPOINT.md:31, echoed at :43 "Supabase `ai_memory` table setup pending (Phase C)").
- **Canonical SQL:** `backend/database/supabase/ai_memory_phase_c.sql` (standalone, idempotent — the Alembic `versions/` directory is owned by another workstream this cycle and was **not** touched).
- **Contract tests:** `backend/tests/models/test_ai_memory_schema_contract.py` (hermetic — parses the SQL and cross-checks the SQLAlchemy model; no DB, no network).

---

## 1. Current-state inventory

### 1.1 The SQLAlchemy model is DEAD CODE and CRASHES ON IMPORT

`backend/models/ai_memory.py` (`AIMemory`, `__tablename__ = "ai_memory"` at :43) is referenced by **no other module**: there is no `from models.ai_memory import …` anywhere in `backend/` (verified by `rg "from models.ai_memory|models\.ai_memory|AIMemory"` — only self-references inside the file), and `backend/models/__init__.py:1-33` does **not** export it. It is therefore never registered on the declarative `Base` metadata and never reaches `create_all`/migrations.

Worse, it **cannot even be imported**:

| Defect | Evidence | Effect |
|---|---|---|
| `embedding: Mapped[list[float]] = mapped_column("vector(1536)", nullable=True)` (models/ai_memory.py:68-74) | A positional `str` to `mapped_column()` is the **column name**, not a type. SQLAlchemy therefore tries to resolve a type for `list[float]` and raises `MappedAnnotationError: Could not locate SQLAlchemy Core type … for the 'vector(1536)' attribute` | `import models.ai_memory` **crashes** (reproduced on SQLAlchemy 2.0.52) |
| `Index("ix_ai_memory_embedding_hnsw", embedding, postgresql_ops={"embedding": …})` (:106-112) + `cls.embedding.cosine_distance(...)` (:154) | `cosine_distance` is a `pgvector.sqlalchemy.Vector` method; the model never uses the pgvector type (and `pgvector` is not a declared dependency in `backend/pyproject.toml`) | Would `AttributeError` at runtime even if the import worked |
| `ForeignKey("users.id", ondelete="CASCADE")` (:55) and `relationship("User", back_populates="ai_memories")` (:98) | There is **no `users` ORM model** (`rg '__tablename__ = .users.'` matches only a test fixture), so the FK target and relationship mirror do not exist | Mapper configuration would fail if the module were ever imported at boot |
| Docstring claims `vector (1536 dims for OpenAI, 768 for local models)` (:9) and `content_type` column (:62-65) | Neither matches the live DB (see §2, §1.3) | Stale documentation |

The dead model's claimed shape ("Shape A": `id, user_id UUID FK, content, content_type, embedding, metadata, created_at, updated_at`) was used by **nobody**. **Fixed in this task** (see §10) so that the ORM, the Alembic migration, and the canonical SQL describe one schema.

### 1.2 The REAL table: three competing definitions, one canonical

| Source | Shape | Status |
|---|---|---|
| `backend/database/migrations/001_pgvector_match_fn.sql` | bootstraps `embedding TEXT` → converts to unconstrained `vector` | legacy bootstrap companion |
| `services/memory_service.py:44-56` (`_PG_SCHEMA`, runtime DDL via `pooled_pg.execute_ddl` at :92) | `id UUID, user_id TEXT, session_id TEXT, agent_type TEXT, task_type TEXT, summary TEXT, embedding TEXT, metadata JSONB, created_at TIMESTAMPTZ` | legacy runtime bootstrap (still runs at service init if table absent) |
| `docs/api-database/migrations/ai_memory_migration.sql:11-20` (manual Phase C SQL) | `id UUID, session_id, agent_type, task_type, summary, embedding VECTOR(384), metadata, created_at` | historical manual runner |
| **`backend/alembic_migrations/versions/2026_09_13_100000_add_ai_memory_table.py:26-55`** | `id UUID DEFAULT gen_random_uuid(), user_id String(255) NULL, session_id String(255) NOT NULL, agent_type 'main', task_type 'general', content TEXT NULL, summary TEXT NOT NULL, metadata JSONB, created_at/updated_at timestamptz, embedding vector(384)` | **CANONICAL** (merged on main) |

Live writers (all hit table `ai_memory`):

| Consumer | Columns/keys written | Evidence |
|---|---|---|
| `CascadeMemoryService.store_memory` (raw SQL) | `user_id, session_id, agent_type, task_type, summary, embedding, metadata` | services/memory_service.py:322-336 |
| `save_memory` (Supabase REST) | `user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at` | services/memory_service.py:759-779 |
| `FreeTierOptimizedVectorStore.upsert_batch` (AutoRAG store) | `id ("user:session:digest" TEXT!), embedding, metadata(=whole payload), created_at` | core/ai_memory/vector_store.py:58-67; ids built in core/memory/auto_rag_injector.py:171-173 |
| `SupabaseVectorBackend.upsert` (experience DB) | `id (uuid5), agent_id, memory_type, content, embedding, metadata.collection, importance_score` | adaptive_engine/supabase_vector_backend.py:92-109 |
| `global_memory` routes | select/update/delete by `id`/`user_id`, sets `summary` | api/routes/global_memory.py:207-216, 245-258, 274, 381-383 |
| `match_ai_memories` RPC caller | reads `id, user_id, session_id, agent_type, task_type, summary, metadata, created_at, similarity` | services/memory_service.py:173-180 |

Live readers: `retrieve_memories` (services/memory_service.py:386-401, 521), `query_context` → `match_ai_memories` RPC (services/memory_service.py:512-518), AutoRAG recall via `match_memories` RPC (core/memory/auto_rag_injector.py:112-117 → vector_store.py:101), experience search via `match_experiences` RPC (supabase_vector_backend.py:129-135), `session_stream.py:94`, `browser_routes.py:690`, `stream_chat_sse.py:200,231`, `cognitive_pipeline_dispatcher.py:230`, `scripts/store_ci_roadmap_to_memory.py:108`, `scripts/migrate_embeddings.py:36`.

### 1.3 The RPC zoo (duplicate capability / naming drift)

| RPC | Defined in | Called by | Match? |
|---|---|---|---|
| `match_ai_memory` (3 args) | docs/api-database/migrations/ai_memory_migration.sql:34 | — | historical |
| `match_ai_memory` (4 args, `filter_user_id`) | alembic `2026_09_13_100000`:77-110 | — | — |
| `match_ai_memory` called with **`p_user_id`** | — | services/memory_service.py:825-833 | ❌ PostgREST resolves RPCs by **named** parameters → PGRST202 "not found" → silently falls back to Python cosine (memory_service.py:840-844) |
| `match_ai_memories` (5 args) | database/migrations/001_pgvector_match_fn.sql:71-108 | services/memory_service.py:177 | ✅ |
| `match_memories` | **defined NOWHERE** | core/ai_memory/vector_store.py:101 (AutoRAG), memory/long_term_memory.py:67-74 | ❌ recall always errors → AutoRAG silently degrades (auto_rag_injector.py:139-141) |
| `match_experiences` (`VECTOR(1536)` arg) | database/migrations/16_add_match_experiences_rpc.sql:22-48 | supabase_vector_backend.py:130-135 | ❌ callers pass **384-dim** vectors (embed_for_pgvector) → dimension mismatch at execution |

### 1.4 Identity model

`user_id` everywhere is an **application-level TEXT identifier** (JWT `sub` string), never a FK:

- `unified_memory_api.py:47` binds `user_id=user.get("sub")` from the authenticated JWT; AUD-5.1 header (:7-9) documents that this router previously leaked cross-user rows.
- Alembic canonical: `user_id String(255), nullable=True, no FK` (versions/2026_09_13_100000:34).
- Runtime DDL: `user_id TEXT DEFAULT NULL` (memory_service.py:47).
- AutoRAG stores `user_id or "anonymous"` (auto_rag_injector.py:169).
- `tenant_id` appears **nowhere** in the ai_memory path: zero hits in `backend/models/` for ai_memory (only crawler.py:26,74, automation_execution.py:46, pending_tasks.py:72 define tenant columns for other tables), zero hits in `services/memory_service.py`, `core/ai_memory/vector_store.py`, `api/routes/global_memory.py`. `AutoRAGInjector.enrich_system_prompt` **accepts** a `tenant_id` parameter but never uses it (auto_rag_injector.py:91). `tenant_id` exists only in unrelated subsystems (worker_service.py:60, core/neon_repository.py:67, core/resilience/auto_remediation.py:45, workers/synaptic_dream.py:39…).

### 1.5 Retention — capability exists, nothing drives it

- `FreeTierOptimizedVectorStore.delete_old_memories(days_old=30)` exists (core/ai_memory/vector_store.py:129-151) but has **zero callers** (`rg "delete_old_memories"` → definition only).
- The manual Phase C SQL left a comment: "Supabase Cron Job হিসেবে সেট করুন: DELETE FROM ai_memory WHERE created_at < NOW() - INTERVAL '90 days'" (docs/api-database/migrations/ai_memory_migration.sql:77-79) — never implemented.
- Existing cleanup facilities in-repo: `MaintenancePipeline.cleanup_automation_executions` (core/maintenance_pipeline.py:162-204; to_regclass guard + age-based DELETE + session commit) and the `Orchestrator._tasks` periodic asyncio list (core/orchestration/periodic_task_scheduler.py:50-53,107) — both are the natural app-side hooks; neither touches ai_memory today.

---

## 2. Embedding dimensions decision — **canonical 384, enforced by `vector(384)` typmod**

**Decision: `ai_memory.embedding` is `vector(384)`.** Mixed dimensions are forbidden by the column typmod itself (pgvector rejects any other-length insert with a dimension error), which is stronger than a CHECK and needs no extra column.

Rationale (code is unanimous at the *effective* layer):

- `core/embeddings.py:20` — `_PG_DIM = 384`; module docstring :3-4: "Production Supabase `ai_memory.embedding` is `vector(384)` … guarantees that every pgvector embedding is exactly 384 dimensions."
- `embed_for_pgvector()` (core/embeddings.py:91-138) **normalizes every request to 384**: callers asking 1536 get a WARNING and 384 output (:100-103); remote fallback requests `dimensions=_REMOTE_DIM` (=384, :22,122); final fallback `hash_vectorize(text, size=_PG_DIM)` (:134). Local model is all-MiniLM-L6-v2 → 384 (:18-19).
- Canonical Alembic migration adds `embedding vector(384)` (versions/2026_09_13_100000:55) and its `match_ai_memory` RPC is typed `VECTOR(384)` (:78).
- The historical manual SQL is `VECTOR(384)` (docs/api-database/migrations/ai_memory_migration.sql:17) and `scripts/migrate_embeddings.py:19,53` re-encodes to "the canonical 384-dimensional pgvector contract".

Stale 1536 references found (documented, not load-bearing): the dead model docstring/comments (models/ai_memory.py:9,67,71), unused class constant `EMBEDDING_DIM = 1536` (core/ai_memory/vector_store.py:28 — never read), a stale comment "already has VECTOR(1536) column" (supabase_vector_backend.py:90, contradicted by the migration on the same table), cosmetic bot strings (tools/social/telegram_bot/conversations.py:238), and legacy callers that *pass* `pg_dim=1536` but are silently normalized to 384 (memory/supabase_store.py:214 + its dead padding branch :223-226, skills/core_knowledge_qa.py:35, services/memory_service.py:697).

**Residual risk (documented):** `memory_service.get_embedding`'s exception fallback can emit a **1536-dim** hash vector (services/memory_service.py:702) — such a row would be rejected by `vector(384)` (fail-closed, no corruption). Follow-up: change `hash_vectorize(text, size=1536)` → `size=_PG_DIM`. Also `match_experiences` is typed `VECTOR(1536)` (migration 16:23) and must be re-typed to 384 — the canonical SQL includes a guarded re-creation (§Part 6).

**If a larger remote model is ever adopted** (e.g. true 1536-d `text-embedding-3-small` at full width via `settings.embedding_model`, core/config_fields.py:212-214), the migration path is: offload rows → `ALTER TABLE ai_memory ALTER COLUMN embedding TYPE vector(1536)` → re-encode via `scripts/migrate_embeddings.py` (parameterized) → recreate ANN indexes/RPCs. Not done now: every live writer/read path is 384.

---

## 3. Identity model decision — **`user_id TEXT` (Supabase `auth.uid()` as text), no `tenant_id`**

**Decision: the schema keys ownership on `user_id TEXT NULL`** exactly as the canonical migration and every live writer already do; **no FK** to a users table (none exists in the ORM, §1.1); `tenant_id` is **not** introduced — it does not exist anywhere in the ai_memory path (§1.4). Adding it now would be speculative schema; it is documented as a future extension (add `tenant_id TEXT NULL` + composite `(tenant_id, user_id)` index + policy change) if multi-tenancy lands.

Consequences for RLS: policies compare `auth.uid()::text = user_id`. Rows with `user_id = 'anonymous'` (auto_rag_injector.py:169) never satisfy `auth.uid()::text = user_id` and are therefore invisible to end users — only `service_role` (the backend, which uses `supabase_service_role_key`, auto_rag_injector.py:59-63) can read/write them. This is the desired fail-safe default.

---

## 4. RLS policy set (Supabase)

`ai_memory` holds per-user conversational memory — direct PostgREST access must be owner-scoped:

1. `ALTER TABLE ai_memory ENABLE ROW LEVEL SECURITY;` — **deny-by-default**: with RLS enabled and no policy, `anon`/`authenticated` see nothing.
2. `REVOKE ALL ON ai_memory FROM anon;` — explicit deny for the anonymous role (defense in depth beyond empty-result semantics).
3. Owner policies on `authenticated` (all scoped to `auth.uid()::text = user_id`):
   - `ai_memory_select_own` — `FOR SELECT USING (auth.uid()::text = user_id)`
   - `ai_memory_insert_own` — `FOR INSERT WITH CHECK (auth.uid()::text = user_id)`
   - `ai_memory_update_own` — `FOR UPDATE USING (...) WITH CHECK (...)`
   - `ai_memory_delete_own` — `FOR DELETE USING (...)`
4. `GRANT SELECT, INSERT, UPDATE, DELETE ON ai_memory TO authenticated; GRANT ALL … TO service_role;`
5. **service_role note:** Supabase's `service_role` carries `BYPASSRLS` — the FastAPI backend (the only writer in practice) is unaffected by the policies; they exist to protect direct client-side Supabase access. This mirrors the historical manual SQL's "Service role full access" policy (docs/api-database/migrations/ai_memory_migration.sql:70-75) but adds the user-scoped layer it lacked.

---

## 5. Vector index decision — **HNSW (m=16, ef_construction=64) baseline; IVFFlat alternative documented**

- HNSW is created **only if no ANN index already exists** on `ai_memory.embedding` (the Alembic migration on main already creates `ix_ai_memory_embedding_ivfflat` with lists=100, versions/2026_09_13_100000:62-73; migration 001 creates `ai_memory_embedding_ivfflat`; the manual SQL creates `ai_memory_embedding_idx`). Two concurrent ANN indexes would double write amplification for zero recall benefit — the DO-block checks all three historical names and skips creation when one exists.
- Chosen opsclass: `vector_cosine_ops` (all readers use `<=>` cosine distance: models/ai_memory.py:154, alembic RPC :103/107, 001 RPC :100/106, 16 RPC :41/46).
- HNSW requires pgvector ≥ 0.5.0 (Supabase ships ≥ 0.5; `CREATE EXTENSION vector` guards availability). If HNSW is unavailable (old self-hosted pgvector), the commented IVFFlat alternative applies:
  `CREATE INDEX … USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);`
- When to prefer which: **HNSW** — better recall/QPS, no training step, robust to incremental upserts (this table is upsert-heavy: vector_store.py:67, supabase_vector_backend.py:109); slightly more memory + slower build. **IVFFlat** — smaller footprint, faster build, but requires `ANALYZE` + reindex as the table grows (lists=100 tuned for ~10⁴-10⁶ rows) and degrades if rows were inserted before index build. For a free-tier 512MB deployment with steady upserts, HNSW is the safer default.

---

## 6. Retention policy — **default 180 days, SQL function + pg_cron example + in-app hook point**

- **Default: 180 days** (`AI_MEMORY_RETENTION_DAYS`), configurable. Rationale: the only in-repo precedent for this data class is 30 days (`delete_old_memories`, vector_store.py:129) and 30/90 days in comments (maintenance_pipeline.py:165, ai_memory_migration.sql:79); 180 days is a conservative privacy default for conversational memory that survives the 30-day free-tier instinct while bounding growth. Admin can lower it via the function argument — per-deployment decision recorded in the sign-off checklist (§7).
- **SQL:** `fn_ai_memory_retention_cleanup(p_days int DEFAULT NULL → 180)` — SECURITY DEFINER, pinned `search_path = public, pg_temp`, age-based DELETE on `created_at`, returns deleted row count, EXECUTE revoked from `PUBLIC`/`anon`/`authenticated`, granted to `service_role`.
- **Scheduler hooks (repo reality):**
  - *DB-side:* commented `pg_cron` example in the SQL (Supabase supports `cron.schedule`); unschedule statement provided as rollback.
  - *App-side:* add a task to `Orchestrator._tasks` (core/orchestration/periodic_task_scheduler.py:50-53) or mirror `MaintenancePipeline.cleanup_automation_executions` (core/maintenance_pipeline.py:162-204: `to_regclass` guard → DELETE → commit) with a `SELECT fn_ai_memory_retention_cleanup(:days)` via `pooled_pg`/session factory. Wiring this Python task is an explicit follow-up (§10) — this task delivers the SQL capability + hook point, not the Python scheduler change.
  - The dead `delete_old_memories` (vector_store.py:129) should either be deleted or routed through the same function once a caller exists.

---

## 7. Privacy / retention sign-off checklist (CHECKPOINT.md:31 item — admin ticks before prod enablement)

- [ ] **RLS verified:** `SELECT relrowsecurity FROM pg_class WHERE relname = 'ai_memory';` → `t` (see §8 verification SQL).
- [ ] **Anon denied:** unauthenticated PostgREST call to `/rest/v1/ai_memory` returns permission error (REVOKE) — not rows.
- [ ] **Owner scope proven:** with a user JWT, `GET /rest/v1/ai_memory?select=*` returns only rows whose `user_id` equals your `auth.uid()`; a foreign user's rows are absent.
- [ ] **Service path works:** backend `save_memory` → `recall_memories` round-trip succeeds via `service_role` (services/memory_service.py:740-848) — RLS must not break the API path.
- [ ] **Dimension contract:** `SELECT DISTINCT(atttypmod) FROM pg_attribute WHERE attrelid='ai_memory'::regclass AND attname='embedding';` → 384 (or run §8 check); `scripts/migrate_embeddings.py` (384-dim) is the designated re-encoder if drift is found.
- [ ] **Retention chosen & scheduled:** `AI_MEMORY_RETENTION_DAYS` value recorded (default 180), pg_cron job scheduled **or** app-side task wired; dry-run executed: `SELECT fn_ai_memory_retention_cleanup(<days>);` and row-count delta reviewed.
- [ ] **`anonymous` rows acknowledged:** rows with `user_id='anonymous'` are owner-less (invisible to all end users); confirm this is acceptable for your deployment or stop anonymous stores in the app layer.
- [ ] **Cross-user leak regression check:** `unified_memory_api` AUD-5.1 behavior re-tested (all endpoints require JWT and scope by `sub`).
- [ ] **Backups/PITR:** Supabase backup window confirmed to cover `ai_memory` before bulk deletes are first run.
- [ ] **RPC reconciliation applied:** `match_memories`, `match_ai_memory(p_user_id …)`, `match_experiences(vector(384), …)` all resolvable (§8 check) — recall paths no longer silently fall back.

---

## 8. Verification queries (post-execution smoke SQL)

```sql
-- 8.1 Table + RLS
SELECT to_regclass('public.ai_memory')            AS table_exists,      -- expect: ai_memory
       relrowsecurity                             AS rls_enabled        -- expect: t
FROM pg_class WHERE oid = 'public.ai_memory'::regclass;

-- 8.2 Column set + embedding dimension (384)
SELECT column_name, data_type,
       character_maximum_length AS vector_dim                -- 384 for the embedding column
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'ai_memory'
ORDER BY ordinal_position;

-- 8.3 Indexes present (HNSW or the pre-existing IVFFlat; btree set)
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'ai_memory';

-- 8.4 RLS policies owner-scoped
SELECT policyname, cmd, qual, with_check FROM pg_policies
WHERE schemaname = 'public' AND tablename = 'ai_memory';       -- expect 4 *_own policies w/ auth.uid()

-- 8.5 anon denied, authenticated granted
SELECT grantee, privilege_type FROM information_schema.role_table_grants
WHERE table_schema='public' AND table_name='ai_memory'
ORDER BY grantee, privilege_type;                              -- expect NO rows for 'anon'

-- 8.6 RPCs resolvable by live callers
SELECT proname, pg_get_function_arguments(oid) FROM pg_proc
WHERE pronamespace = 'public'::regnamespace
  AND proname IN ('match_ai_memory', 'match_ai_memories', 'match_memories', 'match_experiences', 'fn_ai_memory_retention_cleanup');

-- 8.7 Trigger armed
SELECT tgname FROM pg_trigger WHERE tgrelid = 'public.ai_memory'::regclass AND NOT tgisinternal;  -- expect trg_ai_memory_updated_at

-- 8.8 Retention dry-run (0 deletions when nothing expired)
SELECT fn_ai_memory_retention_cleanup(100000);  -- far-future cutoff ⇒ deletes nothing
```

---

## 9. Execution runbook

**Where to run:** Supabase Dashboard → SQL Editor (paste `backend/database/supabase/ai_memory_phase_c.sql`, Run) — or CLI:
`psql "$SUPABASE_DATABASE_URL" -f backend/database/supabase/ai_memory_phase_c.sql`
(The file is a single transaction-safe, re-runnable script; every statement is guarded `IF NOT EXISTS` / `DROP IF EXISTS`+create / DO-block.)

**Order of operations:**
1. Run the whole file once per environment (it is idempotent — re-runs are no-ops).
2. Re-run **after** `alembic upgrade head` on fresh environments if you want the HNSW/RPC/RLS layer applied by SQL even where Alembic hasn't run yet (the SQL reconciles legacy bootstrap tables too).
3. Execute §8 verification queries; tick §7 checklist.
4. Schedule retention (pg_cron example in file, or app-side task per §6).

**Rollback (destructive — keep off-path):**
```sql
-- app-side unschedule: SELECT cron.unschedule('ai-memory-retention-cleanup');
DROP FUNCTION IF EXISTS fn_ai_memory_retention_cleanup(int);
DROP TRIGGER IF EXISTS trg_ai_memory_updated_at ON ai_memory;
DROP FUNCTION IF EXISTS fn_ai_memory_touch_updated_at();
DROP POLICY  IF EXISTS ai_memory_select_own  ON ai_memory;
DROP POLICY  IF EXISTS ai_memory_insert_own  ON ai_memory;
DROP POLICY  IF EXISTS ai_memory_update_own  ON ai_memory;
DROP POLICY  IF EXISTS ai_memory_delete_own  ON ai_memory;
DROP FUNCTION IF EXISTS match_memories(vector, float, int, text);
DROP FUNCTION IF EXISTS match_ai_memory(vector, float, int, text);   -- p_user_id overload (canonical SQL only)
DROP FUNCTION IF EXISTS match_experiences(vector, int, float, text); -- 384 re-type; 1536 variant can be restored from migration 16
-- Last resort (drops all memory data): DROP TABLE IF EXISTS ai_memory;  ← equivalent to alembic downgrade of 2026_09_13_100000
```

---

## 10. Reconciliation outcome — mismatches found, and what was fixed vs documented

**Fixed in this task:**
1. `backend/models/ai_memory.py` rewritten: importable again; column set now equals the canonical SQL/Alembic contract (`id, user_id, session_id, agent_type, task_type, content, summary, embedding, metadata, agent_id, memory_type, importance_score, created_at, updated_at`); `EMBEDDING_DIMENSIONS = 384` module constant; pgvector `Vector(384)` used when the package is present (optional import — `pgvector` is still not a pyproject dependency, so the model degrades to `NullType` instead of crashing); removed the dangling `ForeignKey("users.id")`/`relationship("User")`; `content_type` dropped (never existed in the live DB — live writers don't send it; fold such flags into `metadata` JSONB).
2. `backend/database/supabase/ai_memory_phase_c.sql` — canonical, idempotent Phase C SQL (table superset accepting **all** live writers, RLS §4, HNSW §5, trigger, retention §6, RPC reconciliation §1.3).
3. `backend/tests/models/test_ai_memory_schema_contract.py` — hermetic contract lock: SQL markers, model↔SQL column-set equality, 384-dim consistency across SQL+model, RLS/auth.uid scoping, retention+pg_cron presence.

**Documented only (code follow-ups, intentionally not changed here to keep the milestone small):**
- `memory_service.get_embedding` 1536-dim fallback (services/memory_service.py:702) → use `_PG_DIM`.
- `FreeTierOptimizedVectorStore` writer gaps: TEXT ids (`user:session:digest`) vs UUID PK, discarded top-level `session_id`/`content`, dead `EMBEDDING_DIM` constant (core/ai_memory/vector_store.py:28,58-67; ids from auto_rag_injector.py:171-173) → build `uuid5` ids + top-level columns so the AutoRAG path persists.
- `SupabaseVectorBackend` stale "VECTOR(1536)" comment (supabase_vector_backend.py:90) — the columns it needs (`agent_id, memory_type, importance_score`, `summary` default) are now provided schema-side.
- `memory/supabase_store.py:214,223-226` and `skills/core_knowledge_qa.py:35` pass `pg_dim=1536` (harmlessly normalized) — tidy to `_PG_DIM`.
- Retention wiring: app-side task (§6) + delete or wire `delete_old_memories`.
- `docs/api-database/migrations/ai_memory_migration.sql` is superseded by the canonical SQL + Alembic revision (mark deprecated in a docs pass).

---

## Appendix A — Evidence index (file:line)

| Fact | Source |
|---|---|
| Model dead + crash + claims | backend/models/ai_memory.py:9,43,55,62-74,98,103-124,154; models/__init__.py:1-33 |
| Canonical table shape/dims | backend/alembic_migrations/versions/2026_09_13_100000_add_ai_memory_table.py:26-55 |
| 384 contract + normalization | backend/core/embeddings.py:3-4,18-22,91-103,134 |
| Legacy runtime DDL | backend/services/memory_service.py:44-56,92 |
| Writers | memory_service.py:322-336,759-779; core/ai_memory/vector_store.py:58-67; adaptive_engine/supabase_vector_backend.py:92-109; api/routes/global_memory.py:207-383 |
| Readers/RPC callers | memory_service.py:173-180,512-518,825-833; vector_store.py:101; memory/long_term_memory.py:67-74; supabase_vector_backend.py:129-135 |
| RPC definitions | docs/api-database/migrations/ai_memory_migration.sql:34; alembic:77-110; database/migrations/001_pgvector_match_fn.sql:71-108; database/migrations/16_add_match_experiences_rpc.sql:22-48 |
| Identity (JWT sub binding) | api/routes/unified_memory_api.py:7-9,47; auto_rag_injector.py:169; alembic:34 |
| tenant_id absent from ai_memory path | models/ (crawler.py:26,74; automation_execution.py:46; pending_tasks.py:72 — other tables only); auto_rag_injector.py:91 (accepted, unused) |
| Retention gaps + hook points | vector_store.py:129-151 (no callers); ai_memory_migration.sql:77-79; core/maintenance_pipeline.py:162-204; core/orchestration/periodic_task_scheduler.py:50-53,107 |
| Stale 1536 references | supabase_store.py:214,223-226; core_knowledge_qa.py:35; memory_service.py:692-702; vector_store.py:28; supabase_vector_backend.py:90; migrations/16:23 |
| Embedding model setting | core/config_fields.py:212-214 |
| Phase C pending item | CHECKPOINT.md:31,43 |
