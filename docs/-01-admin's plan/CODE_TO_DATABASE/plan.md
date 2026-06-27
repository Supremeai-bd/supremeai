## Plan: CODE_TO_DATABASE Migration

TL;DR: The repo already has partial Supabase database support and an existing self-evolution scaffolding, but the `docs/-01-admin's plan/CODE_TO_DATABASE/CODE_TO_DATABASE.md` migration plan is not fully implemented. This plan documents the actual work needed to align the repo with that plan, step-by-step, in a new markdown document.

**Steps**
1. Review current repo database integration and extract exact DB-related code paths.
   - Confirm `backend/database/supabase_client.py`, `backend/memory/supabase_store.py`, `backend/core/db_repository.py`, `backend/core/config.py`, `backend/core/evolution_engine.py`, `backend/api/routes/evolution.py`, and `backend/tools/skill_recommender.py` are the main relevant files.
   - Identify where the current implementation is using local SQLite or filesystem storage versus Supabase.

2. Define the migration scope from `CODE_TO_DATABASE.md`.
   - Migrate dynamic skills / skill registry from local files to Supabase.
   - Store prompt templates and guardrails in the database.
   - Move provider configuration and routing rules into the database layer.
   - Persist execution logs and metrics into database tables.
   - Add or improve user session and API key storage through Supabase auth or database tables.

3. Create a Supabase schema and migration strategy.
   - Define required tables: `skills`, `guardrails`, `providers`, `execution_logs`, `user_sessions`, `api_keys`, and any support tables.
   - Use existing `scripts/migrate.py` or a new SQL migration script.
   - Add indexes for search and performance.
   - Ensure local SQLite fallback remains available for development.

4. Refactor backend services to use the database.
   - Add a dedicated `SkillService` / `SkillRepository` to manage `skills` table read/write.
   - Add `GuardrailService` for prompt defenses.
   - Add `ProviderConfigService` for model provider metadata and routing.
   - Refactor `EvolutionEngine` to support DB-backed task history and skill proposals, while preserving current SQLite fallback.
   - Ensure `SupabaseStore` evolution from conversation storage to database-backed fact storage is consistent with plan.

5. Update API surface and endpoints.
   - Add or update `/api/v1/skills`, `/api/v1/guardrails`, `/api/v1/providers`, `/api/v1/execute`, and `/api/evolution` routes.
   - Keep existing `backend/api/routes/evolution.py` but transition it from file-based logs to database logging.
   - Add guardrails retrieval and provider health endpoints as needed.

6. Add logging, metrics, and fallback behavior.
   - Ensure execution logs are written when tasks run.
   - Use `backend/tools/skill_recommender.py` and `backend/core/db_repository.py` as examples for Supabase access patterns.
   - Add caching strategy later, starting with DB correctness first.

7. Verify and document progress.
   - Keep progress notes in a workspace markdown document named clearly under `docs/-01-admin's plan/CODE_TO_DATABASE_PROGRESS.md` or equivalent.
   - Validate with existing tests and add new tests for DB-backed skill storage, guardrails, and evolution engine logic.

**Relevant files**
- `docs/-01-admin's plan/CODE_TO_DATABASE/CODE_TO_DATABASE.md` — source migration plan
- `backend/database/supabase_client.py` — current Supabase client wrapper
- `backend/memory/supabase_store.py` — current Supabase/SQLite store implementation
- `backend/core/evolution_engine.py` — current evolution engine using SQLite task history
- `backend/core/db_repository.py` — fallback pattern between Firebase and Supabase
- `backend/core/config.py` — environment and DB configuration definitions
- `backend/api/routes/evolution.py` — current evolution API and file-based logs
- `backend/tools/skill_recommender.py` — existing Supabase usage for skill history and task logs
- `backend/core/prompt_firewall.py` — current guardrail pattern (local + Llama Guard)

**Verification**
1. Confirm new DB tables and SQL migration script exist and can run against Supabase.
2. Confirm `SkillService` and `GuardrailService` are used by API routes.
3. Confirm `EvolutionEngine` stores task history to DB instead of only SQLite.
4. Confirm tests cover Supabase store behavior, DB repository fallback, and evolution engine write path.
5. Confirm the new progress document is created in `docs/-01-admin's plan/`.

**Decisions**
- Use Supabase PostgreSQL as the primary DB, preserving SQLite fallback for local dev.
- Prioritize the already-present Supabase client wrappers over introducing a new DB stack.
- Keep the plan aligned with repo conventions and existing `backend/core/` architecture.

**Further considerations**
1. Confirm whether `SUPABASE_DATABASE_URL_POOLER` is the preferred runtime connection string, since `backend/core/config.py` already fetches it via `secret_vault`.
2. Decide whether to keep the current file-based quarantine/skill registry approach in `backend/api/routes/evolution.py` during the first phase, or migrate it immediately to DB.
3. Determine the exact workspace file name for the requested new markdown progress document.
