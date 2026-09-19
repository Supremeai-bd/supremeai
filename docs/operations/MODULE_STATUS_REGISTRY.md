# Module Status Registry — Orphaned Feature Modules (Owner Decision Sheet)

**Issue:** #449 — orphaned feature modules (escrow, rider/delivery fleet, diagram parser, 5 open-source adapters, video-to-code)
**Verified on:** `main` @ 5ca2de5 (branch `fix/issue-441-449-decision-support`).
**Method:** repo-wide `git grep` for imports/callers/router registrations outside each module's own tests, checked against the current `ALL_ROUTERS` registry (`backend/api/routers.py` — note: the registry now lives here, not in a moved file).

**This registry is the owner's decision sheet. Every row is DECISION REQUIRED (owner). Nothing has been deleted, wired, or un-wired by this branch — only status markers were added.**

## Verdict summary

| Module | Status | Evidence of (non-)use | Recommendation | Decision |
|---|---|---|---|---|
| `backend/services/escrow_service.py` | ORPHANED-VERIFIED | Zero references outside its own test | archive-after-owner-confirmation | DECISION REQUIRED (owner) |
| `backend/services/delivery_fleet_tracker.py` | ORPHANED-VERIFIED | Only caller = compat shim (`rider_tracker.py:6`) + coverage tooling | archive-after-owner-confirmation (with `rider_tracker.py`) | DECISION REQUIRED (owner) |
| `backend/services/rider_tracker.py` | ORPHANED-VERIFIED | Pure re-export shim; no production importer | archive-after-owner-confirmation (with `delivery_fleet_tracker.py`) | DECISION REQUIRED (owner) |
| `backend/services/diagram_parser_service.py` | WIRED-ON-MAIN (issue claim stale) | `ALL_ROUTERS` entry `backend/api/routers.py:400-406` | none — verify endpoints in prod | resolved by merged PR #581 |
| `backend/services/video_to_code_pipeline.py` | WIRED-ON-MAIN (issue claim stale) | `ALL_ROUTERS` entry `backend/api/routers.py:417-422` | none — optional ffmpeg availability check | resolved by merged PR #581 |
| `backend/integrations/e2b_adapter.py` | ORPHANED-VERIFIED | Class has zero consumers repo-wide; dep not in `backend/pyproject.toml` | archive or extract to separate repo | DECISION REQUIRED (owner) |
| `backend/integrations/openhands_adapter.py` | ORPHANED-VERIFIED | same | archive or extract to separate repo | DECISION REQUIRED (owner) |
| `backend/integrations/browser_use_adapter.py` | ORPHANED-VERIFIED | same | archive or extract to separate repo | DECISION REQUIRED (owner) |
| `backend/integrations/mem0_adapter.py` | ORPHANED-VERIFIED | same | archive or extract to separate repo | DECISION REQUIRED (owner) |
| `backend/integrations/graphiti_adapter.py` | ORPHANED-VERIFIED | same | archive or extract to separate repo | DECISION REQUIRED (owner) |

## Per-module detail

### 1. `backend/services/escrow_service.py` — ORPHANED-VERIFIED
* **Evidence:** `git grep -n escrow -- ':!backend/tests' ':!*.md'` → only self-references inside `escrow_service.py`; only test = `backend/tests/services/test_escrow_service.py`. No `ALL_ROUTERS` entry (`git grep escrow -- backend/api` → 0 hits). Imports nothing beyond `core.cache` + stdlib (`escrow_service.py:20-22`).
* **What it is:** full multi-party escrow state machine (PENDING→FUNDED→CONDITION_MET→RELEASED/DISPUTED/REFUNDED/EXPIRED, `escrow_service.py:28-36`) persisting to Upstash Redis via `core.cache` (30-day TTL, `:24`). No payment-provider integration anywhere — money movement is not real.
* **Recommendation:** **archive-after-owner-confirmation** — complete, tested, but no payment-provider config in prod and no product surface calls it.
* **DECISION REQUIRED (owner).**

### 2. `backend/services/delivery_fleet_tracker.py` — ORPHANED-VERIFIED
* **Evidence:** only inbound reference is the compat shim `rider_tracker.py:6` (`from services.delivery_fleet_tracker import ...`) plus coverage bookkeeping (`backend/analyze_coverage.py:24`, `backend/COVERAGE_90_PLAN.md:120`). No `ALL_ROUTERS` entry; no importer under `api/`, `brain/`, `workers/`, or other `services/` modules.
* **What it is:** complete rider/delivery tracking service (location, route optimization, status machine) over Upstash Redis + free map APIs (`delivery_fleet_tracker.py:1-11`).
* **Recommendation:** **archive-after-owner-confirmation** — no delivery/fleet product surface exists; revive from git history if that product ever ships.
* **DECISION REQUIRED (owner).**

### 3. `backend/services/rider_tracker.py` — ORPHANED-VERIFIED
* **Evidence:** 35-line backward-compatibility bridge re-exporting `delivery_fleet_tracker` (`rider_tracker.py:1-33`); `git grep rider_tracker -- ':!backend/tests' ':!*.md'` → no production importer (only the shim itself, the fleet module, and coverage tooling). Only test = `backend/tests/services/test_rider_tracker.py`.
* **Recommendation:** **archive-after-owner-confirmation** — same product absence as #2; archive as a pair so the shim never dangles.
* **DECISION REQUIRED (owner).**

### 4. `backend/services/diagram_parser_service.py` — WIRED-ON-MAIN (issue claim stale)
* **Evidence of wiring:** `ALL_ROUTERS` entry `{"path": "services.diagram_parser_service", ...}` at `backend/api/routers.py:400-406`, added by merged PR #581 (commit `ee71090`) with an explicit "Issue #449 wire-next" note. The router (prefix `/diagram-parser`, `diagram_parser_service.py:24`) is mounted via `register_all_routers()` (`routers.py:467-522`).
* **Recommendation:** none — cheapest-wire already applied. Owner may confirm `/diagram-parser/*` responds in prod (it registers `optional=True`, so a failed import degrades loudly in the boot mount report).
* ~~DECISION REQUIRED (owner)~~ — resolved; listed for traceability.

### 5. `backend/services/video_to_code_pipeline.py` — WIRED-ON-MAIN (issue claim stale)
* **Evidence of wiring:** `ALL_ROUTERS` entry at `backend/api/routers.py:417-422` (same PR #581); prefix `/video-to-code` (`video_to_code_pipeline.py:24`). ffmpeg is an **optional external dep** with graceful fallback (`video_to_code_pipeline.py:11-12`) — no hard runtime dependency.
* **Recommendation:** none; if frame extraction underperforms in prod, check the ffmpeg binary in the deploy image.
* ~~DECISION REQUIRED (owner)~~ — resolved; listed for traceability.

### 6–10. `backend/integrations/{e2b,openhands,browser_use,mem0,graphiti}_adapter.py` — ORPHANED-VERIFIED
* **Evidence:** each adapter class is re-exported by `backend/integrations/__init__.py:13-17` and referenced **nowhere else in the repo** (zero hits for `E2BAdapter` / `OpenHandsAdapter` / `BrowserUseAdapter` / `Mem0MemoryAdapter` / `GraphitiMemoryAdapter` outside `backend/integrations/` — including tests). No `ALL_ROUTERS` entry; no factory in `core/services.py`.
* **External deps:** none of `e2b`, `openhands`, `browser_use`, `mem0`, `graphiti_core` appear in `backend/pyproject.toml` (or any requirements file) — adapters import them only through `integrations/_flags.import_available` probes.
* **Runtime posture:** zero-cost and inert today — each adapter is double-gated (env flag + dependency probe): `SUPREMEAI_E2B_ENABLED`+`e2b` (`e2b_adapter.py:22,34`), `SUPREMEAI_OPENHANDS_ENABLED`+server URL (`openhands_adapter.py:25,37`), `SUPREMEAI_BROWSER_USE_ENABLED`+`browser_use` (`browser_use_adapter.py:37,241`), `SUPREMEAI_MEM0_ENABLED`+`mem0` (`mem0_adapter.py:21,44`), `SUPREMEAI_GRAPHITI_ENABLED`+`graphiti_core`+URI (`graphiti_adapter.py:25,64`). The modules are only *imported* transitively when the `integrations` package loads (e.g. `api/routes/capabilities.py:105` imports `integrations._flags`); the classes are never constructed or called.
* **Recommendation:** **archive or extract to a separate repo** — external deps not in requirements, zero consumers, and each vendor integration would need its own dependency/flag/cost review before wiring. Alternative (wire-next) only makes sense if the owner wants that specific vendor path; keeping them costs nothing at runtime but does cost review noise (this registry + the silent-errors baseline entries for `e2b_adapter.py` / `graphiti_adapter.py`).
* **DECISION REQUIRED (owner) per adapter.**

## Relationship to the governed module inventory

`MODULES_LIST.md` (repo root + `docs/reference/`) is **generated** by `scripts/sync_modules_list.py` from `docs/audit_reports/module_wiring_audit.json`, and the module operational contract test (`backend/tests/api/test_module_operational_contracts.py`) reads it. The audit JSON tracks 194 modules at package/dir granularity and does **not** carry individual rows for any of the ten files above (verified: zero grep hits in `MODULES_LIST.md`), so no rows were hand-added here — hand edits would be overwritten by the next sync and could break the contract test. If the owner wants these files in the governed inventory, the correct path is adding them to `module_wiring_audit.json` and re-running `scripts/sync_modules_list.py`, referencing this registry in the `Decision` column.

## Marker convention

Each verified-orphaned file carries a module-docstring line: `STATUS: orphaned — see docs/operations/MODULE_STATUS_REGISTRY.md (#449).` (added docstring-only; zero runtime change). Wired files (#4, #5) intentionally carry **no** marker.
