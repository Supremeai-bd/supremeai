# SupremeAI 2.0 — Code Quality Check Sequence (Small → Big)
_Status: ACTIVE_
_Last Updated: 2026-08-06_
_Companion to: [SUPREMEAI_MASTER_AUDIT_PLAN.md](./SUPREMEAI_MASTER_AUDIT_PLAN.md)_

---

## এই ডকুমেন্ট কী, এবং কী না

**Master Audit Plan** বলে দেয় **কোন module কখন** audit হবে (Phase 1 = `backend/core/`, Phase 2 = `backend/api/`, ইত্যাদি)।

**এই ডকুমেন্ট** বলে দেয় — যেকোনো একটা module/ফাইল audit করার সময়, ভেতরে **কোন ধরনের error আগে খুঁজব, কোনটা পরে**। দুটো ডকুমেন্ট conflict করে না — Master Plan-এর প্রতিটা Phase-এর ভেতরে এই sequence অনুসরণ করতে হবে।

**নিয়ম (Master Audit Plan-এর গ্লোবাল রুলসের সাথে সামঞ্জস্যপূর্ণ):**
- প্রতিটা layer শেষে প্রমাণ (grep count / tool output) ছাড়া "clean" দাবি করা যাবে না।
- Fix আলাদা ধাপ — এই sequence শুধু *খুঁজে বের করার* জন্য, approval ছাড়া কোড পাল্টানোর জন্য না।
- P0-P3 severity taxonomy অপরিবর্তিত থাকবে (Master Audit Plan-এর সংজ্ঞা অনুযায়ী)।

---

## কেন এই ক্রম (small → big)

প্রতিটা layer পরের layer-এর noise কমায়। যেমন — syntax error থাকা ফাইলে lint/type checker ভুল বা অসম্পূর্ণ রিপোর্ট দেয়; তাই সবার আগে parse-level সমস্যা সাফ করা লাগে। ক্রমটা মূলত **scope** অনুযায়ী সাজানো — single-file/no-execution থেকে শুরু করে পুরো-monorepo/business-logic পর্যন্ত।

| # | Layer | Scope | Execution লাগে? | Tool (এই repo-তে) | CI-তে বর্তমানে আছে? |
|---|---|---|---|---|---|
| 1 | Syntax errors | একটা ফাইল | না | `py_compile` (Python), `tsc --noEmit` (TS) | ❌ নেই আলাদাভাবে |
| 2 | Static lint | একটা ফাইল | না | `ruff check .`, `pnpm turbo run lint` | ✅ Python: আছে (`supreme-core-ci.yml`)। TS: `turbo run build lint`-এর ভেতরে চলে বলে ধারণা করা হচ্ছে — script-এর ভেতর সত্যিই eslint চলছে কিনা `package.json`-এ verify করা দরকার |
| 3 | Dead/unreachable code | একটা ফাইল, সামান্য বেশি context | না | `vulture`, ruff-এর কিছু rule | ❌ নেই |
| 4 | Bare except / silent error | একটা ফাইল | না | grep pattern + manual review | ⚠️ আংশিক — নিচে দেখুন |
| 5 | Import cycles / module structure | একাধিক ফাইল | না (static) | `pydeps`, `madge` (TS-এর জন্য) | ❌ নেই |
| 6 | Type errors | একাধিক ফাইল (inference) | না (static) | `mypy` (যেখানে hint আছে), `tsc` strict mode | ❌ mypy CI-তে নেই |
| 7 | Test collection ও execution | পুরো test suite | হ্যাঁ | `pytest --collect-only`, তারপর full run | ✅ CI-তে আছে, কিন্তু root-level `tests/`-এ ~৬১টা known failure (Settings secret-cache সন্দেহ) |
| 8 | Security-sensitive patterns | একাধিক ফাইল, cross-check লাগে | আংশিক | `bandit -r backend`, manual review (false-positive বেশি) | ❌ bandit CI-তে নেই |
| 9 | Cross-service/architecture mismatch | পুরো monorepo | হ্যাঁ, manual reasoning | কোনো single tool না — API contract বনাম client call, workflow repo-gating logic, config drift | N/A — সবসময় manual |

---

## 🔴 জরুরি finding — Layer 4 CI-তে সক্রিয়ভাবে চাপা দেওয়া আছে

`supreme-core-ci.yml`-এর `pre-merge-gate` job-এ ruff command-এ এই ignore list আছে:

```
ruff check . --config pyproject.toml --no-fix --extend-ignore=S101,S110,S603,S607,S104,S105,S107,S108,S306,S310,S311,S314,S608,E501,E402
```

`S110` = bandit rule for **`try: ... except: pass`** (bare except যা silently swallow করে)। এটা exactly Layer 4-এর জিনিস, আর এটা CI-তে **explicitly ignore করা আছে** — অর্থাৎ নতুন bare-except pattern যোগ হলেও CI সবুজ থাকবে।

এটা `.agents/AGENTS.md`-এর নিজস্ব **"Anti-Silent Failure"** self-audit rule-এর সাথে সরাসরি সাংঘর্ষিক (ঐ rule বলে: "সিস্টেমের কোথাও কি এমন এক্সেপশন হ্যান্ডলিং আছে যা এরর সাপ্রেস করে?")।

`S608` (SQL injection pattern) ব্ল্যাংকেট ইগনোর করা আছে — আগের সেশনে একটা allowlisted f-string-এর জন্য false-positive পাওয়া গিয়েছিল বলে পুরো rule-ই বন্ধ করে দেওয়া হয়েছে, যেটা risky (নতুন real SQLi ধরাও বন্ধ হয়ে গেছে)। **সুপারিশ:** blanket ignore-এর বদলে `# noqa: S608` দিয়ে শুধু ঐ নির্দিষ্ট লাইনে ইগনোর করা, যাতে বাকি কোডবেস-এ এখনও এই rule সক্রিয় থাকে।

**এটা fix করার জন্য user approval লাগবে** — এখানে শুধু finding রিপোর্ট করা হলো, কোড পাল্টানো হয়নি।

---

## রিকারিং ক্যাডেন্স (একবারের audit না — চলমান রুটিন)

| Layer | কতবার চলবে | Trigger |
|---|---|---|
| 1–2 (syntax, lint) | প্রতিটা push/PR | CI (`pre-merge-gate`) — ইতিমধ্যে আছে |
| 3–4 (dead code, bare except) | সাপ্তাহিক | নতুন GitHub Action cron বা `maintenance_pipeline.yml`-এ যোগ করা |
| 5–6 (import cycles, types) | সাপ্তাহিক/PR-তে যখন অনেক ফাইল change হয় | CI gate বা cron |
| 7 (tests) | প্রতিটা push/PR | ইতিমধ্যে আছে |
| 8 (security) | সাপ্তাহিক + প্রতিটা release-এর আগে | cron + release gate |
| 9 (architecture) | মাসিক/quarterly manual review | কোনো agent একা না, admin sign-off লাগবে |

---

## Master Audit Plan-এর সাথে ব্যবহারবিধি

Master Audit Plan-এর যেকোনো Phase (যেমন Phase 1 = `backend/core/`) চালানোর সময়:

1. প্রথমে সেই module-এর ফাইলগুলোতে Layer 1 (syntax) চালাও, সব clean না হওয়া পর্যন্ত পরের ধাপে যেও না।
2. তারপর Layer 2 (lint) — শুধু Layer 1 pass করা ফাইলে।
3. এভাবে ক্রমান্বয়ে Layer 9 পর্যন্ত।
4. প্রতিটা layer-এর finding Master Audit Plan-এর format-এই লেখা হবে (`[ID] [Severity] [ফাইল:লাইন]` ইত্যাদি), `docs/audit_reports/PHASE_0N_<module>.md`-এ।

---

## এখন পর্যন্ত পাওয়া empirical findings (evidence-সহ)

| ID | Severity | ফাইল | সমস্যা | প্রমাণ | Status |
|---|---|---|---|---|---|
| CQ-001 | P1 | `scripts/testing/security_penetration_test.py:232` | `global REPORT_DIR` ব্যবহারের পর declare — SyntaxError | `py_compile` output | ✅ Fixed (commit `d1b413d`, অন্য agent দ্বারা) |
| CQ-002 | P1 | `.github/scripts/service_preflight_check.py` | Secondary repo-তে Render/Vercel key না থাকায় preflight hard-fail করে পুরো workflow cancel করে | Uploaded CI log | 🔧 Fix ready, apply করা হয়নি এখনো |
| CQ-003 | P2 | `.github/workflows/supreme-core-ci.yml` (ruff command) | `S110`/`S608` blanket-ignore | ruff command লাইন | ❌ Open |
| CQ-004 | P3 | `AGENTS.md` (root) | Windows absolute path symlink, Linux-এ ভাঙা | `ls -la` output | ❌ Open |

---
_Generated as a companion sequence to SUPREMEAI_MASTER_AUDIT_PLAN.md — Code Quality Layering_
