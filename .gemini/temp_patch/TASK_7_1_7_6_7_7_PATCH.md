# SupremeAI — Task 7.1 / 7.6 / 7.7 Implementation Patch

> Target: `SaifulHaqueNiloy/supremeai`
> Base: `main`
> Scope: Canary rollout, Firebase-admin retirement, frontend auth compatibility.
> Safety rule: do not claim a task complete until the acceptance tests below pass in CI and, where applicable, against the live deployment.

## Current-code findings

- `backend/evolution/canary_manager.py` already contains `CanaryRolloutController`, sample accounting, promotion thresholds, and rollback state transitions. It does **not** itself split real HTTP traffic; therefore Task 7.1 is only partially implemented.
- `backend/core/self_evolution/auto_skill_creator.py` already creates a governed change proposal, performs AST/sandbox/benchmark/integrity gates, and suspends the generated skill for HITL approval. Do not remove the HITL gate while adding canary behavior.
- `backend/core/security/ws_auth.py` now requires a JWT either as `?token=` or as the first auth message. Browser WebSocket clients cannot set an arbitrary `Authorization` header, so query-token or first-message auth must be used.
- `frontend/src/services/apiClient.ts` already centralizes `getRawToken()` and `getAuthHeaders()` and stores the user/admin tokens in the existing storage keys. Reuse this source of truth; do not create another token store.
- `frontend/src/hooks/useWebSocket.ts` currently creates `new WebSocket(socketUrl)` without authentication. This is a concrete Task 7.7 gap.
- `backend/utils/firestore_helpers.py` is still an active Firestore client factory, so Task 7.6 must be a migration/removal, not merely deleting `firebase-admin` from a dependency file.

## Task 7.1 — Real Canary Traffic Splitting

### Objective

Turn the existing in-process canary state machine into real traffic isolation without pretending that Render's service-level routing provides percentage splitting.

### Required implementation

1. Keep `backend/evolution/canary_manager.py` as the **policy/decision layer**.
2. Add an edge-routing layer under a clearly isolated directory such as `infra/canary/`.
3. The edge router must support:
   - `CANARY_ENABLED` (default `false`)
   - `CANARY_PERCENT` (default `10`, valid range `0..100`)
   - `STABLE_BACKEND_URL`
   - `CANARY_BACKEND_URL`
   - a deterministic cohort key (prefer authenticated user/tenant ID; otherwise a signed/opaque cookie)
4. Use deterministic hashing so one user remains on the same cohort during a rollout. Do **not** use per-request random routing.
5. Never expose the canary backend URL to the browser as a public client configuration value.
6. Preserve WebSocket upgrade routing using the same cohort decision; a user must not switch stable/canary mid-session.
7. Add an emergency kill switch: `CANARY_ENABLED=false` must route 100% to stable without requiring a code deployment.
8. Add health/rollback integration so the edge layer can stop assigning new cohorts to canary when `CanaryRolloutController.trigger_rollback()` is invoked.
9. Do not route `/health/*`, authentication/bootstrap endpoints, migrations, or other control-plane endpoints through the canary unless explicitly allow-listed.
10. Do not call this a completed Render-native feature. This is an external edge-routing capability that can front the Render services.

### Important architecture constraint

A Cloudflare Worker is acceptable only if the project has an approved Cloudflare account/domain and deployment path. If that is not already available, implement the routing contract and tests but leave the actual edge deployment as a manual infrastructure step. Do not add a new paid service or hard-code a Cloudflare dependency solely to mark 7.1 complete.

### Acceptance tests

- With canary disabled: 100% stable.
- With 10% canary: deterministic cohort distribution is approximately 10% over a sufficiently large synthetic population.
- Same user/tenant receives the same backend repeatedly.
- WebSocket and HTTP choose the same cohort.
- Invalid percentage fails closed to stable.
- Missing canary URL while enabled fails closed to stable and emits an actionable alert/log.
- Rollback immediately stops new canary assignment.
- No public frontend bundle contains the private canary origin.

## Task 7.6 — Firebase-admin / Firestore Retirement

### Objective

Make Supabase/PostgreSQL the authoritative application persistence layer and remove the remaining Firebase/Firestore runtime dependency only after data and behavior have been migrated.

### Required implementation

1. Inventory every remaining Firebase/Firestore consumer before changing dependencies. At minimum inspect:
   - `backend/utils/firestore_helpers.py`
   - `backend/core/gcp_firestore.py`
   - `backend/core/tenant_db.py` / `backend/database/tenant_db.py`
   - `backend/core/messaging/events.py`
   - `backend/storage/asset_manager.py`
   - backup/restore scripts
   - tests and deployment configuration
2. Map each Firestore collection/path to a Supabase table or a deliberate replacement. Preserve tenant isolation and existing authorization semantics.
3. For `hitl_audit_ledger`, use the existing PostgreSQL/HITL ledger design where appropriate; preserve append-only/audit semantics and cryptographic chaining requirements. Do not silently downgrade audit integrity to ordinary mutable rows.
4. Migrate historical data with an idempotent migration script. The migration must be restartable and must not duplicate records.
5. Add parity checks before deleting Firestore code:
   - row/document counts
   - representative tenant records
   - timestamps/IDs
   - audit hash-chain continuity where applicable
   - application read/write round trips
6. Change application code to use the Supabase repository/service layer rather than direct Firestore calls.
7. Remove Firestore fallback behavior from `AutoSkillCreator` and related tenant paths once the Supabase path is proven. Do not leave a silent mock that can make production data appear successfully persisted.
8. Remove Firebase service-account environment variables from production configuration after the final migration verification.
9. Remove unused Firebase/Google Firestore dependencies from the backend dependency manifests and regenerate the lockfile.
10. Delete Firestore helpers only after repository-wide search shows no runtime imports. Keep a migration/archive note documenting the former collection mapping.

### Safety rule

Do **not** delete `firebase-admin`, Firestore helpers, or credentials in the same commit as an unverified data migration. Prefer staged commits: schema/repository → migration → parity verification → application cutover → dependency removal → cleanup.

### Acceptance tests

- Repository-wide search has zero runtime Firestore/Firebase-admin imports, except explicitly documented migration tooling if retained temporarily.
- Application startup succeeds without Firebase credentials.
- HITL/audit records persist and can be read entirely from Supabase.
- Tenant isolation tests pass.
- Backup/restore contains the migrated data and restore drill passes.
- Cold-start memory footprint does not regress.
- No production code silently reports success when persistence is unavailable.

## Task 7.7 — Frontend Auth Compatibility

### Objective

Update every frontend caller affected by the newly authenticated backend endpoints while keeping the existing centralized token handling.

### Required implementation

1. Extend `frontend/src/hooks/useWebSocket.ts` so its default connection obtains the token from `getRawToken()` in `frontend/src/services/apiClient.ts`.
2. Prefer the existing backend-supported query-token form for browser WebSockets:
   - `...?token=<encoded JWT>`
   - never log the full URL/token.
3. If no token exists, fail closed before opening the protected WebSocket (or surface a clear unauthenticated state); do not open an anonymous socket and wait for a confusing 1008 response.
4. Preserve explicit caller-provided URLs, but if they target a protected SupremeAI WS endpoint they must still use the auth contract. Do not blindly append tokens to third-party WebSockets.
5. Update `frontend/src/commandcenter/realtime/websocketManager.ts` similarly, because it is another direct WebSocket client.
6. Audit and fix all protected HTTP/export clients. Reuse `apiClient.getAuthHeaders()` / `getRawToken()` instead of manually reading localStorage in multiple places.
7. Specifically verify:
   - markdown export UI (`frontend/src/components/export/ExportMenu.tsx` and its service path)
   - CI dashboard WebSocket
   - service-topology health stream (admin token required)
   - `/agent/terminal-stream`
   - any `ws/dashboard`, `markdown/export`, `health-stream`, or `terminal-stream` references found by repository search
8. Do not put admin credentials into a user build or expose an admin token to non-admin routes.
9. Ensure a 401 clears the existing token cache through the current `clearAuthToken()` path, and a 403 does not incorrectly erase a valid authenticated token.

### Acceptance tests

- Authenticated WebSocket connects successfully.
- Missing/expired token is rejected cleanly.
- Admin-only health stream accepts an admin token and rejects a normal user token.
- Markdown export succeeds for an authenticated user.
- Terminal stream and CI dashboard preserve auth across reconnects.
- No JWT is printed in console logs, telemetry, error messages, or analytics payloads.
- Existing public endpoints remain usable without forcing authentication where policy says they are public.

## Recommended execution order

1. **7.7 first** — low-risk client compatibility fix for already-protected endpoints.
2. **7.6 in staged migration** — database cutover requires data verification and rollback planning.
3. **7.1 last** — activate real canary traffic only after stable/canary artifacts and rollback telemetry are proven.

## Definition of Done

- [ ] 7.7 frontend auth compatibility tests green.
- [ ] 7.6 Supabase parity + restore drill green; Firebase runtime dependency removed.
- [ ] 7.1 real edge cohort routing tested; emergency kill switch verified.
- [ ] `AUDIT_MASTER_CHECKLIST.md` updated with evidence, not just checked boxes.
- [ ] `MANUAL_STEPS_REMAINING.md` updated to remove only the items actually completed.
- [ ] CI green and production health endpoints verified after deployment.
