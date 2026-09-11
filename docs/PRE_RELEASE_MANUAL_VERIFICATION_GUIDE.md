# SupremeAI Pre-Release Manual Verification Guide

Use this checklist before promoting any release to production. Complete it against the exact commit intended for release, record evidence for every check, and stop immediately when a blocker fails.

## 1. Release identity and ownership

- [ ] Record release version, commit SHA, branch, date, and release owner.
- [ ] Confirm the release is based on the intended staging branch and not a local/WIP branch.
- [ ] Confirm staging and production repositories, Render services, Supabase projects, and payment accounts are clearly identified.
- [ ] Assign a separate rollback owner.
- [ ] Confirm CODEOWNERS approval for CI, migrations, authentication, billing, and deployment changes.
- [ ] Confirm no uncommitted changes exist in the release checkout.
- [ ] Attach the CI run URL and release evidence bundle.

**Evidence:** commit SHA, `git status`, approval links, CI run URL.

## 2. Security and secret safety

- [ ] Confirm secret scanning passed for the exact commit.
- [ ] Search the diff and generated artifacts for passwords, API keys, tokens, private keys, database URLs, and service credentials.
- [ ] Confirm any credential previously exposed in logs, chat, commits, or artifacts has been revoked and replaced.
- [ ] Confirm production secrets exist only in the approved secret manager; never place them in source code or workflow files.
- [ ] Confirm staging and production credentials are different.
- [ ] Confirm JWT, encryption, webhook-signing, and admin secrets are present and non-empty in production.
- [ ] Confirm logs do not print authorization headers, cookies, tokens, request bodies containing secrets, or personal data.
- [ ] Confirm debug mode and verbose exception output are disabled in production.
- [ ] Confirm authentication, RBAC, tenant isolation, and administrative routes require the intended permissions.
- [ ] Confirm rate limits protect login, signup, AI/agent, billing, webhook, and expensive external-service endpoints.

**Evidence:** security scan result, secret-manager checklist, permission test results, log sample.

## 3. Source, dependency, and build verification

- [ ] Run the repository's frozen-lockfile install/check.
- [ ] Run backend syntax compilation and the configured Ruff gate.
- [ ] Run frontend typecheck, lint, build, and test commands.
- [ ] Confirm backend and frontend coverage reports are truthful and meet the configured gate.
- [ ] Confirm no skipped test is undocumented.
- [ ] For every skipped test, record owner, ticket, risk, acceptance evidence, and review/expiry date.
- [ ] Confirm dependency and license scans pass.
- [ ] Review dependency changes for unexpected packages, post-install scripts, or major-version upgrades.
- [ ] Confirm generated files and build output do not contain secrets or local machine paths.
- [ ] Confirm the production build uses the expected runtime mode and does not depend on development-only services.

**Evidence:** CI job links, test summaries, coverage reports, dependency scan, build artifact metadata.

## 4. Database and migration verification

- [ ] Confirm Alembic is the sole migration authority for the active schema.
- [ ] Confirm migration safety checks pass on the exact release commit.
- [ ] Confirm the migration directory exists and contains the expected revision chain.
- [ ] Review every new migration manually for destructive operations, missing indexes, lock-heavy changes, unsafe defaults, and rollback risk.
- [ ] Confirm migrations are backward-compatible with the currently deployed application during rolling deployment.
- [ ] Run migrations against staging from the current production schema state.
- [ ] Verify staging schema against `backend/database/contracts/schema_contract.yaml`.
- [ ] Perform a read-only production schema parity check before promotion.
- [ ] Confirm database backup/restore evidence exists and the restore target is usable.
- [ ] Confirm connection pooling, maximum connections, timeouts, and transaction boundaries are safe for the available tier.
- [ ] Confirm tenant/user scoping exists on every query that reads or changes user data.
- [ ] Confirm rollback means application rollback plus a documented database recovery plan; do not assume destructive migrations can be reversed automatically.

**Evidence:** migration check output, revision IDs, schema diff, backup/restore result, migration owner approval.

## 5. Configuration and infrastructure verification

- [ ] Confirm all required production environment variables are present.
- [ ] Confirm URLs point to production services, not localhost, preview, staging, or personal resources.
- [ ] Confirm CORS, trusted origins, redirect URLs, cookie security, and webhook URLs match the production domains.
- [ ] Confirm TLS/SSL certificates and custom domains are valid.
- [ ] Confirm health and readiness endpoints are configured and return the expected status.
- [ ] Confirm worker, scheduler, scraper, MCP, and API services use compatible versions and configuration.
- [ ] Confirm background jobs have bounded retries, timeouts, idempotency, and dead-letter/error visibility.
- [ ] Confirm external service quotas and free-tier limits are known and sufficient for the expected load.
- [ ] Confirm no unnecessary preview, duplicate worker, or idle paid resource is enabled.
- [ ] Confirm deployment region, runtime, memory, and concurrency settings match the service's actual needs.

**Evidence:** environment-variable inventory by name only, service configuration screenshots/links, health results.

## 6. Staging functional smoke test

Run against staging using test accounts and test data only.

- [ ] Open the public application and verify the main page loads without console errors.
- [ ] Create a test account or sign in with a test account.
- [ ] Verify logout, session expiry, refresh, and unauthorized access behavior.
- [ ] Verify each representative RBAC role can perform allowed actions and is denied forbidden actions.
- [ ] Create, read, update, and archive/delete a representative agent using safe test data.
- [ ] Execute one normal agent request and verify the response, timeout behavior, and audit trail.
- [ ] Verify memory write, memory read, tenant isolation, and deletion/retention behavior.
- [ ] Submit one background job and verify processing, retry behavior, and failure visibility.
- [ ] Verify scraper/MCP/external integrations with non-production accounts or safe read-only operations.
- [ ] Run the payment flow in the provider's test/sandbox mode, including success, failure, duplicate callback, and webhook signature rejection.
- [ ] Verify email/notification behavior if enabled.
- [ ] Test invalid input, oversized input, missing fields, expired tokens, and repeated requests.
- [ ] Test the primary user flow on desktop and mobile viewport sizes.

**Evidence:** timestamped smoke-test output, test account IDs (not passwords), screenshots, request correlation IDs.

## 7. Observability and operations

- [ ] Confirm structured logs include timestamp, service, environment, severity, request/correlation ID, and safe error context.
- [ ] Confirm errors are visible in the configured monitoring system.
- [ ] Confirm alerts exist for elevated error rate, latency, database failures, worker backlog, auth failures, and payment failures.
- [ ] Confirm alert recipients and escalation paths are current.
- [ ] Confirm dashboards show API health, p95 latency, resource usage, database connections, queue depth, and external-service failures.
- [ ] Confirm logs and metrics do not contain secrets or unnecessary personal data.
- [ ] Confirm free-tier resource limits have warning thresholds before exhaustion.
- [ ] Confirm a human can identify the failing service and release from one alert.

**Evidence:** dashboard links, alert test result, sanitized log sample, escalation owner.

## 8. Rollback rehearsal

- [ ] Identify the last known-good production commit and deployment.
- [ ] Confirm that deployment can be restored without rebuilding from an unverified branch.
- [ ] Confirm the rollback owner has access to Render, the repository, the database runbook, and monitoring.
- [ ] Rehearse application rollback in staging.
- [ ] Verify database recovery steps for any migration that cannot be safely downgraded.
- [ ] Define the rollback trigger, such as sustained 5xx errors, authentication failure, payment failure, data corruption, or queue loss.
- [ ] Define communication steps for incident response and user impact.

**Evidence:** rollback deployment ID, rehearsal result, recovery runbook link, decision owner.

## 9. Production promotion gate

Do not promote unless all of these are true:

- [ ] No unresolved P0/P1 security, data-loss, migration, authentication, or billing blocker exists.
- [ ] Exact release commit passed CI.
- [ ] Staging smoke tests passed.
- [ ] Production schema parity was verified read-only.
- [ ] Required secrets and domains were verified.
- [ ] Backup/restore evidence is current.
- [ ] Monitoring and rollback are ready.
- [ ] Release owner and rollback owner gave explicit approval.
- [ ] Release evidence bundle is attached to the release record.

## 10. Controlled deployment

- [ ] Announce the deployment window and expected user impact.
- [ ] Deploy the exact approved commit; do not deploy from a dirty workspace.
- [ ] Apply migrations using the canonical migration process only.
- [ ] Watch startup logs, health checks, migration output, error rate, latency, database connections, worker backlog, and payment events.
- [ ] Do not perform unrelated maintenance during the release window.
- [ ] Keep the previous deployment available until post-deploy verification completes.

## 11. Post-deploy verification

Within the release observation window:

- [ ] Health and readiness endpoints pass repeatedly.
- [ ] Public application loads successfully.
- [ ] Login, logout, session refresh, and one authorized agent action pass.
- [ ] Unauthorized and cross-tenant access remain denied.
- [ ] Memory access and one background worker job pass.
- [ ] Payment callback/webhook verification passes in the appropriate safe mode.
- [ ] No new startup, migration, auth, database, or worker errors appear.
- [ ] Error rate, p95 latency, queue backlog, resource usage, and database connections remain within thresholds.
- [ ] Customer support and incident channels show no release-related regression.
- [ ] Mark the release successful only after the observation window and evidence review.

## 12. Stop and rollback conditions

Stop promotion or roll back when any of the following occurs:

- Secret exposure or authentication bypass.
- Cross-tenant data visibility or unauthorized mutation.
- Migration failure, schema drift, data corruption, or unsafe locking.
- Sustained elevated 5xx errors or severe latency regression.
- Payment duplication, lost callbacks, or incorrect billing state.
- Worker backlog growth with no recovery path.
- Health/readiness failure after the deployment.
- Missing logs, alerts, backups, or rollback access.
- Any release evidence item cannot be independently verified.

## Release record

| Field | Value |
|---|---|
| Release/version | |
| Commit SHA | |
| Staging deployment | |
| Production deployment | |
| Release owner | |
| Rollback owner | |
| Migration revision | |
| CI run | |
| Evidence bundle | |
| Approval time | |
| Observation completed | |
| Final decision | |
| Notes/incidents | |

## Evidence storage rules

- Store links and sanitized command output, not secrets.
- Never commit credentials, raw production data, customer tokens, or private payment data.
- Use the exact commit SHA for every attached result.
- If a check cannot run, mark it **Blocked**, explain why, assign an owner, and do not silently mark it passed.
- Update `docs/SKIPPED_TESTS.md` when a test is intentionally deferred.
- Link this guide with `docs/PRODUCTION_RELEASE_CHECKLIST.md` and the generated release evidence bundle.

## Final sign-off

- [ ] Release owner: ____________________ Date: __________
- [ ] Rollback owner: ___________________ Date: __________
- [ ] Security/data owner: ______________ Date: __________
- [ ] Production approver: ______________ Date: __________

**Decision:** [ ] Approved for production  [ ] Blocked  [ ] Rolled back

**Reason/notes:**

```text

```
