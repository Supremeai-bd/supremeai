# Automated verification and owner-only setup

Baseline: `53b8612` (`main`). A local test or a green merge check is not proof of a live rollout. The jobs below emit evidence when the audited revision actually runs. They do not require someone to run tests or reconcile logs for every release.

## Runs automatically

| Evidence | Where to find it |
| --- | --- |
| Job-name and script-index checks; focused Python, routing (including 402, approved catalog and pre-output deadlines) and deployment contracts | Unified Pipeline on each PR, including drafts; guarded changes still require owner review before landing |
| Core, Gateway and repo test suites; separate Windows path/symlink and MCP Tower jobs | [Full Test Battery](../../.github/workflows/full-test-suite.yml), nightly and after changes to the suite or locks reach `main`. A collection failure, test failure or environment-dependent skip is not a pass. |
| Changed-service deploy, triggered deploy ID and runtime SHA attestation, independent health canary | Each Render matrix job summary. A failed sibling cannot suppress a service's canary. A healthy older revision, `UNREGISTERED`, `not_run`, or `metadata_only` is not release evidence. |
| The same exact-ID verification after an incident rollback is authorized | [Deploy Rollback](../runbooks/rollback.md); the `all` option covers Gateway, Browser and MCP only, and does not revert data migrations. |
| Effective `main` protection status and scheduled platform health evidence | Nightly Ops reports. Platform deep audit runs on its weekly cron, not on every hygiene tick. A trusted-main manual platform audit is report-only; the weekly schedule collects new evidence automatically. The open reports from 15 November are historical until new probes confirm them; they are not closed on missing evidence. The vulnerability scanner uploads its evidence even if it finds issues or another check fails. |

## Owner decisions and one-time access

- **Protect `main` server-side.** At baseline, GitHub's `protected` field was `false` and no effective branch or inherited rules were returned. Require PRs and the always-reported `PR Verification` check for the tested merge revision (after its first hosted run); block direct pushes, force-pushes, deletion and unintended bypasses. Retain routine auto-merge rather than requiring a human review on every PR. Keep risk-based protected review. A required verification check alone does not enforce that review on a UI/API merge; server-side protected-path policy must not use the current catch-all CODEOWNERS rule to require a review on every PR. Restrict the persistent runner at the runner-group/access level as well: a workflow condition is not a GitHub settings boundary. Before restricting the `production` environment to `main`, provision a separate protected PR-review environment so the current Owner Review job is not deadlocked. Restrict production mutation credentials to trusted jobs; do not grant them to the PR runner.
- **Finish the MCP cutover only if the repository still points at the old target.** `RENDER_MCP_SERVICE_ID` must select the replacement service, with its existing Paykari key under `RENDER_API_PAYKARI` (or `RENDER_API_KEY_PAYKARI`). CI reads that ID's direct URLs from Render; no old service or account fallback is attempted. Public caller endpoints such as `RENDER_MCP_URL` are separate configuration; use the verified replacement URL, not a guessed alias.
- **Remediate previously copied credentials.** CI no longer reads or writes service runtime env vars. It does not delete credentials already present. Where earlier deployments copied them, revoke/rotate the affected credentials and remove copies outside their intended service. Configure a service-specific runtime identity and Vault path or an explicitly provisioned runtime env; never send values in a ticket or PR.
- **Authorize privileged staging checks.** Billing restrictions/quotas and the relay's upstream entitlement are authoritative, not a `free` alias or a successful request. Provision the Gateway's [HMAC route policy](../../gateway/SECRETS_MODEL.md) privately and keep the authorization separate from client grants. Authorize a staging database and fixture accounts for live RLS/RPC and disconnected-worker cache tests. Offline tests do not establish staging access, real Docker builds, or live billing behavior. Optional Tower publication needs an authorized destination and token, separate from the CI result.

## Product decisions, not recurring release steps

- Worker execution and receipts: identify an actual `ecosystem:tasks` producer and durable results consumer before advertising task execution. The tracked worker remains a placeholder.
- Browser ships the relay, not `/scrape`, `/browse` or `/recipe`. Decide supported capabilities before exposing new routes.
- Confirm the authenticated sender and replay contract for the two legacy Core CI webhook registrations, supported Telegram/compatibility callers, and the real transcript storage/export path. Outbound delivery remains separate from metadata management.
- Route aliases are not six independently scoped client credentials. Define and verify client grants independently of provider entitlement. Decide the supported AutoHealer persistence contract before replacing the retired path or its older tests.
