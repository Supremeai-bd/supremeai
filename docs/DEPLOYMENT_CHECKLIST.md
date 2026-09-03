# SupremeAI Deployment Checklist

> Run `bash scripts/pre_deploy_check.sh` from the repo root — it automates every ☑ below.
> Target platform: **Render free tier** (backend) + **Vercel/Firebase** (frontend) + **Supabase** (DB).

---

## 1. Code Health

- [ ] All Python files compile: `python3 -m compileall backend -q` → 0 errors
- [ ] Router import check: `python3 scripts/ci/validate_router_imports.py --strict` (from repo root) → 0 failures
- [ ] Boot test: `bash scripts/check_app_boots.sh` → app boots with all routers loaded
- [ ] No `requests` usage in backend: `bash scripts/check_no_requests_in_backend.sh` (httpx only)
- [ ] Frontend typecheck passes: `cd frontend && npx tsc --noEmit`
- [ ] No frontend secrets committed: `python3 scripts/ci/check_frontend_secrets.py`
- [ ] Test suite: `cd backend && poetry run pytest -n auto -q --no-cov` (or CI tier equivalent)

## 2. Database (Supabase)

- [ ] All SQL migrations in `backend/database/migrations/` applied to the target Supabase project (idempotent — safe to re-run; key one: `15_add_user_indexes.sql`)
- [ ] Alembic heads merged, no multiple heads: `cd backend && poetry run alembic heads`
- [ ] Row Level Security enabled where required (`17_enable_rls.sql`, `18_fix_missing_rls_policies.sql`)
- [ ] Connection pooling via PgBouncer-compatible URL (port 6543) for free-tier connection limits
- [ ] Backup taken within the last 24h (`docs/operations/BACKUP_RESTORE_POLICY.md`)

## 3. Secrets & Environment

- [ ] All secrets present in Infisical/Render env — NEVER in code (verify: `python3 scripts/verify_infisical_env.py`)
- [ ] Required production vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `ADMIN_TOTP_SECRET`, `ENV=production`
- [ ] Optional provider keys present only for enabled features (GROQ/GEMINI/OPENROUTER) — system must degrade gracefully when absent
- [ ] `is_bypass_allowed` is False in production (auth bypass disabled)
- [ ] CORS origins list does NOT contain `*` in production

## 4. Render Backend

- [ ] `render.yaml`/service start command: `python main.py` (from `backend/`)
- [ ] Health check path: `/api/v1/health/live` (registered at both `/api/v1/health` and `/health`)
- [ ] Ephemeral-disk awareness: nothing critical written to local disk (learning persistence goes to Supabase/`USE_SUPABASE_VECTOR=true`; `EXPERIENCE_DB_PATH` is best-effort cache only)
- [ ] `WS_MAX_CONNECTIONS` set if different from default 50
- [ ] Free-tier spin-down accepted; keep-alive cron (if used) pings `/api/v1/health/live` only (≤1 req/min, policy-compliant)

## 5. Frontend

- [ ] Backend URL configured via env (no hardcoded localhost in production build)
- [ ] WebSocket/SSE clients implement reconnect with exponential backoff + jitter (cold starts will drop connections)
- [ ] Cold-start UX: first-load spinner/notice covers 30–60s backend wake time

## 6. Post-Deploy Verification

- [ ] `GET /api/v1/health/live` → 200 within 60s of deploy
- [ ] `GET /api/v1/health` → status "healthy" with DB check passing
- [ ] Login flow works (admin + user)
- [ ] One chat round-trip works end-to-end
- [ ] WebSocket reconnects after a forced reconnect (kill + resume tab)
- [ ] Render logs free of tracebacks for 10 minutes post-deploy: `python3 scripts/check_render_status.py`

## 7. Rollback Plan

- [ ] Previous known-good Render deploy ID noted
- [ ] `git revert` strategy understood (revert commit → push → Render auto-deploys)
- [ ] DB migrations are forward-only + idempotent; a code rollback never requires a migration rollback

---

**Gate rule:** do not deploy if any unchecked item in sections 1–3 fails.
