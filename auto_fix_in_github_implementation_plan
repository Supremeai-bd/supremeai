# SupremeAI Smart CI — Advanced Safety & Validation Implementation Plan

> **লক্ষ্য:** Fully automatic pipeline রেখে wrong deploy, AI hallucination, এবং backup failure এর ঝুঁকি কমানো — multi-layer safety net দিয়ে। Human approval ছাড়াই।

---

## 🗺️ Current System — File Map

| File | Role | Critical Gap |
|------|------|-------------|
| [supreme-ci.yml](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-ci.yml) | Main CI/CD pipeline (1758 lines) | Deploy করে 100% traffic-এ, post-deploy monitoring নেই |
| [ci-auto-fix.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/ci-auto-fix.py) | Auto-fix engine (ruff/black/eslint) | Main branch-এ সরাসরি push করে, diff size guard নেই |
| [auto_firestore_backup.py](file:///c:/Users/n/supremeai/supremeai_2.0/scripts/backup/auto_firestore_backup.py) | Firestore backup | Operation async শুরু করে, কিন্তু completion verify করে না; rollback নেই |
| [auto_cross_cloud_replicate.py](file:///c:/Users/n/supremeai/supremeai_2.0/scripts/backup/auto_cross_cloud_replicate.py) | Cross-cloud replication | Bug: `payload.data` → should be `response.payload.data` on line 59 |
| [auto_deploy.sh](file:///c:/Users/n/supremeai/supremeai_2.0/scripts/ci/auto_deploy.sh) | Legacy deploy script | `--allow-unauthenticated` hardcoded, no health check |
| [detect-previous-failures.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/detect-previous-failures.py) | Failure detection | Only 3 consecutive failures tracked |
| [review.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/review.py) | AI code review | Single AI model, no cross-validation |

---

## ⚠️ User Review Required

> [!CAUTION]
> **এই plan implement হলে `supreme-ci.yml` এর deploy-backend job আর সরাসরি 100% traffic দেবে না।** প্রথমে 5% → 25% → 50% → 100% ধাপে যাবে। প্রতিটা ধাপে 5 মিনিট monitoring। মোট deploy time বাড়বে ~20 মিনিট।

> [!WARNING]
> **Multi-model consensus evaluator** এ Gemini + OpenAI API দুটোই call হবে। Free tier থাকলে rate limit হতে পারে। `OPENAI_API_KEY` secret না থাকলে consensus evaluator gracefully Gemini-only mode-এ চলবে।

> [!IMPORTANT]
> **Canary deploy** এর জন্য Cloud Run-এর traffic splitting ব্যবহার হবে — এটা বিনামূল্যে, কোনো extra GCP service লাগবে না।

---

## Open Questions

1. **Observation window কতক্ষণ?** প্রতিটা canary step-এ 5 মিনিট monitor করলে total ~20 min। আরো কমাতে চাইলে 2 মিনিট করা যাবে।
2. **Diff size limit কত?** Default: 300 lines OR 10 files। বড় refactor করতে চাইলে বাড়ানো যাবে।
3. **Real Firestore failover** চাই কি শুধু backup status fix করলেই চলবে? Real failover-এ GCP Global Load Balancer setup দরকার।

---

## 📦 Proposed Changes — Phase-by-Phase

---

### PHASE 1 — Diff Size Guard + Critical File Blocker
**লক্ষ্য:** Auto-fix কখনো বড় বা sensitive change করতে পারবে না।

---

#### [MODIFY] [ci-auto-fix.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/ci-auto-fix.py)

**কী বদলাবে:**
- `commit_changes()` call করার আগে একটা `guard_check()` function যুক্ত হবে
- পরিবর্তিত file count > 10 বা line diff > 300 হলে → commit block, GitHub Issue open
- Critical files (auth, db migrations, secrets handling) touched হলে → hard block
- `FIXES_APPLIED` list-এ file count এবং line stats যুক্ত হবে

**নতুন constants:**
```python
MAX_FILES_CHANGED = 10
MAX_LINES_CHANGED = 300
CRITICAL_FILE_PATTERNS = [
    "migrations/", "alembic/", 
    "core/auth", "core/security",
    ".env", "secrets"
]
```

---

#### [MODIFY] [supreme-ci.yml](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-ci.yml)

**auto-fix job-এ নতুন env var:**
```yaml
MAX_FILES_CHANGED: '10'
MAX_LINES_CHANGED: '300'
```

---

### PHASE 2 — Multi-Model Consensus Evaluator
**লক্ষ্য:** AI নিজের কাজ নিজে review না করে, independent model দিয়ে cross-validate।

---

#### [NEW] [.github/scripts/multi-model-evaluator.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/multi-model-evaluator.py)

**কী করবে:**
- `GEMINI_API_KEY` দিয়ে Gemini Flash 2.5 call করবে
- `OPENAI_API_KEY` থাকলে GPT-4o-mini দিয়েও call করবে
- দুটো model-এর verdict: `safe/unsafe`, confidence score (0-1)
- Voting rule: উভয় "safe" বললে PASS, যেকোনো একটা "unsafe" বললে BLOCK
- Output: `consensus_result`, `models_agreed`, `votes` JSON

**Structure:**
```python
def evaluate_fix_consensus(diff: str, context: str) -> dict:
    votes = []
    votes.append(evaluate_with_gemini(diff, context))
    if os.getenv("OPENAI_API_KEY"):
        votes.append(evaluate_with_openai(diff, context))
    # Minimum 2 "safe" votes needed if 2 models available
    # Minimum 1 "safe" vote needed if only 1 model available (fallback)
    ...
    return {"consensus": "safe/unsafe", "votes": votes, "agreed": bool}
```

---

#### [MODIFY] [supreme-ci.yml](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-ci.yml)

**auto-fix job-এ নতুন step (commit করার আগে):**
```yaml
- name: 🧠 Multi-Model Consensus Check
  id: consensus
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    DIFF_CONTENT: "$(git diff HEAD)"
  run: |
    python .github/scripts/multi-model-evaluator.py
```

- consensus = "unsafe" হলে → commit block, GitHub Issue open with AI reasoning

---

### PHASE 3 — Progressive Canary Deploy + Auto-Rollback
**লক্ষ্য:** 100% traffic-এ সরাসরি না দিয়ে ধাপে ধাপে দেওয়া, প্রতি ধাপে real metric check।

---

#### [NEW] [.github/scripts/canary-deploy.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/canary-deploy.py)

**কী করবে:**
1. `gcloud run services update-traffic` দিয়ে candidate revision-এ traffic দেবে
2. ধাপ: `5% → 25% → 50% → 100%`, প্রতিটায় `OBSERVATION_MINUTES` wait
3. প্রতিটা ধাপে Cloud Monitoring API দিয়ে metric চেক:
   - 5xx error rate < 1%
   - P99 latency < 2000ms
   - Request success rate > 98%
4. কোনো ধাপে threshold cross → instant rollback to previous stable revision
5. সব step PASS হলেই 100% traffic

**Rollback mechanism:**
```python
def rollback_to_stable(service, region, project, stable_revision):
    subprocess.run([
        "gcloud", "run", "services", "update-traffic", service,
        "--region", region, "--project", project,
        f"--to-revisions={stable_revision}=100"
    ])
    notify_slack_or_discord("🚨 AUTO-ROLLBACK triggered! Reverted to " + stable_revision)
```

---

#### [MODIFY] [supreme-ci.yml — deploy-backend job](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-ci.yml) (Lines 769–829)

**বদলাবে:** হেলথচেক pass করার পর সরাসরি `--to-revisions=100` না দিয়ে canary-deploy.py call করবে।

```yaml
- name: 🐤 Progressive Canary Deploy + Monitoring
  id: canary
  env:
    GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
    GCP_REGION: ${{ vars.GCP_REGION || 'us-central1' }}
    CANDIDATE_REVISION: ${{ steps.deploy.outputs.candidate_revision }}
    CANARY_STEPS: "5,25,50,100"
    OBSERVATION_MINUTES: "5"
    ERROR_RATE_THRESHOLD: "0.01"
    LATENCY_P99_THRESHOLD_MS: "2000"
    DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
  run: python .github/scripts/canary-deploy.py
```

---

### PHASE 4 — Post-Deploy Observation Window (30 min)
**লক্ষ্য:** 100% traffic দেওয়ার পরেও 30 মিনিট watch করা, ভুল হলে auto-rollback।

---

#### [NEW] [.github/scripts/post-deploy-monitor.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/post-deploy-monitor.py)

**কী করবে:**
- Deploy সম্পন্ন হওয়ার পর background-এ 30 মিনিট Cloud Logging poll করবে
- Error rate, crash count, latency ট্র্যাক করবে
- Threshold cross হলে previous stable revision-এ auto-rollback
- Discord/Slack-এ alert পাঠাবে

```python
OBSERVATION_DURATION_MINUTES = 30
CHECK_INTERVAL_SECONDS = 60
MAX_ERROR_RATE = 0.02  # 2% error rate threshold
MAX_CRASH_COUNT = 5    # 5 crashes in window
```

---

#### [MODIFY] [supreme-ci.yml](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-ci.yml)

**deploy-backend job-এর পর নতুন job:**
```yaml
post-deploy-monitor:
  name: 🔭 Post-Deploy Observation Window
  needs: [deploy-backend]
  if: needs.deploy-backend.result == 'success'
  timeout-minutes: 35
  runs-on: ubuntu-latest
  ...
```

---

### PHASE 5 — Backup Completion Verify + Rollback
**লক্ষ্য:** Backup শুরু হলেই শেষ ধরা না নিয়ে completion verify করা।

---

#### [MODIFY] [auto_firestore_backup.py](file:///c:/Users/n/supremeai/supremeai_2.0/scripts/backup/auto_firestore_backup.py)

**কী বদলাবে:**
- Export operation start করার পর `operation.result(timeout=1800)` দিয়ে 30 মিনিট poll করবে
- সফল হলে backup manifest লিখবে: `gs://bucket/manifests/latest.json`
- ব্যর্থ হলে Discord alert পাঠাবে + exit code 1
- `backup_status` field: `completed` / `failed` / `in_progress`

---

#### [MODIFY] [auto_cross_cloud_replicate.py](file:///c:/Users/n/supremeai/supremeai_2.0/scripts/backup/auto_cross_cloud_replicate.py)

**Bug fix (line 59):**
```python
# BEFORE (broken):
key_data = json.loads(payload.data.decode("UTF-8"))
# AFTER (fixed):
key_data = json.loads(response.payload.data.decode("UTF-8"))
```

**Additional:**
- Replication failure হলে retry 3x with exponential backoff
- Final failure হলে Discord alert

---

### PHASE 6 — Confidence Calibration Loop (Passive Learning)
**লক্ষ্য:** AI confidence score-এর historical accuracy track করে threshold আস্তে আস্তে adjust করা।

---

#### [NEW] [.github/scripts/confidence-calibrator.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/confidence-calibrator.py)

**কী করবে:**
- প্রতিটা auto-fix এর পর `logs/ci/calibration.json`-এ entry রাখবে:
  ```json
  {
    "run_id": "...",
    "fix_type": "backend",
    "consensus_confidence": 0.94,
    "post_deploy_outcome": "success/rollback",
    "timestamp": "..."
  }
  ```
- নতুন CI run-এ এই history পড়ে adjusted threshold calculate করবে
- যদি last 10 fix-এর 20%+ rollback হয়েছে → threshold 0.95 থেকে 0.98-এ উন্নীত

---

### PHASE 7 — Advanced Validation Report
**লক্ষ্য:** CI Report-এ শুধু pass/fail না দেখিয়ে detailed risk analysis দেখানো।

---

#### [NEW] [.github/scripts/advanced-validation-report.py](file:///c:/Users/n/supremeai/supremeai_2.0/.github/scripts/advanced-validation-report.py)

**Report-এ থাকবে:**
- 🔴/🟡/🟢 Risk Band per job
- Canary progression chart (5% → 25% → 50% → 100%)
- AI consensus vote details (কোন model কী বলল)
- Backup status + last verified timestamp
- Diff stats (files changed, lines changed)
- Rollback history (last 5 deploys)
- Confidence calibration trend

---

#### [MODIFY] [supreme-ci.yml — ci-report job](file:///c:/Users/n/supremeai/supremeai_2.0/.github/workflows/supreme-ci.yml) (Lines 1104–1407)

**বদলাবে:**
- `advanced-validation-report.py` call করবে
- Output: `logs/ci/advanced-report.md` + GitHub Step Summary update

---

## 📋 Implementation Order (Priority)

| # | Phase | Why First | Files Touched | Effort |
|---|-------|-----------|---------------|--------|
| 1 | Diff Guard | সবচেয়ে সহজ, সবচেয়ে দ্রুত risk কমায় | `ci-auto-fix.py` | Low |
| 2 | Bug Fix (line 59) | এটা active bug, যেকোনো সময় crash করবে | `auto_cross_cloud_replicate.py` | Low |
| 3 | Canary Deploy | সবচেয়ে বড় safety net | `supreme-ci.yml`, `canary-deploy.py` | Medium |
| 4 | Post-Deploy Monitor | Canary-র পরিপূরক | `post-deploy-monitor.py`, `supreme-ci.yml` | Medium |
| 5 | Multi-Model Evaluator | AI self-review বন্ধ করে | `multi-model-evaluator.py`, `supreme-ci.yml` | Medium |
| 6 | Backup Verify + Rollback | Backup সিস্টেম trustworthy করে | `auto_firestore_backup.py` | Medium |
| 7 | Advanced Report | Visibility বাড়ায় | `advanced-validation-report.py` | Low |
| 8 | Calibration Loop | Long-term self-improvement | `confidence-calibrator.py` | Low |

---

## 🔍 Verification Plan

### Automated Tests
```bash
# Phase 1 — Diff guard test
python .github/scripts/ci-auto-fix.py  # With 11 files changed → should block

# Phase 3 — Canary test (dry run)
DRY_RUN=true python .github/scripts/canary-deploy.py

# Phase 5 — Backup verify
DRY_RUN=true python scripts/backup/auto_firestore_backup.py

# Phase 6 — Report generation
python .github/scripts/advanced-validation-report.py
```

### Manual Verification
1. Push a lint-breaking commit → Watch auto-fix apply → Verify diff guard blocks if >10 files
2. Merge to main → Watch canary steps in GCP Cloud Run console (5% → 25% → 50% → 100%)
3. Introduce a bug → Verify canary stops at the failing step + auto-rollback
4. Check GitHub Step Summary for advanced report

---

## 🗂️ New Files Summary

| File | Type | Purpose |
|------|------|---------|
| `.github/scripts/multi-model-evaluator.py` | NEW | Gemini + OpenAI cross-validation |
| `.github/scripts/canary-deploy.py` | NEW | Progressive traffic shifting + metrics check |
| `.github/scripts/post-deploy-monitor.py` | NEW | 30-min post-deploy observation |
| `.github/scripts/confidence-calibrator.py` | NEW | Historical accuracy tracking |
| `.github/scripts/advanced-validation-report.py` | NEW | Rich CI report with risk bands |

| File | Type | Changes |
|------|------|---------|
| `.github/scripts/ci-auto-fix.py` | MODIFY | Diff guard, critical file blocker |
| `.github/workflows/supreme-ci.yml` | MODIFY | Canary deploy, multi-model eval, post-deploy job |
| `scripts/backup/auto_firestore_backup.py` | MODIFY | Completion polling, manifest, rollback on failure |
| `scripts/backup/auto_cross_cloud_replicate.py` | MODIFY | Bug fix line 59, retry with backoff |
