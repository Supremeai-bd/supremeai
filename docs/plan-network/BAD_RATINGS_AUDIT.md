---
id: bad-ratings-audit
subject: "SupremeAI — Bad Ratings Audit (সব খারাপ দিক, problem, weakness)"
document_role: audit
planning_authority: Architecture Governance / Security Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-25
target_scope: combined_ecosystem
---

# SupremeAI — Bad Ratings Audit

> **প্রজেক্টের সব খারাপ দিক, bad rating, problem, weakness এক জায়গায়।
> সৎ audit — কোনো লুকানো নেই, কোনো ভুল দাবি নেই।**

**তৈরি:** 2026-09-25 · **Method:** Codebase scan + CI check + security audit

---

## ০. সারাংশ (Executive Summary)

| মেট্রিক | মান | রেটিং |
|---|---|---|
| Empty except blocks | ৩,৩৬৯ | 🔴 CRITICAL |
| Lint suppressions (# noqa/type:ignore) | ৫২২ | 🔴 HIGH |
| Potential unused imports | ৬১৩ | 🟡 MEDIUM |
| Potential SQL injection (f-strings) | ১১১ | 🔴 HIGH |
| eval/exec calls | ৩২ | 🟡 MEDIUM |
| shell=True subprocess | ৬ | 🟡 MEDIUM |
| TODO/FIXME/HACK markers | ৪৬ | 🟡 MEDIUM |
| Potential hardcoded secrets | ১৬৩ | 🔴 HIGH |
| print() in production code | ৪৯ | 🟡 LOW |
| Skipped tests | ২৭ | 🟡 MEDIUM |
| Stale branches | ৩৮ (of ৪০) | 🟡 MEDIUM |
| Files >500 lines | ২৩ | 🟡 COMPLEXITY |
| **Backend LOC** | **২৫২,২৯৪** | 🔴 BLOAT |
| **Frontend LOC** | **৫২,৯২৫** | 🟡 OK |

**Overall Rating: C+ (৬০/১০০)** — কাজ করছে কিন্তু অনেক technical debt

---

## ১. 🔴 CRITICAL — Empty Except Blocks (৩,৩৬৯টা)

**সমস্যা:** ৩,৩৬৯টা `except` block যেগুলো exception ধরে কিছু করে না (silent failure)।

**কেন খারাপ:**
- Error হলে সাইলেন্টলে গিলে ফেলে — কেউ জানে না সমস্যা হয়েছে
- Debugging অসম্ভব — কোথায় error হয়েছে ট্রেস করা যায় না
- Constitution #13 (No Silent Failure) এর সরাসরি ভায়োলেশন

**Top offending files:**
- `backend/runtime/task_runtime.py`
- `backend/adapters/dev_adapter.py`
- `backend/adapters/business_adapter.py`
- `backend/adapters/ux_adapter.py`
- `backend/context_engine/budget.py`

**Fix:** প্রতিটায় `logger.warning()` বা `logger.error()` যোগ করো

---

## ২. 🔴 HIGH — Potential SQL Injection (১১১টা)

**সমস্যা:** ১১১টা f-string SQL query যেখানে table name বা column direct f-string-এ বসানো।

**কেন খারাপ:**
- যদি table/column name user input থেকে আসে → SQL injection
- যদি static হয় → নিরাপদ কিন্তু pattern ভঙ্গুর

**Top offending files:**
- `backend/adaptive_engine/governance.py` (৮+)
- `backend/adaptive_engine/deployment_tracker.py` (৮+)
- `backend/adaptive_engine/resource_registry.py` (৬+)

**Fix:** Parameterized query বা ORM ব্যবহার করো

---

## ৩. 🔴 HIGH — Potential Hardcoded Secrets (১৬৩টা)

**সমস্যা:** ১৬৩টা জায়গায় `password=`, `secret=`, `api_key=`, `token=` এর সাথে string value আছে।

**কেন খারাপ:**
- যদি আসল secret হয় → security breach
- যদি default/test value হয় → ভুলে production-এ চলে যেতে পারে

**Fix:** সব শুধু env var / Infisical থেকে আসবে, কোডে কোনো hardcoded value না

---

## ৪. 🔴 HIGH — Lint Suppressions (৫২২টা)

**সমস্যা:** ৫২২টা `# noqa`, `# type: ignore`, `# pylint: disable` — lint rule suppress।

**কেন খারাপ:**
- প্রতিটা suppression = একটা known issue যেটা fix না করে hide করা হয়েছে
- Type safety ভেঙে পড়ছে
- Code quality ধীরে ধীরে খারাপ হচ্ছে

**Fix:** প্রতিটা suppression review করো — যেগুলো real issue সেগুলো fix করো

---

## ৫. 🟡 MEDIUM — Unused Imports (৬১৩টা)

**সমস্যা:** ৬১৩টা potential unused import।

**কেন খারাপ:**
- Code bloat — unnecessary memory/startup time
- Confusion — কোন import আসলে use হচ্ছে কোনটা না
- Dead code indicator

**Fix:** `ruff --select F401` দিয়ে auto-remove করো

---

## ৬. 🟡 MEDIUM — eval/exec Calls (৩২টা)

**সমস্যা:** ৩২টা `eval()` বা `exec()` call।

**কেন খারাপ:**
- Security risk — arbitrary code execution
- যদি user input থেকে আসে → RCE vulnerability

**নোট:** কিছু legitimate (Redis Lua eval, tool_forge sandbox) — কিন্তু যাচাই দরকার।

**Fix:** প্রতিটা review করো — legitimate না হলে remove

---

## ৭. 🟡 MEDIUM — shell=True Subprocess (৬টা)

**সমস্যা:** ৬টা `subprocess(shell=True)` call।

**কেন খারাপ:**
- Shell injection risk
- যদি user input থাকে → command injection

**Fix:** `shell=False` + `shlex.split()` ব্যবহার করো

---

## ৮. 🟡 MEDIUM — TODO/FIXME/HACK (৪৬টা)

**সমস্যা:** ৪৬টা TODO/FIXME/HACK marker কোডে রয়ে গেছে।

**কেন খারাপ:**
- Incomplete code — কিছু feature অর্ধেক বাকি
- Technical debt accumulating

**Fix:** প্রতিটা TODO review করো — করো বা GitHub Issue খুলে ট্র্যাক করো

---

## ৯. 🟡 MEDIUM — Skipped Tests (২৭টা)

**সমস্যা:** ২৭টা test skip করা আছে।

**কেন খারাপ:**
- Skip = hidden failure
- Coverage inflation — skip হওয়া test coverage গণনায় থাকে কিন্তু আসলে test হয় না

**Fix:** প্রতিটা skip review করো — fix করো বা legitimate reason document করো

---

## ১০. 🟡 MEDIUM — Stale Branches (৩৮টা of ৪০)

**সমস্যা:** ৪০টা branch আছে, এর মধ্যে ৩৮টা stale (merged/done work)।

**Top stale branches:**
- ১৫টা `chore/artifact-regen-*` (auto-regen bot — মুছে ফেলা যায়)
- ৮টা `fix/*` (merged — মুছে ফেলা যায়)
- ৬টা `docs/*` (merged — মুছে ফেলা যায়)
- ৩টা `refactor/*` (merged — মুছে ফেলা যায়)

**Fix:** Merged branches delete করো:
```bash
git branch -d <branch>  # local
git push origin --delete <branch>  # remote
```

---

## ১১. 🟡 COMPLEXITY — Large Files (২৩টা >500 lines)

**সমস্যা:** ২৩টা file ৫০০+ lines — maintainability risk।

**Top offenders:**
| File | Lines | সমস্যা |
|---|---|---|
| `core/zero_cost_architecture/zero_cost_patch_phase1_4.py` | ২,২৪২ | 🔴 অনেক বড় |
| `core/config_classification.py` | ২,০৬০ | 🔴 অনেক বড় |
| `database/supabase_client.py` | ১,৭২৮ | 🔴 অনেক বড় |
| `core/competitive_kit.py` | ১,৫৭৩ | 🔴 অনেক বড় |
| `tools/mcp/mcp_github_cicd.py` | ১,৪৯৪ | 🔴 অনেক বড় |
| `ecosystem/standalone_app.py` | ১,৪৫৪ | 🔴 অনেক বড় |

**Fix:** প্রতিটা বড় file ভেঙে ছোট module বানাও (<300 lines target)

---

## ১২. 🔴 BLOAT — Code Size (৩০৫,২১৯ lines)

**সমস্যা:**
- Backend: ২৫২,২৯৪ lines production code
- Frontend: ৫২,৯২৫ lines production code
- **মোট: ৩০৫,২১৯ lines** — এটা অনেক বেশি

**কেন খারাপ:**
- Maintainability — এত বড় codebase AI agent-দের জন্য কঠিন
- Build time — ধীর
- Cognitive load — নতুন developer/agent confuse হয়

**Fix:** Dead code remove, duplicate merge, module split

---

## ১৩. 🟡 LOW — print() in Production (৪৯টা)

**সমস্যা:** ৪৯টা `print()` call production code-এ (logger হওয়া উচিত)।

**Top offenders:**
- `backend/main.py` (৩টা — bootstrap messages)
- `backend/alembic_migrations/` (৩০+ — migration print)

**Fix:** `print()` → `logger.info()` দিয়ে replace করো

---

## ১৪. Platform Issues (earlier audit থেকে)

| Issue | Status | Priority |
|---|---|---|
| Core service DOWN | ⚠️ Needs restart | P0 |
| Worker 503 not_ready | ⚠️ Startup failure | P1 |
| Groq API key broken (403) | ❌ Re-generate | P1 |
| OpenAI API key broken (403) | ❌ Verify format | P1 |
| Cerebras API key broken (403) | ❌ Re-generate | P1 |
| Discord webhook broken (403) | ❌ Re-create | P2 |
| Resend email broken (403) | ❌ Fix IP block | P2 |
| Cloudflare 4/5 accounts untested | ⚠️ Verify | P3 |
| Telegram webhook not set | ❌ Configure | P1 |

---

## ১৫. Rating Scorecard

| Category | Score | Grade |
|---|---|---|
| **Security** | ৫০/১০০ | D |
| **Code Quality** | ৪৫/১০০ | D |
| **Test Coverage** | ৭০/১০০ | B |
| **Documentation** | ৮৫/১০০ | A |
| **Architecture** | ৭৫/১০০ | B |
| **Platform Health** | ৬০/১০০ | C |
| **Maintainability** | ৪০/১০০ | D |
| **Overall** | **৬০/১০০** | **C+** |

---

## ১৬. Fix Priority (কোনটা আগে করবে)

### P0 — Critical (এই সপ্তাহে)
1. **Core service restart** — platform down
2. **Empty except blocks** — ৩,৩৬৯টা → যত দ্রুত সম্ভব `logger` যোগ করো
3. **Hardcoded secrets** — ১৬৩টা → verify ও fix
4. **SQL injection** — ১১১টা → parameterized query

### P1 — High (এই মাসে)
5. **Groq/OpenAI/Cerebras keys** — re-generate
6. **Telegram webhook** — configure
7. **Lint suppressions** — ৫২২টা review
8. **Stale branches** — ৩৮টা delete

### P2 — Medium (পরবর্তী মাসে)
9. **Unused imports** — ৬১৩টা auto-remove
10. **TODO/FIXME** — ৪৬টা resolve
11. **Skipped tests** — ২৭টা fix
12. **eval/exec** — ৩২টা review

### P3 — Long-term
13. **Large files** — ২৩টা split
14. **Code bloat** — dead code remove
15. **print() → logger** — ৪৯টা replace

---

## রেফারেন্স

- [INTEGRATION_AUDIT.md](./INTEGRATION_AUDIT.md) — API key validity
- [CODEBASE_INTEGRATION_AUDIT.md](./CODEBASE_INTEGRATION_AUDIT.md) — key vs code
- [PLATFORM_STATUS.md](./PLATFORM_STATUS.md) — platform health
- [LESSONS_LEARNED.md](../../LESSONS_LEARNED.md) — past mistakes
- [STATUS.md](../../STATUS.md) — current system status
