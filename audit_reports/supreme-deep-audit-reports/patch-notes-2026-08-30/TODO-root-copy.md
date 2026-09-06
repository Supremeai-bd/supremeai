# SupremeAI 2.0 — Phases 13–17 Audit TODO

## Phase 14 — Dependency / Supply Chain Audit
- [x] Run `pip-audit` on backend dependencies → **54 CVEs in 9 packages** (aiohttp, cryptography, ecdsa, httplib2, litellm, pillow, pyasn1, pydantic-settings, python-dotenv) — AUDIT-014
- [x] Check GitHub Actions workflows for unpinned actions → **AUDIT-006 confirmed** (151 `@vX` tags, no SHA-pin)

## Phase 14.5 — RBAC & Data Privacy
- [x] Verify tenant isolation in multi-tenant queries → **Clean** (insight_mage, churn_prophet, cost_guard use `_tenant_id`/hard-isolated routes)
- [x] PII log-masking → **AUDIT-017 FIXED**: `multi_account_rotator.py` no longer logs raw OTP codes & verification links (py_compile verified)

## Phase 14.75 — LLM Cost Guard Validation
- [x] Validate `cost_guard.py` tier enforcement → **AUDIT-015**: `validate_budget()`/`record_spend()` only used in tests; `task_router.py` test coverage = **0%**
- [x] Confirm `check_budget()` wiring → `llm_gateway.py` + `lifespan.py` ✅
- [x] Run cost guard tests → **35 passed in 48s**; `cost_guard.py` = 66% coverage

## Phase 13.5 — Cross-App API Contract Testing
- [x] Compare backend API schemas vs studio-client usage → **AUDIT-018 FIXED & VERIFIED (11/11 tests pass in `test_audit018_contracts.py`, `test_voice_stream.py`, `test_files_endpoint.py`)**:
  - `/api/voice/voices` (chatService.getVoices) — `backend/api/routes/voice.py` exposes `/voices` ✅
  - `/api/skills/catalog` & `/api/skills/search` — `backend/api/routes/skills.py` registered in `routers.py` ✅
  - `/api/files/` (useSupremeStore PUT) — `backend/api/routes/files.py` tenant-scoped GET+PUT with path-traversal protection ✅
  - `/api/session/{id}/stream` — exists ✅
  - `/api/v1/media/generate-upload-url` — exists ✅

## Phase 15 — Docs vs Code Consistency
- [x] Cross-verify docs vs code → **API-swagger.yaml only documents `/health`** (grossly incomplete vs 60+ routers); cost_guard docstring overstates tier routing (AUDIT-015)

## Phase 16 — E2E Tests
- [x] Cost-guard subset: **35 passed**; full-suite coverage baseline TOTAL = 15% (subset scope)
- [x] Observed `test_headless_terminal_agent.py` = FF (2 failures) during full run (interrupted)
- [ ] Full-suite run to completion (deferred to CI)

## Phase 17 — Rollback Plan Documentation
- [x] `docs/operations/rollback-plan.md` created (blue/green + auto-rollback for all targets)

## Final
- [x] `docs/long-term-maintenance/PHASES_13-17_AUDIT_REPORT.md` written with all findings + recommendations
</content>
