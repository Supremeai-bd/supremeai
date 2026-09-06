# REMAINING MANUAL STEPS — after applying supremeai-audit-patch-v2-20260830

> Source of truth: `audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md` (patched tree).
> Item 7.4 (`str(e)` sweep) was COMPLETED in patch v2 — no longer manual.
> Everything below requires Docker, dashboards (GitHub/Render/Supabase), production traffic, or a maintainer decision.

## 1. Clean production Docker build (checklist 0.5, 0.9)

```bash
cd backend
docker build -t supremeai-core:audit-check .
docker image ls supremeai-core:audit-check   # record size → checklist item 0.9
docker run --rm -e ENV=production -e PORT=8080 -e JWT_SECRET=<dev-only-32+chars> \
  -e DATABASE_URL=<test-db> -p 8080:8080 supremeai-core:audit-check
curl -s http://localhost:8080/api/v1/health/live   # expect 200
```

Also validates: poetry 2.4.1 pin + regenerated `poetry.lock` (AUD-7.4) build cleanly.
Record image size + install time in checklist 0.9, mark 0.5 `[x]` on success.

## 2. Deployed-environment health probe (checklist 0.7)

After the next Render deploy of this patch:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://supremeai-backend-v2.onrender.com/api/v1/health/live
curl -s -o /dev/null -w "%{http_code}\n" https://supremeai-backend-v2.onrender.com/api/v1/health/ready
```

Record both 200s in the checklist (0.7 → `[x]`).

## 3. CI green run + coverage baseline (checklist 0.8, COV-1..7, AUD-1.1)

- Push the patch branch → verify the **AUD-1.1 "Verify Canonical Startup Command"** step goes green.
- Confirm the coverage gate (≥80%) passes with real Postgres; then mark COV-1/2 and the ≥90% module gates from the CI coverage artifact.

## 4. Image signing + SBOM (AUD-6.5, AUD-7.5 deep)

1. Install/verify `cosign` in the deploy job; sign the GHCR image after `deploy-backend-ghcr`
   (`cosign sign ghcr.io/saifulhaqueniloy/supremeai/supremeai-core:<tag>`).
2. Enable Syft (or Trivy SBOM mode) in CI and attach the SBOM to the GitHub Release.

## 5. Runtime capacity baseline (checklist 0.9)

From the Render dashboard, record for the current deployment: image size, install/boot time, memory peak.
The 512 MiB / ~92.8% peak capacity warning stands — see `docs/devops/WORKER_POLICY_AND_CAPACITY_PLAN.md`.

## 6. Backup restore drill (AUD-5.7)

Execute §5 of `docs/operations/BACKUP_RESTORE_POLICY.md` (restore nightly dump into a scratch DB, boot,
run a conversation round-trip + memory recall) and log the result in
`audit_reports/supreme-deep-audit-reports/REAL_TESTING_LOG.md`.

## 7. Decisions / follow-up work (maintainer)

| # | Item | Why manual |
|---|------|-----------|
| 7.1 | Wire **real canary traffic splitting** for `AutoSkillCreator` deployments via `CanaryRolloutController` (Render has no native traffic split on free tier — needs a header/%-routing approach at the edge). | Needs infra decision |
| 7.2 | Repoint or delete the dead `core/resilience/rollback_monitor.py` (targets Cloud Run revisions) to Render image rollback. | Needs Render API integration test |
| 7.3 | Decide whether `/api/v1/evolution/forge` should require a human approval step before `SkillInstaller` (currently auto-promotes; AST+benchmark+sandbox gates pass, but ADR-0002 mandates HITL). | Product/security decision |
| 7.5 | Move HITL/audit records to append-only storage (e.g. DB table + hash chain; `cryptographic_ledger.py` already provides the chaining logic) instead of 30-day Redis retention. | Storage design decision |
| 7.6 | Firebase-admin retirement plan (Firestore tenant path + backup tooling are the last consumers). | Architecture decision |
| 7.7 | Frontend clients of the now-authenticated endpoints: markdown export UI and the CI dashboard WebSocket (`?token=`), service topology health-stream (admin token), `/agent/terminal-stream` must send the JWT. Search `frontend/src` for `ws/dashboard`, `markdown/export`, `health-stream` and attach the stored token. **Note:** patch v2 additionally mounts the previously-dead `service_topology` router — if your frontend consumed the health-stream before, it will now correctly REQUIRE the admin token. | Client update required — **breaking change for anonymous callers by design** |
| 7.8 | API keys: add a per-key `scopes` column if keys are ever meant to authorize routes (currently identification + rate-limit only). | Schema change |

## 8. Secrets / env checklist after merge

- No new required env vars are introduced by this patch.
- `ADMIN_URL` / `SCRAPER_URL` remain optional; when unset, the fallback defaults resolve to
  `settings.admin_url` / `settings.scraper_service_url` (also env-driven, default `""`).
- `UVICORN_WORKERS` stays unset or `1` in Render (the app hard-fails on >1 — enforced policy).
- Optional: set `SUPREMEAI_PUBLIC_PATHS` only if you intentionally want to re-publicize a path;
  `/api/v1/markdown` remains removed from the defaults. `/api/v1/auth/refresh` was ADDED to the
  defaults (fail-closed inside the endpoint; only the access-token middleware gate is skipped).
