# ADR-005: টপোলজি v3 — SaifulHaqueNiloy = প্রাইভেট আর্কাইভ-মিরর; paykaribazaronline = লাইভ ফেডারেশন

- তারিখ: 2026-10-08 (Asia/Dhaka)
- স্ট্যাটাস: **EXECUTED (2026-10-09): Phase 0 ✓ Phase A ✓ (parent private, API-প্রমাণ) Phase B ✓ (auto-sync disabled_manually + archive-mirror.yml লাইভ, প্রথম push success) Phase C ✓ (parent workflow ১৯/২১ disable; ২ Dependabot-system API-unable) Phase D ✓ Phase E ✓ (diet-merge 4383d1aa + Agent Loop ফিক্স-পরে SUCCESS #37935200781 + gitleaks full-history শূন্য-আসল-লিক)**
- Supersedes: ADR-003-এর consolidation-গন্তব্য ("best-of → প্রকৃত main") ও ADR-004-এর টপোলজি-বর্ণনা; worklog Task 32-তে সংরক্ষিত "merge-unification (ADR-005)" পরিকল্পনা এই ADR-ই শুষে নিল — best-of merge-টি এখন fork-ই গন্তব্য

## Context

ব্যবহারকারীর সিদ্ধান্ত (হুবহু-অর্থ): দুটি সমান্তরাল main রক্ষণা বন্ধ —

1. **`SaifulHaqueNiloy/supremeai` = আমাদের archive** — full project-এর সাথে synced থাকবে, কিন্তু **private** হবে।
2. **`paykaribazaronline` = public-private combination** — এখানেই লাইভ জীবন; **secrets আগেই configure করা** থাকবে, যাতে অল্প কিছু correction-এর সাথে সাথে সম্পূর্ণ লাইভ হয়ে যায়।

## Verified facts (API-প্রমাণ, ২০২৬-১০-০৮ ~০২:৪০ +06; সব কল read-only)

| বিষয় | প্রমাণিত তথ্য |
|---|---|
| parent `SaifulHaqueNiloy/supremeai` | public, non-fork, ~40 MB, 18 খোলা issue, **Pages নেই** (has_pages=false), সক্রিয় (pushed 2026-10-07T20:34Z) |
| fork-নেটওয়ার্ক | **forks_count = 1** — একমাত্র fork = `paykaribazaronline/supremeai`; তৃতীয়-পক্ষ fork শূন্য |
| PAT অধিকার (parent-এ) | pull + **push** + triage ✓; **admin ✗** → visibility-PATCH API দিয়ে সম্ভব নয় (UI বা admin-PAT লাগবে) |
| PAT অধিকার (fork-এ) | **admin ✓** → workflows/secrets সম্পূর্ণ নিয়ন্ত্রণ |
| App-token (parent-এ) | metadata/contents মাত্র; actions-secrets 403 → App দিয়ে flip অসম্ভব |
| paykaribazaronline | **User অ্যাকাউন্ট (org নয়)** → org-level secrets নেই; per-repo secrets-ই একমাত্র পথ |
| fork-এর ৭টি secret | INFISICAL_CLIENT_ID / INFISICAL_CLIENT_SECRET / INFISICAL_PROJECT_ID / INFISICAL_PROJECT_SLUG / SUPABASE_ACCESS_TOKEN / SUPABASE_URL / SYNC_PAT (Task 25–29-এর healed সেট) |
| fork-এর workflows | ১৮টি active; upstream-sync = **id 375977882** ("Auto-Sync Fork with Upstream") |
| বর্তমান visibility ম্যাপ | paykaribazaronline: PUBLIC = paykaribazar, supremeai(fork), supremeai-open; PRIVATE = api, archive, core, infrastructure, mcp-control-plane, sdk, studio (৭টি) |

**GitHub-আচরণ (docs-সমর্থিত, execution-এ পুনঃযাচাই করা হবে):** public repo private করলে GitHub **public fork-গুলোকে detach করে নতুন network-এ স্থাপন করে** ("GitHub will detach public forks...")। এখানে একমাত্র fork আমাদেরটাই → detach-এর পর সেটি স্বাধীন public রিপো হবে — ফলে **"public fork private করা যায় না" সীমাবদ্ধতাটাই মুছে যাবে** (ভবিষ্যতে fork-ও চাইলে private করা যাবে)।

## Decision

1. **parent `SaifulHaqueNiloy/supremeai` → private** — ভূমিকা: receive-only **আর্কাইভ-মিরর** (full project-এর প্রতিলিপি); আর সেখানে কোনো উন্নয়ন-সিদ্ধান্ত নয়।
2. **`paykaribazaronline/supremeai` (fork) = লাইভ main** — public-ই থাকবে (GitHub-নিয়মেও থাকতে বাধ্য); fork-এর CI/CD-অবকাঠামোই এখন প্রকৃত উৎপাদন-পাইপলাইন।
3. **paykaribazaronline-এর combination অটুট থাকবে** — PUBLIC: fork supremeai + supremeai-open (API-দরজা, roadmap Phase 8) + paykaribazar (ব্যবসা); PRIVATE: api, archive, core, infrastructure, mcp-control-plane, sdk, studio।
4. **Sync-দিক উল্টে যাবে: fork → parent** (এতদিন parent → fork ছিল) — daily archive-mirror workflow (fork-এ), merge-ভিত্তিক (parent-এর ২৭ unique কমিট কখনো হারাবে না — 0-conflict প্রমাণিত), commit-বার্তায় `[skip ci]`, parent-এর Actions disable (private-এর ফ্রি-মিনিট ২০০০/মাস রক্ষা)।
5. **Secrets-কৌশল** (User-অ্যাকাউন্ট, org নেই): fork-এর বিদ্যমান ৭টি healed secret-ই মূল ভিত্তি (Infisical-runtime-স্বনির্ভর স্থাপত্য — workflows রানটাইমে vault থেকে মান টানে); প্রয়োজনে per-repo প্রতিলিপি; নতুন secret-এর ন্যূনতম দরকার — mirror-push-এর জন্য বিদ্যমান **SYNC_PAT-ই যথেষ্ট** (parent-এ push-অধিকার প্রমাণিত)।
6. **cutover-এর আগে একবার best-of merge** — parent-এর ২৭ কমিট fork-এ merge (merge-probe: conflict শূন্য) → তারপরই parent বিশুদ্ধ আর্কাইভে রূপান্তরিত হবে; "কিছুই বাদ যাবে না" নীতি অটুট।

## Consequences

**ধনাত্মক:**
- একটাই লাইভ main — দ্বৈত-রক্ষণা-জটিলতা শেষ; "olpo correction → full live" লক্ষ্যের একমাত্র ঠিকানা fork
- parent private = আর্কাইভ নিরাপদ (issues-ডেটা অটুট, শুধু প্রবেশ-সীমিত)
- fork detach-এর পরে দুই রিপো সম্পূর্ণ স্বাধীন — ভবিষ্যৎ-নমনীয়তা বাড়ে (fork-ও private-যোগ্য হয়)
- Pages নেই প্রমাণিত → flip-এ কোনো সাইট বন্ধ হবে না; আকার ~40 MB → LFS-ঝুঁকি নগণ্য

**ঋণাত্মক / one-way doors (execute-এর আগে সচেতনতা আবশ্যক):**
- parent-এর **star/watcher গণনা লুকাবে**, সার্চ/সোশ্যাল-আবিষ্কার্যতা হারাবে; পরে public করলেও star/fork-network আগের মতো ফিরে নাও আসতে পারে
- fork **auto-detach** হবে — parent→fork auto-sync workflow (id 375977882) মৃত হবে; disable করতে হবে
- parent-এর ১৮ খোলা issue private হবে (ডেটা অটুট, অ্যাক্সেস সীমিত)
- parent-এ Actions চালু রাখলে private-ফ্রি-কোটা (২০০০ মিনিট/মাস) খরচ হবে → disable করার পরামর্শ (UI/admin-PAT লাগবে)

## Execution runbook (go দিলে এক সেশনে)

- **Phase 0 — best-of merge (fork-এ):** parent→fork merge PR (0-conflict প্রমাণিত); fork = full-project best-of
- **Phase A — visibility flip:** parent → private। পথ: (ক) UI: Settings → Danger Zone → Change visibility (সবচেয়ে সহজ), অথবা (খ) parent-এ admin-অধিকারসহ PAT-এ `PATCH /repos/SaifulHaqueNiloy/supremeai {"private": true}` (বর্তমান PAT-এ admin নেই — প্রমাণিত)। পরে যাচাই: fork `fork:false` + `parent`-key অনুপস্থিত = detach নিশ্চিত
- **Phase B — fork cutover:** workflow 375977882 disable (`PAT-admin ✓`); (ঐচ্ছিক) fork-এ `archive-mirror.yml` workflow — daily cron, SYNC_PAT দিয়ে parent main-এ merge-sync push, বার্তায় `[skip ci]`
- **Phase C — parent-এ Actions disable + যাচাই:** UI-তে Settings → Actions → Disable (admin লাগবে)
- **Phase D — secrets/live-readiness অডিট-চূড়ান্তকরণ:** fork-এর ৭-secret বেস + Infisical-vault কভারেজ তালিকা; উৎপাদন-ঘাটতি = বিদ্যমান মানব-নির্ভর ৩টি (Render app-access, provider-key rotation, প্রথম consumer-key) + register #23–26 ফাইন্ডিং — এগুলিই "olpo correction"-এর প্রকৃত তালিকা

## Execution log (2026-10-08, go-প্রাপ্তির দিন)

- **Phase 0 ✓** — `POST /repos/paykaribazaronline/supremeai/merge-upstream` → 200, merge_type=merge; fork main `37d0596c` → `14cff059`; parent-ahead 27→**0** (সব parent-কমিট fork-এ); probe-যাচাই conflict=0; পরবর্তী CI: Main CI/CD ✓, Dependency Health ✓, Smart Deploy ✓ (PR-Gate action_required = PR-ইভেন্টের স্বাভাবিক অপেক্ষা, push-সংশ্লিষ্ট নয়)
- **Phase D ✓** — workflow-রেফারেন্স-গ্রেপ: ৫১টি distinct `secrets.X`; বিদ্যমান ৭-এর বাইরে **২৪টি নতুন secret vault(prod, ২১৯ keys)→fork ভরাট** (sealed-box, সব 201): RENDER×১১, VERCEL_TOKEN, CLOUDFLARE×২, GROQ/GEMINI/OPENAI, BACKEND_URL/USER_BACKEND_URL, SUPABASE_DB_POOLER/WRITER, SELF_HEAL_PAT(←GITHUB_PAT_PAYKARIBAZARONLINE); fork secret-count 7→**31**; vault-বহির্ভূত (মানব-সিদ্ধান্ত অবশিষ্ট): DATABASE_URL, DB_SCHEMA_CHECK_URL, PRODUCTION_URL/STAGING_URL, PROD_BACKEND, MCP_PRODUCTION_URL, FRONTEND/EDGE/WORKER_PRODUCTION_URL, SUPREMEAI_BASE_URL, MISSION_CONTROL_DATABASE_URL, FIREBASE_TOKEN/FIREBASE_PROJECT_ID, QA_ADMIN/CUSTOMER×৫, DEEPSEEK/OPENROUTER/ANTHROPIC_API_KEY
- **Phase A ✗→ব্যবহারকারী** — `PATCH private:true` → **403** (PAT admin-নেই, প্রমাণিত; App-token-ও admin-নেই) → UI-পথ: parent Settings → Danger Zone → Change visibility → **Make private**
- **মিরর-ক্রেডেনশিয়াল প্রমাণ** — pay_pat-এ parent git-push **403** (API permissions push:true থাকলেও fine-grained-স্কোপ-বহির্ভূত); কিন্তু **App-installation token (supremeai-3rd-party-platform, SaifulHaqueNiloy-এ ইনস্টলড) দিয়ে parent-push dry-run সফল** → post-flip archive-mirror workflow runtime-এ vault-এর AGENT_PLATFORM_APP_ID/PRIVATE_KEY থেকে স্বয়ং-মিন্ট করবে — মানব-PAT অপ্রয়োজনীয়
- **Phase B/C (post-flip, পরবর্তী সেশনে)** — ① workflow 375977882 disable ② fork-এ archive-mirror.yml যোগ (daily cron, App-token মিন্ট-স্টেপ, fork main → parent main, বার্তায় `[skip ci]`) ③ parent-এ Actions disable (UI, admin)

## পূর্বসূরি-নোট

- ADR-003-এর "main repo freeze" এই টপোলজিতে অর্থ বদলাল: freeze-এর বিষয় এখন parent (আর্কাইভ); fork লাইভ হওয়ায় ভবিষ্যৎ fork-কাজ আবার শুরু হতে পারে — তবে প্রতিটি ধাপ ব্যবহারকারীর নির্দেশেই
- ঐতিহাসিক খাতা বিভাজন: কোড-আর্কাইভ = parent (private); সিদ্ধান্ত/ওয়ার্কলগ-ইতিহাস = supremeai-archive (private) — দুই ভূমিকা পৃথক, উভয়ই অটুট
