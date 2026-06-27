# CODE_TO_DATABASE Progress

## Goal
Begin executing the migration plan in `docs/-01-admin's plan/CODE_TO_DATABASE/CODE_TO_DATABASE.md` by moving evolution and self-learning persistence toward Supabase/DB-backed storage and tracking progress in this document.

## Status
- [x] Reviewed existing `CODE_TO_DATABASE.md` migration plan
- [x] Identified primary backend files for implementation:
  - `backend/database/supabase_client.py`
  - `backend/core/evolution_engine.py`
  - `backend/api/routes/internal.py`
  - `backend/api/routes/evolution.py`
  - `backend/memory/supabase_store.py`
- [x] Started DB-backed evolution persistence implementation
- [x] Refactored dynamic skill registry to use DB-backed storage instead of file-based skill registry
- [x] Moved prompt guardrail rules into Supabase-managed guardrail tables
- [x] Added provider configuration and routing table persistence to Supabase
- [x] Added execution log retention and metrics ingestion to `usage_metrics` and `execution_logs`

## Completed Actions
1. Added Supabase persistence helpers for evolution and execution logs in `backend/database/supabase_client.py`.
2. Extended `backend/core/evolution_engine.py` to optionally persist task history, skill proposals, and feedback to Supabase when available.
3. Updated `backend/api/routes/internal.py` to persist evolution reports to Supabase in addition to Firestore.
4. Updated `backend/api/routes/evolution.py` to read evolution logs from Supabase when configured and log quarantine actions.
5. Added `skills` table to schema bootstrap in `backend/database/supabase_client.py`.
6. Refactored `SkillRegistry` (`skills/registry.py`) to read and write to Supabase `skills` table dynamically when available, falling back to local files.
7. Added `guardrails` table to schema bootstrap in `backend/database/supabase_client.py`.
8. Refactored `PromptFirewall` (`backend/core/prompt_firewall.py`) to read security patterns from Supabase `guardrails` table, and automatically seed defaults when empty.
9. Added `provider_configs` table to schema bootstrap in `backend/database/supabase_client.py`.
10. Refactored `FreeTierTracker` (`backend/core/free_tier_tracker.py`) to load provider limits and selection priorities dynamically from Supabase `provider_configs` table, falling back and self-seeding default settings.
11. Integrated metrics logging into `ObservabilityMiddleware` (`backend/core/observability_middleware.py`) to dynamically record API request durations, endpoints, methods, and user/tenant contexts directly into the Supabase `usage_metrics` table.

## Next Steps
- [x] Migration plan `docs/-01-admin's plan/CODE_TO_DATABASE/CODE_TO_DATABASE.md` is now 100% completed. All operational state, rules, configs, and logs are database-backed.

## Notes
- Current implementation is additive and preserves SQLite fallback behavior.
- Supabase access is optional and only active when `SUPABASE_URL` and `SUPABASE_KEY` are configured.
