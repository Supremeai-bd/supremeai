# Backup & Restore Policy (AUD-5.7)

> Status: tooling exists and is wired; the enforced schedule/retention decision below
> is the recorded policy. The DBA-verified restore drill is a MANUAL step (see
> `audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md`).

## 1. What is critical persistent data

| Data | Store | Criticality | Backup mechanism |
|---|---|---|---|
| Tenancy data (users, tasks, conversations, artifacts) | Supabase/PostgreSQL (Render runtime) | CRITICAL | Supabase PITR (platform) + `scripts/backup/superai_backup_manager.py` dumps |
| Long-term memory (`ai_memory` incl. pgvector embeddings) | Postgres `ai_memory` | HIGH | included in DB dumps; embeddings are reproducible from source content |
| Skill proposals / evolution artifacts | `~/.supremeai/proposals` + SQLite/Supabase `skill_proposals` | MEDIUM | Supabase copy is canonical; local FS is ephemeral on Render |
| Configuration control plane | Postgres config tables / Infisical | HIGH | Infisical env snapshots + config registry exports |
| Uploaded attachments | Render disk + Supabase | MEDIUM | not durable on free tier; document as best-effort |

## 2. Schedules

1. **Logical dump (daily, automated):** `scripts/backup/superai_backup_manager.py create`
   via nightly `audit-release.yml` maintenance job output → stored off-box (GCS via
   `auto_cross_cloud_replicate.py` when `GCP_*` credentials are configured; otherwise the
   admin backup dump endpoint `api/routes/admin.py` provides on-demand capture).
2. **Platform PITR:** Supabase built-in continuous backup (7-day on current plan) is the
   primary recovery mechanism — **verify plan tier in the Render/Supabase dashboard (manual)**.
3. **Pre-deploy snapshot:** `SafetyRollbackManager` (wired via `core/integration_layer.py`)
   creates gzip+SHA256 in-process backups of files it mutates before any deployment-time
   change.

## 3. Retention

- Nightly logical dumps: **30 days** rolling.
- Pre-deploy snapshots: **7 days** rolling.
- Supabase PITR: per platform plan.

## 4. Restore expectations (RTO/RPO)

| Scenario | RPO | RTO | Procedure |
|---|---|---|---|
| Accidental data loss (table/row) | ≤ 24 h (nightly dump) or ≤ minutes (PITR) | ≤ 2 h | Supabase PITR restore to timestamp → verify row counts → repoint service |
| Full instance loss | ≤ 24 h | ≤ 4 h | Restore latest dump into fresh Supabase project → update `DATABASE_URL` → redeploy image → run `/api/v1/health/full` |
| Bad autonomous/self-evolution change | 0 | ≤ 15 min | `SafetyRollbackManager` rollback or Render image rollback |

## 5. Verification drill (must be executed manually, then recorded)

1. Restore the latest nightly dump into a scratch database.
2. Boot the backend against the scratch DB (`ENV=local`, `DATABASE_URL=...scratch`).
3. Assert: login works, one conversation round-trip works, `ai_memory` recall returns rows.
4. Record date/operator/SHA in `audit_reports/supreme-deep-audit-reports/REAL_TESTING_LOG.md`.
