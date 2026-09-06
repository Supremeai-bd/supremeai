# SCRIPT INTELLIGENCE AUDIT — সম্পূর্ণ বিশ্লেষণ (v9)

> **Task 10** | Branch: `script-intelligence-v9` | Base: `audit-fixes-v8` (e2e298a)
> **সমস্যা (আপনার ভাষায়):** "there is many script but all of them aren't intelligent enough... they can't find automatically, if we change something in codebase script don't track them"
> **সমাধান:** প্রতিটি script-এর hardcoded তালিকা → **অটো-ডিসকভারি**। এখন codebase বদলালে script নিজে নতুন/বদলানো ফাইল খুঁজে নেবে।

---

## ১. মূল সমস্যা কী ছিল — প্রমাণসহ

| # | প্রমাণিত রোট (stale) | ফলাফল |
|---|---|---|
| 1 | `dead_code_verified_finder.py` এর `REPO_ROOT = Path(__file__).parent.parent` ভুলে **scripts/** ফোল্ডারে resolve হতো | **০টি ফাইল স্ক্যান হতো, script "কোনো dead code নেই" বলে silent green দিত** — সবচেয়ে বড় বিপদ |
| 2 | একই script-এ ৭টি entry-point path-ই ভুল (`api/routers.py`, `core/app.py`... আসল হলো `backend/core/app.py`) | ভুতুড়ে ইনভেন্টরি নিয়ে বিশ্লেষণ |
| 3 | `superai_health_check.py` — ৪টি ফাইলের নাম ভুল (`cache.py`, `auto_healer.py`, `smart_router.py`, `security.py` আর নেই) | হেডলাইনে ভুলভাবে "MISSING" রিপোর্ট |
| 4 | `pre_merge_guard.py` — ডোমেইনগুলো string-জোড়া literal (`supremeai-primary-node` + render-domain ইত্যাদি) | ডোমেইন বদলালে গার্ড পুরনো URL টেস্ট করত |
| 5 | `generate_modular_audits.py` — ৩৪টি target-এর মধ্যে ৯টি ফাইল নেই | অডিটে "(not found)" ফ্যান্টম রো |
| 6 | `_INDEX.md` — ৩০টি রেফারেন্সের ১৭টি ফাইল রিপোর কোথাও নেই, ~২০০ script মোটেই মিসিং | ইনডেক্সই মিথ্যা |
| 7 | `test_runners.py` — ৮টি টেস্ট-ফাইল literal যার ফোল্ডারই নেই + `--list-suites` দিলে **crash (exit 2)** | টেস্ট ডিসকভারি মৃত |
| 8 | `hardcode_config_scanner.py`, `check_hardcoded_deployment_config.py`, `auto_api_doc_sync.py`, `fix_scripts_2.py`, `safety_guard.py`, `superai_transform.py` — সবখানে পুরনো path literal | রিফ্যাক্টর করলেই সব script অন্ধ |

---

## ২. নতুন মূল ইঞ্জিন — `scripts/lib/auto_discovery.py` (SIL-00)

সব script এখন এই শেয়ার্ড লাইব্রেরি ব্যবহার করে:

| ফাংশন | কী আবিষ্কার করে |
|---|---|
| `find_repo_root()` | `__file__` থেকে উপরে walk করে — যেকোনো cwd থেকে চলে; `SUPREMEAI_REPO_ROOT` env override |
| `get_layout()` | backend/frontend/scripts/docs root মার্কার দিয়ে চেনে |
| `discover_py_files()` | `git ls-files` (gitignore-সম্মত) + glob fallback — এখন ১৮১৪ ফাইল |
| `discover_fastapi_routes()` | **AST parse** (import ছাড়া!) — import-crash হলেও route পায়; এখন **৭৫৩ route** |
| `discover_core_modules()` | role ভিত্তিক: config/app/app_builder/health/startup_validator — নাম বদলালে candidate-chain absorb করে |
| `discover_service_urls()` | env pin → `RENDER_*_URL` → `render.yaml` convention — **কখনো নিজে থেকে ডোমেইন বানায় না**, না পেলে fail-loud |
| `require()` | আবিষ্কার ০ হলে **loud fail** — silent-green অসম্ভব |

---

## ৩. কোন কোন script intelligent করা হলো (১২টি + ১টি নতুন)

### SIL-01 — Analysis scanners (Agent 10-a)
| Script | আগে (hardcoded) | পরে (intelligent) |
|---|---|---|
| `advanced_analysis/dead_code_verified_finder.py` | ৭ stale entry + ২৫ `__init__` path + ২৫ package নাম | core-role + router-registry + `__main__`-guard AST detection; **প্রমাণিত**: probe ফাইল দিলে 1457→1460 modules, মুছলে 1457 |
| `advanced_analysis/hardcode_config_scanner.py` | stale `core/config_*.py` সাবস্ট্রিং | role-based candidates; missing হলে `[discovery] skipping` নোট; A/B টেস্টে output অপরিবর্তিত |
| `ci/check_hardcoded_deployment_config.py` | stale `frontend/src/api.ts` anchor | `discover_files` দিয়ে ৪৪৬ frontend entry; exception anchor runtime-resolved |

### SIL-02 — Health / Test / Guard (Agent 10-b)
| Script | আগে | পরে |
|---|---|---|
| `health/superai_health_check.py` | ৭ literal (৪টি ভুল) | ৭/৭ role resolve; patch-module inventory discovered; **প্রমাণিত**: probe দিলে 39→40, মুছলে 39 |
| `testing/test_runners.py` | ৮টি মৃত test-path + `--list-suites` crash | pattern-based discovery (**৪৭৪ টার্গেট**); crash ফিক্সড — এখন exit 0; **প্রমাণিত**: 474→475→474 |
| `pre_merge_guard.py` | literal ডোমেইন | resolution ladder: `PRE_MERGE_DOMAINS` (মানুষের override, ভুল হলে exit 2) → `PRE_MERGE_SERVICE_URLS` pin → `RENDER_*_URL` → render.yaml; **v7 fail-loud কন্ট্রাক্ট অক্ষত**; কিছুই না পেলে DiscoveryError→exit 2, কখনো গেস করা ডোমেইন probe করে না |

### SIL-03 — DevOps / Docs / Codemods (Agent 10-c)
| Script | আগে | পরে |
|---|---|---|
| `devops/generate_modular_audits.py` | ৩৪ literal, ৯ মৃত | ৪৪ discovered target (relocation + role-glob); `--list-targets`/`--dry-run`; ১৪০৮ ফাইলের audit build /tmp-তে verify; **প্রমাণিত**: probe দিলে 121→122, মুছলে 121 |
| `refactor/superai_transform.py` | ৫ literal (২ মৃত) | ১১ discovered module (successor খুঁজে নিল: `core/cache_manager.py`, `services/auto_healer.py`); `--yes` alias |
| `docs/auto_api_doc_sync.py` | মৃত `api_reference.md` path | candidate-chain (docs/api_reference.md → API_REFERENCE.md → docs/api.md → create-at); mock OpenAPI সার্ভারে লাইভ টেস্টেড |
| `fix_scripts_2.py` | মৃত `deploy/update_render.py` | ১২ discovered target; `--dry-run` যোগ; md5 অপরিবর্তিত প্রমাণিত |

### SIL-04 — মেটা-ইন্টেলিজেন্স (Agent 10-d)
| আইটেম | বর্ণনা |
|---|---|
| **নতুন**: `generate_script_index.py` | AST দিয়ে ২২৬ script / ৩৩ group-এর ইনডেক্স বানায়; hand-written বাংলা সেকশন সংরক্ষণ (`<!-- hand: -->` মার্কার); `--check` flag CI-তে stale-ইনডেক্স ধরবে (exit 1); **প্রমাণিত**: probe দিলে index-এ ঢোকে + `--check` fail করে, মুছলে বের হয় |
| `_INDEX.md` | regenerate — ১৭টি মৃত রেফারেন্স গেছে, ২২৬ real script ঢুকেছে |
| `safety_guard.py` | `approval_requests.json` candidate-discovery; read-mode-এ ফাইল না থাকলে clear নোট, crash না |

---

## ৪. যেগুলো বদলানো হয়নি — কারণসহ

| শ্রেণি | উদাহরণ | কারণ |
|---|---|---|
| ইতিমধ্যে intelligent | `detect_silent_errors.py` (AST walker), `mutation_testing.py` (v7-তেই fail-loud), `verify_capabilities.py` | hardcoded inventory নেই |
| পুরোপুরি ডেটা-ড্রিভেন | `resource_collection/*`, `i18n/*` | টার্গেট বাইরের API/ডেটা, রিপো-স্ট্রাকচার নয় |
| একবারী codemod/মৃত | `fix_backend.py`, `fix_urls.py`, `fix_time_sleep.py`, `refactor_scanner_fixes.py` | ঐতিহাসিক one-off; নতুন `auto_discovery` প্যাটার্নে লেখা পরবর্তী codemod |
| বাইরের সার্ভিস ইন্টিগ্রেশন | `deploy/*render*`, `devops/update_vault.py` | URL/সার্ভিস API কল; env-ভিত্তিকই সঠিক |

> **বাকি থাকা literal-গুলো ইচ্ছাকৃত candidate-list** (যেমন `test_runners.py`-এ `backend/core/cache.py`): এগুলো `existing_paths()` দিয়ে filter হয় — ফাইল থাকলে ধরে, না থাকলে skip-note। ভবিষ্যৎ rename absorb করাই এদের কাজ।

---

## ৫. নতুন প্যাটার্ন — ভবিষ্যতের script যেভাবে লিখবেন

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.auto_discovery import (
    get_layout, discover_py_files, existing_paths, require,
)

layout = get_layout()
targets = existing_paths(candidates, relative_to=layout.backend)
require(targets, "audit targets")   # ০ হলে loud fail — silent green নেই
```

নিয়ম: **আবিষ্কার করো → filter করো → খালি হলে চিৎকার করো।** কখনো ফাইল-তালিকা literal লিখবেন না।

---

## ৬. টেস্ট সামারি

- ১২/১২ script `--help` exit 0; compileall clean
- ৩টি auto-tracking probe প্রমাণ (health 39→40→39, audit 121→122→121, dead-code 1457→1460→1457)
- `pre_merge_guard`: v7 কন্ট্রাক্ট টেস্ট (override honored / malformed exit 2 / zero-discovery exit 2)
- Scanner A/B equivalence (violation set অপরিবর্তিত); scanner নিজেই এখন exit 0
- **১০০% ভেরিফিকেশন**: ৫টি patch virgin base-এ `git am` → lib self-test + index `--check` পাস

## ৭. Patch তালিকা (zip-এ আছে)

| Patch | বিষয় |
|---|---|
| 0001 | `scripts/lib/auto_discovery.py` (নতুন লাইব্রেরি) |
| 0002 | SIL-01 analysis scanners (৩ ফাইল) |
| 0003 | SIL-02 health/test/guard (৩ ফাইল) |
| 0004 | SIL-03 devops/docs/refactor (৪ ফাইল) |
| 0005 | SIL-04 index generator + _INDEX.md + safety_guard |
