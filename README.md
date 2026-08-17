# SupremeAI 

> **[🤖 AI AGENT INSTRUCTION]** 
> This is the central entry point for the SupremeAI project. When updating:
> 1. Keep it high-level, clear, and up-to-date with the current architecture.
> 2. Do not bloat this file with minor technical details (use other brain files for that).

SupremeAI has been significantly simplified to prioritize development speed, reduce infrastructure costs, and streamline deployments. 

## Simplified Architecture (August 2026)

### 1. Unified Repository & Services
Instead of managing multiple decoupled microservices and repositories, SupremeAI now operates on a much simpler model:
- **Backend**: A single unified Python FastAPI service (`/backend`) containing both User and Admin APIs (protected by JWT role guards).
- **Frontend**: A static React/Vite single-page application (`/frontend`), built using pnpm workspaces.

### 2. Deployment Model (Render)
We have moved away from complex GitHub Actions Docker builds and multi-target deployments.
Deployments are now managed by a single `render.yaml` Blueprint which provisions:
- **`supremeai-backend` (Web Service)**: Deploys directly from source using Poetry.
- **`supremeai-frontend` (Static Site)**: Deploys directly from source using Vite static builds.

All other legacy services (`supremeai-admin`, `supremeai-background-worker`) have been archived and suspended.

### 3. Local Development
To run the full stack locally:
```bash
# Terminal 1: Backend
cd backend
poetry install
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
pnpm install
pnpm run dev
```

### Archive
All legacy code (mobile apps, desktop apps, java workers, cloudflare workers, and complex CI pipelines) has been moved to the `_archive/` folder. This ensures nothing is permanently lost if rollback or reference is needed.
