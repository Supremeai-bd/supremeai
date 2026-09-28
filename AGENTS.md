<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- Source of truth: .github/constitution/rules.yml · Generator: scripts/ci/generate_agents_md.py -->
<!-- CI drift check: system-gates.yml → agents-md-sync. To change rules, edit rules.yml. -->


# SupremeAI — AGENTS.md v2 (Universal Operating Constitution & Agent Bootstrap)

> rules_version: `2.2` · যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।
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

### 6. The Dual-State Loop (Solver → Peer Reviewer)
কখনো অলস বসে থাকা যাবে না। অ্যাক্টিভ গ্রুপে আনক্লেইমড ইস্যু থাকলে সলভার মোড (State A); সব কাজ ক্লেইমড থাকলে ওপেন PR-এর টেস্ট ও পিয়ার রিভিউ মোড (State B)। **State B:** `gh pr list --state open` দিয়ে open PR দেখো → 4-Pillar Rubric মেনে পরীক্ষা করো → `gh pr review <PR#> --comment -b '<findings>'`।

### 7. Sequential Hold (GSPQ Break Protection)
PR তৈরির পর: `gh issue view <prev-seq-issue#> --json state -q .state` দিয়ে predecessor seq merge নিশ্চিত করো। `OPEN` ফেরত পেলে → `gh pr edit <PR#> --add-label 'queue:hold'` + comment কারণ। Predecessor merged হলে label সরিয়ে queue unlock করো।

### 8. Control Plane Handshake & Heartbeat (নাটাই প্রোটোকল)
নাটাই ছাড়া ঘুড়ি ওড়া নিষিদ্ধ। সেশনে কাজ শুরুর আগে এজেন্ট Control Tower-এ (mcp.json) সংযুক্ত হয়ে হার্টবিট পাঠাবে (`python scripts/agents/mcp_tower_client.py heartbeat --slot agent-<N> --name <id>` বা MCP `agent_heartbeat` টুল)। হার্টবিট না থাকলে কন্ট্রোল প্লেন জানবে না কে জীবিত আর কে ক্র্যাশড, স্লট লিজ ড্রপ হবে এবং কেন্দ্রীয় কিল-সুইচ কাজ করবে না।

---

## Bootstrap Checklist (সেশন শুরু হলে ঠিক এই ক্রমে কাজ করো)

1. `git fetch origin --prune && cat AGENTS.md` — সেশন শুরুতে সর্বদা main sync ও AGENTS.md পড়ো — rules পরিবর্তন হয়েছে কিনা দেখো
2. `python scripts/agents/acquire_role_slot.py --role <lane>` — অটো-ডিসকভারি: পরবর্তী প্রায়োরিটি ইস্যু (P0 → group seq) নিজে খুঁজে স্লট ও ব্রাঞ্চ তৈরি করে। নির্দিষ্ট ইস্যুর জন্য: --issue <id>
3. `./scripts/ci/atomic_claim.sh <issue#> <agent>` — ইস্যু ক্লেইম ও 'Touching files:' ঘোষণা করো (GH_TOKEN অটো-fallback: gh auth login)
4. `python scripts/agents/mcp_tower_client.py heartbeat --slot agent-<N> --name <id>` — নাটাই হ্যান্ডশেক: Control Tower-এ হার্টবিট পাঠিয়ে নিজেকে 'state=online' রেজিস্টার করো
5. `3-Tier Verification (Reflection → Boot Smoke → Pytest)` — কোনো টেস্ট ভাঙা বা ডিলিট করা নিষিদ্ধ
6. `gh pr create ... && gh issue edit <issue#> --add-label 'has-pr'` — [Coder/CI/Platform only — Planner PR নিষিদ্ধ] PR খুলে অবিলম্বে has-pr লেবেল দাও
7. `Sequential hold check: gh issue view <prev-seq-issue> --json state` — পূর্ববর্তী seq মার্জ না হলে → gh pr edit <PR#> --add-label queue:hold + comment কারণ

_কাজ শুরুর আগে সর্বদা `git fetch origin --prune && cat AGENTS.md` চালাও।_

---

## System যা আটকাবে (মনে রাখার দরকার নেই — শুধু জেনে রাখো কেন আটকালো)

| Gate | কখন আটকাবে | Enforcement |
| :--- | :--- | :--- |
| Lease Gate | PR head branch লেখকের leased slot-এর বাইরে (bot slot-mismatch), বা mesh lease মেয়াদ শেষ | CI (system-gates.yml) |
| Verification Gate | PR description-এ Test Evidence সেকশন নেই (টেস্ট লগ/কমান্ড আউটপুট ছাড়া PR BLOCK) | CI (system-gates.yml) |
| Scope Gate | claim-এ declare করা 'Touching files:'-এর বাইরের ফাইল PR-এ বদলালে BLOCK | CI (system-gates.yml) |
| Collision Gate | অন্য open PR-এর ফাইলের সাথে direct overlap হলে BLOCK | CI (pr-gate.yml (check-collisions, strict mode #2002)) |
| Self-Merge Gate | নিজের PR নিজে approve/merge করলে BLOCK | branch protection + pr-helper review |
| Test Guard | test delete/skip/threshold-নামানো হলে BLOCK | constitution audit engine extension |
| Post-Merge Watch | merge-এর ১৫ মিনিটের মধ্যে main লাল হলে auto-revert | merge-train land job |

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
- সক্রিয় গ্রুপ সিকোয়েন্সের পরবর্তী উন্মুক্ত ইস্যুটি গ্রহণ করো।
- কোনো ব্লকার পেলে তাৎক্ষণিক ব্লকার ইস্যু তৈরি করে পরবর্তী আনক্লেইমড কাজে এগিয়ে যাও।

---

## একমাত্র কঠিন নিয়ম (মোট ৩টা, বাকি সব system-এর ভার)

1. সততা ও নির্ভরযোগ্যতা: কোড ও টেস্ট ১০০% খাঁটি হতে হবে; টেস্ট ম্যানিপুলেশন (delete/skip/fake assertion) সর্বোচ্চ অপরাধ।
2. পরমাণু স্কোপ: এক PR এক উদ্দেশ্য (১ Issue = ১ Branch = ১ PR, সর্বোচ্চ ১-২ ফাইল)।
3. অবিরাম সক্রিয়তা: সলভার বা পিয়ার রিভিউয়ার মোডে কাজ করো, কখনো অলস বসে থাকবে না।

---

> সম্পূর্ণ machine-readable rule registry: `.github/constitution/rules.yml` (CI এটা থেকে gate চালায়)।
> **এই file-টি registry থেকে GENERATED — হাতে এডিট করবে না।**
