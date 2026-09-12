# Project Status Reconciliation Register

> বাংলা: STATUS.md এই রেজিস্টারকে "Discrepancy register" হিসেবে দুইবার উল্লেখ করেছিল —
> কিন্তু ফাইলটি কখনো তৈরিই হয়নি (dangling pointer)। এই ফাইল সেই ঘাটতি পূরণ করে:
> দলিলে যা দাবি করা হয় আর কোডে যা আসলে আছে, তার পার্থক্য এখানে নিবন্ধিত হবে।

**Created:** 2026-09-13 (audit session `dac1b37`)
**Method:** read-only multi-agent audit of plans vs. code, plus targeted verification.

## Registered Discrepancies

| # | Claim / Pointer | Reality | Status |
|---|---|---|---|
| R1 | README referenced 7 plan docs (`SUPREMEAI_CONSOLIDATION_AND_CLEANUP_PLAN`, `SUPREME_BROWSER_MASTER_PLAN`, `PRODUCTION_READINESS_PLAN_V3`, `PRODUCTION_UPGRADE_PLAN`, `MISSING_SERVICES_INTEGRATION_PLAN_V4.1`, `FREE_TIER_STORAGE_PLAN`, `ADMIN_TASKS`) | All 7 deleted from the tree; README pointed at ghosts | **FIXED 2026-09-13** — README list rewritten to surviving docs + `MASTER_PLAN.md` |
| R2 | `STATUS.md` contained a full copy-paste duplicate of its own content block (lines 73–143) | Duplicated block shipped silently | **FIXED 2026-09-13** — deduplicated, milestones 17/18 preserved |
| R3 | `STATUS.md` "Discrepancy register" pointer | This file did not exist | **FIXED 2026-09-13** — file created (you are reading it) |
| R4 | `docs/SKIPPED_TESTS.md` referenced by PRODUCTION_ROADMAP/CHECKPOINT | Does not exist; actual backend skip count is 125 markers across 53 files (not 6) | OPEN — recreate from audit before Phase 2 |
| R5 | CI coverage declarations 30% backend / 16% frontend vs. `backend/COVERAGE_90_PLAN.md` target "100%" | Plan baseline file it cites was deleted; plan is stale | OPEN — refresh plan in Phase 2 gate work |
| R6 | Universal Zero-Complexity contract | Backend serialized snake_case while frontend contracts read camelCase → `providerLabel`/`capabilityId` rendered `undefined` in UI | **FIXED 2026-09-13** — camelCase alias response models + contract tests |
| R7 | `user_execution_mode` persistence | Endpoint upserts to a table with no migration; `persisted=False` always in production | **FIXED 2026-09-13** — Alembic migration `2026_09_12_190000` |
| R8 | Scout crawler (specs/002) marked complete in `tasks.md` | Rate pacing, robots, redirect re-validation, event coverage, persistence, research wiring were missing; crawler unreachable from API | **PARTIALLY FIXED 2026-09-13** — pacing/robots/redirects/events/fail-closed shipped; DB persistence + research wiring remain (Phase 1) |
| R9 | `performance_metrics` table (migration `j9k0l1m2n3o4`) | Zero writers, zero readers — dead schema; live learning store writes `learning_events` instead | OPEN — drop table or wire writer in Phase 2 |
| R10 | `backend/tools/learning/Diagnosed deployment failures and orches.ini` | 1,544 lines of pasted CI logs committed as a pseudo-config file (documented P0 hygiene risk, possible secret-bearing log content) | **FIXED 2026-09-13** — file deleted; rotate any Render/GitHub tokens that appeared in those logs (external action required) |
| R11 | `STATUS.md` governance section claims "All Production Readiness Audit (Phases 1-7) … 100% complete" | Contradicted by R4–R9 above and by the 125-skip audit | OPEN — phase-gate scoreboard replaces absolute claims once Phase 2 lands (`MASTER_PLAN.md` §7) |

## Rule

A pointer without a target is a defect. Any doc that cites another artifact must either link to it or fix the pointer. New discrepancies are appended here with a date and an owner, never silently ignored (Constitution: No Silent Failure).
