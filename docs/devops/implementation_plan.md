# docs/devops — Implementation Plan

> **Source Plans:** `CI_DEBUGGING_ROADMAP.md`, `SUPREME_DEVOPS_DEPLOYMENT.md`  
> **Goal:** CI/CD pipeline stability + zero-downtime deployment + self-healing dev workflow.

---

## 1. `CI_DEBUGGING_ROADMAP.md` — 10-Step CI Triage Protocol

**Goal:** CI failure-এ guesswork শূন্য, 10-step canonical workflow দিয়ে diagnose + fix + verify।

### ✅ Already Documented (Codified as Runbook)

এই ডকুমেন্টটি **process documentation** — implementation এর পরিবর্তে এটি execute করার SOP। কোনো নতুন code দরকার নেই, তবে এটি automatable।

### 🚧 Pending Tasks

#### Step 1 — CI Triage Script (Automate 10 Steps)

- **কাজ:** 10-step workflow একটি `scripts/ci/triage.sh` script-এ automate করা
- **ফাইল:** `backend/scripts/ci/triage.sh` (new)
- **Features:**
  - Auto `git fetch + reset` (Step 1)
  - Auto `poetry install` (Step 2)
  - Auto import validation (Step 3)
  - Auto parallel test run + failure report (Steps 4-5)
- **টেস্ট:** `bash scripts/ci/triage.sh --dry-run`

#### Step 2 — Import Validation Script

- **কাজ:** `scripts/ci/validate_router_imports.py --strict` → সব `backend/*.py` import করে দেখা
- **ফাইল:** `backend/scripts/ci/validate_router_imports.py` (exists? verify)
- **টেস্ট:** `poetry run python scripts/ci/validate_router_imports.py --strict`

#### Step 3 — GitHub Actions: Self-Healing CI Job

- **কাজ:** CI fail হলে auto-comment on PR with root cause (Step 5-7 automating)
- **ফাইল:** `.github/workflows/ci.yml` → failure step-এ `scripts/ci/report_failure.py` যোগ

---

## 2. `SUPREME_DEVOPS_DEPLOYMENT.md` — Deployment Strategy

### ✅ Already Done

| Component | Status |
| --- | --- |
| Render deployment (`render.yaml`) | ✅ Active |
| Docker container | ✅ (`Dockerfile`) |
| GitHub Actions CI | ✅ (`.github/workflows/`) |
| Alembic migrations | ✅ (`alembic_migrations/`) |

### 🚧 Pending Tasks

#### Step 1 — Zero-Downtime Deploy Guard

- **কাজ:** Deploy-এর আগে health check → পুরনো instance gracefully shutdown
- **ফাইল:** `backend/core/app.py` lifespan → graceful shutdown handler verify করা
- **টেস্ট:** Render deploy করে health endpoint monitor করা

#### Step 2 — Deployment Checklist Automation

- **কাজ:** [`docs/DEPLOYMENT_CHECKLIST.md`](file:///f:/supremeai/docs/DEPLOYMENT_CHECKLIST.md) (currently empty!) পূরণ করা এবং pre-deploy script তৈরি
- **ফাইল:** `backend/scripts/pre_deploy_check.sh` (new)
- **Checklist Items:**
  - [ ] All tests pass
  - [ ] No broken imports
  - [ ] Alembic migrations up-to-date
  - [ ] `.env` secrets verified via Infisical
  - [ ] `render.yaml` validated

#### Step 3 — Rollback Script

- **কাজ:** Deploy fail হলে পূর্ববর্তী Git SHA-তে auto-rollback
- **ফাইল:** `backend/scripts/rollback.sh` (new)
- **Integration:** `CHECKPOINT.md` version number ব্যবহার করে

---

## Implementation Priority Order

```
Priority 1 (CI Stability):
  Step 2 (CI) → Import validation script verify & run
  Step 1 (CI) → CI Triage script create

Priority 2 (Deployment Safety):
  Step 2 (Devops) → Deployment checklist fill + pre-deploy script
  Step 1 (Devops) → Zero-downtime guard verify

Priority 3 (Automation):
  Step 3 (CI) → Self-healing CI GitHub Action
  Step 3 (Devops) → Rollback script
```

## Verification Gate

```bash
# Import validation
cd backend && poetry run python scripts/ci/validate_router_imports.py --strict
# → 0 import errors

# Pre-deploy check
bash scripts/pre_deploy_check.sh
# → all checks pass

# Full test
cd backend && poetry run pytest -n auto --timeout=120 -q --no-cov
```
