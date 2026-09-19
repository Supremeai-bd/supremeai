# Backup & Restore Drill (P2)

> Status: **Procedure defined — first drill pending (owner action)**.
> Ground truth: Supabase Postgres (`<project-ref>`) is the only
> stateful system of record. Render services are stateless (rebuildable from
> this repo); anything "persisted" in Render disks or instance memory is
> disposable by design.

## What must survive a total outage

| Data | Store | Backup mechanism | Owner-verified? |
| --- | --- | --- | --- |
| App Postgres (users, contracts, chat, memory/pgvector) | Supabase | Supabase managed daily backups / PITR (plan-dependent) | ☐ owner to confirm plan + retention |
| Secrets | Infisical `prod` (138 variables) | Infisical versioning; export snapshot quarterly | ☐ schedule export |
| Object storage (uploads) | Supabase Storage | bucket replication depends on plan | ☐ owner to confirm |
| Config/feature flags | DB + env | restore with DB | n/a |
| Code & infra definitions | GitHub `SaifulHaqueNiloy/supremeai` | git itself + branch protection | ✅ |

## Quarterly restore drill (the part everyone skips — don't)

A backup that has never been restored is a rumour, not a backup. Each quarter:

1. **Freeze point**: note current `main` SHA and Infisical export timestamp.
2. **Provision scratch target**: create `supremeai-drill-<date>` Supabase
   project (or restore-branch) — NEVER drill against production.
3. **Restore**: apply the latest backup/PITR snapshot to the scratch target.
   Record elapsed time and any schema drift.
4. **Boot evidence**: run the stack against the scratch DB
   (`DATABASE_URL=postgres://…drill… SUPABASE_ALLOW_DB_DEGRADATION=false`) and
   capture `GET /health/ready` → `ready`, login of a seeded test user, one chat
   round-trip, `GET /health/full` output pasted below the drill log.
5. **Measure**: RTO = time from "disaster declared" to step 4 green. RPO =
   age of the newest restored transaction. Compare against the targets below.
6. **File it**: append the drill log to this file (dated section) and update
   the Verified column. A drill without written evidence did not happen.

## Targets (proposed, owner to ratify)

| Metric | Target | Current evidence |
| --- | --- | --- |
| RPO (max data loss) | ≤ 24 h (Supabase daily) / ≤ 5 min with PITR enabled | ☐ confirm PITR |
| RTO (core API restored) | ≤ 2 h | ☐ first drill pending |
| Restore rehearsal cadence | quarterly | never run yet |

## Supabase-specific gotchas

- `service_role` key is required for logical restores of RLS-gated tables;
  store the drill runbook copy INSIDE the restricted Infisical scope only.
- pgvector extension must be enabled on the scratch project before restore or
  memory-table copies fail mid-way.
- Auth users live in Supabase Auth (not plain tables) — verify the auth
  schema is included in the restore, then check a seeded login in step 4.
