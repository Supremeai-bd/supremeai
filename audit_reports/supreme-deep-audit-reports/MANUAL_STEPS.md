# Manual Task List

Remaining work that requires operator review, external credentials, or a deliberate rollout:

## External and production-only tasks

- [ ] Provision and verify MCP gateway persistence in the production database.
- [ ] Complete MCP gateway route registration and end-to-end transport tests against deployed nodes.
- [ ] Review tenant isolation, authorization scopes, SSRF policy, secret handling, and audit retention for gateway connections.
- [ ] Configure and verify Supabase `ai_memory` schema, RLS, retention, and privacy sign-off.
- [ ] Triage the six skipped tests reported by the latest checkpoint; reconcile this with the older audit count of 103 before setting a target.
- [ ] Run root-level lint across `tools/`, `scripts/`, `packages/`, and `.github/scripts/`, then fix or explicitly baseline findings.
- [ ] Review stale remote branches and repository stashes before cleanup; preserve any needed work before deletion.
- [ ] Perform production deployment verification, health checks, rollback readiness, and observability review.
- [ ] Complete CI hard-blocking, branch protection/CODEOWNERS, backup-restore drill, and data-retention/privacy approval before customer launch.

## Code follow-ups requiring an intentional implementation slice

- [ ] Validate the execution-mode Settings UI end to end against the backend contract, including authorization and persistence; the frontend contract exists but audit evidence is incomplete.
- [ ] Validate `SCRAPER_BACKEND_URL` resolution in every scraper-backed path and add an integration test for deployed and local configurations.
- [ ] Finish unified-store staging rollout: exercise `chatSlice` behind the feature flag, verify legacy-store compatibility, and define rollback criteria before enabling it.
- [ ] Decide whether medium-priority provider stubs (`cloud_sandbox_orchestrator`, resource lifecycle, swarm base classes, skill provisioning) should be implemented, converted to explicit capability responses, or formally deferred.
- [ ] Raise backend/frontend coverage to the project gates after skip-marker triage; do not count skipped tests as coverage.

## Findings reconciled during this review

- [x] `chatSlice` is present in the checkout; the older audit statement that it is missing is stale. Its rollout is still unverified.
- [x] Device-fingerprint generation and API-client collection are present; middleware/backend propagation and enforcement still need an end-to-end proof.
- [x] Existing `pass` matches are mostly exception-handler fallbacks, test fixtures, or intentional empty classes; review only runtime stubs that raise `NotImplementedError` before changing them.
- [ ] Re-run the audit against the current commit and update stale counts/statuses, especially the 103-versus-6 skipped-test discrepancy.
