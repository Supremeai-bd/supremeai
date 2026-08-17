# SupremeAI 2.0 — Blue/Green Deployment & Rollback Plan

> **Phase 17 — Rollback & Deployment Safety** · Doc-vs-Code verified against `infrastructure/`, `render.yaml`, and `apps/`.

## 1. Objective

Provide a **safe, automated default rollback path** for every SupremeAI deployment target so a bad deploy never leaves production broken without a revert strategy. This document is the **single source of truth** for blue/green (canary) deployment and rollback triggers across Cloud Run, Render, Firebase, and Docker Compose (on-premise).

## 2. Deployment Targets & Strategies

| Target | Strategy | Rollback Signal | Rollback Action |
|--------|----------|-----------------|-----------------|
| **Cloud Run (GCP)** | Blue/green via revision traffic split | Health check / readiness failure | Shift 100% traffic to previous revision |
| **Render** | Blue/green via deploy branch + manual rollback | Health probe `/api/v1/ready` failure | Render "Rollback to previous deploy" |
| **Firebase Hosting** | Atomic releases (versioned) | `firebase hosting:channel` verify fails | Redeploy previous release |
| **Docker Compose (on-prem)** | Blue/green via tagged image + compose override | `healthcheck` fails | Restart previous image tag |
| **Helm (Kubernetes)** | Blue/green via two releases | `kubectl rollout status` fails | `kubectl rollout undo` |

## 3. Blue/Green Deployment Procedure

### 3.1 Pre-Deployment Gates (must all pass)
- [ ] `infrastructure/check_deploy_gate.py` passes (deploy gate)
- [ ] `pytest --cov=backend` passes (≥ 38% coverage gate)
- [ ] `npm run build` / `pnpm build` succeeds in CI
- [ ] `npm audit --production` + `pip-audit` have no **new** P0/P1 CVEs vs baseline
- [ ] Contract tests (Phase 13.5) pass: backend ↔ studio-client/mobile endpoints all resolve
- [ ] Secrets present in target env (no `${VAR:-}` silent-empty fallbacks in prod)

### 3.2 Blue (Current) & Green (New) Flow
1. **Build green image/tag** — versioned as `<commit-sha>` (never `latest` in prod).
2. **Deploy green** alongside blue (no traffic switch yet).
3. **Run green smoke tests**:
   - `GET /api/v1/live` → 200
   - `GET /api/v1/ready` → `{"ready": true}`
   - Synthetic transaction ping (Phase 16) → success
4. **Shift traffic gradually** (canary):
   - Cloud Run: 0% → 10% → 50% → 100%
   - Observe error rate, latency, and cost metrics at each step.
5. **Keep blue live** for at least 1 observation window (default 15 min) after 100% switch before retiring.

### 3.3 Automated Rollback Trigger
Any of the following during the canary/observation window **automatically reverts** to blue:
- `GET /api/v1/ready` returns non-200 or `ready != true` for *3 consecutive* probes
- Error rate > 2% over 60s (per `metrics_collector`)
- Health probe timeout > 5s for 3 consecutive checks
- LLM cost/quota guard trips (Phase 14.75) after a deploy — proxies runaway spend regression

## 4. Rollback by Target

### 4.1 Cloud Run
```bash
# List revisions
gcloud run revisions list --service supremeai-api --region us-central1

# Shift 100% traffic to previous stable revision
gcloud run services update-traffic supremeai-api \
  --to-revisions PREVIOUS_REVISION=100 \
  --region us-central1
```

### 4.2 Render
1. Dashboard → Service → **Manual Deploy** → "Previous Deploy".
2. Or via API (if `RENDER_API_KEY` set):
```bash
curl -X POST "https://api.render.com/v1/services/$SERVICE_ID/deploys/$PREVIOUS_DEPLOY_ID/rollback" \
  -H "Authorization: Bearer $RENDER_API_KEY"
```

### 4.3 Firebase Hosting
```bash
# Deploy to preview channel first
firebase hosting:channel:deploy preview-<sha> --expires 1h

# On success, promote / rollback to previous release
firebase hosting:clone <prev> live
```

### 4.4 Docker Compose (on-premise)
See `backend/tools/devops/on_premise_deployer.py` (verified: no hardcoded secrets; uses `${POSTGRES_PASSWORD:-}`).
```bash
# Blue = previous tag, Green = new tag
docker compose -f docker-compose.prod.yml up -d --no-deps \
  --force-recreate backend=supremeai/backend:<PREV_TAG>

# Verify health
curl -f http://localhost:8000/api/v1/ready || \
  docker compose restart backend
```

### 4.5 Helm (Kubernetes)
```bash
# Blue/green via two releases
helm upgrade --install supremeai-blue ./helm/supremeai --set image.tag=<prev> -n prod
helm upgrade --install supremeai-green ./helm/supremeai --set image.tag=<new> -n prod

# Undo a bad rollout
kubectl rollout undo deployment/supremeai-backend -n prod
kubectl rollout status deployment/supremeai-backend -n prod --timeout=120s
```

## 5. Data Safety & Migration Reversibility

- **No destructive migrations auto-run on deploy.** Alembic migrations (`backend/alembic/`) must be backward-compatible (additive only) or have an explicit downgrade script reviewed pre-deploy.
- **Rollback must not lose data:** green writes go to the same DB; if schema changed, rollback requires the matching `alembic downgrade` run first.
- **Cache/Redis:** on rollback, flush the semantic cache version key to avoid serving stale green-shaped responses.

## 6. Kill Switch (Emergency)

1. **Admin kill-switch:** `POST /api/v1/swarm/halt` (verified registered in `routers.py`).
2. **LLM spend kill-switch:** `CostGuard` per-tenant/per-agent hard budget (Phase 14.75).
3. **Full stop:** set service to 0 replicas / disable route; users get 503 (fail-closed) rather than corrupted state.

## 7. Post-Rollback Checklist

- [ ] Traffic fully on blue (previous stable)
- [ ] `/api/v1/ready` healthy on all targets
- [ ] Root-cause documented (link to GitHub issue / audit finding)
- [ ] Green image tagged `broken-<sha>` for debugging (not deleted)
- [ ] Deploy gate (`check_deploy_gate.py`) updated to catch the regression class
- [ ] Contract tests + E2E re-run before next deploy attempt

## 8. Ownership & Runbook

| Role | Responsibility |
|------|----------------|
| On-call engineer | Execute rollback procedure, verify health |
| Release engineer | Run blue/green canary, observe metrics |
| Security/Architect | Review root cause, update automated guards |
| QA | Re-run contract + E2E tests post-rollback |

> **Empirical note:** This plan is aligned with the master audit's Phase 17 requirement and documented targets verified against `infrastructure/docker-compose.prod.yml`, `render.yaml`, `backend/api/routers.py`, and `backend/tools/devops/on_premise_deployer.py`.
</content>
