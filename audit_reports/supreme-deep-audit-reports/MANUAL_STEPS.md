# MANUAL_STEPS — Actions Requiring Human / Infrastructure Access

> Generated: 2026-08-30 (audit remediation session, base `9b0eb16c42`)
> Companion to `AUDIT_MASTER_CHECKLIST.md`. Items below could not be completed in the
> offline verification sandbox because they require Docker, the Render/Supabase/GitHub
> dashboards, production traffic, or a maintainer decision.

## 1. Clean production Docker build (Phase 0.5) — requires Docker

```bash
cd backend
docker build -t supremeai-core:audit-check .
docker image ls supremeai-core:audit-check   # record size → checklist item 0.9
docker run --rm -e ENV=production -e PORT=8080 -e JWT_SECRET=<dev-only-32+chars> \
  -e DATABASE_URL=<test-db> -p 8080:8080 supremeai-core:audit-check
curl -s http://localhost:8080/api/v1/health/live   # expect 200
```

Also validates: poetry 2.4.1 pin + regenerated `poetry.lock` (AUD-7.4) build cleanly.

## 2. Deployed-environment health probe (Phase 0.7)

**Partially executed (2026-08-30, patch v3 session):** live probe on the CURRENT deployed image returned
`/api/v1/health/live` = **200** (alias `/health/live` = 200) but `/api/v1/health/ready` = **503** —
root-caused to code defects fixed in patch v3 (AUD-1.7), not to the database itself. Also note: the
currently deployed image predates patch v2.

After the next Render deploy of `main` + patch v3:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://supremeai-backend-v2.onrender.com/api/v1/health/live
curl -s -o /dev/null -w "%{http_code}\n" https://supremeai-backend-v2.onrender.com/api/v1/health/ready
```

Record both 200s in the checklist (0.7 → `[x]`). If ready remains 503 after deploy, check
`SUPABASE_DATABASE_URL_POOLER` / `DATABASE_URL` env in the Render dashboard (the fixed check now
logs the concrete failure server-side).

## 3. CI green run + coverage baseline (Phase 0.8, COV-1..7)

- Push the patch branch → verify the **AUD-1.1 "Verify Canonical Startup Command"** step
  goes green (it now probes `/api/v1/health/live`, so a wrong boot fails CI).
- Confirm the coverage gate (≥80%) passes with real Postgres; then mark
  COV-1/2 and the >=90% module gates from the CI coverage artifact.

## 4. Image signing + SBOM (AUD-6.5, AUD-7.5 deep)

1. Install/verify `cosign` in the deploy job; sign the GHCR image after
   `deploy-backend-ghcr`, e.g. `cosign sign ghcr.io/saifulhaqueniloy/supremeai/supremeai-core:<tag>`.
2. Enable Syft (or Trivy SBOM mode) in CI and attach the SBOM to the GitHub Release.

## 5. Runtime capacity baseline (Phase 0.9)

From the Render dashboard, record for the current deployment:
image size, install/boot time, memory peak. Note: the 512 MiB / ~92.8% peak
capacity warning stands — see `docs/devops/WORKER_POLICY_AND_CAPACITY_PLAN.md`.

## 6. Backup restore drill (AUD-5.7)

Execute §5 of `docs/operations/BACKUP_RESTORE_POLICY.md` (restore nightly dump into a
scratch DB, boot, run a conversation round-trip + memory recall) and log the result in
`audit_reports/supreme-deep-audit-reports/REAL_TESTING_LOG.md`.

## 7. Decisions / follow-up work (maintainer)

| # | Item | Why manual |
|---|------|-----------|
| 7.1 | Wire **real canary traffic splitting** for `AutoSkillCreator` deployments via `CanaryRolloutController` (Render has no native traffic split on free tier — needs a header/%-routing approach at the edge). | Needs infra decision |
| 7.2 | Repoint or delete the dead `core/resilience/rollback_monitor.py` (targets Cloud Run revisions) to Render image rollback. | Needs Render API integration test |
| 7.3 | Decide whether `/api/v1/evolution/forge` should require a human approval step before `SkillInstaller` (currently auto-promotes; AST+benchmark+sandbox gates pass, but ADR-0002 mandates HITL). | Product/security decision |
| 7.4 | ~~Sweep remaining routes returning `str(e)` to clients~~ **✅ DONE in patch v2 (2026-08-30)** — `keys.py`, `conversations.py` (x3, HTTPException pass-through preserves ownership 404), `preferences.py`, `admin.py` now return generic 500s with `correlation_id` (uuid) and log full detail server-side via `logger.exception`. No further action. | ~~Code sweep~~ resolved |
| 7.5 | Move HITL/audit records to append-only storage (e.g. DB table + hash chain; `cryptographic_ledger.py` already provides the chaining logic) instead of 30-day Redis retention. | Storage design decision |
| 7.6 | Firebase-admin retirement plan (Firestore tenant path + backup tooling are the last consumers). | Architecture decision |
| 7.7 | Frontend clients of the now-authenticated endpoints: markdown export UI and the CI dashboard WebSocket (`?token=`), service topology health-stream (admin token), `/agent/terminal-stream` must send the JWT. Search `frontend/src` for `ws/dashboard`, `markdown/export`, `health-stream` and attach the stored token. | Client update required — **breaking change for anonymous callers by design** |
| 7.8 | API keys: add a per-key `scopes` column if keys are ever meant to authorize routes (currently identification + rate-limit only). | Schema change |

## 8. Secrets / env checklist after merge

- No new required env vars are introduced by this patch.
- `UVICORN_WORKERS` stays unset or `1` in Render (the app now hard-fails on >1 — this was
  already the enforced policy).
- Optional: set `SUPREMEAI_PUBLIC_PATHS` only if you intentionally want to re-publicize a
  path; `/api/v1/markdown` was removed from the defaults.
