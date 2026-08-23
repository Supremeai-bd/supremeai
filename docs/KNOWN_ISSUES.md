# Known Issues & Technical Debt

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When updating known issues or tech debt:
> 1. Add new items to the top of the relevant section.
> 2. When fixing an issue, change `[ ]` to `[x]` but do not delete it immediately.
> 3. Keep descriptions actionable.

This file tracks non-critical bugs, warnings, and technical debt in the SupremeAI project.
Agents should refer to this list when looking for optimization opportunities or when fixing related components.

## Current Issues
- [x] **CI Red on main (Core CI ৩টি job) — 2026-08-18 ফিক্সড:** (1) `pnpm-lock.yaml` outdated (root importer-এ stale `cross-env`/`ioredis`/`@types/node` ইত্যাদি dependencies) → `pnpm install --lockfile-only` করে lockfile resync করা হয়েছে; (2) Render backend (`srv-da07ogmgekts739amqa0`) এ `SUPREMEAI_ADMIN_PASSWORD_HASH` ও `INFISICAL_TOKEN` critical key missing ছিল → Render API দিয়ে যোগ করা হয়েছে; (3) Infisical vault-এ `INFISICAL_CLIENT_SECRET` critical key missing + Universal Auth 401 (rotated machine identity create হয়নি) → vault-এ key যোগ + `verify_infisical_env.py`-তে INFISICAL_TOKEN fallback যোগ।
- [x] **`generate_types.py` cwd-নির্ভর crash — 2026-08-18 ফিক্সড:** CI-তে `working-directory: backend` থাকায় `filename.relative_to(Path.cwd())` ValueError দিত → `relative_to(_REPO_ROOT)` করা হয়েছে। সাথে ৪টি generated-file-এ timestamp লাইন (determinism breaker) রিমুভ + Windows-এ emoji crash ঠেকাতে UTF-8 reconfigure যোগ।
- [x] **React error #31 crash on Admin Dashboard login (Active Monitor E2E)** — raw error object `{code,message,errors}` passed to global toast and rendered as React child. Fixed in `apiInterceptor.ts` + `useErrorHandler.ts` + `ToastProvider.tsx` + `ui/Toast.tsx` (string coercion).
- [ ] **Secrets rotation অসম্পূর্ণ (P1):** Infisical Machine Identity (`INFISICAL_CLIENT_ID/SECRET`) rotate করা হয়েছে কিন্তু Infisical-এ create করা হয়নি (401)। Render API keys, GitHub PATs, Supabase/Neon credentials এখনো `MANUAL_REQUIRED`। বাকি work `f:\_supremeai_secrets_backup\rotated_secrets.json` + step scripts-এ।
- [ ] **Render backend-docker-এ ৯০টি important/optional key missing** (SUPABASE_DATABASE_URL, STRIPE_*, REDIS_URL, QDRANT_* ইত্যাদি) — CI gate pass কিন্তু production feature degraded। `.env`/vault থেকে value verify করে যোগ করা দরকার।
- [ ] **Infisical Universal Auth এখনো 401** — `verify_infisical_env.py` INFISICAL_TOKEN fallback-এ চলে; সঠিক Machine Identity তৈরি করলে warning চলে যাবে।

## Technical Debt
- [ ] Example Tech Debt: E.g., refactor this component to use a newer library version.

---
*(Check items off `[x]` as they are resolved and add new ones at the top of their respective sections)*
