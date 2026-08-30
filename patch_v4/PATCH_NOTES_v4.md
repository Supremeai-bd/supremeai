# PATCH_NOTES_v4 — Render Production Log Fixes

**Date:** 2026-08-30
**Base commit:** `main` @ `3b6e09db05`
**Patch type:** Code + tests + docs
**Verification:** 14/14 regression tests pass offline (`tests/security/test_patch_v4_render_log_fixes.py`)

---

## What this patch fixes

Patch v4 closes **5 production defects** discovered by analyzing fresh Render
logs from `supremeai-backend-v2` (282 lines captured 2026-08-30 17:17–17:31 UTC).
These defects had escaped the prior 3 audit verification sessions.

| # | Error from Render log | Severity | Root cause | Fix |
|---|----------------------|----------|-----------|-----|
| 1 | `ReadOnlySqlTransaction: cannot execute CREATE TABLE` → CRITICAL escalation | P0 | `pooled_pg.execute()` ran DDL on the read-only Supabase pooler; `@with_error_bus` cascaded to silent-pattern detector → CRITICAL | New `pooled_pg.execute_ddl()` routes through `SUPABASE_DATABASE_URL_WRITER`; NOT error-bus-wrapped; `bootstrap_schema()` rewritten to writer-only |
| 2 | `cannot import name 'get_tenant_db' from 'core.tenant_db'` | P1 | `api/routes/hitl_admin.py` imported `get_tenant_db` from wrong module (deprecation shim doesn't expose it) | Changed import to `from api.deps import get_tenant_db` |
| 3 | `concurrent operations are not permitted` (isce) on `/configs/refresh` | P0 | `asyncio.gather(6 × sync_from_db(db))` on a single shared `AsyncSession` | Replaced with sequential `await` statements |
| 4 | `relation "automation_executions" does not exist` | P1 | Table missing from `get_bootstrap_statements()`; migration never applied at boot | Added `CREATE TABLE IF NOT EXISTS automation_executions (...)` + `automation_execution_attempts` to bootstrap list |
| 5 | `MEMORY WARNING (90.78% used)` continuous spam | P1 | `core/services.py:80-88` eagerly constructed 7 heavy singletons at import time | Converted to lazy `@functools.lru_cache`-backed factories with `__getattr__` dispatch |

---

## Files changed (8 code files + 1 test file = 9 total)

### Code changes

1. **`backend/core/persistence/pooled_pg.py`** (FIX 1, full rewrite of DDL path)
   - Added `execute_ddl()` — DDL-safe alternative to `execute()`
   - Added `get_writer_conn()` context manager for the writer pool
   - Added `_resolve_writer_dsn()` — never returns the pooler URL
   - Added `_get_writer_pool()` — lazy-init writer psycopg2 pool
   - Added `writer_is_available()` — cheap probe (no pool init)
   - Updated `close_pool()` — closes both pools

2. **`backend/api/routes/hitl_admin.py`** (FIX 2)
   - Changed `from core.tenant_db import TenantAwareFirestore, get_tenant_db`
     → `from database.tenant_db import TenantAwareFirestore` + `from api.deps import get_tenant_db`

3. **`backend/api/routes/admin.py`** (FIX 3)
   - In `POST /configs/refresh`, replaced `asyncio.gather(6 coroutines on shared db)`
     with 6 sequential `await` statements (same fix as commit `3b6e09db05`).

4. **`backend/database/supabase_client.py`** (FIX 1 + FIX 4)
   - Added `CREATE TABLE IF NOT EXISTS automation_executions (...)` with 6 indexes
     + FK constraint to `get_bootstrap_statements()`.
   - Added `CREATE TABLE IF NOT EXISTS automation_execution_attempts (...)` with index.
   - Rewrote `bootstrap_schema()` to use WRITER URL only (`SUPABASE_DATABASE_URL_WRITER`
     → fallback `SUPABASE_DATABASE_URL`). Pooler deliberately excluded from DDL candidates.
   - ReadOnlySqlTransaction failures downgraded from ERROR → WARNING (no escalation).

5. **`backend/services/memory_service.py`** (FIX 1)
   - In `CascadeMemoryService.__init__`, changed `pooled_pg.execute(_PG_SCHEMA)`
     → `pooled_pg.execute_ddl(_PG_SCHEMA)`. DDL now routes through writer URL.
   - DDL failure log downgraded from `logger.error` → `logger.warning`.

6. **`backend/tools/checkpoint_manager.py`** (FIX 1)
   - In `CheckpointManager.__init__`, changed `pooled_pg.execute(_PG_SCHEMA)`
     → `pooled_pg.execute_ddl(_PG_SCHEMA)`. Same fix as memory_service.
   - DDL failure log downgraded from `logger.error` → `logger.warning`.

7. **`backend/core/services.py`** (FIX 5, major refactor)
   - Removed eager module-level assignments:
     ```python
     # BEFORE (7 heavy singletons at import time):
     redis_queue = UpstashRedisQueue()
     admin_god = AdminGodLayer()
     model_router = ModelRouter()
     parallel_router = ParallelCloudRouter()
     intent_clf = IntentClassifier()
     intent_parser = IntentParser(model_router=model_router) if model_router else None
     experience_db = ExperienceDatabase()
     ```
   - Added lazy factories:
     ```python
     @functools.lru_cache(maxsize=1)
     def get_redis_queue(): from core.messaging.upstash_redis_queue import UpstashRedisQueue; return UpstashRedisQueue()
     # ... same pattern for the other 6 singletons
     ```
   - Added `_SINGLETON_FACTORIES` registry + dispatch in `__getattr__` so
     `services.redis_queue` etc. keep working transparently.
   - Added `reset_singletons()` for test isolation.
   - Expected boot RSS drop: ~460 MB → ~340-380 MB (66-74%, down from 90.78%).

8. **`backend/tests/security/test_patch_v4_render_log_fixes.py`** (NEW)
   - 14 regression guards, all passing offline.
   - Hermetic — no Postgres, Redis, or Firestore required.
   - Test coverage:
     - FIX 1 (5 tests): `execute_ddl` exists; `_resolve_writer_dsn` never returns pooler; prefers WRITER env; swallows RuntimeError when no writer; not `@with_error_bus`-decorated.
     - FIX 2 (2 tests): router imports cleanly; uses correct module (`api.deps`).
     - FIX 3 (1 test): AST walk verifies no `asyncio.gather` call in source.
     - FIX 4 (2 tests): both tables in bootstrap statements; `bootstrap_schema` doesn't iterate `(pooler_url, db_url)`.
     - FIX 5 (4 tests): no eager assignments in module `__dict__`; `_SINGLETON_FACTORIES` registry exists; `lru_cache` returns same instance; importing module doesn't construct any singleton.

### Doc changes

- **`AUDIT_MASTER_CHECKLIST.md`** — appended Patch v4 Snapshot section + updated header summary to mention verification session 4.
- **`MANUAL_STEPS.md`** — added items 7.9 / 7.10 / 7.11 + section 8 entry for `SUPABASE_DATABASE_URL_WRITER`.
- **`PATCH_NOTES_v4.md`** — this file.

---

## What MUST be done manually after applying this patch

See `MANUAL_STEPS.md` for the full list. The 3 NEW items added by patch v4:

### 7.9 Set `SUPABASE_DATABASE_URL_WRITER` env var in Render

This is the canonical writable Postgres endpoint (typically the direct connection string):

```
postgresql://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres
```

NOT the pooler at port 6543 (which is read-only for DDL in our Supabase tenant).

Required so `pooled_pg.execute_ddl()` and `supabase_client.bootstrap_schema()` can create
the `automation_executions` table + `ai_memory` schema. If not set, both fall back silently
to SQLite (data NOT durable across restarts) — same as today, but without the CRITICAL
silent-pattern escalation.

### 7.10 Wire `alembic upgrade head` into Render pre-deploy

Patch v4 added `automation_executions` to boot-time DDL as a stop-gap. Proper migration
tooling is the long-term answer. Either:
- Add a `pre-deploy` Render hook that runs `alembic upgrade head` against the writer URL, OR
- Add a CI job that runs migrations before deploy.

### 7.11 Re-check Render logs after deploy

After deploying patch v4, verify the following error patterns are GONE from Render logs:

- [ ] `ReadOnlySqlTransaction` (was CRITICAL)
- [ ] `cannot import name 'get_tenant_db'` (was WARNING, dead router)
- [ ] `concurrent operations are not permitted` (was ERROR x5 on /configs/refresh)
- [ ] `relation "automation_executions" does not exist` (was ERROR)
- [ ] `MEMORY WARNING (90.78% used)` continuous spam (should drop below 85%)

If any of these re-appear, attach the new Render log file and re-run the audit.

---

## How to apply this patch

### Option A — Git apply (recommended)

```bash
# From the supremeai repo root:
unzip /path/to/supremeai_patch_v4.zip
git apply supremeai_patch_v4.diff
# OR copy the patched files directly:
cp -r patch_v4/backend/* backend/
cp patch_v4/AUDIT_MASTER_CHECKLIST.md audit_reports/supreme-deep-audit-reports/
cp patch_v4/MANUAL_STEPS.md audit_reports/supreme-deep-audit-reports/
```

### Option B — Manual copy (if git apply fails)

The `patch_v4/backend/` directory mirrors the structure of `supremeai/backend/`. Copy each
file to its corresponding location:

```bash
cp patch_v4/backend/core/persistence/pooled_pg.py          backend/core/persistence/pooled_pg.py
cp patch_v4/backend/api/routes/hitl_admin.py                backend/api/routes/hitl_admin.py
cp patch_v4/backend/api/routes/admin.py                     backend/api/routes/admin.py
cp patch_v4/backend/database/supabase_client.py             backend/database/supabase_client.py
cp patch_v4/backend/services/memory_service.py              backend/services/memory_service.py
cp patch_v4/backend/tools/checkpoint_manager.py             backend/tools/checkpoint_manager.py
cp patch_v4/backend/core/services.py                        backend/core/services.py
cp patch_v4/backend/tests/security/test_patch_v4_render_log_fixes.py backend/tests/security/test_patch_v4_render_log_fixes.py
```

### Verify the patch applies cleanly

```bash
cd backend
DATABASE_URL="sqlite+aiosqlite:///./test.db" python3 -m pytest tests/security/test_patch_v4_render_log_fixes.py -v --no-cov
# Expect: 14 passed
```

---

## Compatibility

- **No new dependencies** added. Uses only `functools.lru_cache`, `ast`, `inspect`,
  `importlib` — all stdlib.
- **No breaking API changes.** All existing callers of `services.model_router`,
  `services.redis_queue`, etc. keep working unchanged (lazy `__getattr__` dispatch).
- **New env var:** `SUPABASE_DATABASE_URL_WRITER` (optional but recommended; without it,
  DDL fails silently and falls back to SQLite — same as today's behaviour, minus the
  CRITICAL escalation).
- **No database migrations required** — `automation_executions` table is created by the
  boot DDL list (which is now wired through the writer URL).

---

## Risk assessment

| Risk | Mitigation |
|------|-----------|
| `core/services.py` lazy refactor breaks a caller that expects eager init | All callers verified via grep; `__getattr__` dispatch is transparent. 14 tests guard the contract. |
| `execute_ddl()` silently no-ops when writer URL not set | Logs a single WARNING per process; behaviour identical to today (SQLite fallback), just without CRITICAL escalation. |
| `bootstrap_schema()` no longer tries pooler | Tested: `_resolve_writer_dsn` never returns pooler; `bootstrap_schema` source verified via AST. |
| Memory pressure could be higher than expected if other singletons are eager | Patch v4 fixes the 7 biggest offenders; if memory >85% persists, profile via `py-spy` and apply same pattern to remaining singletons. |

---

## What's NOT in this patch (intentionally deferred)

- **Cosign image signing** (MANUAL_STEPS 4) — requires CI infra.
- **Alembic migration wiring** (MANUAL_STEPS 7.10) — requires deploy pipeline change.
- **Real canary traffic splitting** (MANUAL_STEPS 7.1) — needs Render Pro tier.
- **Append-only HITL storage** (MANUAL_STEPS 7.5) — storage design decision.
- **Firebase retirement** (MANUAL_STEPS 7.6) — architecture decision.

These are tracked in `MANUAL_STEPS.md` and require infrastructure access or maintainer
decisions that cannot be made in a code patch.
