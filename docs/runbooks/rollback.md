# Rollback Runbook (Render application rollback)

**Scope:** the three Render services declared in `render.yaml` — `supremeai-api`
(`gateway/Dockerfile`), `supremeai-browser` (`browser/Dockerfile`), and
`supremeai-mcp-tower` (Node, `infrastructure/mcp-control-plane`). Render has
`autoDeploy: false` on every service, so a rollback is a **re-deploy of a
known-good commit SHA** through
[`scripts/ci/render_trigger_deploy.py`](../../scripts/ci/render_trigger_deploy.py),
not a Render-native "rollback" button.

Database recovery (Supabase PITR, data corruption) is a different procedure —
see [`docs/DISASTER_RECOVERY_RUNBOOK.md`](../DISASTER_RECOVERY_RUNBOOK.md).

---

## 1. When to roll back

Roll back when the currently deployed revision is the cause and a forward-fix
would take longer than a re-deploy:

- **Error-rate spike** after a deploy (5xx or provider errors above the
  pre-deploy baseline sustained for more than a few minutes).
- **Health checks failing** — `supremeai-api` `/healthz`, `supremeai-browser`
  `/health`, `supremeai-mcp-tower` `/health` unhealthy or flapping in Render.
- **Critical production bug** with user-visible impact (auth broken, requests
  failing, data written incorrectly) that is traced to the deployed SHA.
- **Failed or partial deploy** where the new revision is live but unhealthy,
  or where the deploy pipeline reported success while the running SHA differs
  from the expected SHA.

Do **not** roll back for: a bad config/secret value (fix the env var instead),
an external provider outage, or a database-only incident. Roll back forward
only — never force-push, never rewrite `main`.

## 2. Pre-rollback checklist

Complete all five before dispatching the workflow:

1. **Identify the last known good SHA.** Use Render → service → *Deploys*, or
   the previous successful run of `deploy-and-verify` in
   `unified-pipeline.yml`. Record the full 40-character SHA.
2. **Confirm the SHA is on `main`.** `git merge-base --is-ancestor <sha> origin/main`
   must succeed — the workflow re-checks this and refuses SHAs that are not
   ancestors of `main`.
3. **Check dependent services.** Services deploy independently. If the bad
   change spans `gateway/`, `browser/`, and `infrastructure/mcp-control-plane/`
   (or `render.yaml`/`config/service_registry.yaml`), roll back **all**
   affected services together (`service: all`) — a mixed-version fleet can be
   worse than the bad deploy.
4. **Check for schema changes.** If the bad deploy shipped a migration, read
   section 7 before dispatching.
5. **Announce it.** Post the incident, the target SHA, and the affected
   service in the on-call channel so nobody deploys `main` mid-rollback.

## 3. How to trigger

GitHub → **Actions** → **Deploy Rollback** → *Run workflow* (branch `main`):

| Input | Value |
| --- | --- |
| `service` | `api`, `browser`, `mcp-tower`, or `all` |
| `target_sha` | full 40-char SHA of the known-good commit |
| `reason` | one line: symptom + why this SHA (audit trail) |

CLI equivalent:

```bash
gh workflow run deploy-rollback.yml \
  -f service=api \
  -f target_sha=<40-char-sha> \
  -f reason="5xx spike after <bad-sha>; last known good"
```

What the run does, per service:

1. Requires the **`production`** environment approval (required reviewers).
2. Checks out the repository **at `target_sha`** (not `main`).
3. Validates the SHA exists and is an ancestor of `main`.
4. Triggers the deploy with strict mode: `EXPECTED_SHA=<target_sha>`,
   `REQUIRE_EXPECTED_SHA=1`, and waits for a terminal Render state. If Render
   cannot build that commit, the run **fails** — it will not fall back to
   branch HEAD.
5. Runs `scripts/ci/render_deploy_attestation.py` (`EXPECTED_SHA` +
   `RELEASE_URL`) to confirm the *running* revision, not just HTTP health.
6. Prints a summary annotation: service, previous SHA (main HEAD at dispatch),
   rolled-back-to SHA, reason, operator, outcome.

`service: all` produces one approval-gated job per service, so `all` may need
to be approved more than once.

**Required configuration:** secret `RENDER_API_KEY`, plus one service ID per
service — secrets `RENDER_SERVICE_ID_API`, `RENDER_SERVICE_ID_BROWSER`,
`RENDER_SERVICE_ID_MCP_TOWER`. The workflow falls back to the repository
variables already used by `scripts/ci/plan_render_deploys.py`
(`RENDER_API_SERVICE_ID`, `RENDER_SCRAPER_SERVICE_ID` / `RENDER_BROWSER_SERVICE_ID`,
`RENDER_MCP_SERVICE_ID`). If a service ID cannot be resolved, the run fails
loudly instead of skipping.

## 4. Post-rollback verification (within 10 minutes)

1. **Health:** `curl -fsS https://supremeai-api-ulw0.onrender.com/healthz`,
   `.../health` on `supremeai-browser` and `supremeai-mcp-tower`. Expect 200.
2. **Running revision:** check the attestation step output and `/release` on
   each service — the reported commit must equal `target_sha`.
3. **Smoke tests:** sign-in, one read path, one write path, and one agent or
   tool invocation through the gateway; MCP Tower `/health` plus one tool call.
4. **Monitoring:** confirm the error rate and latency return to the pre-deploy
   baseline in Grafana/Prometheus; watch for at least one full traffic window
   before declaring the incident closed.
5. **Record it:** link the workflow run in the incident; note the previous SHA,
   target SHA, and reason so the forward-fix is unambiguous.

## 5. If the rollback itself fails

1. **Build failure on the target SHA** — Render cannot build that commit (for
   example, it predates a Dockerfile change, or the build cache is broken).
   Pick an earlier known-good SHA on `main`; if none exists, forward-fix.
2. **Deploy is live but unhealthy** — do not re-run the same rollback blindly.
   Check Render logs and the service env vars; a rollback cannot fix a config
   or secret that was changed out-of-band. Fix the env var, then redeploy the
   same SHA.
3. **Attestation mismatch** — the service is up but the running SHA differs
   from the target. Treat it as a failed rollback: open the Render dashboard,
   confirm which commit is live, and re-trigger.
4. **Escalation path:** on-call engineer → service owner (CODEOWNERS for
   `gateway/`, `browser/`, `infrastructure/mcp-control-plane/`) → platform lead.
   Escalate immediately if the outage affects authentication, payments, or
   tenant data; that is a P0. If Render controls are unreachable, suspend
   traffic at the edge (Cloudflare keep-warm/proxy workers) and escalate.
5. Every failed rollback attempt is evidence for the incident — keep the run
   links rather than retrying silently.

## 6. Rollback of the rollback

A rollback is just a deploy, so the way back is the same workflow with
`target_sha` set to the revision you want to return to (usually the SHA that
was live before the rollback). Never force-push `main` or rewrite history to
"undo" a rollback; redeploy.

## 7. Database migrations are NOT reverted

The rollback workflow **only redeploys application code**. It does not touch
database state:

- Migrations applied by the bad deploy stay applied. Alembic revisions live
  under `core/alembic_migrations/` and are forward-only by convention.
- If the bad deploy changed the schema, rolling the application back can break
  it (old code against a new schema). **Coordinate with the DB owner before
  dispatching** and prefer a forward-fix migration over a manual downgrade.
- Never hand-edit production schema or run ad-hoc `downgrade` statements
  during an incident without the DB owner present.
- For data loss or corruption, stop here and follow
  [`docs/DISASTER_RECOVERY_RUNBOOK.md`](../DISASTER_RECOVERY_RUNBOOK.md)
  (Supabase PITR) instead.
