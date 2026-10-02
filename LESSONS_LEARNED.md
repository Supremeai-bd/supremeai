# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-10-02 — 🔁 Stale Re-file লুপ: পুরনো SHA-র "RED on main" + বন্ধ-ইস্যুর স্মৃতিহীনতা (#2983)

- **সমস্যা:** একই পরিবারের ঘটনা দিনে তিনবার — #2972-76 বন্ধ (owner mass-triage 06:59Z) → **#2979-82 পুনর্জন্ম** (13:47Z, একই `ci-fail:<fingerprint>` কী) → বন্ধ → **#2989 আবার পুনর্জন্ম** (17:03Z, একই কী `a19e931c1ebf`, পুরনো Sep-25 SHA-র ব্যর্থ রান, বর্তমান main সবুজ)। প্রতিটি চক্রে owner/ফ্লিট-ট্রায়াজ, register-এ ৫টি প্রায়-অভিন্ন কমেন্ট, ভুয়া "main-red" সংকেত।
- **Root Cause:** ফাইলারের দুটি জন্মগত ফাঁক — (১) **fresh-tip অন্ধতা**: ব্যর্থ রানের head-SHA বর্তমান main HEAD কি না কেউ দেখেনি — পুরনো tip-এর ব্যর্থতাও "RED on main" সাজে; (২) **closed-history স্মৃতিহীনতা**: `find_existing_fix_issue` শুধু `state=open` দেখে — ইস্যু বন্ধ হওয়ার সাথে সাথে dedup-স্মৃতি মুছে যায়, পরের স্ক্যানই আবার জন্ম দেয় (GitHub-এ conditional-create নেই)।
- **ফিক্স (#2983 — register v2.2):**
  1. **Fresh-tip gate** (`route_failure` main-path): ব্যর্থ run-SHA ≠ বর্তমান `main` HEAD → `stale-tip` রুট (পর্যবেক্ষণ-সারি, fix-issue নয়); ব্যতিক্রম — ওই workflow-র সর্বশেষ main-রান বর্তমান tip-এই লাল হলে সত্যিকারের main-red, ফাইল হবে। API-down হলে gate fail-open (মিথ্যা-দমন নয়)।
  2. **Closed-history dedupe** (`find_recently_closed_fix_issue`): একই marker-এ `stale_refile_window_days` (৭) দিনের ভেতরে বন্ধ ইস্যু → `already-tracked (closed-history)` — re-file নয়। প্রথম-লাইন মার্কার-চুক্তি (উদ্ধৃত-মার্কার ≠ নিজের); শুধু main-red fingerprint-কীতে প্রযোজ্য — `pr:N`/`branch:X` কী নয় (PR/branch-এর নতুন ব্যর্থতা বৈধ নতুন ইস্যু)।
  3. SSOT: `pipeline_failure_policy.fresh_tip_gate` + `.stale_refile_window_days` (rules.yml); AGENT_RULES Rule 14-এ CI-ফাইলিং fresh-tip বাধ্যতামূলকতা।
- **Lesson (101%):** অটো-ফাইলারের dedup-স্মৃতি শুধু "খোলা" অবস্থায় টাটকালে সেটি ভুলে যাওয়া মানেই জন্ম-মৃত্যু-চক্র — বন্ধ-ইতিহাসও উইন্ডো-সহ মনে রাখতে হয়। আর "RED on main" দাবির একমাত্র সৎ-প্রমাণ হলো ব্যর্থ-SHA == বর্তমান tip — "কোনোদিন একটা রান লাল ছিল" সংকেত নয়; প্রতিটি ফাইলিং-সিদ্ধান্ত বর্তমান-সত্যের (tip) সাথে যাচাইযোগ্য হতে হবে।

## 2026-10-02 — 🔁 Enforcement-নয়েজ ত্রিমুখ: Guard-এর CAS-branch-বিনাশ + Register-এর উইন্ডো-অন্ধতা + GC-র claim-অন্ধতা (#2960)

- **সমস্যা:** তিনটি পারস্পরিক-সংযুক্ত নয়েজ/ধ্বংস-জেনারেটর — (১) `agent_identity.py`-এর #2950 git-push-as-CAS প্রোটোকল (`agent/<name>` identity + `role/<role>` lock branch) প্রতিটি push-এ Branch Creation Guard-এ "issue number নেই" violation + **branch-delete** খেত — CAS-state নষ্ট হয় identity-collision (দুই machine একই `glm5.2-coder-1` পেলো) + lock-churn (প্রমাণ: `role/ci-fixer` ×২২, `agent/glm5.2-coder-1` ×১৫ ব্যর্থ রান, watch-ইস্যু #2958/#2964); (২) রেজিস্টারের হীল-চেক শুধু **উইন্ডো-বাইরে** যাওয়া fingerprint-এই চলত — ব্যর্থতা সেরে গেলেও (সর্বশেষ রান সবুজ) fix-ইস্যু অযথা খোলা থাকত (#2960: Issue Template Guard main-এ পরে সবুজ, তবু P1 জীবিত; লাইভ ড্রাই-রানে ৫টি স্টেল সারি ধরা পড়ল); (৩) orphan-GC **claimed + in-progress** ইস্যু বন্ধ করে দিল (লাইভ-ঘটনা 01:43) — ইস্যু বন্ধ হওয়ায় Guard কাজ-চলা work-branch-ই মুছে ফেলল ("issue is closed")।
- **Root Cause:** (১) Guard জানত না যে কিছু branch কখনো কাজ-branch নয় — state-carrier (identity/lock CAS); claim-ইস্যু-ভিত্তিক একক মানদণ্ড সব branch-এ চাপানো হয়েছিল। (২) "Active"-এর সংজ্ঞা ছিল "উইন্ডোতে ব্যর্থ রান আছে" — "কিন্তু পরে সবুজ হয়েছে" চেকটি শুধু উইন্ডো-বাহির পথে ছিল।
- **ফিক্স (#2960):**
  1. **Protocol-branch শ্রেণি** (`branch_creation_policy.protocol_branch_patterns: ["agent/*", "role/*"]` — SSOT rules.yml + DEFAULT): agent-actor-এর জন্য branch-জন্মে ALLOW, কখনো delete নয়। নিরাপত্তা-সীমা: প্রকৃত এনফোর্সমেন্ট PR-টাইমে (Claim Gate + Lease Gate অনিবার্য) — branch-জন্মে ছাড় ≠ PR-ছাড়; অজানা actor এখনো default-deny agent-শ্রেণিতে।
  2. **উইন্ডো-ভেতরেই হীল** (`pipeline_failure_register.py` v2.1): প্রতিটি active fp-এর workflow+branch সর্বশেষ রান প্রতি-স্ক্যানে যাচাই — `success` হলে সাথে সাথে healed + fix-ইস্যু auto-close (flaky-পুনরাবৃত্তি হলে fp prev-state থেকে আবার active হয়ে ফেরে); ডাবল-হীল-গার্ড (in-window + out-of-window পথে একই fp একবারই)।
  3. **Orphan-GC claim-সুরক্ষা** (লাইভ-ঘটনা 01:43): GC একটি **claimed + status:in-progress** ইস্যু (#2960) বন্ধ করেছিল — claim করা agent তখনো ফিক্স লিখছিল; ইস্যু বন্ধ হওয়ায় Guard তার work-branch-ই মুছে দিয়েছিল ("issue is closed")। এখন `_claimed_recently`: in-progress লেবেল + `orphan_claim_protect_hours` (৬ঘ) উইন্ডোর ভেতরের সাম্প্রতিক Atomic-Claim → GC-স্পর্শ নয়; পরিত্যক্ত পুরনো claim (উইন্ডো-বাইরে) এখনো GC হবে — চিরস্থায়ী-লেবেল-ফাঁদ নয়।
- **Lesson (101%):** এনফোর্সমেন্ট-সিস্টেমের নিজের state-carrier (lock/identity branch) এনফোর্সমেন্ট-টার্গেট হলে সেটি self-sabotage — guard নিজেই CAS-নিরাপত্তা ভাঙে, ফিক্সটি আবার guard-এর কারণে ব্যর্থ রান জন্মায় (feedback loop)। GC-র মতো "পরিচ্ছন্নতা-অটোমেশন"-ও জীবিত-কাজ শনাক্তকরণ ছাড়া ধ্বংসাত্মক — claim মানে চলমান কাজ, ইস্যু-লাইফসাইকেল আর branch-লাইফসাইকেল একই চেইনে বাঁধা। আর ট্র্যাকিং-সিস্টেমে "active" মানে অবশ্যই "এখনো লাল", "কোনোদিন লাল ছিল" নয় — পুনরুদ্ধার-সনাক্তকরণ (latest-run-জানা) প্রতিটি স্ক্যানে চালাতে হবে, window-expiry-র উপর ভরসা করা যাবে না।

## 2026-10-01 — 🧊 Old-Code Push & এক-ইস্যু-বোঝা: Stale-Base Merge-ঝুঁকি + গ্রুপ-মডেল ভুল বোঝা (#2935)

- **সমস্যা:** দুটি সমান্তরাল ঘটনা — (১) planner-এর PR #2924/#2926 পুরনো main-base-এ জন্মেছিল (merge-base main-HEAD-এর ৪-৬ commit পেছনে); main এগিয়ে যাওয়ার পর সেগুলো merge করলে `rules.yml`/`pr.yml`/`AGENT_RULES.md`-এর নতুন পরিবর্তন চুপচাপ revert হয়ে যেত ("old code push"); (২) "সব ব্যর্থতা এক গ্রুপে" চাহিদাটি v1-এ **একটিমাত্র ledger-ইস্যুতে** ভুলভাবে বাস্তবায়িত হয়েছিল — ফলে এক claimer-এর পুরো বোঝা নিতে হতো, সমান্তরাল ফিক্স অসম্ভব ছিল।
- **Root Cause:** (১) PR-র freshness-র কোনো root-enforcement ছিল না — "behind main" ধরা পড়ত শুধু conflict হলে, non-conflicting stale-merge নীরবে main কোড মুছে দিত; (২) "গ্রুপ" শব্দের সংজ্ঞা অস্পষ্ট ছিল — গ্রুপ মানে **একই লেবেল-সূচি**, একই ইস্যু-বডি নয়।
- **ফিক্স (#2935):**
  1. **Freshness Gate** (`.github/scripts/constitution/freshness_gate.py` → pr.yml system-gates, blocking): merge-base ≠ main-HEAD হলেই BLOCK (strict মোড) + self-heal নির্দেশনা — "new main er sathe mil thakle e push hobe" এখন কাঠামোগত সত্য; AI evaluator-ও একই সংকেত compare-API থেকে পড়ে (Safety-ক্রাইটেরিয়া)।
  2. **Register v2:** `workflows_watched: ["*"]` — নতুন pipeline যোগ হলে ট্র্যাকিং-আপডেট লাগে না (workflow_run-নাম ছিল দ্বিতীয় হার্ডকোড-জায়গা — সেটিও periodic full-scan দিয়ে কভার)।
  3. **এক-গ্রুপ-প্রতি-ব্যর্থতা-ইস্যু:** প্রতিটি অ্যাকশনেবল ব্যর্থতার নিজস্ব claimable ইস্যু (`group:pipeline-failures`) — held PR-গুলোর কারণ (কোন গেট লাল, কোন ফাইল, claim/template/freshness কী ঠিক করতে হবে) ইস্যু-বডিতে; হীল হলে auto-close।
  4. **AI PR Evaluator** (`ai_pr_evaluator.py` + workflow): ২-ক্রাইটেরিয়া (Value+Safety) রায় AUTO_MERGE/HOLD_AND_FIX/CLOSE — HOLD রায়ের কারণ per-PR ইস্যুতে যায় (register-শেয়ার্ড মার্কার-চুক্তি `<!-- pfr-fix:pr:{N} -->`)।
- **Lesson (101%):** "গ্রুপ" মানে সূচি+লেবেল, মনোলিথ-ইস্যু নয় — সমান্তরালতা রক্ষার চাবিকাঠি প্রতি-কাজের আলাদা claimability। আর merge-ঝুঁকির একমাত্র সৎ-পরিমাপ হলো merge-base vs main-HEAD — conflict-হীনতা নিরাপত্তার প্রমাণ নয় (non-conflicting stale-merge-ই সবচেয়ে নীরব রিগ্রেশন)। ট্র্যাকিং-সিস্টেমে নাম-হার্ডকোড মানে প্রতিটি নতুন pipeline-এ ভুলের নতুন সুযোগ — ডিফল্ট সবসময় wildcard + ব্যতিক্রম-তালিকা।

## 2026-10-01 — 🛡️ Advisory Templates & Allowlist-Identity: "উপদেশ-ভিত্তিক গভর্নেন্স মানেই ফাঁকা দরজা" (#2912)

- **সমস্যা:** Red-team audit (breaker role) দুটি মূল ফাঁক পেয়েছে — (১) issue/PR টেমপ্লেট ছিল advisory: GitHub-এর native template শুধু web UI-তে auto-apply হয়, agent-রা `gh issue/pr create --body` দিয়ে freeform body দিলে `blank_issues_enabled: false`-ও কিছুই আটকাত না — Touching Files/Verification চুক্তি অদৃশ্য; (২) agent-ডিটেকশন ছিল allowlist-of-prefixes (`supremeai-*`) — `supremeai-` দিয়ে শুরু না-হওয়া যেকোনো নতুন/অজানা বট "human" বলে সব গার্ট bypass করতে পারত। লাইভ প্রমাণ: planner অন্যের claimed issue #2912-এর নম্বর নিয়ে নিজের কাজের branch/PR (#2913) খুলতে গিয়েছিল।
- **Root Cause:** Enforcement ডিজাইন ছিল "ভালো আচরণ আশা করা" (advisory template + prefix-allowlist) — "ভুল করা অসম্ভব করা" (poka-yoke) নয়।
- **ফিক্স (#2912, Template Enforcement Chain):**
  1. `template_gate.py` + `issue-template-guard.yml` (on: issues opened/edited) — agent-created work-issue-তে Mission/Priority/Touching Files/Verification সেকশন যাচাই; violation-এ `template:violating` লেবেল + বাংলা self-heal কমেন্ট; edit-এ ঠিক হলে লেবেল সরে।
  2. **চেইন-ডকট্রিন:** `template:violating` issue-র claim অবৈধ → Branch Creation Guard ব্লক (inline যাচাই — label মুছলেও bypass নয়) → PR Template Gate (pr.yml) ব্লক।
  3. `identity_policy` default-deny: মানুষ শুধু `human_allowlist`-এ; trusted infra-bot আলাদা তালিকায়; **বাকি সব actor = agent** — অজানা পরিচয় আর "human" বলে ফাঁকি দিতে পারে না।
  4. `branch_creation_policy` exempt-সংকোচন: `backport/*`, `release/*` এখন issue+claim চায়; `group/*`, `docs/*` স্পষ্টভাবে `pr_gated_branch_patterns`-এ (PR-টাইম Lease Gate-এর এখতিয়ার)।
  5. Claim-source hygiene: ledger-marker/`type:ledger`/`type:platform-alert` issue-র claim আর branch-license নয়।
- **Lesson (101%):** টেমপ্লেট/নিয়ম লেখা মানেই enforcement নয় — enforcement-পয়েন্ট সেটাই যেখানে ভুলটা জন্মায় (issue-জন্ম, branch-জন্ম, PR-জন্ম)। আর identity-যাচাই সবসময় default-deny হবে: "who is NOT in the trusted list" — "who LOOKS like an agent" নয়।

## 2026-09-28 — 🏛️ Rules vs. Architecture Conflation: কন্সটিটিউশনে পাইপলাইন অটোমেশন ঢুকিয়ে এজেন্টদের কনফিউজ করা এবং 'The 101% Benefit Principle'

- **সমস্যা:** `AGENTS.md`-তে Rule 28 হিসেবে "Cascade Hold" (আগের ধাপে সমস্যা থাকলে পেছনের সব PR অটো-হোল্ড) এবং Rule 27 হিসেবে "Dynamic Queue Insertion (+1 শিফট)" অন্তর্ভুক্ত করা হয়েছিল। এটি ছিল এজেন্টের জন্য বড় বিভ্রান্তি: Cascade Hold বা Queue Shifting হলো সিআই/মার্জ ট্রেনের **আর্কিটেকচার ও ইঞ্জিন অটোমেশন** (`scripts/ci/issue_queue_manager.py`), যা এজেন্টের নিজের আচরণ বা কোড লেখার কোনো রুল নয়। এর ফলে আর্কিটেকচার ও রুলসের সীমানা গুলিয়ে সিস্টেম আবার স্ফীত ও জটিল হচ্ছিল।
- **Root Cause:** আর্কিটেকচারাল মেকানিজম (ইঞ্জিন কীভাবে কাজ করে) এবং এজেন্টের কন্সটিটিউশনাল রুলস (এজেন্ট কী আচরণ করবে/কী করবে না)-এর মধ্যে স্পষ্ট সীমারেখা না টানা।
- **The 101% Benefit Principle:**  
  > **“সমস্যা পেলে শুধু কোড ফিক্স করা ১% লাভ; কিন্তু সেই সমস্যা ভবিষ্যতে আর কখনোই যেন না ঘটতে পারে তা রুট লেভেলে বন্ধ করা ১০১% লাভ।”**  
  - রুলসের কাজ হলো ১০১% সুরক্ষাকবচ তৈরি করা যাতে ভুলের রুট-কজ সমূলে বিনাশ হয়।
  - আর্কিটেকচারের কাজ হলো সিস্টেমকে টেকনিক্যালি রান করানো (মার্জ ট্রেন, ডিস্ট্রিবিউটেড লকিং ইত্যাদি)।
- **ফিক্স:**
  - `AGENTS.md` থেকে Rule 27 ও Rule 28 অপসারণ করে সিআই আর্কিটেকচারে স্থানান্তর করা হয়েছে।
  - `AGENTS.md`-তে শুধুমাত্র এজেন্টের বাস্তব কার্যকরী আচরণ রুলস হিসেবে রাখা হয়েছে:
    1. **Slot Isolation:** `acquire_role_slot.py` + `<lane>-<N>-<issue#>-<slug>`.
    2. **Atomic Claim Lock & File Declaration:** কাজ শুরুর আগে ক্লেইম ও কমেন্টে `Touching files: ...` ঘোষণা।
    3. **3-Tier Verification First:** অনুমানে ডিলিট/এডিট নিষিদ্ধ। (১) Reflection check, (২) Boot smoke test, (৩) Pytest.
    4. **Atomic Blast Radius:** ১ PR = ১ ইস্যু, সর্বোচ্চ ১–২ ফাইল।
    5. **The Dual-State Game (Solver ➔ Peer Reviewer):** আনক্লেইমড কাজ থাকলে কোডার (State A); কাজ শেষ হলে সহকর্মীর PR অডিটকারী পিয়ার রিভিউয়ার (State B)।
- **লেসন:** রুলস সবসময় সংক্ষেপ, সরাসরি এবং ভুলের রুট-কজ নির্মূলকারী হতে হবে। ইঞ্জিনের মেকানিক্সকে রুলস বানিয়ে এজেন্টের কনটেক্সট বা ব্রেন জ্যাম করা আত্মঘাতী।

## 2026-09-28 — 🔁 Duplicate PRs: 12টি Branch-এ Issue-Number না থাকায় ও `has-pr` Label-বিহীন PR খোলায় ১টি Issue-এ ৪টি পর্যন্ত PR (GAP-DUPLICATE-01) (#2296)

- **সমস্যা:** Step 1 execution-এ Issue #2252, #2253, #2255, #2256, #2248-এর জন্য ২-৪টি করে duplicate PR তৈরি হয়। মোট ১২টি `coder-1`, `coder-2` ইত্যাদি generic slot-only branch name ব্যবহার করায় কোনো agent-ই detect করতে পারেনি যে সেই issue-এ আগে কাজ চলছে।
- **Root Causes (4টি):**
  1. **Branch name-এ issue number নেই** — `coder-1`, `coder-4` শুধু slot; দ্বিতীয় agent-এর কাছে collision signal ছিল না।
  2. **PR open করার পর `has-pr` label issue-এ যোগ করা হয়নি** — `atomic_claim.sh` শুধু `status:in-progress` check করে, `has-pr` চেক করেনি।
  3. **Concurrent agents race** — একাধিক agent একই মিলিসেকেন্ডে একই issue unclaimed দেখে দুজনেই PR খুলেছে।
  4. **Pre-PR duplicate check নেই** — `gh pr create` করার আগে কেউ check করেনি "এই issue-এ কোনো open PR আছে কি?"
- **ফিক্স:**
  - `AGENTS.md` Rule **#24**: `gh pr create` সফল হওয়ার সাথে সাথে `gh issue edit <N> --add-label 'has-pr'` বাধ্যতামূলক (zero-tolerance)।
  - `AGENTS.md` Rule **#25**: Branch name format MUST be `<lane>-<N>-<issue_number>-<slug>` — generic slot-only (`coder-1`) strictly forbidden।
  - `atomic_claim.sh` update: `has-pr` label দেখলেই claim abort (exit 1); open PR search করে backfill করে। `BRANCH_NAME` env var চেক করে issue number আছে কিনা।
- **লেসন:** **"একটা লেবেল সব duplicate ঠেকায়।"** PR খোলার সাথে সাথে `has-pr` label = পরবর্তী সব agent-এর জন্য hard stop। Branch name-এ issue number = collision-detection trivial। এই দুটো নিয়ম এক সাথে থাকলে ৪টি root cause-এর ৩টিই আপনা-আপনি বন্ধ হয়।
