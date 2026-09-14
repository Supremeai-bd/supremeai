# Rollback Procedure (P2)

> Status: **Active procedure** — paths verified against this repo's deploy
> automation (ci-deploy-production.yml, render-deploy reusable action,
> Render auto-deploy on main, firebase web.app hosting).

## Trigger criteria (rollback when any of these is true)

1. `GET /health/ready` on core → 503 for > 10 min immediately after a deploy.
2. Error rate on core > 10% for > 5 min with a deploy in the window.
3. Data-integrity or secret-leak suspicion of any size (roll back AND open an
   incident; see kvdb.io lesson from the 2026-09-13 audit).
4. Frontend boots to a broken shell (vendor chunk crash — the PR #292
   manualChunks circular-import class of failure).

## Decision first, then act

- **Backend-only regression** → Roll back the offending Render service only.
- **Frontend-only regression** → redeploy last-good frontend build; backend
  keeps serving (health contract keeps old clients working).
- **DB migration involved** → NEVER "roll back" destructive migrations by
  redeploying old code alone; follow BACKUP_RESTORE_DRILL.md and assess data
  impact first. Code-off-new-schema must be the assumption before migrating.

## Backend (Render) rollback — 5 minutes

1. Identify last-known-good commit: the latest `main` commit whose
   post-deploy probes were green (GitHub Actions run history + Render deploy
   history both record the SHA).
2. Trigger redeploy of that commit via Render dashboard ("Deploy → latest
   commit from main" pick previous) or CLI:
   `python scripts/ci/render_trigger_deploy.py` after pinning the service to
   the known-good SHA in a branch deploy. Avoid a full CI run for speed.
3. Verify recovery on the CANONICAL probes only:
   `GET /health/live` → alive, `GET /health/ready` → ready.
4. If the rollback itself fails to boot → escalate to owner immediately
   (that indicates an env/state regression, not a code regression).

## Frontend rollback — 10 minutes

1. Rebuild from the last-known-good SHA in CI (Build Verification job also
   re-runs the frontend build-contract check — do not deploy a bundle that
   fails it).
2. Redeploy firebase hosting (web.app) with that build.
3. Verify: app boots, login works, browser console clean.

## Database schema rollback

1. Stop: check whether the migration is reversible and whether data was
   written in the new shape.
2. Forward-fix preferred: ship a migration that restores the old invariant
   instead of reversing data changes.
3. Only if irreversible AND data loss acceptable → restore per
   BACKUP_RESTORE_DRILL.md, then redeploy matching code.

## After every rollback (mandatory)

- Open a post-mortem note in `docs/audits/` within 48 h: trigger, detection
  lag, rollback lag, and the contract/test that would have caught it.
- Add the missing gate as a test in the same PR that re-lands the fix — the
  wire-first doctrine applies to CI gates too.
