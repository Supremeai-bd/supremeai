# SupremeAI 2.0 — Centralized Deployment Strategy

_Status: ACTIVE_  
_Last Updated: 2026-07-24_

---

## 📐 Platform Roles & Architecture Matrix

SupremeAI 2.0 operates under a strict **Zero-Cost Multi-Cloud Model**. To eliminate configuration drift and operational fragmentation, deployment targets are consolidated into well-defined primary and secondary operational roles.

| Deployment Target | Component | Primary/Secondary Role | Purpose & Responsibilities |
|---|---|---|---|
| **Render** (`render.yaml`) | FastAPI Backend | 🌟 **PRIMARY** | Hosts `supremeai-user-api` and `supremeai-admin-api` Python services with auto-deploy on `main`. |
| **Vercel** (`vercel.json`) | Studio Client | 🌟 **PRIMARY** | Hosts React 19/Vite 7 frontend (`supremeai-studio-client`) with CDN edge caching and client routing. |
| **Firebase** (`firebase.json`) | Admin Dashboard | 🛡️ **SECONDARY / FALLBACK** | Hosts static admin God Mode web application build (`supremeai-admin.web.app`). |
| **Cloudflare** (`wrangler.toml`) | Edge Worker / Mesh | ⚡ **EDGE ROUTER** | Global traffic routing, DDoS protection, edge caching, and vanity domain rewrites. |
| **Netlify** (`netlify.toml`) | Frontend Mirror | 📦 **DEPRECATED / MIRROR** | Backup mirror for client app. Recommended for decommissioning if primary Vercel target is healthy. |

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
- **Frontend (Vercel):** Deployed via Vercel GitHub Integration or `pnpm --filter=supremeai-studio-client deploy`.
- **Admin (Firebase):** `firebase deploy --only hosting`.
