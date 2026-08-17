# 🏛️ The Tri-Pillar Distribution Strategy

## 1. Overview
The **Tri-Pillar Distribution Strategy** is the core architectural foundation for **SupremeAI 2.0**. By physically separating the backend, user portal, and admin portal across three specialized zero-cost/freemium platforms, we ensure maximum security, high availability, and targeted scaling.

This architecture completely eliminates "multi-platform conflicts" and brings our infrastructure into a "Stability-First Mode".

---

## 2. The Three Pillars

### ⚙️ Pillar 1: The Engine (Render)
- **Role:** Backend API & Core Logic
- **Tech Stack:** FastAPI, Python, Redis, Supabase (PostgreSQL).
- **Responsibilities:**
  - Handles all core business logic and AI orchestration.
  - Manages secure connections to the PostgreSQL database (Supabase).
  - Validates authentication tokens received from frontends.
  - Runs database migrations in complete isolation (`alembic upgrade head`).
- **Deployment:** Deployed as a Docker image via GitHub Container Registry (GHCR) and triggered via Render Deploy Hook.

### 🚀 Pillar 2: The Face (Vercel)
- **Role:** User Dashboard
- **Tech Stack:** React, Next.js/Vite (`apps/studio-client` built in `VITE_PORTAL_TYPE=user` mode).
- **Responsibilities:**
  - Handles the public-facing UI and core user interactions.
  - Communicates directly with the Render backend via API calls.
- **Deployment:** Deployed via Vercel CLI / Vercel Actions natively from the monorepo.

### 🌐 Pillar 3: The Command Center (Firebase Hosting)
- **Role:** Admin Dashboard
- **Tech Stack:** React, Vite (`apps/studio-client` built in `VITE_PORTAL_TYPE=admin` mode) or static HTML/JS (`admin/dashboard`).
- **Responsibilities:**
  - Hosts the high-privilege administrative interfaces.
  - Utlizies **Firebase Auth** for robust administrator authentication.
  - Completely isolated from the User Dashboard infrastructure to prevent cross-contamination or accidental exposure of admin privileges.
- **Deployment:** Deployed as static assets using `firebase-tools`.

---

## 3. Security & Data Flow (Critical)

1. **Authentication Flow:**
   The Admin Dashboard uses Firebase Auth to authenticate the user. Once authenticated, the client sends the Firebase `idToken` to the Render backend (`/api/admin/firebase-login`). The backend validates this token securely and issues a backend JWT if authorized.
2. **Database Isolation:**
   Neither the Vercel app nor the Firebase app connects directly to the database. All data operations pass through the **Render API**, keeping the Supabase connection string completely hidden from the frontends.
3. **CORS Restrictions:**
   The backend enforces strict CORS policies. The `CORS_ORIGINS` environment variable is explicitly set to allow only the specific Vercel and Firebase domains.

---

## 4. CI/CD Pipeline & Stability-First Mode

Our deployment pipeline (`supreme-core-ci.yml`) is designed for stability and control.

### Manual Triggers (Stability-First)
To prevent constant server restarts and downtime from minor changes or broken builds, automatic deployments on `push` are disabled. The pipeline uses `workflow_dispatch` (Manual Trigger). Deployments only happen when a developer explicitly clicks "Run workflow" in GitHub Actions after verifying tests locally.

### Parallel Deployment Jobs
When triggered, the pipeline executes three parallel jobs:
1. `deploy-to-render`: Pushes Docker image to GHCR and calls Render.
2. `deploy-to-vercel`: Builds and deploys the User Portal.
3. `deploy-frontend-prod`: Builds and deploys the Admin Portal to Firebase.

This ensures all components are perfectly synchronized and deployed at the exact same version, ensuring zero downtime.
