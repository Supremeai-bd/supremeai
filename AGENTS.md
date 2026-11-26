<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- Source of truth: .github/constitution/rules.yml · Generator: scripts/ci/generate_agents_md.py -->
<!-- CI drift check: system-gates.yml → agents-md-sync. To change rules, edit rules.yml. -->


# SupremeAI — AGENTS.md (Universal Operating Constitution & Agent Bootstrap — Unified v3.1)

> rules_version: `3.3` · যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।
>
> Agent-কে ঘুড়ির মতো স্বাধীনভাবে উড়তে দাও; কিন্তু নাটাই সবসময় SupremeAI Admin / Control Plane-এর হাতে থাকবে।

### Operator Creed (admin — non-negotiable)

- Fastest, lightest, secure, zero-cost — and actually used. Every feature must earn its place.
- Single source of logic: the same job always follows the same code path. A justified exception ships with a comment explaining why it exists.
- Find a problem → fix it at the root. No over-engineering.
- Never hoard defensive copies 'in case something breaks'. Fixing it a hundred times beats creating one layer of speculative waste.

---

## The Living Protocols (Root-Cause Invariants — ১০১% লাভ)

### 1. Atomic Claim Lock & File Declaration
গ্রুপ সিকোয়েন্সের (GSPQ) প্রথম আনক্লেইমড ইস্যুটি ক্লেইম করো (`atomic_claim.sh`)। ক্লেইম কমেন্টে 'Touching files: file1, file2' ঘোষণা করো। নো ক্লেইম, নো কোড।

### 2. Verify First (3-Tier Verification)
অনুমানে ফাইল ডিলিট বা এডিট নিষিদ্ধ। পরিবর্তনের আগে ও পরে ৩ স্তর যাচাই আবশ্যক: (১) Reflection check (grep), (২) Boot smoke test (python -c 'import main'), (৩) Pytest। টেস্ট ম্যানিপুলেশন (delete/skip/fake assertion) কঠোরভাবে নিষিদ্ধ।

### 3. Mandatory 'has-pr' Label
PR খোলার সাথে সাথেই gh issue edit <id> --add-label 'has-pr' চালাতে হবে। এটি ডুপ্লিকেট PR তৈরি হওয়া রুট থেকে বন্ধ করে।

### 4. Automated CI Guard & Pure Solver Lane
কোডারদের ম্যানুয়াল PR রিভিউ লেখার কোনো প্রয়োজন নেই — PR নিরাপত্তা, টেস্ট ও রিগ্রেশন স্বয়ংক্রিয় CI Gates (Lease, Verification, Scope, Collision) এবং PR Helper পরিচালনা করে। কোডার এজেন্টের ১০০% ফোকাস থাকবে ইস্যু সমাধান, ৩-স্তর যাচাই ও পরমাণু PR তৈরিতে।

### 5. Standard Group Issue Creation Protocol (পরবর্তী ইস্যু তৈরির নিয়ম)
ভবিষ্যতে যখনই নতুন গ্রুপ বা সিকোয়েন্স ইস্যু তৈরি করা হবে, তা অবশ্যই স্ট্যান্ডার্ড টেমপ্লেট (`scripts/ci/create_group_issue.py` বা GitHub issue form) অনুযায়ী তৈরি করতে হবে। প্রতিটি ইস্যুতে স্পষ্টভাবে থাকতে হবে: (১) Group ও Sequence ট্যাগ (`group:step-X`, `seq:Y`), (২) Predecessor নির্ভরতা, (৩) 'Touching files' ও পরমাণু ব্লাস্ট রেডিয়াস ঘোষণা, (৪) ৩-স্তর ভেরিফিকেশন নির্দেশাবলী, (৫) বাধ্যতামূলক বাংলা/বাংলিশ কোড কমেন্টস (`# বাংলা মন্তব্য:`), এবং (৬) স্পষ্ট স্ট্রেজিং নোটিশ: 'গ্রুপ সম্পূর্ণ শেষ হওয়ার পর ১টি একক PR হবে — মাঝপথে কোনো বিচ্ছিন্ন PR নয়'।

### 6. Issues as Live Operational Truth & TelDrive Backup (ডকুমেন্টেশন Issues-এ সংরক্ষণ ও TelDrive ব্যাকআপ নীতি)
রিপোজিটরির ভেতরে নতুন কোনো বিচ্ছিন্ন .md ফাইল তৈরি করে ফাইল স্প্রল বা সাইজ বাড়ানো নিষিদ্ধ। এজেন্টের সমস্ত নতুন আর্কিটেকচারাল সিদ্ধান্ত, গাইড, প্ল্যান ও অপারেশনাল ট্রুথ সরাসরি সংশ্লিষ্ট GitHub Issue-তে কমেন্ট বা বডিতে যুক্ত করতে হবে (GitHub Issues as Live Operational Truth)। আর বিদ্যমান কোনো দীর্ঘ ডক্স বা রেফারেন্স ফাইল কোডবেসে না জমিয়ে সরাসরি TelDrive (টেলিগ্রাম ব্যাকআপ ক্লাউড)-এ সংরক্ষণ ও ব্যাকআপ করতে হবে। এর ফলে রিপোর সাইজ হালকা থাকবে এবং সমস্ত সিদ্ধান্ত ট্র্যাকেবল থাকবে।

### 7. Persistent Branch Lifecycle (পারসিস্টেন্ট ব্রাঞ্চ লাইফসাইকেল — #4200 ক্যানোনিকাল মডেল)
ক্যানোনিকাল এজেন্ট-লাইফসাইকেল: Issue → Atomic Claim → Persistent Issue Branch (agent/<issue>-slug) → Checkpoint Commit/Push → এজেন্ট সেশন শেষ হলেও ব্রাঞ্চ টেকে → পরবর্তী এজেন্ট discover/resume করে → latest main-এর বিপরীতে verify → READY → PR → PR Gate → Merge Gate → Main Pipeline। ব্রাঞ্চ হলো টেকসই ওয়ার্কস্পেস, এজেন্ট হলো বদলে যাওয়া কর্মী, PR হলো integration artifact — lifecycle checkpoint নয়। চেকপয়েন্ট push বৈধ এবং PR ছাড়াই হবে; PR তৈরি হবে কেবল branch:ready ট্রানজিশনে। ব্রাঞ্চ state labels (branch:active/paused/orphaned/ready) সমন্বয়-সংকেত মাত্র — source of truth নয়; git branch existence, commit history ও issue linkage-ই কর্তৃত্বপূর্ণ। ব্রাঞ্চ cleanup/ডিলিশন কেবল fail-closed merged/completed-proof পথেই (scripts/ci/cleanup_stale_branches.py) করা যাবে।

### 8. Architecture Preservation & DRY 3-Pipeline Law (একক ৩-পাইপলাইন ও রিইউজিবিলিটি নীতি)
সিস্টেমের বিদ্যমান আর্কিটেকচার যেমন আছে হুবহু তেমন অক্ষত ও অপরিবর্তিত থাকবে যদি না পরিবর্তন একান্তই অপরিহার্য (Preserve architecture intact until it is must)। সিআই/সিডি ফ্র্যাগমেন্টেশন ও ফাইল স্প্রল বন্ধ করে DRY (Don't Repeat Yourself) ও Reusable কাঠামোর ৩টি একক পাইপলাইন বলবৎ থাকবে: (১) PR-এ থাকবে ১টি গেট (PR Gate — স্কোপ, লিজ, ভেরিফিকেশন ও পলিসি গার্ড), (২) Merge Train-এ থাকবে ১টি (Train Gate — ব্যাচ রোলআপ, সিকোয়েন্স ও ডিপেন্ডেন্সি হোল্ড), এবং (৩) Main-এ মার্জের পর থাকবে ১টি (Main CI/CD — টেস্ট, বিল্ড, পোস্ট-মার্জ রিলিজ ও জানিটর)। ডুপ্লিকেট রান বা বিক্ষিপ্ত ট্রিগার সম্পূর্ণ নিষিদ্ধ।

### 9. Strict Sequential Priority Resolution (অগ্রাধিকার অনুযায়ী একক-PR ফিক্স ও মার্জ নীতি — সম্পূর্ণ বাস্তবভিত্তিক)
গ্রুপ বা স্বাধীন যেকোনো কাজের ক্ষেত্রে সমান্তরাল একাধিক PR নিয়ে টানাটানি এবং মাঝপথে `queue:hold`-এ PR জমিয়ে রাখা সম্পূর্ণ নিষিদ্ধ। একই গ্রুপের সব ইস্যু persistent issue branch-এ ক্রমানুসারে একের পর এক এজেন্ট সম্পন্ন করবে; PR তৈরি হবে কেবল READY ট্রানজিশনে (integration boundary — Persistent Branch Lifecycle দ্রষ্টব্য)। আর কিউতে থাকা সমস্ত ওপেন PR সর্বদা সর্বোচ্চ প্রায়োরিটি (Rank 1 / P0) অনুযায়ী এক-একটি করে মূল্যায়ন করা হবে: লোকাল ও CI টেস্ট ১০০% গ্রিন নিশ্চিত করে সরাসরি `main`-এ মার্জ সম্পন্ন করতে হবে এবং তারপরই কেবল পরবর্তী অধস্তন PR-এ হাত দেওয়া যাবে (Strict Sequential Priority Resolution)। এটি সিআই জ্যাম, ব্রাঞ্চ ড্রিফট, ডেডলক ও ক্রস-PR কনফ্লিক্ট চিরতরে নির্মূল করে সর্বোচ্চ গতি ও কার্যকারিতা নিশ্চিত করে।

### 10. Bi-Directional Cross-Repo Patch Protocol (উভয় রিপোতে স্বয়ংক্রিয় প্যাচ ও পিআর নীতি)
যদি কোনো এজেন্ট একটি রিপোতে (যেমন supremeai বা supremeai-public) কাজ করার সময় লক্ষ্য করে যে অপর রিপোতেও সঙ্গতিপূর্ণ পরিবর্তন প্রয়োজন, তবে জটিল কোনো ম্যানুয়াল ধাপ ছাড়াই সরাসরি হেল্পার স্ক্রিপ্ট `python scripts/ci/create_cross_repo_patch.py --target <public|private> --slug <slug>` ব্যবহার করে স্ট্যান্ডার্ড git diff/patch তৈরি করবে, যা `.patches/<target>/<slug>.patch` (supremeai থেকে `.patches/public/*.patch`, supremeai-public থেকে `.patches/private/*.patch`) ফাইলে সংরক্ষিত হবে এবং ক্লেইমে 'Touching files:' হিসেবে ঘোষণা করবে। (অথবা সরাসরি `bridge_submit_patch`-এ `repo: "supremeai-public"` দিয়েও পাবলিক রিপোতে PR খোলা যাবে।) সোর্স রিপোর PR মার্জ হওয়া মাত্রই অটোমেটেড সিআই স্ক্রিপ্ট (`apply_cross_repo_patch.py`) টার্গেট রিপোতে স্বয়ংক্রিয়ভাবে নতুন ব্রাঞ্চ তৈরি করে প্যাচ অ্যাপ্লাই করবে এবং 'auto-sync' লেবেলযুক্ত PR ওপেন করবে। সার্কুলার লুপ প্রতিরোধে বটের তৈরি PR-এ এই অটোমেশন নিষ্ক্রিয় থাকবে **শুধু তখনই, যখন প্যাচ ফাইলটি ইতিমধ্যে টার্গেট রিপোতে merge হয়ে `.patches/` থেকে মুছে ফেলা হয়েছে** — অর্থাৎ লুপ বন্ধের আসল নিয়ম হলো: merge শেষে ইনপুট প্যাচ মুছে ফেলা। (`github.actor != 'github-actions[bot]'` শর্তটি 2026-11-23-এ সরানো হয়েছে, কারণ স্ক্রিপ্ট কখনো সরাসরি main-এ push করে না — সবসময় নতুন ব্রাঞ্চ ও PR খোলে।) ⚠️ **অবশিষ্ট ঝুঁকি:** প্যাচ ফাইলটি merge-এর পরেও `.patches/`-এ থেকে গেলে প্রতিটি পরবর্তী push-এ আবার sync চেষ্টা হবে (একই ব্রাঞ্চ-নামে force-push হয়ে আগের PR আপডেট হবে)। তাই merge-এর পর প্যাচ মোছা বাধ্যতামূলক।

### 11. MCP Tower Push & Tooling Governance (টাওয়ার রাইট/পুশ ও টুলিং নীতি)
MCP Tower-এ পূর্ণাঙ্গ GitHub Write/Push টুলস (`github_push_file`, `bridge_submit_patch`, `github_merge_pr`, `guardian_act`) সক্রিয়। তবে `main`-এ অন্ধ পুশ সম্পূর্ণ নিষিদ্ধ (fail-closed: main branch direct-push blocked)। সমস্ত কোড পরিবর্তন শাখা ব্রাঞ্চ (`agent/<issue>-slug`) বা ব্রিজ ওয়ার্ক অর্ডারে পুশ হবে এবং ৩-স্তর ভেরিফিকেশন ও CI Gate পাস করে মার্জ হবে। Progressive Disclosure (`tool-visibility.ts`)-এর কারণে অনেক টুল `tools/list`-এ লুকানো থাকে—নাম জানতে `tower_catalog` / `tower_describe` ও কল করতে `tower_invoke` (বা সরাসরি `tools/call`) ব্যবহার করো। `bridge_submit_patch` শুধু `supremeai` টার্গেট করে; `supremeai-public`-এ পুশ করতে `github_push_file` + `github_merge_pr`-এ `repo: "supremeai-public"` দাও। এছাড়া এপিআই টেস্টিংয়ের জন্য Hoppscotch (`api-schemas/hoppscotch/`) এবং লাইভ ট্র্যাফিক মনিটরিংয়ে Umami Analytics ক্লাউড এজ-এ কনফিগার করা।

---

## Bootstrap Checklist (সেশন শুরু হলে ঠিক এই ক্রমে কাজ করো)

1. `git fetch origin --prune && cat AGENTS.md` — সেশন শুরুতে সর্বদা main sync ও AGENTS.md পড়ো — rules পরিবর্তন হয়েছে কিনা দেখো
2. `cat docs/PR_TO_PRODUCTION_LIFECYCLE.md` — বর্তমান PR, runner ও deployment চুক্তি পড়ো
3. `python scripts/agents/acquire_role_slot.py --role <lane>` — অটো-ডিসকভারি: পরবর্তী প্রায়োরিটি ইস্যু নিজে খুঁজে স্লট ও ব্রাঞ্চ তৈরি করে। নির্দিষ্ট ইস্যুর জন্য: --issue <id>
4. `./scripts/ci/atomic_claim.sh <issue#> <agent>` — ইস্যু ক্লেইম ও 'Touching files:' ঘোষণা করো (GH_TOKEN অটো-fallback: gh auth login)
5. `python scripts/agents/mcp_tower_client.py heartbeat --slot agent-<N> --name <id>` — Control Tower Heartbeat: MCP মেশে নিজেকে 'state=online' রেজিস্টার করো
6. `3-Tier Verification (Reflection → Boot Smoke → Pytest)` — কোনো টেস্ট ভাঙা বা ডিলিট করা নিষিদ্ধ
7. `gh pr create ... && gh issue edit <issue#> --add-label 'has-pr'` — স্বাধীন কাজের ক্ষেত্রে বা সম্পূর্ণ গ্রুপের কাজ শেষ হলে একক PR খোলো এবং অবিলম্বে has-pr লেবেল দাও

এক কমান্ড বিকল্প: `./scripts/agents/session_boot.sh --lane <role> [--issue N]` — উপরের ১–৫ ধাপ একসাথে চালায় (গেট bypass নয়; dry-run: `--dry-run`)।
PR-এর আগে Test Evidence: `scripts/ci/capture_test_evidence.sh` চালিয়ে pytest/tsc/vitest output PR body-তে পেস্ট করো (manual copy নয়)।

_কাজ শুরুর আগে সর্বদা `git fetch origin --prune && cat AGENTS.md` চালাও।_

---

## System যা আটকাবে (মনে রাখার দরকার নেই — শুধু জেনে রাখো কেন আটকালো)

| Gate | কখন আটকাবে | Enforcement |
| :--- | :--- | :--- |
| Lease Gate | PR head branch লেখকের leased slot-এর বাইরে (bot slot-mismatch), বা mesh lease মেয়াদ শেষ | CI (pr.yml) |
| Verification Gate | PR description-এ Test Evidence সেকশন নেই (টেস্ট লগ/কমান্ড আউটপুট ছাড়া PR BLOCK) | CI (pr.yml) |
| Scope Gate | claim-এ declare করা 'Touching files:'-এর বাইরের ফাইল PR-এ বদলালে BLOCK | CI (pr.yml) |
| Collision Gate | অন্য open PR-এর ফাইলের সাথে direct overlap হলে BLOCK | CI (pr.yml) |
| Self-Merge Gate | নিজের PR নিজে approve/merge করলে BLOCK | CI (pr.yml) |
| Test Guard | test delete/skip/threshold-নামানো হলে BLOCK | CI (pr.yml) |
| Post-Merge Watch | merge-এর ১৫ মিনিটের মধ্যে main লাল হলে (watchdog admin-alert — কোনো অন্ধ auto-revert নয়, revert সিদ্ধান্ত অ্যাডমিনের নাটাইয়ে) | CI (main.yml) |
| Predecessor Group Merge Hold Gate | পূর্ববর্তী গ্রুপ (Predecessor Group) সম্পূর্ণ না হলে পরবর্তী গ্রুপের PR queue:hold ছাড়া মার্জ করা নিষিদ্ধ | CI (pr.yml) |
| Claim Gate (claim-before-work) | PR লেখকের linked issue-এ valid claim (assignee / Atomic Claim comment / group participation) নেই — claim ছাড়া PR BLOCK। supremeai-* এজেন্ট-লেখক কখনো exempt নয় (OWNER association-ও বট-অ্যাকাউন্টকে বাইপাস দেয় না); মানুষ (OWNER/MEMBER/COLLABORATOR) advisory | CI (pr.yml) |
| Discovery Disclosure Gate (Charter Rule #7 flywheel) | PR body-তে discovery-মার্কার (discovered/found/পাওয়া গেছে + bug/vulnerability/root-cause) থাকলে 'Discovery issue: #N' রেফারেন্স বাধ্যতামূলক — মার্কার ছাড়া ফাইল করা discovery কমেন্টেই মরে যেত | CI (pr.yml) |
| Topological Sequence Gate (#2682) | PR শুধু Layer 4/5 (API/Frontend) ফাইল বদলায় অথচ নিচের কোনো লেয়ারের (Schemas/Tools/Workers/Core) ফাইল স্পর্শ না করে এবং PR body-তে '## Reflection Evidence' (why + alternatives_rejected) না থাকলে BLOCK — অন্ধ UI/API-প্রথম কোডিং নিষিদ্ধ | CI (pr.yml) |
| Branch Creation Guard (no-branch-without-claim) | এজেন্ট-actor এমন branch তৈরি করলে যাতে issue-number নেই, বা issue বন্ধ/অনুপস্থিত, বা actor-এর সেই issue-তে Atomic Claim/assignee নেই — branch-ই delete + issue-এ ব্যাখ্যা-কমেন্ট (self-heal; মানুষ-actor advisory-allow, বিদ্যমান branch grandfathered) | CI (branch-creation-guard.yml) |

---

## Peer Review Protocol (The 4-Pillar Rubric)

| Pillar | প্রশ্ন ও মানদণ্ড |
| :--- | :--- |
| **1. System Stability** | সিস্টেম বা আর্কিটেকচারে কোনো ব্রেকিং পরিবর্তন বা অঘোষিত সাইড-ইফেক্ট আছে কি না? |
| **2. Real Benefit** | বাস্তব উন্নতি হয়েছে কি না? (LOC হ্রাস / ডেড-কোড ছাঁটাই / বাগ ফিক্স / নির্ভরযোগ্যতা বৃদ্ধি) |
| **3. Zero Regression** | সব টেস্ট সফল কি না? কোনো টেস্ট ডিলিট, স্কিপ বা ফেইক অ্যাসারশন করা হয়নি তো? |
| **4. Scope Narrowness** | ঘোষিত ফাইলের বাইরে ড্রাইভ-বাই রিফ্যাক্টরিং বা অনাকাঙ্ক্ষিত কোড ঢুকেছে কি না? |

---

## তোমার স্বাধীনতা (কেউ আটকাবে না)

- সমাধানের বাস্তবসম্মত অ্যাপ্রোচ ও ডিজাইন প্যাটার্ন নিজে বেছে নাও।
- ১ম এজেন্টের সাজেশনের সাথে নিজের কোড অ্যানালাইসিস মিলিয়ে সবচেয়ে সেরা সমাধান বেছে নেওয়ার পূর্ণ স্বাধীনতা কোডারের রয়েছে।
- এজ-কেস মোকাবিলায় এবং শতভাগ কনভার্জেন্স অর্জনে প্রয়োজনে অতিরিক্ত অভ্যন্তরীণ টেস্ট বা ডিফেন্সিভ গার্ড যোগ করার স্বাধীনতা রয়েছে।
- যেকোনো সন্দেহজনক বা অযাচাইকৃত সোর্স দেখলে সরাসরি ভেটো (Veto/বাধা) দিয়ে নিরাপদ বিকল্প প্রস্তাব করার পূর্ণ অধিকার প্রতিটি এজেন্টের রয়েছে।

---

## একমাত্র কঠিন নিয়ম (মোট ৩টা, বাকি সব system-এর ভার)

1. সততা ও নির্ভরযোগ্যতা: কোড ও টেস্ট ১০০% খাঁটি হতে হবে; টেস্ট ম্যানিপুলেশন (delete/skip/fake assertion) সর্বোচ্চ অপরাধ।
2. সম্পূর্ণ গ্রুপের একক PR (Full Group = 1 Unified PR): গ্রুপের প্রতিটি ইস্যুর জন্য পৃথক পৃথক PR খোলার প্রয়োজন নেই। ১ম ইস্যু শেষ হলে সরাসরি গ্রুপ ব্রাঞ্চে পুশ হবে, ২য় এজেন্ট সেই ব্রাঞ্চ থেকেই ২য় ইস্যুর কাজ করবে, এবং সম্পূর্ণ গ্রুপের সমস্ত কাজ শেষ হলে পুরো গ্রুপের জন্য মাত্র ১টি একক ও সমন্বিত PR তৈরি হবে।
3. অবিরাম সক্রিয়তা: কিউ থেকে ক্রমানুসারে পরবর্তী কাজ তুলে নাও, কোনো কাজে ব্লকার পেলে সাথে সাথে ব্লকার ইস্যু ফাইল করে এগিয়ে যাও।
4. বাংলা/বাংলিশ ব্যবহারের বাধ্যবাধকতা: আমাদের পুরো টেক টিম বাংলাদেশি — তাই যেখানেই সম্ভব বাংলা (বা প্রাঞ্জল বাংলিশ) ব্যবহার করতে হবে। (১) কোডের ভেতরের সমস্ত মন্তব্য ও সিদ্ধান্তের ব্যাখ্যা (code comments — e.g. '# বাংলা মন্তব্য:'), (২) অ্যাডমিনের যেকোনো প্রশ্নের উত্তর, বার্তা ও স্ট্যাটাস রিপোর্ট, এবং (৩) PR সামারি, ডেসক্রিপশন ও ইস্যু ডিসকাশনে বাংলা বা বাংলিশ ১০০% বাধ্যতামূলক (Mandatory Bengali/Banglish)। কেবল কোড সিনট্যাক্স, ভ্যারিয়েবল নেম ও শেল কমান্ড ব্যতীত সমস্ত যোগাযোগ ও ব্যাখ্যা বাংলায় হতে হবে।
5. আর্কিটেকচার স্থায়িত্ব ও ৩-পাইপলাইন নীতি (Architecture Preservation & DRY 3-Pipeline Law): আর্কিটেকচার যেমন আছে হুবহু তেমন অক্ষত থাকবে যদি না কোনো পরিবর্তন একান্তই অপরিহার্য (until it is must)। সিআই/সিডি-তে কোনো ওয়ার্কফ্লো স্প্রল বা ডুপ্লিকেট রান থাকবে না — প্রতিটি অ্যাকশনে মাত্র ৩টি একক, DRY ও Reusable পাইপলাইন কাজ করবে: (১) PR-এ ১টি গেট (PR Gate), (২) Merge Train-এ ১টি (Train Gate), এবং (৩) Main-এ ১টি (Main CI/CD)।
6. অগ্রাধিকার অনুযায়ী এক-একটি করে ফিক্স ও মার্জ নীতি (Fast & Effective Sequential Law): সিআই এবং ডেভেলপার সময়ের অপচয় রোধে সর্বদা সর্বোচ্চ অগ্রাধিকার (Rank 1 / P0) PR-টি আগে শতভাগ গ্রিন ও মার্জ করতে হবে, তারপর ক্রমানুসারে পরবর্তী PR-এ যেতে হবে। সমান্তরালভাবে একাধিক ইন্টার-ডিপেন্ডেন্ট PR নিয়ে টানাটানি নিষিদ্ধ।
7. ডকুমেন্টেশন Issues-এ সংরক্ষণ ও TelDrive ব্যাকআপ নীতি (Issues as Operational Truth & TelDrive Backup): রিপোতে অপ্রয়োজনীয় .md তৈরি সম্পূর্ণ নিষিদ্ধ। সমস্ত নতুন স্থাপত্য সিদ্ধান্ত, গাইড ও প্ল্যান সরাসরি GitHub Issue-তে নথিভুক্ত হবে এবং দীর্ঘস্থায়ী ডক্স TelDrive-এ ব্যাকআপ রাখা হবে।
8. সমকক্ষ এজেন্টের স্বাধীনতা ও যৌথ যাচাই (Peer Autonomy & Synthesis): ১ম এজেন্ট ও কোডার উভয়েই সমকক্ষ বুদ্ধিমত্তার অধিকারী। ১ম এজেন্ট সমস্যা ও একাধিক সমাধানের সাজেশন দেবে ('আমার সাজেশন এটি, তোমার মতামত কি?'), কিন্তু কোডারকে পূর্ণ স্বাধীনতা দিতে হবে। কোডার ১ম এজেন্টের সাজেশন ও নিজের কোডবেস অ্যানালাইসিস ক্রস-ভেরিফাই করে যেটি বাস্তবিক বিচারে সেরা কেবল সেটাই বাস্তবায়ন করবে।
9. সংক্ষিপ্ততা ও জিরো-ব্লোট নীতি (Conciseness & Zero Doc Bloat): অ্যাডমিনের সুনির্দিষ্ট রিকোয়ারমেন্ট ছাড়া কোনো দীর্ঘ নথি, ভারী ডকস বা অপ্রয়োজনীয় ফাইল তৈরি নিষিদ্ধ। সমস্ত রুলস, যুক্তি ও লার্নিং পয়েন্ট-টু-পয়েন্ট সর্বোচ্চ ২-৩ লাইনে সীমাবদ্ধ থাকবে।
10. ডায়নামিক কিউ ও টুলস-ফার্স্ট ক্রম (Dynamic Tools-First Ordering): রুট কজ সমাধান ও টুলস/ওয়ার্কার সবার আগে প্রস্তুত করতে হবে। কিউতে নতুন কোনো জরুরি সমস্যা এলে পূর্বের কাজের সাথে বুদ্ধিমত্তার সাথে তুলনা করে কিউ ডায়নামিকালি রি-অর্ডার করতে হবে।
11. ক্ল্যারিফাই ও কনভার্জেন্স চক্র (Clarify & Converge Lifecycle): প্ল্যানার/অডিটর এজেন্টের জন্য কোড লেখার পূর্বেই সম্ভাব্য অস্পষ্টতা ও এজ-কেস (Clarify) টাস্কে চিহ্নিত করা বাধ্যতামূলক। একইভাবে কোডার এজেন্টের কাজ শেষ করে PR খোলার পূর্বে ইস্যুর প্রতিটি রিকোয়ারমেন্ট এবং কোড ডিফের শতভাগ মিল (Convergence) যাচাই করা বাধ্যতামূলক — কোনো অসম্পূর্ণ কাজ বা আনহ্যান্ডেলড TODO রেখে PR খোলা যাবে না।
12. সার্বজনীন উৎস প্রামাণ্যতা ও সমকক্ষ এজেন্টের ভেটো ক্ষমতা (Universal Source Legitimacy & Peer Veto): এটি সকল এজেন্টের জন্য বাধ্যতামূলক সার্বজনীন নিয়ম। কোনো অবস্থাতেই এমন কোনো সোর্স (রিপোজিটরি, লাইব্রেরি, এপিআই বা কোড) থেকে কিছু গ্রহণ করা যাবে না যার প্রামাণ্যতা নিয়ে বিন্দুমাত্র সন্দেহ বা প্রশ্ন রয়েছে। যেকোনো টাস্কে এক্সটার্নাল সোর্স যুক্ত থাকলে, যেকোনো এজেন্ট (Auditor, Coder, Planner, PR Helper) যদি সেই সোর্সকে শতভাগ লেজিট (Legit) ও নিরাপদ মনে না করে, তবে সাথে সাথে সেই সোর্স ব্যবহারে বাধা (Object/Block/Veto) দেওয়ার পূর্ণ অধিকার ও বাধ্যবাধকতা তার রয়েছে।

---

> সম্পূর্ণ machine-readable rule registry: `.github/constitution/rules.yml` (CI এটা থেকে gate চালায়)।
> **এই file-টি registry থেকে GENERATED — হাতে এডিট করবে না।**
