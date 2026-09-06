# Render সার্ভিস অডিট রিপোর্ট — SupremeAI প্রজেক্ট

**তারিখ:** 2026-09-06  
**অডিট প্রকার:** Read-Only Codebase Analysis  
**অনুসন্ধানের স্কোপ:** `F:\supremeai` পুরো repo

---

## ১. সার্ভিস রেজিস্ট্রি ও টপোলজি সামারি

| সার্ভিস নাম | প্রমাণিত URL | স্ট্যাটাস | প্ল্যাটফর্ম |
|---|---|---|---|
| `supremeai-primary-node` | `https://supremeai-primary-node.onrender.com` | Active | Render Free Tier |
| `supremeai-worker-node` | `https://supremeai-worker-node.onrender.com` | Active | Render Free Tier |
| `supremeai-scraper-node` | `https://supremeai-scraper-node.onrender.com` | Active | Render Free Tier |
| `supremeai-mcp-tower` | `https://supremeai-mcp-tower.onrender.com` | Active | Render Free Tier |
| `supremeai-backend-v2` (legacy) | `https://supremeai-backend-v2.onrender.com` | Decommissioned candidate | Render Free Tier |
| `supremeai-scraper-6nwi` (legacy) | `https://supremeai-scraper-6nwi.onrender.com` | Legacy reference | Render Free Tier |

> **সোর্স:** `docs/architecture/service_registry.yaml`, `docs/architecture/service_topology.yml`, `infrastructure/wrangler.toml`

---

## ২. চারটি আলাদা Render অ্যাকাউন্ট সিস্টেম

প্রজেক্টটি চারটি স্বতন্ত্র Render অ্যাকাউন্ট/API-key জোড়া চালায়:

| # | অ্যাকাউন্ট রোল | API Key Env Var | Default Service ID | সেটিং |
|---|---|---|---|---|
| 1 | `core` / `primary` | `RENDER_API_KEY_1` | `srv-dabm7dfqj5pc738jkbmg` | 450m cap |
| 2 | `worker` | `RENDER_API_KEY_2` | `srv-dabm7evqj5pc738jkf30` | 450m cap |
| 3 | `scraper` | `RENDER_API_KEY_3` | `srv-dabm7gfqj5pc738jkicg` | 450m cap |
| 4 | `mcp` | `RENDER_API_KEY_4` | `srv-dabm7inqj5pc738jkrt0` | 450m cap |

**অতিরিক্ত ব্যাকআপ কীগুলো:**
- `RENDER_API_KEY_BACKUP` → worker অ্যাকাউন্টে fallback হিসেবে ব্যবহৃত
- `RENDER_BACKUP_API_KEY_2` → scraper অ্যাকাউন্টে fallback হিসেবে ব্যবহৃত
- `RENDER_API_KEY` →通用 fallback হিসেবে `_1`, `_4`-এ ব্যবহৃত

> **সোর্স:** `backend/services/render_account_service.py:49-54`, `scripts/deploy_all_services.py:10-15`

---

## ৩. CI/CD ডিপ্লয়মেন্ট পাইপলাইন

### ৩.১ মূল ওয়ার্কফ্লো: `.github/workflows/ci.yml`

```
render-deploy-preflight → publish-core-image → render-budget-guard → deploy-core
                                                         → deploy-worker
                                                         → deploy-scraper
                                                         → deploy-mcp
                                                         → db-schema-check
```

**প্রতিটি deploy job-এর জন্য:**
- Core: `RENDER_API_KEY_1` + `RENDER_PRIMARY_SVC_ID`
- Worker: `RENDER_API_KEY_2` (fallback: `RENDER_API_KEY_BACKUP`) + `RENDER_WORKER_SVC_ID`
- Scraper: `RENDER_API_KEY_3` (fallback: `RENDER_BACKUP_API_KEY_2`) + `RENDER_SCRAPER_SVC_ID`
- MCP: `RENDER_API_KEY_4` + `RENDER_MCP_SVC_ID`

### ৩.২ പ്രিফ্লাইট চেক (Preflight)

`scripts/ci/render_deploy_preflight.py` দুইভাবে কাজ করে:
1. **Remote Preflight:** `RENDER_PREFLIGHT_URL` এন্ডপয়েন্ট থেকে JSON(status) পড়ে
2. **Direct Preflight:** সরাসরি Render API-তে কল করে বর্তমান মাসের build minutes হিসাব করে

### ৩.৩ Build Budget Guard

`scripts/ci/render_build_budget_guard.py`:
- ৪৫০ মিনিট threshold（500-এর মধ্যে ৯০%）
- crossed হলে `autoDeploy: "no"` সেট করে
- নিচে গেলে আবার `autoDeploy: "yes"` রিস্টোর করে

### ৩.৪ Maintenance ওয়ার্কফ্লো

`.github/workflows/maintenance.yml`-এ:
- Daily cooldown recheck scheduler চালায়
- `render-recheck-scheduler.py` বর্তমান cooldown অ্যাকাউন্টগুলো চেক করে

---

## ৪. ব্যাকএন্ড সার্ভিস ও ডাটাবেজ

### ৪.১ `RenderAccountService`

**ফাইল:** `backend/services/render_account_service.py`

ক্লাসটি যা করে:
- `get_configured_accounts()` → ৪টি অ্যাকাউন্ট লোড করে env থেকে
- `get_status_overview()` → সব অ্যাকাউন্টের aggregate status রিটার্ন করে
- `refresh_account_status()` → Render API-তে কল করে actual usage calculating, cooldown setting
- `manual_override()` → অ্যাডমিনের মাধ্যমে ম্যানুয়াল override

**ডাটাবেজ টেবিল:**
- `render_account_states` — latest known state, plan, usage, cooldown
- `render_preflight_events` — audit trail

**মাইগ্রেশন:** `backend/alembic_migrations/versions/2026_09_06_120000_add_render_account_state.py`

### ৪.২ অ্যাডমিন API

**ফাইল:** `backend/api/routes/render_preflight_admin.py`

```
GET  /api/v1/admin/render/preflight
POST /api/v1/admin/render/accounts/{role}/recheck
POST /api/v1/admin/render/accounts/{role}/override
GET  /api/v1/admin/render/events
```

> সব এন্ডপয়েন্ট `require_admin_token` + `admin_rate_limit` দিয়ে গObjectives।

---

## ৫. গোপনীয়তা ও কনফিগারেশন সমস্যা

### ৫.১ হার্ডকোডেড সার্ভিস IDs (Critical)

নিচের ফাইলগুলোতে সার্ভিস IDs হার্ডকোডেড আছে:

| ফাইল | হার্ডকোডেড ID | সমস্যা |
|---|---|---|
| `scripts/deploy/trigger_render_deploy.py` | `srv-da666f8u01pc739bm3t0` | পুরানো backend-v2 |
| `scripts/deploy/check_render.py` | `srv-da666f8u01pc739bm3t0` | পুরানো |
| `scripts/deploy/check_render_auto_deploy.py` | `srv-da666f8u01pc739bm3t0` | পুরানো |
| `scripts/deploy/check_render_svc.py` | `srv-da666f8u01pc739bm3t0` | পুরানো |
| `scripts/deploy/update_render_env2.py` | `srv-da666f8u01pc739bm3t0` | পুরানো |
| `scripts/deploy/update_infisical_render.py` | `srv-da666f8u01pc739bm3t0` | পুরানো |
| `scripts/ci/render_build_budget_guard.py` | ৪টা default_svc IDs | Fallback হিসেবে fine |
| `scripts/ci/render_trigger_deploy.py` | env থেকে নেয় (OK) | ✅ |
| `scripts/devops/set_roles.py` | env থেকে নেয় (OK) | ✅ |

**সারাংশ:** অনেক পুরানো ডিপ্লয়/চেক স্ক্রিপ্টগুলো `srv-da666f8u01pc739bm3t0` (backend-v2) hardwoodcoded ধরে রাখা আছে, যা সম্ভবত ডিরোল্ট হয়েছে।

### ৫.২ হার্ডকোডেড URL-সমূহ

| ফাইল/Dir | হার্ডকোডেড URL | সমস্যা |
|---|---|---|
| `infrastructure/wrangler.toml` | `supremeai-backend-v2.onrender.com`, `supremeai-primary-node.onrender.com` | Mixed legacy + current |
| `scripts/ci/render_trigger_deploy.py` | Debug logging এ api_key expose | **Sensitive info leak risk** |
| `backend/core/config_classification.py` | `onrender.com` placeholder logic | OK - validation code |
| `docs/ADMIN_TASKS.md` | Multiple .onrender.com URLs | Documentation only |
| `docs/architecture/multi-platform-failover-strategy.md` | Old URLs | Outdated docs |

### ৫. inconsistensies

| সমস্যা | বিবরণ |
|---|---|
| **নামকরণ inconsistensy** | `core` vs `primary`, `RENDER_PRIMARY_SVC_ID` vs `RENDER_CORE_SVC_ID` |
| **API Key fallback chain** | `RENDER_API_KEY_4` → `RENDER_API_KEY` (通用), `_2` → `_BACKUP`, `_3` → `_BACKUP_API_KEY_2` |
| **Service ID mapping** | `set_roles.py` এ `RENDER_CORE_SVC_ID` ব্যবহৃত, কিন্তু বাকicodebase-এ `RENDER_PRIMARY_SVC_ID` |
| **Deleted services referenced** | `delete_render_services.py`-এ ব环卫 service IDs আছে যা ডিলিটের পরেও রেফারেন্স বroye |

---

## ৬. গোপনীয়তা ও সুরক্ষা সংক্রান্ত উদ্বেগ

### ৬.১ API Key Distribution

```
RENDER_API_KEY      → Universal fallback (core + mcp)
RENDER_API_KEY_1    → Core/Primary account
RENDER_API_KEY_2    → Worker account
RENDER_API_KEY_3    → Scraper account
RENDER_API_KEY_4    → MCP account
RENDER_API_KEY_BACKUP → Worker backup
RENDER_BACKUP_API_KEY_2 → Scraper backup
```

**সংকেত:**
- `secrets_registry.yaml`-এ `RENDER_API_KEY_1` through `_4` ও `RENDER_BACKUP_API_KEY_2` কে **"Classified ecosystem/render key"** হিসেবে লেবেল করা হয়েছে
- `RENDER_API_KEY` এবং `RENDER_API_KEY_BACKUP` কে `important` হিসেবে চিহ্নিত

### ৬.২ API Key Leak Risk

`scripts/ci/render_trigger_deploy.py:37`:
```python
print(f"DEBUG: api_key starts with {api_key[:5]}, length={len(api_key)}")
```

এটি CI লগ-এ API key prefix expose করে। ইভেন limited character-set revealing también risk-inducing fallback পরিস্থিতিতে।

### ৬.৩ Infisical Sync Strategy

`scripts/sync_render_secrets.py`:
- Phase 3: Infisical Vault-এ সব backend URLs + IDs সেভ করে
- Phase 4: GitHub Actions secrets-এ encrypted সেভ করে
- Phase 5: Cloudflare Worker env vars আপডেট করে

**সমস্যা:** Infisical এবং GitHub Actions দুটোতে একই secret জমা থাকতে পারে, což一方面意味着 leak surface বেড়ে যাবে।

---

## ৭. সেবার ব্যবহার প্যাটার্ন

### ৭.১ Service Topology

```
admin-portal → SUPREMEAI_ADMIN_API_URL → Render Core
user-portal  → SUPREMEAI_USER_API_URL  → Render (Vercel-এ, আলাদা)
scraper      → SCRAPER_SERVICE_URL      → Render Scraper
```

**নোট:** `docs/architecture/service_topology.yml` explicitly মতিচ্ছন্নভাবে দুইটা আলাদা Render অ্যাকাউন্ট থাকা সত্ত্বেও admin ও user portal একই shared backend ব্যবহার করতে পারে — এটা integration failure-এর কারণ হয়েছে (নicho অ্যাডমিনস্ট্র্যাটর:১-৩৯ লাইন)।

### ৭.₂ Legacy Service Cleanup Required

`scripts/devops/delete_render_services.py` এ নিচের সার্ভিস IDs deletion-এর জন্য enlist করা আছে:

```python
services_to_delete = {
    RENDER_API_KEY_1: [
        'srv-dabgugdg1s2s73cmcha0',  # worker (legacy)
        'srv-dabgtp7avr4c73855fgg',  # scraper (legacy)
        'srv-daabrass728c73fuongg',  # ecosystem (old)
        'srv-da666f8u01pc739bm3t0'   # backend-v2 (old primary)
    ],
    RENDER_API_KEY_3: [
        'srv-daacds1srm7s73eif4kg'   # ecosystem-test-worker
    ]
}
```

এগুলো **ডিরোল্ট** হওয়া উচিত কিন্তু অনেক স্ক্রিপ্টে masih reference আছে।

---

## ৮. সুরক্ষা সমস্যাসমূহ ও उ advisable ফিক্সেস

### ৮.১ High Priority

| # | সমস্যা | প্রভাব | সুপারিশ |
|---|---|---|---|
| 1 | `render_trigger_deploy.py`-এ debug logging এ API key prefix expose | CI log-এ partial key leak | Debug statement remove করুন অথবা env var toggle করুন |
| 2 | Multiple legacy service IDs hardcoded | Stale config, potential accidental deploy to wrong service | সব হার্ডকোডেড ID references environment variables-তে move করুন |
| 3 | `srv-da666f8u01pc739bm3t0` (backend-v2)在各种スクリプトでstill referenced | পুরানো service-এ accidental deploy হতে পারে |.Deployment registry maintain করুন, actively used services-এর list |
| 4 | RENDER_API_KEY_4 fallback to general RENDER_API_KEY | MCP account compromise হলে universal access চলে যায় | Account-specific keys enforce করুন |
| 5 | Mixed naming (PRIMARY vs CORE) | Configuration confusion, human error | Standardize names: `PRIMARY` ব্যবহার করুন |

### ৮.২ Medium Priority

| # | সমস্যা | প্রভাব | সুপারিশ |
|---|---|---|---|
| 6 | `secrets_registry.yaml`-এ `_1` through `_4` এর criticality "optional" | Compliance audit এ issue হতে পারে | রENDER accounts-কে critical/important হিসেবে mark করুন |
| 7 | `update_cors_hosts.py` CORS config service-by-service প্যাচ | Race condition: partial updates possible | Atomic update pattern ব্যবহার করুন অথবা downtime schedule করুন |
| 8 | Infisical + GitHub Actions duplicate secret storage | Attack surface Increased | GitHub Actions-তে `Infisical/secrets-action` সরাসরি ব্যবহার করুন, duplicate storage কমfy |
| 9 | `delete_render_services.py`-এ ২টি account-এর keys在同一 dictionary-এ | Cross-account blast radius | Per-account key scoping maintain করুন |
| 10 | `render.yaml`-এ MCP service start command `python scripts/runtime/infisical_bootstrap.py npm run start` | Complex bootstrap, potential failure modes | Startup script health-check ও timeout handling যোগ করুন |

### ৮.৩ Low Priority / Technical Debt

| # | সমস্যা | প্রভাব | সুপারিশ |
|---|---|---|---|
| 11 | Multiple onrender.com URLs hardcoded in docs | Documentation drift | Docs-এ dynamic config references ব্যবহার করুন |
| 12 | `render_account_service.py`-এ 450.0 default cap | Free tier quota อาจ在未来 change হয় | Configurable from environment/registry |
| 13 | Legacy `supremeai-backend.onrender.com` vs `supremeai-primary-node.onrender.com` naming | User confusion | Redirect বা CNAME setup করুন |

---

## ৯. রেন্ডার অ্যাকাউন্ট State ম্যানেজমেন্ট (New Feature)

**ইন্টিগ্রেশন:** 2026-09-06 migration দিয়ে নতুন `render_account_states` টেবিল যোগ করা হয়েছে।

**ফিচারসমূহ:**
- Auto cooldown (10 days default, exponential backoff → max 30)
- Quota tracking with 450m/500m threshold
- Manual override capability via admin API
- Event audit trail (`render_preflight_events`)
- Fail-closed deployment gating

**CI Integration:**
- Preflight job output `build_allowed` boolean
- Budget guard toggles `autoDeploy` yes/no automatically
- Scheduler rechecks cooled accounts daily

---

## ১০. সার্বিক প্রতিযোগিতামূলক মূল্যায়ন

| কাঠামো | মান | মন্তব্য |
|---|---|---|
| Account Isolation | 🟡 Partial | ৪টি account আছে কিন্তু fallback chains cross-account access দিয়ে |
| Secret Management | 🟢 Good | Infisical vault + GitHub Actions encrypted secrets |
| CI/CD Pipeline | 🟢 Good | Preflight → Build → Budget Guard → Deploy chain |
| Monitoring/Observability | 🟡 Medium | Cooldown events tracked, but no real-time alerting pipeline |
| Legacy Debt | 🔴 High | অনেক হার্ডকোডেড IDs ও URLs, inconsistent naming |
| Documentation | 🟡 Medium | Service registry exists but outdated URLs mixed |
| Failover Strategy | 🟡 Medium | Multi-account setup exists but shared backend vulnerability |
| Zero-Cost Protection | 🟢 Good | 450m cap enforced with autoDeploy toggle |

---

## ১১. স্পষ্টত: যা যা Pending/Unresolved

1. **Legacy Service Cleanup** — `srv-da666f8u01pc739bm3t0` এবং অন্যান্য পুরানো IDs ক্লিনআপ বাকি
2. **API Key Rotation Schedule** — কোনো rotation policy নেই
3. **Real-time Alerting** — Discord/Slack/webhook-এ cooldown/alert integration নেই
4. **Failover Testing** — এক ACCOUNT ডাউন হলে fallback কেমন কাজ করে তা যাচাই নেই
5. **Service Topology Enforcement** — admin/user portal আলাদা backend-এ যাওয়ার enforcement নেই
6. **Security Audit of Render API Key Prefix Logging** — `render_trigger_deploy.py:37` ফিক্সPending

---

*অডিট সম্পূর্ণ হয়েছে। কোনো ফাইল মডিফাই করা হয়নি।*
