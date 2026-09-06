# Intelligent Render Deploy Preflight — Admin Task Checklist

## Goal

Replace static Render build-budget assumptions with a dynamic, MCP-backed account status system. Render/API responses remain the source of truth; the cooldown is only a scheduled recheck window, never an automatic assumption that the quota has reset.

## Recommended state flow

```text
UNKNOWN -> READY -> DEPLOYING -> READY
                    |
                    v
             LIMIT_DETECTED -> COOLDOWN -> RECHECK_REQUIRED
                                      |             |
                                      |             +--> READY
                                      +----------------> COOLDOWN
```

Account records should support at least: `ready`, `unknown`, `deploying`, `limit_detected`, `cooldown`, `recheck_required`, `blocked`, and `error`.

## Database work — run manually

### 1. Create the Render account status table

Use the project migration system (Alembic/Supabase migration already used by this repository). Create a migration for a table such as `render_account_status`:

- `id` UUID/text primary key
- `account_role` varchar/text NOT NULL — `core`, `worker`, `scraper`, `mcp`
- `provider` varchar/text NOT NULL DEFAULT `render`
- `service_id` varchar/text NOT NULL
- `status` varchar/text NOT NULL
- `reason_code` varchar/text NULL — e.g. `build_time_limit`, `api_unavailable`, `missing_credentials`
- `reason_message` text NULL
- `usage_minutes` numeric NULL
- `safe_build_minutes` numeric NULL
- `detected_at` timestamptz NULL
- `last_checked_at` timestamptz NULL
- `recheck_at` timestamptz NULL
- `reset_at` timestamptz NULL when Render provides an actual reset date
- `retry_count` integer NOT NULL DEFAULT 0
- `last_error` text NULL
- `last_render_payload` jsonb NULL; redact tokens/secrets before storing
- `manual_override` boolean NOT NULL DEFAULT false
- `manual_override_by` text NULL
- `manual_override_reason` text NULL
- `created_at` timestamptz NOT NULL DEFAULT now()
- `updated_at` timestamptz NOT NULL DEFAULT now()

Add a unique constraint on `(provider, account_role, service_id)` and indexes on `(status, recheck_at)` and `(account_role, updated_at DESC)`.

### 2. Create the preflight event/history table

Create `render_preflight_events` for auditability:

- `id` UUID/text primary key
- `account_status_id` foreign key
- `workflow_run_id` text NULL
- `commit_sha` text NULL
- `event_type` text NOT NULL — `check`, `limit_detected`, `cooldown_started`, `recheck`, `ready`, `deploy_skipped`, `manual_override`
- `old_status` text NULL
- `new_status` text NOT NULL
- `reason_code` text NULL
- `details` jsonb NULL; redact secrets
- `created_at` timestamptz NOT NULL DEFAULT now()

Add indexes on `(account_status_id, created_at DESC)` and `(workflow_run_id)`.

### 3. Create alert records

Reuse `system_alerts` if appropriate; otherwise create `render_preflight_alerts` with:

- account role
- alert type
- severity
- message
- first_seen_at
- last_seen_at
- resolved_at
- notification status

Deduplicate repeated alerts by `(account_role, reason_code, unresolved)`.

### 4. Security requirements

- Enable RLS if using Supabase.
- Only admin/service roles may update status or create manual overrides.
- Regular users may not see Render API keys, raw provider payloads, or internal account identifiers.
- Encrypt or redact sensitive payload fields before persistence.
- Never store `RENDER_API_KEY_*` values in the database.
- Add retention cleanup for raw payloads/events, for example 30–90 days.

## MCP server work

### 5. Add an MCP status tool

Implement a read-only tool such as:

`get_render_account_status(account_role?: string)`

Return:

```json
{
  "account_role": "core",
  "status": "ready|unknown|cooldown|recheck_required|blocked|error",
  "reason_code": "build_time_limit",
  "usage_minutes": 197.98,
  "safe_build_minutes": 450,
  "last_checked_at": "...",
  "recheck_at": "...",
  "reset_at": null,
  "source": "render_api|cached|manual_override"
}
```

### 6. Add a controlled refresh tool

Implement an admin/service-only tool:

`refresh_render_account_status(account_role: string, force?: boolean)`

Rules:

- Query Render API and deployment history.
- Treat unknown API results as `unknown`, never as zero usage.
- Detect actual limit responses from Render API/deploy logs.
- Persist status and an audit event in one transaction.
- Do not extend the cooldown on every CI request.
- `force=true` is restricted to admins and must create a `manual_override`/`recheck` event.

### 7. Add a status summary tool

Implement:

`get_render_deploy_preflight()`

It should return all configured roles, their status, the blocking reason, next recheck time, and whether deployment is allowed.

## Cooldown and recheck rules

### 8. Use a recheck date, not a fake ready date

When a real build-time limit is detected:

- Set `status = cooldown`.
- Set `detected_at = now()`.
- Set `recheck_at = now() + interval '10 days'` only if there is no provider reset date.
- If Render supplies `reset_at`, prefer that date over the fixed 10-day interval.
- Keep the original reason and error.
- Do not move `recheck_at` forward on every request.

### 9. Recheck after cooldown

At or after `recheck_at`:

- Query Render again.
- If capacity is available, set `status = ready` and resolve the alert.
- If still limited, increment `retry_count`, record an event, and set the next recheck date using a bounded backoff.
- Cap the backoff and expose the next date to admins.
- If the provider cannot be queried, set `status = unknown` or `error`; do not mark ready.

## CI/GitHub Actions work

### 10. Replace static preflight assumptions

Update `scripts/ci/render_deploy_preflight.py` and the workflow calling it:

- Query the MCP preflight endpoint/tool or a secured backend endpoint.
- Remove static per-account output such as `coreready197.98` as the decision source.
- Render a table with: account, status, usage, cap, reason, last checked, recheck date.
- Block only accounts explicitly marked blocked/limit_detected/cooldown when the deployment requires that account.
- Fail closed for unknown provider state when the deployment would consume that account.
- Do not block unrelated services because one optional account is unavailable unless the workflow needs it.
- Export `build_allowed`, `blocked_accounts`, and `recheck_at` as workflow outputs.

### 11. Prevent unnecessary Docker builds

Ensure the preflight job runs before Docker build/push jobs and that build jobs use `needs: render-preflight` plus an explicit `if` condition. The skipped reason must appear in the GitHub Step Summary.

### 12. Add workflow concurrency

Use a concurrency group per account/service so multiple deployments cannot race against the same Render account:

```yaml
concurrency:
  group: render-${{ matrix.account_role }}
  cancel-in-progress: false
```

## Scheduler/automation work

### 13. Schedule rechecks

Add one scheduled job (GitHub Actions cron, backend scheduler, or existing workflow scheduler) that runs daily and calls the MCP refresh operation only for records whose `recheck_at <= now()`.

The scheduler must be idempotent and safe to retry.

### 14. Add alerting

Notify admins when:

- A limit is detected.
- A deployment is skipped.
- A cooldown recheck succeeds.
- A cooldown recheck fails again.
- Render API credentials/service IDs are missing.
- Status remains unknown beyond the configured threshold.

## Admin UI/API work

### 15. Add admin status endpoint

Expose an admin-protected endpoint such as:

- `GET /api/v1/admin/render/preflight`
- `POST /api/v1/admin/render/accounts/:role/recheck`
- `POST /api/v1/admin/render/accounts/:role/override`

Return masked, operator-friendly data only.

### 16. Add admin dashboard section

Show:

- Current status per account.
- Usage and safe cap.
- Reason and provider source.
- Last check and next recheck.
- Event history.
- Recheck now action.
- Manual override with required reason.

## Testing checklist

### 17. Unit tests

- Parse Render deployment timestamps correctly.
- Usage is never treated as zero when data is missing.
- Limit response creates cooldown exactly once.
- Repeated checks do not extend the existing cooldown.
- A successful recheck returns the account to ready.
- A failed recheck creates a new event and bounded next date.
- Provider/API errors produce unknown/error status.
- Manual override is audited.
- Secrets are absent from persisted payloads and logs.

### 18. Integration tests

- MCP status tool reads current DB state.
- MCP refresh tool updates DB and event history atomically.
- CI preflight blocks only the required account.
- Unknown status fails closed for a deployment that needs that account.
- Optional accounts do not block unrelated deployments.
- Admin endpoint rejects normal users.

### 19. Regression checks

Run:

- Existing backend test suite.
- Existing frontend test suite.
- Silent error detector.
- Secret scan.
- Migration upgrade/downgrade test.
- GitHub Actions YAML validation.
- Render preflight script with fixtures for ready, blocked, unknown, API timeout, and reset scenarios.

## Manual rollout order

1. Apply database migrations.
2. Configure MCP database access and Render API credentials through the secret manager.
3. Deploy MCP status/read tools.
4. Backfill one status row for each Render role.
5. Run manual refresh and verify stored status/events.
6. Enable admin endpoint/UI.
7. Run CI in report-only mode for several runs.
8. Compare MCP results with Render dashboard.
9. Enable blocking mode after results match.
10. Remove the old static hardcoded thresholds only after the dynamic path is proven.
11. Keep a documented manual override and rollback procedure.

## Acceptance criteria

- No deployment decision depends on hardcoded current usage values.
- Every status includes source, last check, reason, and next recheck when applicable.
- Ten-day cooldown is a recheck schedule, not a readiness assumption.
- Repeated CI runs do not extend cooldown dates.
- All state transitions are auditable.
- Render credentials never enter logs, database payloads, or GitHub summaries.
- A provider outage produces an explicit unknown/error state and safe CI behavior.
- Admins can manually recheck or override with an audit reason.

## Rollback

If the MCP/database path fails, switch CI to report-only mode, preserve the last known status, and require manual approval for deployment. Do not restore numeric hardcoded usage values as a silent fallback; use an explicit `unknown/manual_review` state instead.

## Suggested first implementation slice

1. Database migrations for `render_account_status` and `render_preflight_events`.
2. MCP `get_render_deploy_preflight` and `refresh_render_account_status`.
3. Dynamic CI preflight integration in report-only mode.
4. Tests and secret redaction.
5. Enable blocking mode after comparison with Render.

This document is intentionally a manual execution checklist; apply migrations, secret configuration, MCP wiring, and GitHub workflow changes manually in the order above.

## SupremeAI control-plane handoff — database work required manually

The repository now contains provider-neutral contracts and a local deterministic fake store in `backend/core/contracts/`, plus the unexecuted schema draft `backend/database/migrations/manual/20260907_canonical_control_plane.sql`. Because database access was not granted, the following items remain manual and must be completed before claiming durable control-plane support:

1. Review and apply the canonical execution, event, and approval SQL draft through the approved migration workflow; replace placeholder tenant authorization with the project’s real membership function.
2. Introspect every created column, default, foreign key, index, unique constraint, trigger, and RLS policy. Confirm tenant/workspace scoping on every row and reject cross-tenant reads and writes.
3. Create restricted server-side RPCs for execution creation, status transitions, event append, idempotency replay, approval issue/consume, audit append, and preflight refresh. Pin `search_path`, revoke public execute, and grant only the service/admin roles.
4. Configure Supabase Data API exposure and Realtime publication only for the required tables. Verify event replay, sequence ordering, duplicate suppression, and tenant filtering.
5. Configure retention jobs for executions, events, approvals, raw provider payloads, artifacts, and audit evidence; verify backup and restore in staging.
6. Connect and authorize MCP tools for read-only status, controlled refresh, deploy preflight, and admin audit. Require idempotency keys, redaction, authorization, and audit events for every mutating operation.
7. Configure secrets and provider identifiers in the secret manager only: Render roles/service IDs, model keys, MCP credentials, webhook signing secrets, browser egress controls, and environment-specific values. Never persist provider keys or raw secret-bearing payloads.
8. Run the integration/adversarial checks: forged actor, IDOR/BOLA, cross-tenant access, approval replay/expiry, duplicate event append, retry/restart recovery, cancellation, unknown provider state, and secret redaction.
9. Apply in staging first, run database advisors/security checks, migration upgrade/downgrade checks, RLS inspection, orphan/tenant-isolation queries, and realtime delivery checks. Attach outputs to the release evidence bundle before production rollout.
10. Configure the daily due-record scheduler and alert delivery. Ensure retries are idempotent and only records with `recheck_at <= now()` are refreshed.

### Local-only completion status

- Completed locally: merge-policy registry, decision evidence, route inventory/drift, deployment evidence/integrity, route knowledge graph/query/impact reports, canonical contracts, deterministic fake persistence, contract tests, and manual schema draft.
- Not complete locally or remotely: live database migration, RLS authorization verification, Supabase/MCP wiring, secret configuration, scheduler, production adapters, deployment rollout, and production acceptance evidence.
