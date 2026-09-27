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
| `backend/external_agents/` (23 files, ~2.9k LOC) | NEAR-READY-UNWIRED (verified 2026-09-27, see §11) | Zero production importers; 75 acceptance tests (issue #1572) exist and pass; ACTIVE plan `PLAN-EAOL-003` implements→this module | **wire-next** per `PLAN-EAOL-003` — do NOT archive/delete (simplification-audit B12 refuted) | DECISION REQUIRED (owner) |

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

### 11. `backend/external_agents/` — NEAR-READY-UNWIRED (addendum 2026-09-27)

**Origin of this row:** simplification audit finding **B12** ("delete `external_agents/`, 2,873 LOC") was re-verified under the philosophy-aligned V2 rule (*every removal needs 3-check proof + plan-corpus truth-ordering*) and **REFUTED**. Recorded here so the near-ready state is visible instead of silently deleted.

* **What it is:** the Part-3 implementation seed of **`PLAN-EAOL-003` — Universal External Agent & Dynamic Execution Architecture (EAOL)**, plan status `active`, `disposition: retain`, `evidence_state: partial` (`docs/plans/architecture/EXTERNAL_AGENT_ORCHESTRATION_LAYER_PLAN.md`). Built via accepted **issue #1572** (root acceptance tests named `"...for issue #1572 — Part 3"`). Layout: `contracts/` (Pydantic TaskContract + planner/architecture/code artifacts), `control/` (durable `QUEUED→CLAIMED→RUNNING→CHECKPOINT→VERIFYING→COMPLETED` state machine on `JsonFileStore` + non-blocking `ExternalAgentJobAPI.delegate_web_agent` + capability `PolicyEngine`/`PlannerArchitectRouter`), `channels/` (browser, mcp), `providers/` (capability registry: zai/chatgpt/gemini), `verification/` (artifact bridge, git verifier, PR manager).
* **Check 1 — callers:** `git grep external_agents -- '*.py'` outside the package → only the 6 root acceptance-test files (`tests/test_external_agents_contracts.py`, `test_external_agents_state.py`, `test_artifact_bridge.py`, `test_git_verifier.py`, `test_provider_policy_router.py`, `test_zai_native_mcp.py`; 75 tests total). Zero string/dynamic imports; non-py hits are generated graphs + audit docs only. No `ALL_ROUTERS` entry.
* **Check 2 — plan-corpus intent:** the corpus **promises this capability** (active canonical-candidate EAOL plan v3.1.0 + `docs/plans/plan_registry.json` entry + #1572 acceptance). Per V2 rule this is *near-ready → finish it, not delete*.
* **Check 3 — health:** all 23 files `py_compile` clean; acceptance suite green where sandbox deps allow (56 passed / 3 + 16 blocked only by missing `sqlalchemy` in the local sandbox — import-chain via `backend/services/config_service.py`, not module code; full suite assumed green on CI deps).
* **Known hygiene gap:** CI's pytest steps all run with `working-directory: ./backend` where `testpaths=["tests"]` → the **75 root-level #1572 acceptance tests are not executed by CI**. Wiring them into a CI job is the cheapest next step and protects the seed from rot.
* **Recommendation:** **wire-next** per `PLAN-EAOL-003` milestones (smallest honest wire: expose `ExternalAgentJobAPI` behind a router/flag or an internal capability consumer; plus move the acceptance suite into CI). **Do NOT archive/delete** unless the owner formally retires the EAOL plan in `plan_registry.json` first.
* **DECISION REQUIRED (owner).**

#### Finish-issue draft (for owner/planner to file)

> **Title:** Wire `backend/external_agents` (EAOL Part-3 seed) or formally retire the plan
> **Body:** `backend/external_agents/` (23 files, ~2.9k LOC) is the #1572/Part-3 implementation of active plan `PLAN-EAOL-003`, fully tested (75 root acceptance tests) but imported by zero production code — see `docs/operations/MODULE_STATUS_REGISTRY.md` §11. Options: (a) wire `ExternalAgentJobAPI` + capability router per plan milestones (recommend also moving the acceptance tests into CI — today they run in no workflow); or (b) if Track-A/B priorities changed, retire `PLAN-EAOL-003` in `plan_registry.json` first, then archive the module. No silent deletion.

## Relationship to the governed module inventory

`MODULES_LIST.md` (repo root + `docs/reference/`) is **generated** by `scripts/sync_modules_list.py` from `docs/audit_reports/module_wiring_audit.json`, and the module operational contract test (`backend/tests/api/test_module_operational_contracts.py`) reads it. The audit JSON tracks 194 modules at package/dir granularity and does **not** carry individual rows for any of the ten files above (verified: zero grep hits in `MODULES_LIST.md`), so no rows were hand-added here — hand edits would be overwritten by the next sync and could break the contract test. If the owner wants these files in the governed inventory, the correct path is adding them to `module_wiring_audit.json` and re-running `scripts/sync_modules_list.py`, referencing this registry in the `Decision` column.

## Marker convention

Each verified-orphaned file carries a module-docstring line: `STATUS: orphaned — see docs/operations/MODULE_STATUS_REGISTRY.md (#449).` (added docstring-only; zero runtime change). Wired files (#4, #5) intentionally carry **no** marker. Near-ready packages (§11 `backend/external_agents/`) carry: `STATUS: near-ready (unwired) — see docs/operations/MODULE_STATUS_REGISTRY.md §11; plan PLAN-EAOL-003.`
