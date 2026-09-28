<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- Source of truth: .github/constitution/rules.yml · Generator: scripts/ci/generate_agents_md.py -->
<!-- CI drift check: system-gates.yml → agents-md-sync. To change rules, edit rules.yml. -->


# SupremeAI — AGENTS.md v2 (Universal Operating Constitution & Agent Bootstrap)

> rules_version: `2.4` · যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।
>
> Agent-কে ঘুড়ির মতো স্বাধীনভাবে উড়তে দাও; কিন্তু নাটাই সবসময় SupremeAI Admin / Control Plane-এর হাতে থাকবে।

---

## The Living Protocols (Root-Cause Invariants — ১০১% লাভ)

### 1. Dynamic Slot & Branch-as-Lease
১ এজেন্ট = ১ স্লট (acquire_role_slot.py)। দূরবর্তী বা লোকাল ব্রাঞ্চের প্রথম ফাঁকা স্লট (gap) বরাদ্দ হবে (১–৯ ব্যস্ত থাকলে ১০; মাঝের কোনো স্লট খালি হলে সেই গ্যাপ স্লট)। ব্রাঞ্চ নাম: `<lane>-<N>-<issue#>-<slug>`। PR মার্জ বা ক্লোজ হলে ব্রাঞ্চ স্বয়ংক্রিয়ভাবে মুছে যাবে (ব্রাঞ্চ নেই মানে স্লটের কাজ সম্পন্ন ও স্লট মুক্ত)। অন্যের স্লট বা ব্রাঞ্চে হাত দেওয়া বা push করা সম্পূর্ণ নিষিদ্ধ।

### 2. Atomic Claim Lock & File Declaration
গ্রুপ সিকোয়েন্সের (GSPQ) প্রথম আনক্লেইমড ইস্যুটি ক্লেইম করো (`atomic_claim.sh`)। ক্লেইম কমেন্টে 'Touching files: file1, file2' ঘোষণা করো। নো ক্লেইম, নো কোড।

### 3. Verify First (3-Tier Verification)
অনুমানে ফাইল ডিলিট বা এডিট নিষিদ্ধ। পরিবর্তনের আগে ও পরে ৩ স্তর যাচাই আবশ্যক: (১) Reflection check (grep), (২) Boot smoke test (python -c 'import main'), (৩) Pytest। টেস্ট ম্যানিপুলেশন (delete/skip/fake assertion) কঠোরভাবে নিষিদ্ধ।

### 4. Atomic Blast Radius
১ Issue = ১ Branch = ১ PR (সর্বোচ্চ ১–২ ফাইল)। ক্লেইম করা স্কোপের বাইরে ড্রাইভ-বাই রিফ্যাক্টরিং নিষিদ্ধ।

### 5. Mandatory 'has-pr' Label
PR খোলার সাথে সাথেই gh issue edit <id> --add-label 'has-pr' চালাতে হবে। এটি ডুপ্লিকেট PR তৈরি হওয়া রুট থেকে বন্ধ করে।

### 6. Automated CI Guard & Pure Solver Lane
কোডারদের ম্যানুয়াল PR রিভিউ লেখার কোনো প্রয়োজন নেই — PR নিরাপত্তা, টেস্ট ও রিগ্রেশন স্বয়ংক্রিয় CI Gates (Lease, Verification, Scope, Collision) এবং PR Helper পরিচালনা করে। কোডার এজেন্টের ১০০% ফোকাস থাকবে ইস্যু সমাধান, ৩-স্তর যাচাই ও পরমাণু PR তৈরিতে।

### 7. Group Staging & Sequential Hold (GSPQ Break Protection)
গ্রুপ সিকোয়েন্সের (e.g. `group:step-2`, `group:step-3`) কোনো PR এককভাবে বিচ্ছিন্নভাবে `main`-এ মার্জ হবে না। PR খোলার সাথে সাথে `queue:hold` লেবেল যুক্ত থাকবে। পূর্ববর্তী সিকোয়েন্সের স্ট্যাটাস পরীক্ষা করো (`gh issue view <prev-seq-issue#>`). পুরো গ্রুপের সকল PR গ্রিন ও অডিট সম্পন্ন হলে তবেই Merge Train চালু হবে।

### 8. Control Plane Heartbeat (MCP Fleet Presence)
সেশনে কাজ শুরুর আগে এজেন্ট Control Tower-এ (mcp.json) হার্টবিট পাঠাবে (`python scripts/agents/mcp_tower_client.py heartbeat --slot agent-<N> --name <id>` বা MCP `agent_heartbeat` টুল)। এটি সেন্ট্রাল মেশে এজেন্টের উপস্থিতি ও লিজ সক্রিয় রাখে।

### 9. Group Closeout Harvest & Benefit Gate (Zero Loss Invariant)
সম্পূর্ণ গ্রুপের কাজ শেষ হলেই কেবল আসল চিত্র পরিষ্কার বোঝা যায়। তাই যেকোনো গ্রুপ সিকোয়েন্সের (GSPQ) সব কোডার PR তৈরি ও টেস্ট গ্রিন হওয়ার পর শেষ ফেজটি (seq: N+1) হবে 'Capability Harvest & Benefit Audit'। দায়িত্বপ্রাপ্ত এক্সিকিউটর: Planner Agent / SuperAgent (Admin বা SupremeAI) অথবা PR Helper। পুরো গ্রুপের সমস্ত diff একসাথে অডিট করো: কাজের কোনো দরকারি লজিক বা ক্ষমতা কি হারিয়ে গেছে? যদি হ্যাঁ, তবে ক্যানোনিকাল মডিউলে তা রিকভার করো। জিরো ক্যাপাবিলিটি লস ও ১০১% বাস্তব লাভ নিশ্চিত হলে তবেই Merge Train চালু হবে, গ্রুপ ক্লোজ হবে এবং পরবর্তী গ্রুপ শুরু হবে।

### 10. Standard Group Issue Creation Protocol (পরবর্তী ইস্যু তৈরির নিয়ম)
ভবিষ্যতে যখনই নতুন গ্রুপ বা সিকোয়েন্স ইস্যু তৈরি করা হবে, তা অবশ্যই স্ট্যান্ডার্ড টেমপ্লেট (`scripts/ci/create_group_issue.py` বা GitHub issue form) অনুযায়ী তৈরি করতে হবে। প্রতিটি ইস্যুতে স্পষ্টভাবে থাকতে হবে: (১) Group ও Sequence ট্যাগ (`group:step-X`, `seq:Y`), (২) Predecessor নির্ভরতা, (৩) 'Touching files' ও পরমাণু ব্লাস্ট রেডিয়াস ঘোষণা, (৪) ৩-স্তর ভেরিফিকেশন নির্দেশাবলী, (৫) বাধ্যতামূলক বাংলা/বাংলিশ কোড কমেন্টস (`# বাংলা মন্তব্য:`), এবং (৬) স্পষ্ট স্ট্রেজিং নোটিশ: 'গ্রুপ সম্পূর্ণ শেষ হওয়ার পর Merge Train চালু হবে — কোনো বিচ্ছিন্ন মার্জ নয়'।

### 11. Flexible Group Branching — Connected vs Independent Work (#2378)
কাজের প্রকৃতি অনুযায়ী দুই পথ। **Connected Work** = ইস্যুতে `group:<name>` লেবেল থাকলে একাধিক agent একটি শেয়ার্ড গ্রুপ ব্রাঞ্চ `group/<name>`-এ কাজ করবে (acquire_role_slot.py বিদ্যমান গ্রুপ ব্রাঞ্চ শেয়ার বা origin/main থেকে তৈরি করবে — মাঝপথে reset-to-main কখনো নয়) → গ্রুপ শেষে ১টি PR + গ্রুপ-লেভেল ৩-স্তর ভেরিফিকেশন + Merge Train গ্রুপ-কমপ্লিটে। প্রতিটি agent atomic_claim.sh --files দিয়ে ফাইল-বাউন্ডারি ঘোষণা করবে — একই গ্রুপ ব্রাঞ্চে দুই agent-এর ঘোষণায় overlap থাকলে claim বাতিল। গ্রুপ ব্রাঞ্চে origin/main auto-sync নয় — sync হবে Merge Train-এ। **Independent Work** = standalone ইস্যুতে পূর্বের মতোই `১ Issue = ১ Branch = ১ PR`। Lease Gate গ্রুপ ব্রাঞ্চে group-সদস্যতা যাচাই করে (gates.py _group_lease_check)।

### 12. Living Pipeline Canon (ARCH-LIVING-PIPELINE-01)
এই অধ্যায়ের Protocol ১–১১-এর ক্যানোনিকাল স্পেক: `docs/architecture/ARCH-LIVING-PIPELINE-01.md` — ৬-স্তর স্বশাসন পাইপলাইন (১ Slot Lease → ২ Atomic Claim → ৩ ৩-স্তর Verification → ৪ Dual-State Game → ৫ Merge Train → ৬ Janitor) + constitution-গেট স্তর। Evidence-ভিত্তিক বাস্তবায়ন রোডম্যাপ: `docs/plans/ARCH-LIVING-PIPELINE-01-IMPL.md` (reality-check, gap register G1–G7, ফেজড PR-α→ζ)। স্পেক ও রিপো-বাস্তবতা সাংঘর্ষিক হলে file:line প্রমাণসহ reality-check-ই প্রধান — স্পেক হালনাগাদ করো বা gap হিসেবে নথিভুক্ত করো; নীরব পথ-চ্যুতি কখনো নয়। (#2396)

### 13. Mandatory Agent Push-as-PR Protocol (বাধ্যতামূলক PR পুশ)
এজেন্ট কোনো কাজ শুধু লোকাল ব্রাঞ্চে ফেলে রাখতে পারবে না। কাজ শেষ হওয়ার সাথে সাথে: (১) রিমোট ব্রাঞ্চে পুশ করতে হবে (`git push origin <branch>`), (২) স্বাধীন কাজের ক্ষেত্রে অবিলম্বে `gh pr create` চালিয়ে PR খুলতে হবে, এবং গ্রুপ কাজের ক্ষেত্রে গ্রুপের ১ম এজেন্ট PR খুলবে আর পরবর্তী এজেন্টরা গ্রুপ ব্রাঞ্চে পুশ করে PR বডিতে নিজেদের সিকোয়েন্স ও `Closes #N` যুক্ত করবে, (৩) সাথে সাথে সংশ্লিষ্ট ইস্যুতে `gh issue edit <id> --add-label 'has-pr'` দিতে হবে। প্রতিটি কাজের অগ্রগতি PR হিসেবে GitHub-এ দৃশ্যমান ও অডিটেবল হতে হবে।

---

## Bootstrap Checklist (সেশন শুরু হলে ঠিক এই ক্রমে কাজ করো)

1. `git fetch origin --prune && cat AGENTS.md` — সেশন শুরুতে সর্বদা main sync ও AGENTS.md পড়ো — rules পরিবর্তন হয়েছে কিনা দেখো
2. `cat docs/architecture/ARCH-LIVING-PIPELINE-01.md` — Living Pipeline canon পড়ো — Protocol ১–১২-এর উৎস-স্পেক; ৬-স্তর পাইপলাইনের পূর্ণ প্রেক্ষাপট ও গেট-ম্যাপ (#2396)
3. `python scripts/agents/acquire_role_slot.py --role <lane>` — অটো-ডিসকভারি: পরবর্তী প্রায়োরিটি ইস্যু (P0 → group seq) নিজে খুঁজে স্লট ও ব্রাঞ্চ তৈরি করে। নির্দিষ্ট ইস্যুর জন্য: --issue <id>
4. `./scripts/ci/atomic_claim.sh <issue#> <agent>` — ইস্যু ক্লেইম ও 'Touching files:' ঘোষণা করো (GH_TOKEN অটো-fallback: gh auth login)
5. `python scripts/agents/mcp_tower_client.py heartbeat --slot agent-<N> --name <id>` — Control Tower Heartbeat: MCP মেশে নিজেকে 'state=online' রেজিস্টার করো
6. `3-Tier Verification (Reflection → Boot Smoke → Pytest)` — কোনো টেস্ট ভাঙা বা ডিলিট করা নিষিদ্ধ
7. `gh pr create ... && gh issue edit <issue#> --add-label 'has-pr'` — [Coder/CI/Platform only — Planner PR নিষিদ্ধ] PR খুলে অবিলম্বে has-pr লেবেল দাও
8. `Group staging hold: gh pr edit <PR#> --add-label queue:hold` — গ্রুপ সিকোয়েন্সের কোনো PR একা মার্জ হবে না — সম্পূর্ণ গ্রুপ শেষ হলে Merge Train শুরু হবে

_কাজ শুরুর আগে সর্বদা `git fetch origin --prune && cat AGENTS.md` চালাও।_

---

## System যা আটকাবে (মনে রাখার দরকার নেই — শুধু জেনে রাখো কেন আটকালো)

| Gate | কখন আটকাবে | Enforcement |
| :--- | :--- | :--- |
| Lease Gate | PR head branch লেখকের leased slot-এর বাইরে (bot slot-mismatch), বা mesh lease মেয়াদ শেষ | CI (system-gates.yml) |
| Verification Gate | PR description-এ Test Evidence সেকশন নেই (টেস্ট লগ/কমান্ড আউটপুট ছাড়া PR BLOCK) | CI (system-gates.yml) |
| Scope Gate | claim-এ declare করা 'Touching files:'-এর বাইরের ফাইল PR-এ বদলালে BLOCK | CI (system-gates.yml) |
| Collision Gate | অন্য open PR-এর ফাইলের সাথে direct overlap হলে BLOCK | CI (pr-gate.yml (check-collisions, strict mode #2002)) |
| Self-Merge Gate | নিজের PR নিজে approve/merge করলে BLOCK | CI (system-gates.yml) |
| Test Guard | test delete/skip/threshold-নামানো হলে BLOCK | CI (system-gates.yml) |
| Post-Merge Watch | merge-এর ১৫ মিনিটের মধ্যে main লাল হলে (watchdog admin-alert — কোনো অন্ধ auto-revert নয়, revert সিদ্ধান্ত অ্যাডমিনের নাটাইয়ে) | CI (integration-gate.yml) |

---

## Group Closeout Audit Protocol (The 4-Pillar Rubric)

| Pillar | প্রশ্ন ও মানদণ্ড |
| :--- | :--- |
| **1. System Stability** | সিস্টেম বা আর্কিটেকচারে কোনো ব্রেকিং পরিবর্তন বা অঘোষিত সাইড-ইফেক্ট আছে কি না? |
| **2. Real Benefit** | বাস্তব উন্নতি হয়েছে কি না? (LOC হ্রাস / ডেড-কোড ছাঁটাই / বাগ ফিক্স / নির্ভরযোগ্যতা বৃদ্ধি) |
| **3. Zero Regression** | সব টেস্ট সফল কি না? কোনো টেস্ট ডিলিট, স্কিপ বা ফেইক অ্যাসারশন করা হয়নি তো? |
| **4. Scope Narrowness** | ঘোষিত ফাইলের বাইরে ড্রাইভ-বাই রিফ্যাক্টরিং বা অনাকাঙ্ক্ষিত কোড ঢুকেছে কি না? |

---

## তোমার স্বাধীনতা (কেউ আটকাবে না)

- সমাধানের বাস্তবসম্মত অ্যাপ্রোচ ও ডিজাইন প্যাটার্ন নিজে বেছে নাও।
- সক্রিয় গ্রুপ সিকোয়েন্সের পরবর্তী উন্মুক্ত ইস্যুটি গ্রহণ করো।
- কোনো ব্লকার পেলে তাৎক্ষণিক ব্লকার ইস্যু তৈরি করে পরবর্তী আনক্লেইমড কাজে এগিয়ে যাও।

---

## একমাত্র কঠিন নিয়ম (মোট ৫টা, বাকি সব system-এর ভার)

১. সততা ও নির্ভরযোগ্যতা: কোড ও টেস্ট ১০০% খাঁটি হতে হবে; টেস্ট ম্যানিপুলেশন (delete/skip/fake assertion) সর্বোচ্চ অপরাধ।
২. পরমাণু স্কোপ: এক PR এক উদ্দেশ্য (১ Issue = ১ Branch = ১ PR, সর্বোচ্চ ১-২ ফাইল)।
৩. অবিরাম সক্রিয়তা: কিউ থেকে ক্রমানুসারে পরবর্তী কাজ তুলে নাও, কোনো কাজে ব্লকার পেলে সাথে সাথে ব্লকার ইস্যু ফাইল করে এগিয়ে যাও।
৪. বাংলা/বাংলিশ ব্যবহারের বাধ্যবাধকতা: আমাদের পুরো টেক টিম বাংলাদেশি — তাই যেখানেই সম্ভব বাংলা (বা প্রাঞ্জল বাংলিশ) ব্যবহার করতে হবে। (১) কোডের ভেতরের সমস্ত মন্তব্য ও সিদ্ধান্তের ব্যাখ্যা (code comments — e.g. '# বাংলা মন্তব্য:'), (২) অ্যাডমিনের যেকোনো প্রশ্নের উত্তর, বার্তা ও স্ট্যাটাস রিপোর্ট, এবং (৩) PR সামারি, ডেসক্রিপশন ও ইস্যু ডিসকাশনে বাংলা বা বাংলিশ ১০০% বাধ্যতামূলক (Mandatory Bengali/Banglish)। কেবল কোড সিনট্যাক্স, ভ্যারিয়েবল নেম ও শেল কমান্ড ব্যতীত সমস্ত যোগাযোগ ও ব্যাখ্যা বাংলায় হতে হবে।
৫. গ্রুপ কমপ্লিট ও ব্যাচ ল্যান্ডিং (Batch Landing Law): গ্রুপ সিকোয়েন্সের কোনো PR বিচ্ছিন্নভাবে main-এ মার্জ হবে না। প্রতিটি PR 'queue:hold'-এ থাকবে। সম্পূর্ণ গ্রুপের সব PR তৈরি, টেস্ট গ্রিন এবং গ্রুপ ক্লোজআউট অডিট সফল হলে তবেই Merge Train রোলআপের মাধ্যমে পুরো গ্রুপ একসাথে main-এ ল্যান্ড করবে।

---

> সম্পূর্ণ machine-readable rule registry: `.github/constitution/rules.yml` (CI এটা থেকে gate চালায়)।
> **এই file-টি registry থেকে GENERATED — হাতে এডিট করবে না।**
