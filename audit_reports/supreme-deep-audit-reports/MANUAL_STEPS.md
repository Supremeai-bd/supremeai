# Manual Task List

Remaining work that requires operator review, external credentials, or a deliberate rollout:

## External and production-only tasks

- [ ] Provision and verify MCP gateway persistence in the production database.
- [ ] Complete MCP gateway route registration and end-to-end transport tests against deployed nodes.
- [ ] Review tenant isolation, authorization scopes, SSRF policy, secret handling, and audit retention for gateway connections.
- [ ] Configure and verify Supabase `ai_memory` schema, RLS, retention, and privacy sign-off.
- [x] Triage the six skipped tests reported by the latest checkpoint; reconciled: the "6 skipped" count was an import-time `--collect-only` artifact, while the active codebase has 103 markers across 53 files documented in `docs/SKIPPED_TESTS.md`.
- [ ] Run root-level lint across `tools/`, `scripts/`, `packages/`, and `.github/scripts/`, then fix or explicitly baseline findings.
- [ ] Review stale remote branches and repository stashes before cleanup; preserve any needed work before deletion.
- [ ] Perform production deployment verification, health checks, rollback readiness, and observability review.
- [ ] Complete CI hard-blocking, branch protection/CODEOWNERS, backup-restore drill, and data-retention/privacy approval before customer launch.

## Code follow-ups requiring an intentional implementation slice

- [x] Validate the execution-mode Settings UI end to end against the backend contract, including authorization and persistence (`SettingsPage.tsx` wired to `connectionsApi`, contracts, and `SettingsPage.test.tsx`).
- [x] Validate `SCRAPER_BACKEND_URL` resolution in every scraper-backed path and add an integration test for deployed and local configurations (`api.ts`, `api.test.ts`, and `test_scraper_resolution.py`).
- [ ] Finish unified-store staging rollout: exercise `chatSlice` behind the feature flag, verify legacy-store compatibility, and define rollback criteria before enabling it.
- [ ] Decide whether medium-priority provider stubs (`cloud_sandbox_orchestrator`, resource lifecycle, swarm base classes, skill provisioning) should be implemented, converted to explicit capability responses, or formally deferred.
- [ ] Raise backend/frontend coverage to the project gates after skip-marker triage; do not count skipped tests as coverage.

## Configuration and integration findings from the root audit

- [ ] Deploy the canonical `USER_CORS_ORIGINS`, `ADMIN_CORS_ORIGINS`, and `CORS_ORIGINS` values consistently across every backend node; verify authenticated browser preflight from each production frontend.
- [ ] Run the production compose stack with and without the `observability` profile; confirm OTLP is disabled in the base profile and healthy when the collector profile is enabled.
- [ ] Verify the corrected Grafana and Prometheus bind mounts exist in the deployment checkout and that dashboards load after a clean volume/bootstrap.
- [ ] Verify the deployed image exposes `/health/live`, `/api/v1/health/live`, and `/api/v1/health/ready` on the same application entrypoint used by the container healthcheck.
- [ ] Validate that the deployed frontend build uses the intended `VITE_USER_BACKEND`/`VITE_ADMIN_BACKEND` values; build-time Vite variables cannot be changed after deployment.
- [ ] Execute browser preflight and authenticated request tests for `X-Device-Fingerprint`, `X-CSRF-Token`, `Authorization`, and `X-JIT-OTP` against each portal origin.

## Findings reconciled during this review

- [x] `chatSlice` is present in the checkout; the older audit statement that it is missing is stale. Its rollout is still unverified.
- [x] Device-fingerprint generation and API-client collection are present; middleware/backend propagation and enforcement still need an end-to-end proof.
- [x] Existing `pass` matches are mostly exception-handler fallbacks, test fixtures, or intentional empty classes; review only runtime stubs that raise `NotImplementedError` before changing them.
- [x] Re-run the audit against the current commit and update stale counts/statuses: the 103-vs-6 skipped test discrepancy is reconciled. 6 was an import-time `--collect-only` count, while 103 active markers exist across 53 test files governed in `docs/SKIPPED_TESTS.md` with target <30.
