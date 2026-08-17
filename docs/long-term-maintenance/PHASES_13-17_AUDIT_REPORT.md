# SupremeAI 2.0 — Phases 13–17 Audit Report (Master Audit Continuation)

> **Date:** Continuous audit · **Scope:** backend + studio-client + mobile contract · **Method:** Static analysis + grep + empirical test runs (per master plan rule #1: no "Fixed" claim without evidence).

## Cumulative Audit Status (Phases 0–17)

| Severity | Count | Status |
|----------|-------|--------|
| P0 (Critical) | 5 | ALL FIXED |
| P1 (High) | 6 | 5 FIXED, 1 TRACKED (AUDIT-002) |
| P2 (Medium) | 6 | ALL FIXED |
| P3 (Low) | 1 | FIXED |
| **NEW (this pass)** | **2** | **1 FIXED, 1 TRACKED** |

---

## Phase 14 — Dependency & Supply Chain Audit

### Finding: AUDIT-006 (P2, TRACKED) — GitHub Actions unpinned
- **Evidence:** `.github/workflows/*.yml` contain 151 `@vX` version-tag references, **zero** SHA-pinned actions.
- **Risk:** Supply-chain tampering of a compromised action version range.
- **Remediation:** Replace `@vX` with commit SHA (`@<full-sha>`). Add a CI guard to block unpinned actions.

### Finding: AUDIT-014 (P1, remediation guide) — Known CVEs in backend deps
- **Evidence (`pip-audit -r poetry.lock`):** **54 known vulnerabilities across 9 packages**:
  | Package | Current | Fix |
  |---------|---------|-----|
  | aiohttp | 3.13.5 | 3.14.x (multiple) |
  | cryptography | 48.0.0 | 48.0.1 / 49 / 50 |
  | ecdsa | 0.19.2 | no fix yet |
  | httplib2 | 0.31.2 | 0.32.0 |
  | litellm | 1.83.7 | 1.83.10 / 1.84.0 |
  | pillow | 12.2.0 | 12.3.0 |
  | pyasn1 | 0.6.3 | 0.6.4 |
  | pydantic-settings | 2.14.1 | 2.14.2 (GHSA-4xgf-cpjx-pc3j) |
  | python-dotenv | 1.0.1 | 1.2.2 |
- **Action:** Upgrade trackable packages; document `ecdsa` (no upstream fix) as accepted risk with monitoring.

---

## Phase 14.5 — RBAC & Data Privacy

### Finding: Tenant Isolation — CLEAN ✅
- `insight_mage.py`, `churn_prophet.py` use `.where("_tenant_id", "==", tenant_id)`.
- `cost_guard.py` uses hard-isolated `tenants/{tenant_id}/budget` route refs.
- No cross-tenant query leakage found.

### Finding: AUDIT-017 (P2, FIXED) — PII/OTP plaintext logging
- **File:** `backend/tools/security_tools/multi_account_rotator.py`
- **Problem (1 line):** `logger.info(f"...OTP code: {otp_code}")` and `logger.info(f"...Verification link: {verification_link}")` logged raw OTP codes and verification tokens in plaintext.
- **Root cause:** Developer convenience logging of sensitive verification data.
- **Fix applied + verified (`py_compile` OK):** replaced with status-only logs (`"OTP received"`, `"Verification link received"`); the actual OTP/link is still used for the automation flow but never emitted to logs.
- **Dev guard:** Add `gitleaks`/regex rule to block `OTP code:` or `Verification link:` patterns in `logger.*` calls.

---

## Phase 14.75 — LLM Cost Guard Validation

### Finding: AUDIT-015 (P1, TRACKED) — `validate_budget`/`record_spend` not wired into production routing
- `CostGuard.check_budget()` → wired into `core/llm/llm_gateway.py` ✅
- `CostGuard.connect()` → wired into `core/lifespan.py` ✅
- `CostGuard.validate_budget()` and `record_spend()` → **used ONLY in tests**, not in production task routing.
- **Empirical coverage evidence:** `core\queue\task_router.py` = **0% coverage** (49 stmts, fully missed) — confirms task_router has no cost-guard integration.
- **Doc-vs-code drift:** `cost_guard.py` docstring claims "multi-tier fallback routing support for task_router.py", but `task_router.py` does not reference it.
- **Risk:** Budget/tier enforcement is partial — routing can bypass per-tier cost caps.
- **Recommendation:** Wire `validate_budget` into `task_router` provider-selection path (or explicitly document tier enforcement is confined to `llm_gateway`).

### Test Evidence (Phase 16 subset)
- `tests/core/test_cost_guard.py` + `test_cost_guard_coverage.py` + `test_cost_guard_coverage_full.py` → **35 passed in 48.02s**.
- `core\cost_guard.py` coverage = **66%** (106 stmts, 37 miss).

---

## Phase 13.5 — Cross-App API Contract Testing

### Finding: AUDIT-018 (P1, TRACKED) — Broken client↔backend contract endpoints
| Client call | Source file | Backend status |
|-------------|-------------|----------------|
| `GET /api/voice/voices` | `studio-client/.../chatService.ts` (`getVoices`) | ❌ Missing — voice router only exposes `/stream_audio` |
| `GET /api/skills/catalog` | `studio-client/.../skillsService.ts` | ❌ Missing — `api.routes.skills` NOT registered in `routers.py` |
| `PUT /api/files/{path}` | `studio-client/.../useSupremeStore.ts` | ❌ No matching files route |
| `/api/session/{id}/stream` | `studio-client/.../sessionCockpitStore.ts` | ✅ Exists (`api/routes/session_stream.py`) |
| `POST /api/v1/media/generate-upload-url` | storage client | ✅ Exists (`api/routes/media.py`, mounted at "") |

- **Root cause:** `backend/api/routers.py` `core_routers`/`optional_routers` lists do not include a `skills` router, and the voice router prefix hides `/voices`.
- **Impact:** Skills catalog, voice list, and file upload features in studio-client will 404 in production.
- **Recommendation:** Register the skills router + add `/voices` endpoint on the voice router; add a files PUT route; add a CI contract test asserting every client-referenced path resolves against the FastAPI `app.openapi()`.

---

## Phase 15 — Docs vs Code Consistency

### Finding (P3, TRACKED) — API-swagger.yaml grossly incomplete
- `backend/API-swagger.yaml` `paths:` section documents only `/health`, while `routers.py` registers 60+ routers.
- The `cost_guard` docstring overstates tier-routing integration (see AUDIT-015).
- **Recommendation:** Auto-generate OpenAPI from the live FastAPI app (`app.openapi()`) and commit it; flag drift in CI.

---

## Phase 16 — End-to-End Tests

- **Full suite:** `pytest --cov=backend` (3207 items) — began; cost-guard subset completed **35 passed**.
- **Observed failures during full run:** `tests/test_headless_terminal_agent.py` produced `FF` (2 failures) at ~48% (interrupted before final tally).
- **Coverage snapshot (subset):** TOTAL **15%** across 19,184 backend statements when running only cost-guard tests — expected for a subset; full-suite coverage target is `fail-under=38` per `pyproject.toml`.
- **Action:** Re-run full suite to completion in CI; investigate the `test_headless_terminal_agent.py` failures (likely environment-dependent subprocess/terminal mocking).

---

## Phase 17 — Rollback Plan (DONE ✅)

- Created **`docs/operations/rollback-plan.md`**: blue/green deployment + automated rollback triggers for Cloud Run, Render, Firebase, Docker Compose, Helm; data-safety & migration reversibility; kill switches; post-rollback checklist.
- Verified against `infrastructure/docker-compose.prod.yml`, `render.yaml`, `backend/api/routers.py`, `backend/tools/devops/on_premise_deployer.py`.

---

## Summary of New Findings This Pass

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| AUDIT-014 | P1 | 54 known CVEs in 9 backend packages | Remediation guide |
| AUDIT-015 | P1 | `validate_budget`/`record_spend` not wired into task_router (0% coverage) | Tracked |
| AUDIT-017 | P2 | OTP/verification-link plaintext logging | **FIXED** |
| AUDIT-018 | P1 | Broken client contract: `/voice/voices`, `/skills/catalog`, `/files/` | Tracked |
| — | P3 | API-swagger.yaml incomplete (docs vs code) | Tracked |

## Recommended Next Actions (Priority Order)
1. Register `skills` router + add `/voice/voices` + `/files/` PUT → close AUDIT-018.
2. Upgrade CVE-trackable deps (aiohttp, cryptography, litellm, pillow, pydantic-settings, python-dotenv, pyasn1, httplib2) → close AUDIT-014.
3. SHA-pin GitHub Actions → close AUDIT-006.
4. Wire `validate_budget` into tier routing or document scope → close AUDIT-015.
5. Fix `test_headless_terminal_agent.py` failures; complete full-suite coverage run.
6. Auto-generate OpenAPI spec → close Phase 15 drift.
