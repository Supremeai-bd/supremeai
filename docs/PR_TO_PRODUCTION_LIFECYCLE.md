# SupremeAI PR-to-Production Lifecycle Architecture

## 1. Overview
This document specifies the authoritative, deterministic lifecycle of code in the SupremeAI monorepo from the moment a Pull Request (PR) is opened until changes are verified in production.

---

## 2. End-to-End Pipeline Workflow

```mermaid
flowchart TD
    subgraph S1["1. PR Creation & Fast Validation (< 60s)"]
        PR["Developer Opens PR"] --> FastSafety["Tier 1: Fast Safety Gate (Ubuntu)"]
        PR --> RuntimeReadiness["Tier 1: Runtime Readiness (Ubuntu)"]
        FastSafety --> RuffLint["Ruff Lint & Syntax Guard"]
        FastSafety --> SecretCheck["Secret Hygiene & Naming Guard"]
        RuntimeReadiness --> WiringAtlas["Wiring Atlas Check"]
        RuntimeReadiness --> SurfaceGuard["Public Surface Guard"]
        RuntimeReadiness --> TimeoutGuard["Timeout & Silent Failure Guard"]
    end

    subgraph S2["2. Local Heavy Verification (Local Self-Hosted Runner)"]
        FastSafety --> HeavyGate["Tier 2: Heavy Test Battery (Local PC)"]
        RuntimeReadiness --> HeavyGate
        HeavyGate --> CorePytest["Pytest Full Suite (core/ + gateway/)"]
        HeavyGate --> Typecheck["TypeScript Typecheck (studio/)"]
        HeavyGate --> DBContract["DB Schema & RLS Policy Check"]
        HeavyGate --> SAST["Bandit SAST & Security Scan"]
    end

    subgraph S3["3. Autonomous Landing & Post-Merge Triggers"]
        HeavyGate --> PRMerge["PR Merge to main"]
        PRMerge --> ResolveTargets["Resolve Production Targets (scripts/ci/plan_render_deploys.py)"]
        PRMerge --> SatSync["Federation Sync (scripts/ci/federation_satellite_sync.py)"]
        PRMerge --> EdgeDeploy["Deploy Cloudflare Edge Mesh"]
        PRMerge --> StudioDeploy["Deploy Studio UI (studio/)"]
    end

    subgraph S4["4. Production Deployment Matrix"]
        ResolveTargets --> RenderTrigger["Trigger Render Deployment"]
        RenderTrigger --> PreflightAudit["Render Quota & Preflight Audit"]
        PreflightAudit --> LiveDeploy["Deploy Backend Services (API, Gateway, Agents)"]
        LiveDeploy --> CanaryVerify["Render Canary & Synthetic Health Verification"]
        StudioDeploy --> CloudflarePages["Cloudflare Pages / Vercel Edge Deploy"]
    end

    subgraph S5["5. Live Mesh & Keep-Warm Telemetry"]
        CloudflarePages --> UserTraffic["User / Client Requests"]
        UserTraffic --> CloudflareProxy["Cloudflare Edge Proxy & Cache Mesh"]
        CloudflareProxy --> RenderCanary["Production Render Endpoints"]
        RenderCanary --> RedisTelemetry["Upstash Redis Rate Limit & Metric Mesh"]
    end
```

---

## 3. Stages Detailed Breakdown

### Stage 1: Fast Safety & Runtime Gates (Tier 1)
- **Runner:** GitHub-hosted `ubuntu-24.04` (Fast, isolated).
- **Target Execution Time:** `< 60 seconds`.
- **Components:**
  - `scripts/ops/wiring_atlas.py --check`: Validates full dependency graph and service topology.
  - `scripts/ci/secret_hygiene_guard.py`: Detects hardcoded secrets, keys, or credentials.
  - `scripts/ci/timeout_policy_guard.py`: Enforces timeout boundaries across all external API calls.
  - `scripts/ci/silent_failure_guard.py`: Forbids swallowed exceptions (`except: pass`).

### Stage 2: Heavy Gate Verification (Tier 2)
- **Runner:** Self-hosted runner (`supremeai-local-pc`) or fallback runner.
- **Components:**
  - Full backend test suites across `core/` and `gateway/`.
  - Frontend typecheck and build validation for `studio/`.
  - Database schema safety and contract validation.

### Stage 2b: Autonomous Auto-Merge (Gated)
- **Role Isolation:** Autonomous agents only write code, verify locally, and open the Pull Request. Agents must never force-merge or bypass gates.
- **Merge Condition:** The gated `auto-merge` job in `unified-pipeline.yml` executes natively once `fast-gate`, `runtime-readiness`, and `render-heavy-gate` (or fallback) pass 100%. No human or bot manual intervention is needed.

### Stage 3: Post-Merge Actions & Deployment
- **Single-Monorepo SSOT:** All builds and artifacts deploy directly from the unified monorepo.
- **Target Resolution:** `scripts/ci/plan_render_deploys.py` identifies changed services to deploy only what changed.
- **Edge Deployment:** Deploys Cloudflare Worker proxy and Studio frontend (`studio/`).

### Stage 4: Continuous Audits & Health Watchdog
- Nightly and periodic health scans via `.github/workflows/ops-maintenance.yml` and `.github/workflows/opportunistic-nightly-audit.yml`.
