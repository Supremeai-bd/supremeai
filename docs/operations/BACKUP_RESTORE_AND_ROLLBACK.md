# Backup, Restore, and Rollback Runbook

> Task: production contract closure, 2026-09-14.
> This runbook collects everything needed to recover SupremeAI after data loss or a bad
> deploy. It also discharges the reference in `docs/audits/MANUAL_STEPS.md` §6, which
> points at a `docs/operations/BACKUP_RESTORE_POLICY.md` that was never written — treat
> **this** file as that policy from now on.
>
> Contracts referenced: `docs/operations/OPERATIONAL_CONTRACTS.md` (health paths,
> role policy), `docs/deployment/ENV_EVIDENCE_MATRIX.md` (secrets inventory).

## Recovery targets (STARTERS — re-baseline after the first drill)

| Target | Definition | Starter value |
|---|---|---|
| **RPO** | Max acceptable data loss (time since last restorable backup) | **≤ 24 h** (one daily DB backup cycle) |
| **RTO** | Max acceptable time from "disaster declared" to "service restored" | **≤ 4 h** (includes detection, restore into scratch DB, cutover, verification) |

Actuals from each drill go into the drill log table at the bottom of this file.
`scripts/deploy/disaster_recovery_test.py` measures `recovery_time_minutes` per step —
use its output as the recorded number.

---

## (a) Supabase / Postgres backup policy

**Primary — Supabase managed backups.** Supabase dashboard → Database → Backups.
Scheduled backups run automatically (daily on paid plans; **free-tier projects have no
scheduled backups — only manual dashboard backups**). If the production project is on
the free tier, the GitHub Actions `pg_dump` workflow below is **mandatory**, not optional.

**Secondary — `pg_dump` via GitHub Actions (suggested).** A scheduled workflow on the
repo (public repos get free Actions minutes):

```yaml
# .github/workflows/db_backup.yml (to be added; not enforced by CI yet)
on:
  schedule:
    - cron: "0 2 * * *"   # daily 02:00 UTC
jobs:
  dump:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pg_dump "${{ secrets.SUPABASE_DATABASE_URL_WRITER }}" \
            --no-owner --format=custom --file backup_$(date -u +%F).dump
      # then upload the artifact / push to private storage; retention handled below
```

- **Retention: 7 days minimum, 30 days preferred** (matches
  `auto_firestore_backup.py`'s default `RETENTION_DAYS=30`). Rotate by deleting
  artifacts older than the window.
- Dump the **writer** URL (`SUPABASE_DATABASE_URL_WRITER`, direct port 5432 — see
  MANUAL_STEPS §7.9), not the 6543 pooler.

**Existing repo tooling (what the scripts actually do — verified, not invented):**

| Script | What it does |
|---|---|
| `scripts/backup/superai_backup_manager.py` | All-in-one backup manager. `create [--components db,env,…]` produces a compressed archive of: DB dump (Postgres/Supabase/SQLite), `.env`, git-aware source snapshot, Redis export, config files, optional logs — with SHA-256 integrity (`verify <id>`) and rotation (`max_backups=10`). Also `list`, `restore <backup_id>`, `schedule --hours N`. Default output dir: `~/my-project/backups`. ⚠️ The `.env` component contains secrets — store archives only in encrypted storage. |
| `scripts/backup/backup_telegram.py` | "Zero-knowledge" encrypted (gzip + hash) backups of Database, AI Memory, and codebase state delivered through a private Telegram bot vault. Useful as an off-site copy when no S3/GCS is available. |
| `scripts/backup/auto_firestore_backup.py` | Managed Firestore export to a GCS bucket (`BACKUP_BUCKET`, `RETENTION_DAYS=30`, optional `COLLECTION_IDS`). |
| `scripts/backup/auto_cross_cloud_replicate.py` | Initial sync + ongoing reconciliation of Firestore collections to a secondary cloud project (`SYNC_INTERVAL_MINUTES`, `BATCH_SIZE`) — multi-cloud redundancy. |
| `scripts/backup/create_desktop_backup.py` | Developer convenience: clean local project archive / AI digest / diff patches. **Not** a production DR tool. |

---

## (b) Redis (Upstash) persistence policy

- **Position: Redis data is EPHEMERAL by design.** It holds rate-limit windows, cache
  entries, and queue transport state — all rebuildable. Do not build recovery tooling
  for it; do not store the only copy of anything there.
- Upstash free tier has **no persistence by default**: on an eviction/flush, the system
  must keep working. The rate limiter (`core/rate_limit.py`) transparently falls back to
  its bounded in-memory limiter and the cache layers miss-and-refill (see contract §5).
- If a durable queue is ever required, move that workload to Supabase tables or the
  `messaging/gcp_pubsub_queue.py` adapter — do not enable Upstash persistence as a fix.
- Verify after any Redis incident: `/health/ready` stays `200` and 429s still appear
  under load (fallback active), then confirm Redis reconnected in logs.

## (c) Uploaded files / workspace directories — NOT durable

- The backend container creates `/app/data`, `/app/uploads`, `/app/logs`, `/app/tmp`
  (`backend/Dockerfile`), but **Render's filesystem is ephemeral**: every deploy, restart,
  or free-tier spin-down/scale-up **wipes them**. Same for `*.db` SQLite files used by
  degraded fallbacks (ecosystem.db, marketplace.db …).
- What this means operationally:
  1. User uploads **do not survive** any restart — if uploads must persist, write them to
     Supabase Storage (or another object store) instead of local disk.
  2. Anything that must survive (AI memory, conversation logs, billing records) must live
     in Postgres/Firestore — never only in `/app/data`.
  3. The `SUPABASE_ALLOW_DB_DEGRADATION` escape hatch (worker/scraper/mcp only — contract
     §4) explicitly trades durability for availability; never enable it on the core node
     expecting files to persist.
  4. Treat "file present on disk" as a cache, never as a record.

## (d) Secrets recovery via Infisical

- Source of truth for secrets is the **Infisical project** (slug in GitHub secret
  `INFISICAL_PROJECT_SLUG`; CI authenticates with `INFISICAL_CLIENT_ID`/`_SECRET` —
  see `.github/workflows/ci.yml`). Render/GitHub env values are *projections* of it.
- Recover a lost secret: Infisical dashboard → project → environment folder
  (e.g. `prod/…`) → copy value → re-set on the affected Render service → restart.
  Full inventory to cross-check: `docs/deployment/ENV_EVIDENCE_MATRIX.md`.
- Repo helpers (verified to exist): `scripts/deploy/add_secrets_to_infisical.py`
  (bulk push), `scripts/runtime/infisical_bootstrap.py` (local bootstrapping),
  `scripts/deploy/update_infisical_render.py` (sync Infisical → Render).
- Rotation: `scripts/security/secrets_rotation_manager.py` /
  `scripts/security/auto_secret_rotate.py`; after any rotation update the evidence
  matrix dates. **Never** recover secrets from a `superai_backup_manager.py` `.env`
  backup unless the archive is in encrypted storage — prefer Infisical as the source.

## (e) Restore drill procedure (targets: RPO ≤ 24h, RTO ≤ 4h)

Run quarterly (see checklist below). Clock every step — the measured total is the real RTO.

1. **Declare** — pick the latest restorable backup (Supabase scheduled backup, or the
   newest artifact/dump). Note its timestamp → `RPO = now − backup_time`.
2. **Integrity** — for repo-tool backups: `python scripts/backup/superai_backup_manager.py verify <backup_id>` (SHA-256 check).
3. **Restore into scratch** — restore into a **scratch** Supabase project/schema, never over
   production (dashboard restore or `pg_restore -d "$SCRATCH_URL"`).
4. **Boot against scratch** — start a staging instance (`ENV=staging`) with
   `DATABASE_URL`/`SUPABASE_DATABASE_URL_POOLER` pointed at the scratch DB.
5. **Verify function** — run the production smoke test
   (`scripts/ci/production_smoke_test.py`: health → login → `/auth/me` → chat → logout;
   env `SMOKE_BASE_URL`, `SMOKE_EMAIL`, `SMOKE_PASSWORD`, `SMOKE_SKIP_AUTH` if authless),
   plus `curl /health` (full) and one memory-recall query.
6. **Cutover or discard** — real incident: repoint the service env at the restored DB and
   redeploy. Drill: document and tear down the scratch.
7. **Automated option** — `python scripts/deploy/disaster_recovery_test.py` orchestrates
   DR test types (`database_restore`, `backup_recovery`, `region_failback`,
   `firewall_test`, `network_partition`), returns per-step status and
   `recovery_time_minutes`, and flags failures against `max_recovery_time` (default
   30 min per test; pass a config to match the 4h RTO envelope for the full drill).
8. **Record** — fill the drill log at the bottom of this file; update RPO/RTO starters
   if reality differs.

## (f) Rollback procedures

### Backend (Render)

1. **Preferred — Render dashboard:** Service → "Rollback" / previous deploy → redeploy
   the last known-good image. Render keeps prior deployments; this is the fastest
   (minutes) path and needs no rebuild.
2. **Image-based deploys** (GHCR tags): redeploy the previous tag via
   `scripts/deploy/update_render_image.py` + `scripts/deploy/trigger_render_deploy.py`
   (or the Render API) when you need a version older than the immediately previous deploy.
3. **Health gate after rollback:** `/health/ready` must be `200` before considering the
   incident closed (canonical path — contract §1). The Docker `HEALTHCHECK` uses
   `/health/live`; Render uses readiness, so a bad deploy is auto-rolled-back only if
   readiness fails during deploy — a *functional* regression needs the manual rollback.

### Frontend (Firebase Hosting / Vercel)

- **Firebase Hosting** (e.g. `supremeai-a.web.app`): `firebase hosting:rollback` from the
  project with the CLI, or Console → Hosting → previous release → "Roll back". Rollback is
  instant (edge cache swap) and does **not** require a rebuild.
- **Vercel/Render static**: Vercel → Deployments → previous → "Promote to Production".
- Frontend rollbacks are independent of backend rollbacks — roll back whichever side
  regressed; check the frontend↔backend URL contract (`OPERATIONAL_CONTRACTS.md` §6)
  if both moved.

### Database migrations — alembic downgrade caution

- **Default policy: roll code back, do NOT downgrade the schema.** Migrations must be
  additive/expand-contract so the previous app version runs against the newer schema.
- `alembic downgrade` is **destructive** (drops columns/tables, loses data written since
  upgrade). It is only permitted when: (a) the upgrade was clearly the damage source,
  (b) you have a fresh backup (§a), and (c) a maintainer explicitly runs it manually —
  never as part of an automated rollback.
- If a bad migration shipped and hot-fixed forward is impossible: restore from backup
  into scratch (§e), reconcile the delta rows, then decide. See also MANUAL_STEPS §7.10
  (wire `alembic upgrade head` into pre-deploy so drift can't accumulate).
- Boot-time DDL (`pooled_pg.execute_ddl`) is additive-only by design; it cannot undo a
  schema change.

## Quarterly drill checklist

| # | Item | Done? (date/initials) |
|---|---|---|
| 1 | Confirm latest Supabase backup / `pg_dump` artifact exists and is < 24 h old (RPO holds) | ☐ |
| 2 | Run restore drill §e end-to-end into scratch; record measured RTO | ☐ |
| 3 | Run `python scripts/deploy/disaster_recovery_test.py` and archive its JSON result | ☐ |
| 4 | Execute one backend Render rollback to previous deploy (staging first, prod if safe) and verify `/health/ready` | ☐ |
| 5 | Execute one frontend Firebase Hosting rollback in a disposable project/channel | ☐ |
| 6 | Verify Infisical exports a complete, current secret list; diff against `ENV_EVIDENCE_MATRIX.md` | ☐ |
| 7 | Confirm ephemeral-storage assumptions still hold (no critical data found under `/app/uploads`, `/app/data`) | ☐ |
| 8 | Verify backup retention window actually rotates (oldest artifact ≤ 30 days) | ☐ |
| 9 | Update RPO/RTO starter values from measurements; log in the table below | ☐ |

## Drill / incident log

| Date | Type (drill/incident) | Backup used (age) | Measured RTO | Measured RPO | Result | Notes |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | No drill recorded yet |
