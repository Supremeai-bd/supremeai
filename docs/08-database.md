# 08 — Database

## Engines & Stores

SupremeAI uses a **polyglot persistence** layout, each store with a specific job:

| Store | Technology | Used for |
|-------|-----------|----------|
| **Primary OLTP** | PostgreSQL via **Supabase** (asyncpg) | All domain tables, auth, billing, telemetry |
| **Vector search** | **pgvector** (1536-dim) | `ai_memory` semantic memory, RAG |
| **Cache / queue / rate limits** | Redis 7 / Upstash (TLS `rediss://`) | Caching, task queue, messaging, rate limiting |
| **Local vector store** | ChromaDB (`CHROMADB_PATH`) | Local-first embeddings fallback |
| **Optional vector DB** | Qdrant (`qdrant-client`) | Alternative vector backend |
| **Knowledge graph** | Neo4j (`tools/graph_service.py`) | Skill dependency graphs, MCP knowledge-graph server |
| **Doc store** | Firestore (`google-cloud-firestore`) | Backups, audits, cross-cloud replication |
| **Test / degraded mode** | SQLite via aiosqlite (in-memory) | pytest and `SUPABASE_ALLOW_DB_DEGRADATION` fallback |

## Connection Management (PgBouncer-safe)

`backend/database/session.py` builds the async engine with settings specifically required by Supabase's **transaction-pool mode (PgBouncer)**:

- Driver rewrite: `postgresql://` → `postgresql+asyncpg://`
- `NullPool`, `pool_pre_ping=True`
- `statement_cache_size=0` and **UUID-random prepared-statement names** (avoids PgBouncer's duplicate-prepared-statement errors)
- TLS via `core/db_ssl.build_supabase_ssl_context()` (`SUPABASE_DB_CA_CERT`)
- Slow-query listeners logging past `DB_SLOW_QUERY_THRESHOLD` (default 0.2 s)

`core/db.py::get_engine()` provides the pooled engine used by health checks; `database/supabase_client.py` exposes the `db` singleton (supabase-py with a psycopg2 fallback, retry decorator) and runs `bootstrap_schema()` non-fatally at startup (bounded by `DB_BOOTSTRAP_TIMEOUT` = 30 s). `database/pgbouncer_pool.py`, `multi_db_router.py` and `tenant_db.py` cover pooling strategy, multi-DB routing and tenant isolation.

## ORM Layer

SQLAlchemy 2.0 async (`create_async_engine`, `AsyncSession`, `async_sessionmaker`) with declarative base `models/base.py::Base`. Verified key tables (`__tablename__`):

**Agents & evolution:** `agent_sessions`, `agent_reflections`, `dynamic_agents`, `dynamic_capabilities`, `agent_genomes`, `agent_offspring`, `breeding_pools`, `skill_fitness`, `agent_performance_logs`, `weakest_link_reports`

**Execution & governance:** `execution_chains`, `execution_logs`, `execution_policies`, `automation_executions`, `automation_executions_attempts`, `code_proposals`, `patch_telemetry`, `integrations`, `plugin_manifests`, `user_plugin_installations`

**Memory:** `ai_memory` (pgvector 1536-dim — populated via `core/embeddings.embed_for_pgvector()`)

**Platform ops:** `performance_metrics`, `performance_alerts`, `system_config`, `system_alerts`, `system_dependencies`, `api_endpoints`, `system_incidents`, `selector_healing_events`, `handoff_events`

**Users & billing:** `user_wallets`, `transaction_ledger`, `target_platform_credentials`, `translation_cache`, `voice_sessions`, `churn_predictions`, `retention_actions`

## Migrations

Two complementary systems:

1. **Alembic** (`alembic.ini`, `alembic_migrations/`) — the Python-managed path; `env.py` targets `models.base.Base.metadata`. Versions include `001_initial_schema.sql`, `add_idempotency`, `add_ci_reports_table`, `add_ecosystem_tables`, `create_system_config`, `add_sentinel_morphic_schema`, `add_patch_telemetry_table`, `tier_s_features.py`, plus merge heads.
2. **Raw SQL migrations** (`backend/database/migrations/01…18`) — infrastructure-level SQL: initial setup, phase-2 tables, user preferences, schema upgrade, referral system, tenant config, SSO, offline sync, indexes, **RLS enablement + RLS policy fixes**, match-experiences RPC.

Operational commands and CI checks:

```bash
# Apply migrations (backend/)
poetry run alembic upgrade head

# Repo-root helpers
python scripts/db/auto_migrate.py        # guided migration run
python scripts/db/run_migration.py       # one-off migrations
python scripts/db/auto_seed.py           # seed data
python scripts/db/ingest_knowledge.py    # knowledge ingestion into ai_memory
python scripts/db/load_coldstart_knowledge.py   # coldstart knowledge seed JSONs
python scripts/db/validate_retrieval.py  # verify retrieval quality

# CI guards
python scripts/ci/check_database_schema.py      # live prod DB vs schema contract
#   contract: backend/database/contracts/schema_contract.yaml
python scripts/ci/check_migration_safety.py     # pre-deploy migration risk gate
python scripts/advanced_analysis/db_model_drift_checker.py
python scripts/advanced_analysis/migration_safety_diff.py
```

## Row-Level Security

Raw migrations enable **Supabase RLS** and repair policies — access control is enforced at the database layer in addition to API middleware. The `match-experiences` RPC provides server-side vector similarity search for the experiences/memory domain.

## Data Lifecycle on Free Tier

Unbounded growth is the main free-tier risk (Supabase storage caps). Verified mitigations:

- **`db-retention.yml`** (GitHub Actions, daily `30 3 * * *`): calls Supabase Management API RPCs `public.prune_evolution_logs(N)` and `public.prune_learning_data(N)` — default **30-day retention**. The workflow header notes `evolution_logs` once reached ~258 K rows (~87 % of DB).
- **`scripts/monitoring/capacity_planner.py`** tracks usage and recommends sleep/wake and prune actions (Telegram alerts).
- **`scripts/backup/`** (`superai_backup_manager.py`, `auto_firestore_backup.py`, `auto_cross_cloud_replicate.py`, `backup_telegram.py`) provide layered backup/replication so prunes are safe.

## Frontend Local-First Mirror

`frontend/src/store/localFirstDb.ts` maintains a Dexie/IndexedDB mirror — tables `chat_messages`, `conversations`, `user_preferences`, `sync_queue` — with Supabase background sync. The UI remains responsive during backend cold starts and queues mutations for later sync; the Supabase JS client (`lib/supabase.client.ts`) uses `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` (RLS applies to anon access).

## Conventions for New Models

1. Declare the model in `backend/models/` on the shared `Base`; add `__tablename__` explicitly.
2. Create the Alembic revision (`alembic revision --autogenerate -m "..."`) **and** mirror any server-level objects (indexes, RLS, RPCs) as raw SQL in `database/migrations/` with the next sequence number.
3. Update `backend/database/contracts/schema_contract.yaml` — CI's post-deploy `db-schema-check` compares the live database against it and fails on drift.
4. Vector columns must use the pgvector type with dim=1536 to match `core/embeddings.embed_for_pgvector()`.
5. Never assume Redis or Postgres presence in unit tests — the root `conftest.py` swaps in SQLite/mocked Redis automatically.
