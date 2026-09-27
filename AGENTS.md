<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- Source of truth: .github/constitution/rules.yml · Generator: scripts/ci/generate_agents_md.py -->
<!-- CI drift check: system-gates.yml → agents-md-sync. To change rules, edit rules.yml. -->


# SupremeAI — AGENTS.md v2 (Universal Operating Constitution & Agent Bootstrap)

> rules_version: `2.1` · যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।
>
> Agent-কে ঘুড়ির মতো স্বাধীনভাবে উড়তে দাও; কিন্তু নাটাই সবসময় SupremeAI Admin / Control Plane-এর হাতে থাকবে।
>
> 💎 **The 101% Benefit Principle: সমস্যা পেলে শুধু কোড ফিক্স করা ১% লাভ; কিন্তু সেই সমস্যা ভবিষ্যতে আর কখনোই যেন না ঘটতে পারে তা রুট লেভেলে বন্ধ করা ১০১% লাভ।**
>
> 🏛️ কন্সটিটিউশনাল রুলস (Rules) হলো এজেন্টের কাজের অলঙ্ঘনীয় বাউন্ডারি যা ভুলের রুট-কজ ধ্বংস করে (১০১% লাভ)। সিস্টেম আর্কিটেকচার (Cascade Hold, Rollup Train, Dynamic Queue Shift, DB Schemas) থাকে docs/architecture/ এবং সিআই স্ক্রিপ্টে।

---

## The Living Protocols (Root-Cause Invariants — ১০১% লাভ)

### 1. Slot Isolation
১ এজেন্ট = ১ স্লট (acquire_role_slot.py)। ব্রাঞ্চ নেমে অবশ্যই ইস্যু নম্বর থাকবে: <lane>-<N>-<issue#>-<slug>। অন্যের স্লট বা ব্রাঞ্চে হাত দেওয়া বা push করা নিষিদ্ধ।

### 2. Atomic Claim Lock & File Declaration
কাজ শুরুর আগে atomic_claim.sh দিয়ে ইস্যু ক্লেইম করো এবং কমেন্টে 'Touching files: file1, file2' ঘোষণা করো। নো ক্লেইম, নো কোড।

### 3. Verify First (3-Tier Verification)
অনুমানে ফাইল ডিলিট বা এডিট নিষিদ্ধ। পরিবর্তনের আগে ও পরে ৩ স্তর যাচাই আবশ্যক: (১) Reflection check (grep), (২) Boot smoke test (python -c 'import main'), (৩) Pytest। টেস্ট ম্যানিপুলেশন (delete/skip/mock) কঠোরভাবে নিষিদ্ধ (Rule 21)।

### 4. Atomic Blast Radius
১ Issue = ১ Branch = ১ PR (সর্বোচ্চ ১–২ ফাইল)। ক্লেইম করা স্কোপের বাইরে ড্রাইভ-বাই রিফ্যাক্টরিং নিষিদ্ধ।

### 5. Mandatory 'has-pr' Label
PR খোলার সাথে সাথেই gh issue edit <id> --add-label 'has-pr' চালাতে হবে। এটি ডুপ্লিকেট PR তৈরি হওয়া রুট থেকে বন্ধ করে (Rule 24)।

### 6. The Dual-State Game (Solver ➔ Peer Reviewer)
কখনো অলস বসে থাকা যাবে না। লেনে বা অ্যাক্টিভ গ্রুপে আনক্লেইমড কাজ থাকলে সলভার (State A); সব কাজ ক্লেইমড থাকলে সহকর্মীদের ওপেন PR অডিটকারী পিয়ার রিভিউয়ার (State B) (Rule 28)।

---

## Bootstrap Checklist (সেশন শুরু হলে ঠিক এই ক্রমে কাজ করো)

1. `python scripts/agents/acquire_role_slot.py --role <lane>` — নিজের ডেডিকেটেড স্লট নাও
2. `python scripts/agents/agent_solution_memory.py search --query '<problem>'` — কালেক্টিভ মেমোরিতে অতীত সমাধান খোঁজো
3. `export BRANCH_NAME='<lane>-<N>-<issue#>-<slug>' && ./scripts/ci/atomic_claim.sh <issue#> <agent>` — ইস্যু ক্লেইম ও ফাইল ঘোষণা করো
4. `3-Tier Verification (Reflection -> Boot Smoke -> Pytest)` — কোনো টেস্ট ভাঙা বা ডিলিট করা নিষিদ্ধ
5. `gh pr create ... && gh issue edit <issue#> --add-label 'has-pr'` — PR খুলে অবিলম্বে has-pr লেবেল দাও

Full rule map: [`docs/agents/RULES_INDEX.md`](docs/agents/RULES_INDEX.md) · Priority order: [`docs/agents/ISSUE_PRIORITY_POLICY.md`](docs/agents/ISSUE_PRIORITY_POLICY.md)

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
| **1. Philosophy** | ঘুড়ি ও নাটাই নীতি মেনেছে কি না? (Zero harm to project/peers) |
| **2. Real Benefit** | সিস্টেমে বাস্তব উন্নতি হয়েছে কি না? (LOC হ্রাস / বাগ ফিক্স / নির্ভরযোগ্যতা বৃদ্ধি) |
| **3. Zero Regression** | কোনো টেস্ট ডিলিট, স্কিপ বা ফেইক মক করা হয়নি তো? (Rule 21) |
| **4. Scope Narrowness** | ক্লেইম করা স্কোপের বাইরে ড্রাইভ-বাই রিফ্যাক্টরিং বা বাড়তি কোড ঢুকেছে কি না? |

---

## তোমার স্বাধীনতা (কেউ আটকাবে না)

- সমাধানের approach নিজে বেছে নাও — architecture, pattern, library (stack অগ্রাধিকার মানলে ভালো, বাধ্য না)
- যেকোনো unclaimed issue চেয়ে নাও (lane-অগ্রাধিকার advisory, আটকানো নয়)
- আটকে গেলে blocker issue খোলো এবং পরের কাজে যাও — চুপচাপ বসে থেকো না
- ভুল হলে LESSONS_LEARNED.md-তে এক লাইন যোগ করো — শাস্তি নেই, পুনরাবৃত্তি-প্রতিরোধই লক্ষ্য (১০১% লাভ)

---

## একমাত্র কঠিন নিয়ম (মোট ৩টা, বাকি সব system-এর ভার)

1. সৎ থাকো — কাজ 'দেখতে ভালো' না, 'সত্যিই ভালো' হতে হবে (test manipulation = সর্বোচ্চ অপরাধ, ১০১% বেনিফিট)
2. পরমাণু থাকো — এক PR এক উদ্দেশ্য (১ Issue = ১ Branch = ১ PR)
3. চলমান থাকো — সলভার বা পিয়ার রিভিউয়ার মোডে কাজ করো, কখনো অলস বসে থেকো না

---

> সম্পূর্ণ machine-readable rule registry: `.github/constitution/rules.yml` (CI এটা থেকে gate চালায়)।
> **এই file-টি registry থেকে GENERATED — হাতে এডিট করবে না।**
