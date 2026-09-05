# SupremeAI 2.0 — Centralized Deployment Strategy


> ⚠️ **CANONICAL DEPLOYMENT NOTICE (Audit 0.10, 2026-08-30):** The active production
> architecture is **Render (Docker runtime) + PostgreSQL/Supabase**, with the frontend on
> **Firebase Hosting**. Cloud Run / GCP deploy paths and Firebase Functions are **retired
> legacy** material kept for history only (see `_archive/`). Where this document describes
> Cloud Run, Vercel, or Firebase Functions as active infrastructure, that content is
> historical and superseded by `docs/devops/SUPREME_DEVOPS_DEPLOYMENT.md` and
> `audit_reports/supreme-deep-audit-reports/AUDIT_MASTER_CHECKLIST.md` Phase 0.
_Status: ACTIVE_  
_Last Updated: 2026-07-24_

---

## 📐 Platform Roles & Architecture Matrix

SupremeAI 2.0 operates under a strict **Zero-Cost Multi-Cloud Model**. To eliminate configuration drift and operational fragmentation, deployment targets are consolidated into well-defined primary and secondary operational roles.

| Deployment Target | Component | Primary/Secondary Role | Purpose & Responsibilities |
|---|---|---|---|
| **Render** (`render.yaml`) | FastAPI Backend | 🌟 **PRIMARY** | Hosts `supremeai-user-api` and `supremeai-admin-api` Python services with auto-deploy on `main`. |
| **Firebase** (`firebase.json`) | Frontend + Admin Dashboard | 🌟 **PRIMARY** | The only frontend deploy target wired into CI (`deploy-frontend` job in `ci.yml`, via `w9jds/firebase-action`). Hosts both the user app and admin God Mode app (`supremeai-a.web.app` / `supremeai-admin.web.app`). |
| **Vercel** | — | ❌ **NOT USED (2026-09-05 verified)** | No `vercel.json` in the repo and no `deploy-to-vercel` job in `ci.yml`. Any Vercel projects connected to this repo are auto-deploying via the Vercel GitHub App integration independently of CI, with no production purpose — they should be disconnected (Project Settings → Git → Disconnect) to stop wasting free-tier build minutes and to remove noisy unrelated check failures on PRs. |
| **Cloudflare** (`wrangler.toml`) | Edge Worker / Mesh | ⚡ **EDGE ROUTER** | Global traffic routing, DDoS protection, edge caching, and vanity domain rewrites. |
| **Netlify** (`netlify.toml`) | Frontend Mirror | 📦 **DEPRECATED / MIRROR** | Not wired into CI either. Same recommendation as Vercel above if still connected. |

---

## 🔒 Configuration Sync Policy

All sensitive environment variables across platforms MUST be kept synchronized in real-time.

```bash
# Sync secrets across all connected platforms:
python scripts/sync_all_platforms_env.py
```

---

## 🚀 Deployment Commands

- **Backend (Render):** Deployed via GitHub Actions pipeline on `git push origin main`.
- **Frontend + Admin (Firebase):** Deployed via GitHub Actions `deploy-frontend` job on `git push origin main` (or manually: `firebase deploy --only hosting`).
