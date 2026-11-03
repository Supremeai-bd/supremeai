# ADR-007 — টপোলজি v4: Open-Core Private-Live (v3 cutover-এর উপরে ভেরিয়েন্ট-সিদ্ধান্ত)

**Status:** EXECUTED (2026-10-09) — fork private+detached ✓, diet লাইভ main-এ (cron 0 2,8,14,20) ✓, Agent Loop ফিক্স-পরে SUCCESS ✓, archive-mirror প্রতিদিন ৪× parent-এ ff-push ✓, gitleaks শূন্য-আসল-লিক ✓; অবশিষ্ট মানব-ক্লিক: key-rotation (৪×403) + App-install paykaribazaronline-এ + Render re-point
**তারিখ:** 2026-10-09 (Asia/Dhaka)
**উপরে-নির্মিত:** ADR-005 (টপোলজি v3 cutover), ADR-006 (বিভাজন-নীতি), Task 36–38 নিরীক্ষা-প্রমাণ

---

## Context (প্রেক্ষাপট)

ADR-005 cutover-এর সব প্রস্তুতি প্রমাণিত (Task 36: fork = parent-এর অতিসেট, behind=0, ৩১-secret, tower ১০/১০)।
cutover-পরবর্তী লাইভ-fork-এর **visibility** প্রশ্নটি খোলা ছিল: public showcase (v3) নাকি private core (v4)।

প্রমাণ-ভিত্তি (Task 36–38 API-অডিট):

1. **fork public = Actions মিনিট আনলিমিটেড-ফ্রি; fork private = কোটা-বাস্তবতা।**
   fork-এ scheduled runs/day ≈ **৩৯** (Continuous Agent Loop ২৪ + Nightly Ops ৯ + Auto-Sync ৪ + Issue Ops ১ + Code Quality ১)।
   private হলে ≈ ১,১৭০ run/মাস × ২–৫ মিনি = **২,৩০০–৫,৮০০ মিনি/মাস → একা একটি ২,০০০-মিনিট পুল ডুবিয়ে দেয় (১৫–১৭ দিনে)।**
2. **দুই-অ্যাকাউন্ট মিনিট-pool "failover" অবৈধ পথ:** Actions-মিনিট রিপোর নিজ অ্যাকাউন্টের পুলে বাঁধা; ক্রস-অ্যাকাউন্ট CI-split = দুই-লাইভ-মেইন পুনরুৎপাদন (ADR-003/005 বিরোধী "Drift Trap")।
3. **v4-এর খরচ ব্যবস্থাপনাযোগ্য:** সময়সূচি-ডায়েট (Agent Loop ২৪→৪, Nightly ৯→১; Auto-Sync তো Phase B-তে disable-ই হবে) → ~৭ run/day ≈ **৪০০–৬৫০ মিনি/মাস** → ২,০০০-পুলে **>১,৩০০ মিনি উদ্বৃত্ত** push/PR CI-এর জন্য।
4. **নিরাপত্তা-ভিত্তি (pasted-পরামর্শ যাচাইকৃত, Task 38):** তৃতীয়-পক্ষ fork=0, watchers=0, stars=0; `sourcemap: false` ইতিমধ্যে (frontend/vite.config.ts:209); একমাত্র বাস্তব ঝুঁকি = হিস্ট্রি-সিক্রেট → rotation-তালিকা + gitleaks-গেট।
5. **বিপরীতযোগ্যতা প্রমাণিত:** fork-detach-এর পর PAT-এর admin=True/maintain=True → এক API-call-এ private↔public উভয় দিক সম্ভব (one-way door নয়)।
6. **Tower-continuity প্রমাণিত (Task 39 প্রোব):** `account.registry.ts`-এ `github-test-ground` এ মাত্র ১ লিংক দিয়ে একটি অ্যাকাউন্ট সরিয়ে ফেলা হয়েছে paykaribazaronline/supremeai + GITHUB_PAT_PAYKARIBAZARONLINE — cutover-এর পরও অপরিবর্তিত কাজ করবে; `github-primary` (parent) collaborator-push-অধিকারে চলবে। registry-পরিবর্তন শূন্য।
7. **Public-ফেস প্রস্তুত:** `supremeai-open` (LICENSE + README + api-schemas/ + docs/ + examples/) Task 25–29-এই open-boundary হিসেবে নির্মিত; infrastructure-এ byte-parity যন্ত্র (PR#5) বিদ্যমান।

## Decision (সিদ্ধান্ত)

**v4 বেছে নেওয়া হলো** — cutover (ADR-005 Phase 0–D অপরিবর্তিত) সম্পন্ন হওয়ার **পরে** fork-এ নিম্ন Phase E প্রয়োগ হবে:

1. **Fork → PRIVATE flip** — এজেন্ট API-call-এ (PAT admin), detach-পরবর্তী স্বাধীন রিপোতে; কোনো মানব-ক্লিক নেই।
2. **Schedule-diet** — Continuous Agent Loop cron `0 * * * *` (২৪/day) → `0 2,8,14,20 * * *` (৪/day); Nightly Ops ৯/day → ১/day; বাকি cron অপরিবর্তিত; Auto-Sync Phase B-তেই disable।
3. **Public-projection sync** — নতুন workflow `open-projection.yml` (private fork-এ): নির্বাচিত public-safe path (PROJECTION_MAP: docs-উপসেট, api-schemas-উৎস, examples, client-kit) → `supremeai-open` main-এ push (App-installation token, contents:write — নতুন PAT লাগবে না); **gitleaks fail-closed গেট** প্রতি sync-এ; byte-parity যন্ত্র ব্যবহারযোগ্য।
4. **`supremeai-open` = generated-repo নীতি** — মানব-সরাসরি-push বন্ধ; সব সম্পাদনা উৎস-রিপোতে, sync-এ ছড়াবে (parity-drift প্রতিরোধ)।
5. **Fallback:** যেকোনো মুহূর্তে v3-তে ফেরা = fork public flip (এক API-call) + diet-উল্টো — শূন্য-ক্ষতি।

## Consequences (ফলাফল)

- **ভালো:** ১০০% কোড-গোপনীয়তা (লক্ষ্য "কোড যেন অন্য কেউ না পায়" পূর্ণ); প্রত্যাশিত মিনিট ~৪০০–৬৫০/মাস (কোটার ১/৩-এর নিচে); public-গ্রহণযোগ্যতা supremeai-open দিয়ে অটুট; মাইনিট-বিলিং সারপ্রাইজ শূন্য।
- **সতর্কতা:** প্রজেকশন-sync ভাঙলে public-ফেস পুরনো হয়ে থাকবে → sync-failure-এ সতর্ক-notify (workflow-এ বিল্ট-ইন); PROJECTION_MAP-এ ভুল path হলে হয় কম বা বেশি ফাঁস — তাই প্রথম sync শুধু-পড়া diff-মোডে যাচাই করে।
- **এক-মুখী অংশ অপরিবর্তিত:** parent-flip (মানব-ক্লিক) এখনও one-way door — সেটি ADR-005-এই নথিভুক্ত।
- **মিনিট-পুল স্থিতি:** paykaribazaronline-এর ৭ private satellite একই ২,০০০-পুল শেয়ার করে — diet-পরবর্তী হেডরুম হিসাবে সেটিও থাকবে।

## Runbook — Phase E (cutover-সেশনের শেষ ধাপ)

1. `POST /repos/paykaribazaronline/supremeai` → `{"private": true}` (PAT) → detach+private যাচাই (fork-নেতৃত্ব API-তে fork=false, private=true)।
2. Schedule-diet PATCH: দুই workflow-ফাইল commit (fork main, `[skip ci]` প্রয়োজন নেই — private-এ push-CI পুল থেকেই)।
3. `open-projection.yml` commit + fork-এ secret `OPEN_SYNC` path (App-token self-mint, vault AGENT_PLATFORM_*)।
4. প্রথম sync diff-মোডে → যাচাই → বাস্তব push → supremeai-open main tip প্রমাণ।
5. tower-এ `github-test-ground` description "test ground" → "live main (private)" রিনেম-ঐচ্ছিক (কার্য-পরিবর্তন নেই)।
6. ADR-005 status → Executed; এই ADR-007 status → Executed; worklog-চূড়ান্ত নিরীক্ষা (৩১-secret, diet-পরে runs/day ≈ ৭, প্রথম mirror-puশ প্রমাণ)।

## প্রস্তুতি-আর্টিফ্যাক্ট

- `prepared/v4/schedule-diet-patch.md` — হুবহু cron-পরিবর্তন (2 workflow)
- `prepared/v4/open-projection.yml` — সম্পূর্ণ workflow (PROJECTION_MAP স্থান-চিহ্নসহ)
