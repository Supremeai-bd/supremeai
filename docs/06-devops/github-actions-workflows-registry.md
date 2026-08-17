# 🚀 SupremeAI 2.0 — GitHub Actions Workflows & Jobs Registry

This document serves as the complete, authoritative registry of all **12 GitHub Actions Workflows** and their respective **jobs** in the `supremeai` monorepo.

---

## 📑 Quick Navigation Index

| Workflow Name | Trigger(s) | Total Jobs | Purpose & Category |
|---|---|---|---|
| 1. [🧠 SupremeAI Core CI](#1--supremeai-core-ci-supreme-core-ciyml) | Push (`main`, `develop`), PR, Daily Cron (`00:00 UTC`), Dispatch | 21 Jobs (Graph Nodes) | Core Quality Gate, Testing, Security, Docker & Multi-Target Deploy |
| 2. [🤖 Manual Maintenance & Auto-Fix](#2--manual-maintenance--auto-fix-maintenance_pipelineyml) | Daily Cron (`02:00 UTC`), Dispatch | 17 Jobs | Automated Maintenance, Security Audit, PR Fixes & Docs |
| 3. [📦 SupremeAI Release Builder](#3--supremeai-release-builder-supreme-release-buildsyml) | Git Tag Push (`v*`), Dispatch | 2 Jobs | Cross-Platform Multi-Target Release Builds (APK, VSIX, EXE) |
| 4. [📱 SupremeAI Mobile CD (Fastlane)](#4--supremeai-mobile-cd-fastlane-supreme-mobile-cdyml) | Git Tag Push (`v*.*.*`) | 2 Jobs | Automated Mobile Store Deployments (Play Store & TestFlight) |
| 5. [Auto-Fix CI Pipeline](#5-auto-fix-ci-pipeline-auto-fixyml) | PR (`main`, `develop`), Daily Cron (`02:00 UTC`) | 3 Jobs | Automated Code Formatting, Lint Fixing & Security Auditing |
| 6. [🧹 Cache Janitor (Auto Cleanup)](#6--cache-janitor-auto-cleanup-cache-janitoryml) | Daily Cron (`03:30 UTC`), Dispatch | 1 Job | Stale/Orphaned GitHub Actions Cache Purging |
| 7. [🛡️ Database Disaster Recovery Drill](#7-database-disaster-recovery-drill-disaster-recovery-drillyml) | Quarterly Cron (`04:00 UTC 1st day`), Dispatch | 1 Job | Zero-Data-Loss Backup & Restore Verification Drill |
| 8. [⚡ k6 Performance Benchmark Drill](#8--k6-performance-benchmark-drill-k6-load-testingyml) | Weekly Cron (`Sun 02:00 UTC`), Dispatch | 1 Job | API Load & Latency Benchmark Stress Testing |
| 9. [🫀 Instance Keep-Alive](#9--instance-keep-alive-keepaliveyml) | Every 14 mins Cron (`*/14 * * * *`), Dispatch | 2 Jobs | Cold-Start Elimination for Render Free Tier Instances |
| 10. [Weekly Self-Audit Scan](#10-weekly-self-audit-scan-self-audit-scanyml) | Weekly Cron (`Mon 03:00 UTC`), PR, Dispatch | 1 Job | Pure-Python Offline AST Quality & Pattern Scanner |
| 11. [🔄 Sync from Production](#11--sync-from-production-sync-from-prodyml) | Dispatch | 1 Job | Bi-Directional Codebase Mirroring for Staging Repos |
| 12. [🤖 Agent Workflow Hooks](#12--agent-workflow-hooks-custom-agent-mds) | Event / Special Manual Dispatch | 8 Modules | Specialized AI Agent Prompt & Skill Execution Hooks |

---

## 1. 🧠 SupremeAI Core CI (`supreme-core-ci.yml`)

- **File Path:** [`.github/workflows/supreme-core-ci.yml`](file:///.github/workflows/supreme-core-ci.yml)
- **Triggers:** Push to `main`/`develop`, Pull Requests, Daily Cron (`00:00 UTC`), Manual Dispatch.
- **Concurrency:** Single active pipeline instance (`cancel-in-progress: true`).

### Exact Jobs Breakdown (18 Jobs in GitHub Graph):

1. **`changes` (Path Change Detection):**
   - *Description:* Detects file modifications across backend, frontend, docker, and docs using `dorny/paths-filter`.
2. **`pre-merge-gate` (🚧 Pre-Merge Gate - Iron Curtain):**
   - *Description:* Runs zero-gap stub data checks, security blind spot scans, Ruff linting, admin router auth checks, and HTTP timeout audit.
3. **`check-render-quota` (📊 Check Render Build Quota):**
   - *Description:* Checks Render API limits to determine whether to trigger Render Webhook deploy or use pre-built GitHub Docker image.
4. **`observability-audit` (🔬 Observability Audit - No Silent Errors):**
   - *Description:* Scans Python files to ensure no bare `except:` or swallowed exceptions exist in critical paths.
5. **`production-readiness` (🚀 Production Readiness):**
   - *Description:* Runs Safety Guard file protection validation, Multi-Model Security/Logic Validator, and Codegraph knowledge base generator.
6. **`security-audit` (🛡️ CodeQL & Trivy Security Scan):**
   - *Description:* Performs GitHub CodeQL SAST analysis and parallel Trivy vulnerability scans for Python & Node.js.
7. **`docker-build` (🐳 Build Base Image):**
   - *Description:* Builds `backend-ci-base:latest` Docker image and pushes to GitHub Container Registry (`ghcr.io`).
8. **`frontend-core` (🌐 Frontend Monorepo - Turbo):**
   - *Description:* Runs Pnpm Turborepo build & lint, Studio Client Vitest, Web Chat Vitest, and VS Code Extension unit tests.
9. **`flutter-integration-tests` (📱 Flutter Integration Test):**
   - *Description:* Runs Android & iOS simulator integration tests for mobile app on macOS runner.
10. **`backend-core` (🐍 Backend - Test):**
    - *Description:* Executes unit and integration tests using `pytest -n auto` with coverage reporting.
11. **`deploy-static-render` (🌐 Deploy Frontend - Render Static):**
    - *Description:* Triggers deploy hook for Vite static frontend client on Render.
12. **`build-backend-image` (🐳 Build & Push Backend Image):**
    - *Description:* Builds production `supremeai-backend` Docker image and pushes to GHCR.
13. **`deploy-backend` (🚀 Deploy Backend - Cloud Run):**
    - *Description:* Deploy API image to Google Cloud Run (Disabled when Render is active).
14. **`build-and-release-desktop` (🖥️ Build & Release Desktop App):**
    - *Description:* Matrix build job executing Tauri builds across macOS, Linux, and Windows for desktop distribution.
15. **`canary-deploy` (🚀 Canary Deploy Backend - Cloud Run):**
    - *Description:* Performs canary traffic-splitting deployment on Cloud Run.
16. **`deploy-user-backend` (🚀 Deploy User Backend - Render):**
    - *Description:* Triggers isolated deployment for User/Customer API backend service on Render.
17. **`deploy-admin-backend` (🚀 Deploy Admin Backend - Render):**
    - *Description:* Triggers isolated deployment for God-Mode Admin API backend service on Render.
18. **`deploy-combined-backend` (🚀 Deploy Combined Backend - Render):**
    - *Description:* Deploys combined Admin & User backend when monorepo changes affect both roles.
19. **`deploy-admin-firebase` (🚀 Deploy Admin Portal - Firebase):**
    - *Description:* Builds and deploys Admin Studio Client frontend to Firebase Hosting.
20. **`deploy-user-vercel` (🚀 Deploy User Portal - Vercel):**
    - *Description:* Builds and deploys User Portal frontend to Vercel.
21. **`sync-mirror` (📤 Sync to Secondary Repo):**
    - *Description:* Mirrors latest production commits to secondary/staging repository (`SaifulHaqueNiloy/supremeai`).

---

## 2. 🤖 Manual Maintenance & Auto-Fix (`maintenance_pipeline.yml`)

- **File Path:** [`.github/workflows/maintenance_pipeline.yml`](file:///.github/workflows/maintenance_pipeline.yml)
- **Triggers:** Daily Cron (`02:00 UTC`), Manual Workflow Dispatch.

### Exact Jobs Breakdown (16 Jobs):

1. **`gatekeeper` (🚦 Check 24h Gap):**
   - *Description:* Enforces 24-hour execution gap for scheduled runs to avoid wasted GitHub runner minutes.
2. **`setup` (Pipeline Initializer & Dependency Cache):**
   - *Description:* Generates Python requirement cache keys and exports backend dependencies.
3. **`health-check` (🩺 Run Health Check):**
   - *Description:* Executes `tools.health_checker` script to verify backend service modules.
4. **`auto-lint-fix` (💅 Run Auto-Lint & Format Fix):**
   - *Description:* Runs `ruff check --fix`, `black`, and `isort`, submitting an automated Pull Request with formatting fixes.
5. **`dependency-vulnerability-scan` (📦 Run Vulnerability Scan):**
   - *Description:* Exports lightweight `reqs.txt` and runs `pip-audit` to scan Python packages for CVEs in <15s.
6. **`generate-codebase-docs` (📝 Auto-Generate & Deploy Docs):**
   - *Description:* Generates OpenAPI specifications, updates `API-swagger.yaml`, and builds Docusaurus site for GitHub Pages.
7. **`worker-test` (⚡ Cloudflare Worker Test):**
   - *Description:* Runs Vitest tests for Cloudflare Worker script `scripts/cloudflare_worker.test.mjs`.
8. **`generate-db-schema` (📊 Generate DB Schema Diagram):**
   - *Description:* Generates visual ERD database diagrams using `erdantic api.routes.task` and Graphviz.
9. **`performance-e2e-test` (🧪 Human Simulation & Load Tests):**
   - *Description:* Boots FastAPI server & Vite preview client, executing Playwright end-to-end accessibility & chat tests.
10. **`ci-failure-smart-summary` (🧠 Smart CI Failure Summary):**
    - *Description:* Analyzes logs from failed CI pipeline runs and generates AI-driven diagnostic summaries.
11. **`outdated-dependency-report` (📦 Outdated Dependency Report):**
    - *Description:* Checks for outdated Python and Node.js packages and logs a Markdown comparison table.
12. **`auto-dependency-upgrade` (📦 Auto Dependency Upgrade PR):**
    - *Description:* Upgrades non-major Poetry & Pnpm packages via AI agent and submits an automated Pull Request.
13. **`changelog-generator` (📝 Changelog Generator Auto PR):**
    - *Description:* Parses git commits from past 30 days and generates an updated `CHANGELOG.md` PR.
14. **`cache-purge` (🗑️ Purge Redis Cache):**
    - *Description:* Triggers HTTP `FLUSHDB` to Upstash Redis REST API to clear server caches.
15. **`api-health-check` (Generate API Health Report):**
    - *Description:* Runs `scripts/generate_api_health_report.py` to compare FastAPI routes against pytest test coverage.
16. **`cost-guard-defcon` (Run Cost Guard):**
    - *Description:* Evaluates API token consumption and cloud metrics to enforce Zero-Cost operating policies.
17. **`ai-db-optimizer` (AI Database Index Optimizer):**
    - *Description:* Analyzes query execution plans and uploads Playwright/E2E test report artifacts.

---

## 3. 📦 SupremeAI Release Builder (`supreme-release-builds.yml`)

- **File Path:** [`.github/workflows/supreme-release-builds.yml`](file:///.github/workflows/supreme-release-builds.yml)
- **Triggers:** Git Tag Push matching `v*` (e.g., `v2.0.0`), Manual Dispatch.

### Jobs Breakdown:

1. **`build-artifacts` (Multi-Matrix Binary Builder):**
   - *Description:* Matrix build job executing across `ubuntu-latest` and `windows-latest`:
     - **APK Target:** Compiles Android `arm64-v8a` release APK with Gradle & Pub caching.
     - **VSIX Target:** Packages VS Code extension bundle using `vsce package`.
     - **EXE Target:** Compiles standalone Windows executable using PyInstaller.
2. **`publish-github-release` (GitHub Release Publisher):**
   - *Description:* Collects built APK, VSIX, and EXE artifacts and publishes them to official GitHub Releases.

---

## 4. 📱 SupremeAI Mobile CD (`supreme-mobile-cd.yml`)

- **File Path:** [`.github/workflows/supreme-mobile-cd.yml`](file:///.github/workflows/supreme-mobile-cd.yml)
- **Triggers:** Git Tag Push matching `v*.*.*`.

### Jobs Breakdown:

1. **`deploy-android` (Google Play Store Deploy):**
   - *Description:* Decodes Android Keystore JKS and Play Store JSON credentials, then triggers Fastlane to publish release AAB/APK to Google Play Console.
2. **`deploy-ios` (Apple TestFlight Deploy):**
   - *Description:* Sets up App Store Connect API keys on `macos-latest` runner and invokes Fastlane to deploy iOS build to TestFlight.

---

## 5. 🤖 Auto-Fix CI Pipeline (`auto-fix.yml`)

- **File Path:** [`.github/workflows/auto-fix.yml`](file:///.github/workflows/auto-fix.yml)
- **Triggers:** PR to `main`/`develop`, Daily Cron (`02:00 UTC`).

### Jobs Breakdown:

1. **`auto-fix` (Format & Lint Auto-Fixer):**
   - *Description:* Executes `isort`, `black`, `ruff check --fix`, and `safety scan`, then automatically commits formatted code.
2. **`vulnerability-scan` (Vulnerability Prophet Agent Scan):**
   - *Description:* Runs `VulnerabilityProphet` agent script to scan Python AST patterns for security flaws.
3. **`performance-check` (Performance Guardian Agent Check):**
   - *Description:* Executes `PerformanceGuardian` agent to check memory usage and query latencies.

---

## 6. 🧹 Cache Janitor (`cache-janitor.yml`)

- **File Path:** [`.github/workflows/cache-janitor.yml`](file:///.github/workflows/cache-janitor.yml)
- **Triggers:** Daily Cron (`03:30 UTC`), Manual Dispatch.

### Jobs Breakdown:

1. **`cleanup` (Stale Cache Remover):**
   - *Description:* Queries GitHub API for Actions caches and deletes caches older than 7 days or orphaned from closed branches.

---

## 7. 🛡️ Database Disaster Recovery Drill (`disaster-recovery-drill.yml`)

- **File Path:** [`.github/workflows/disaster-recovery-drill.yml`](file:///.github/workflows/disaster-recovery-drill.yml)
- **Triggers:** Quarterly Cron (`04:00 UTC` on 1st of every 3rd month), Manual Dispatch.

### Jobs Breakdown:

1. **`disaster_recovery_drill` (Backup & Restore Verification):**
   - *Description:* Executes `scripts/disaster_recovery_drill.py` in dry-run mode to verify point-in-time recovery capabilities on Supabase/Postgres.

---

## 8. ⚡ k6 Performance Benchmark Drill (`k6-load-testing.yml`)

- **File Path:** [`.github/workflows/k6-load-testing.yml`](file:///.github/workflows/k6-load-testing.yml)
- **Triggers:** Weekly Cron (`Every Sunday at 02:00 UTC`), Manual Dispatch.

### Jobs Breakdown:

1. **`k6_load_test` (k6 Stress & Latency Test):**
   - *Description:* Installs Grafana `k6` load testing tool and executes `k6/load_test.js` to benchmark HTTP endpoint throughput.

---

## 9. 🫀 Instance Keep-Alive (`keepalive.yml`)

- **File Path:** [`.github/workflows/keepalive.yml`](file:///.github/workflows/keepalive.yml)
- **Triggers:** Every 14 Minutes Cron (`*/14 * * * *`), Manual Dispatch.

### Jobs Breakdown:

1. **`ping-user` (Customer Web Service Ping):**
   - *Description:* Sends an HTTP GET ping to Customer API health endpoint to prevent Render free-tier instance from sleeping.
2. **`ping-admin` (Admin Control Panel Ping):**
   - *Description:* Sends an HTTP GET ping to Admin API health endpoint in parallel.

---

## 10. 🔬 Weekly Self-Audit Scan (`self-audit-scan.yml`)

- **File Path:** [`.github/workflows/self-audit-scan.yml`](file:///.github/workflows/self-audit-scan.yml)
- **Triggers:** Weekly Cron (`Mondays at 03:00 UTC`), PR to `main`/`develop`, Manual Dispatch.

### Jobs Breakdown:

1. **`self-audit` (Pure-Python AST Scanner):**
   - *Description:* Runs `scripts/quality/self_audit_scan.py` using Python standard library AST module (zero network dependencies) to detect anti-patterns.

---

## 11. 🔄 Sync from Production (`sync-from-prod.yml`)

- **File Path:** [`.github/workflows/sync-from-prod.yml`](file:///.github/workflows/sync-from-prod.yml)
- **Triggers:** Manual Dispatch (Staging repository exclusive).

### Jobs Breakdown:

1. **`sync-code` (Bi-Directional Repository Mirroring):**
   - *Description:* Fetches latest commits from production repo (`paykaribazaronline/supremeai`) and merges them into staging repo using `theirs` conflict strategy.

---

## 12. 🤖 AI Agent Custom Workflow Modules (`.github/workflows/*.md`)

- **Location:** `.github/workflows/`
- **Purpose:** Special markdown prompt definitions and capability modules invoked by AI subagents:
  1. `architect_agent.md` — Autonomous System Architect protocol.
  2. `connector_agent.md` — Multi-platform secret and API integration agent.
  3. `cost_auditor_agent.md` — Zero-cost enforcement and token budget auditor.
  4. `developer_agent.md` — Feature implementation and refactoring protocol.
  5. `guardian_expert.md` — Security and vulnerability remediation guard.
  6. `learner_agent.md` — Self-evolution and skill ingestion engine.
  7. `sentinel_agent.md` — Real-time health monitoring and anomaly detector.
  8. `ui_compliance_agent.md` — UI design aesthetic and accessibility compliance checker.

---
_Generated for SupremeAI 2.0 Monorepo — CI/CD Architecture Registry_
