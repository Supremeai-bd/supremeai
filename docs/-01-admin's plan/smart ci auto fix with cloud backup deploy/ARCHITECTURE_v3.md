# 🏗️ SupremeAI Self-Evolving CI v3.0 — Architecture Document

## 🎯 Vision
> "SupremeAI evaluates itself, fixes itself, and deploys itself — with a 24h-delayed backup safety net"

---

## 🌍 System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEVELOPER / GITHUB                                  │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              SUPREMEAI SELF-EVOLVING CI v3.0                       │   │
│  │  (Single Pipeline — All Jobs — SupremeAI API Powered)            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GCP CLOUD                                       │
│  ┌──────────────────────────┐    ┌──────────────────────────┐              │
│  │  MAIN SERVER             │    │  BACKUP SERVER           │              │
│  │  supremeai-api           │    │  supremeai-api-backup  │              │
│  │  (us-central1)           │    │  (us-east1 / europe)     │              │
│  │                          │    │                          │              │
│  │  • Latest deployment     │    │  • Last known good       │              │
│  │  • Live traffic (100%)    │    │  • Standby (0% traffic)  │              │
│  │  • Health checked        │    │  • Auto-failover target  │              │
│  │                          │    │  • 24h+ behind main      │              │
│  └──────────────────────────┘    └──────────────────────────┘              │
│           │                              │                                   │
│           └──────────────┬───────────────┘                                   │
│                          │                                                  │
│                   Cloud Load Balancer                                        │
│                    (with health checks)                                      │
│                          │                                                  │
│                          ▼                                                  │
│                    ┌──────────┐                                              │
│                    │  USERS   │                                              │
│                    └──────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 CI Pipeline Flow (Perfect DAG)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 0: SUPREMEAI HEALTH CHECK ⭐ (NEW)                                  │
│  • Live API (supremeai-api) reachable কিনা চেক                              │
│  • Down থাকলে external AI fallback activate                                │
│  • Backup server health check                                               │
│  • Output: ai_provider = "supremeai" | "openai" | "gemini" | "local"          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: DETECT + PLAN                                                     │
│  • detect-changes → কোন জব রান করবে তা ঠিক করে                            │
│  • check-previous-failures → আগের ফেইলার চেক করে                          │
│  • combine-decisions → ফাইনাল প্ল্যান তৈরি করে                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: PARALLEL TEST JOBS (each with embedded auto-fix)                 │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ backend-test│  │ studio-build│  │ mobile-     │  │ webchat     │     │
│  │             │  │             │  │ analyze     │  │ build       │     │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │     │
│  │ │Run Tests│ │  │ │Build    │ │  │ │Analyze  │ │  │ │Build    │ │     │
│  │ └────┬────┘ │  │ └────┬────┘ │  │ └────┬────┘ │  │ └────┬────┘ │     │
│  │      │      │  │      │      │  │      │      │  │      │      │     │
│  │ ┌────▼────┐ │  │ ┌────▼────┐ │  │ ┌────▼────┐ │  │ ┌────▼────┐ │     │
│  │ │FAIL?    │ │  │ │FAIL?    │ │  │ │FAIL?    │ │  │ │FAIL?    │ │     │
│  │ │→ Call   │ │  │ │→ Call   │ │  │ │→ Call   │ │  │ │→ Call   │ │     │
│  │ │SupremeAI │ │  │ │SupremeAI │ │  │ │SupremeAI │ │  │ │SupremeAI │ │     │
│  │ │API      │ │  │ │API      │ │  │ │API      │ │  │ │API      │ │     │
│  │ │→ Fix    │ │  │ │→ Fix    │ │  │ │→ Fix    │ │  │ │→ Fix    │ │     │
│  │ │→ Branch │ │  │ │→ Branch │ │  │ │→ Branch │ │  │ │→ Branch │ │     │
│  │ └────┬────┘ │  │ └────┬────┘ │  │ └────┬────┘ │  │ └────┬────┘ │     │
│  └──────┼──────┘  └──────┼──────┘  └──────┼──────┘  └──────┼──────┘     │
│         │                │                │                │                │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: CI REPORT (collects all results + fix status + confidence)        │
│  • কোন জব পাস/ফেইল হয়েছে                                                  │
│  • কোন জবে auto-fix অ্যাপ্লাই হয়েছে                                       │
│  • প্রতিটি ফিক্সের confidence score কত                                      │
│  • Fix branches তালিকা                                                      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: SUPREMEAI EVALUATOR ⭐ (NEW)                                      │
│  • সব error logs + fixed code → SupremeAI live API `/v1/ci/evaluate`      │
│  • SupremeAI returns:                                                       │
│    - final_confidence: 0.0-1.0                                              │
│    - risk_assessment: "safe" | "caution" | "dangerous"                      │
│    - deploy_recommendation: true | false                                    │
│    - human_review_required: true | false                                    │
│  • Fallback: OpenAI/Gemini দিয়ে cross-validate                             │
│  • Output: evaluator_result JSON                                            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: DECISION ENGINE ⭐ (NEW)                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  IF evaluator.confidence >= 0.95 AND risk == "safe":               │   │
│  │    → MERGE fix branch → main                                       │   │
│  │    → PROCEED to deploy phase                                       │   │
│  │                                                                    │   │
│  │  IF evaluator.confidence >= 0.7 AND risk == "caution":           │   │
│  │    → RETRY dispatch (only failed jobs)                             │   │
│  │    → NO auto-merge (human review required)                        │   │
│  │    → CREATE GitHub issue for review                                │   │
│  │                                                                    │   │
│  │  IF evaluator.confidence < 0.7 OR risk == "dangerous":             │   │
│  │    → DELETE all fix branches                                       │   │
│  │    → STOP pipeline                                                 │   │
│  │    → CREATE GitHub issue (CRITICAL)                                │   │
│  │    → ALERT via Slack/Discord webhook                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼ (only if deploy approved)
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 6: DEPLOY (Sequential, Gated)                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  deploy-backend-main                                                │   │
│  │    ├── Step 1: Build & push Docker image to GAR                   │   │
│  │    ├── Step 2: Deploy to MAIN Cloud Run (candidate tag, 0% traffic)│   │
│  │    ├── Step 3: Health check MAIN (6 attempts, 5s interval)         │   │
│  │    ├── Step 4: IF health FAILS →                                  │   │
│  │    │            • Rollback main traffic (keep previous)           │   │
│  │    │            • Route 100% traffic to BACKUP server             │   │
│  │    │            • ALERT: "Main deploy failed, backup active"     │   │
│  │    │            • STOP further deploys                            │   │
│  │    ├── Step 5: IF health PASSES →                                  │   │
│  │    │            • Route 100% traffic to MAIN revision            │   │
│  │    │            • Write deploy manifest (logs/deploy/latest.json)│   │
│  │    │            • Schedule backup update check (24h later)       │   │
│  │    └── Step 6: Cleanup old main revisions (keep last 5)          │   │
│  │                                                                    │   │
│  │  deploy-studio (Firebase)                                         │   │
│  │    ├── Only if main deploy succeeded                              │   │
│  │    └── Download artifact → Firebase deploy                        │   │
│  │                                                                    │   │
│  │  deploy-webchat (Firebase)                                        │   │
│  │    ├── Only if main deploy succeeded                              │   │
│  │    └── Download artifact → Firebase deploy                        │   │
│  │                                                                    │   │
│  │  staging-dispatch                                                  │   │
│  │    ├── Only if all deploys succeeded                              │   │
│  │    └── Push to mirror repo                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Backup Update Strategy (24h Delayed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SEPARATE WORKFLOW: backup-update.yml (Runs every 24h)                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Step 1: Read last main deploy manifest                            │   │
│  │          (logs/deploy/latest.json)                                 │   │
│  │                                                                    │   │
│  │  Step 2: Check if deploy was >24h ago                              │   │
│  │          IF NO → SKIP (too recent)                                 │   │
│  │                                                                    │   │
│  │  Step 3: Health check MAIN server                                  │   │
│  │          IF FAIL → SKIP (main unstable, don't touch backup)       │   │
│  │                                                                    │   │
│  │  Step 4: Deploy SAME image to BACKUP server                        │   │
│  │          • supremeai-api-backup service                            │   │
│  │          • Different region (us-east1 / europe)                  │   │
│  │          • Same image SHA from main deploy                         │   │
│  │                                                                    │   │
│  │  Step 5: Health check BACKUP server                                │   │
│  │          IF PASS → Write backup manifest                           │   │
│  │          IF FAIL → Rollback backup, ALERT human                    │   │
│  │                                                                    │   │
│  │  Step 6: Write backup deploy log                                   │   │
│  │          (logs/deploy/backup-latest.json)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Failover Scenarios

### Scenario 1: Main Deploy Succeeds
```
Developer Push → CI Pass → Deploy Main → Health Pass → Route 100% to Main
                                               │
                                               ▼ (24h later)
                                        Update Backup
```

### Scenario 2: Main Deploy Fails (Health Check)
```
Developer Push → CI Pass → Deploy Main → Health FAIL → Rollback Main
                                               │
                                               ▼
                                        Route 100% to Backup
                                               │
                                               ▼
                                        ALERT: "Backup Active"
                                               │
                                               ▼
                                        STOP: No studio/webchat deploy
                                        STOP: No backup update
```

### Scenario 3: Main Server Crashes After 24h
```
Main running for 25h → Main crashes → Load Balancer detects
                                               │
                                               ▼
                                        Route 100% to Backup
                                               │
                                               ▼
                                        Backup has 24h-old code
                                               │
                                               ▼
                                        System stays UP (degraded)
                                        ALERT: "Main down, backup active"
```

### Scenario 4: SupremeAI API Down During CI
```
CI Starts → Health Check Phase 0 → SupremeAI API DOWN
                                               │
                                               ▼
                                        Fallback to OpenAI/Gemini
                                               │
                                               ▼
                                        CI continues with external AI
                                               │
                                               ▼
                                        Deploy continues (if approved)
```

---

## 📊 Confidence Score System

| Score | রঙ | Risk Level | Deploy? | Backup Update? | Human Alert? |
|-------|-----|-----------|---------|----------------|--------------|
| 0.95-1.0 | 🟢 | safe | ✅ YES | ✅ YES (after 24h) | ❌ NO |
| 0.85-0.94 | 🟡 | caution | ⚠️ MANUAL | ❌ NO | 🟡 ISSUE created |
| 0.70-0.84 | 🟠 | warning | ❌ NO (retry only) | ❌ NO | 🟡 ISSUE created |
| 0.00-0.69 | 🔴 | dangerous | ❌ NO | ❌ NO | 🔴 CRITICAL alert |

---

## 🔑 Key Design Decisions

### 1. Why 24h Delay for Backup?
- **Main server might have latent bugs** that appear after hours
- **24h observation window** catches most issues
- **Backup stays stable** while main is being validated
- **If main crashes after 12h**, backup still has last known good (36h old)

### 2. Why Separate Backup Service?
- **Different GCP region** = different failure domain
- **Independent scaling** = backup doesn't compete with main
- **Separate health checks** = backup health is independent
- **Zero traffic by default** = backup costs minimal

### 3. Why SupremeAI Evaluator?
- **Self-improving loop** = SupremeAI learns from its own mistakes
- **Domain knowledge** = SupremeAI understands its own codebase better
- **Cost efficiency** = Use own API instead of paying OpenAI
- **Fallback chain** = SupremeAI → OpenAI → Gemini → Local (never fully broken)

---

## 🗂️ File Structure

```
.github/
├── workflows/
│   ├── supreme-ci-v3.yml          # ⭐ Main CI workflow (single pipeline)
│   ├── backup-update.yml          # ⭐ Scheduled backup update (24h)
│   └── emergency-failover.yml     # ⭐ Manual failover trigger
│
├── scripts/
│   ├── ci-auto-fix-v3.py          # ⭐ Auto-fix engine (SupremeAI API first)
│   ├── supremeai-evaluator.py     # ⭐ NEW: Evaluates fixes via live API
│   ├── ci-health-check.py         # ⭐ NEW: Checks API health + backup status
│   ├── ci-decision-engine.py      # ⭐ NEW: Merges AI + confidence + risk
│   ├── deploy-backend.py          # ⭐ NEW: Deploy with failover logic
│   └── detect-previous-failures.py # Existing (unchanged)
│
└── actions/
    └── setup-backend/             # Existing (unchanged)

logs/
├── ci/                            # CI reports (existing)
│   ├── latest.json
│   └── run-{id}.json
└── deploy/                        # ⭐ NEW: Deploy manifests
    ├── latest.json                # Last main deploy info
    ├── backup-latest.json         # Last backup deploy info
    └── history/                   # Deploy history

scripts/
└── emergency-failover.sh         # ⭐ NEW: Manual failover script
```

---

## 🔧 Required GCP Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Cloud Run Service | `supremeai-api` | Main production API |
| Cloud Run Service | `supremeai-api-backup` | Backup API (different region) |
| Cloud Load Balancer | `supremeai-lb` | Routes traffic + health checks |
| Cloud Scheduler | `backup-update-job` | Triggers backup update workflow |
| GAR Repository | `supremeai-repo` | Docker images |
| Firebase Hosting | `supremeai-admin` | Studio client |
| Firebase Hosting | `supremeai-a` | Web chat |

---

## 📈 Monitoring & Alerting

### Metrics to Track:
1. `ci_evaluator_confidence` — Average confidence score per run
2. `ci_evaluator_risk_distribution` — safe/caution/dangerous counts
3. `deploy_main_success_rate` — Main deploy success %
4. `deploy_backup_lag_hours` — How far behind backup is
5. `failover_count` — How many times backup took over
6. `supremeai_api_availability` — API uptime during CI

### Alerts:
- **CRITICAL**: Main deploy failed, backup active
- **CRITICAL**: SupremeAI API down >5 min during CI
- **WARNING**: Backup >48h behind main
- **WARNING**: Confidence < 0.7 for 3 consecutive runs
- **INFO**: Backup successfully updated

---

*Document Version: 3.0*
*Date: 2026-06-26*
*Author: SupremeAI CI Architecture Team*
