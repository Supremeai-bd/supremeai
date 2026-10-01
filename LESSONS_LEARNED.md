# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

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

## 2026-09-27 — 🏷️ Missing-Cat Metadata Class: Bot Wrapper-ই File Path-কে Title/Body বানিয়ে দেয় (#2158)

- **Issue:** #2158 — PR #2156 `supremeai-coder-1-bot` খুলেছিল যার title = `/tmp/wire_title.txt`, body = `/tmp/wire_body.md` (literal path strings)। Wrapper চেয়েছিল `--title "$(cat "$F")"`, পাঠিয়েছে path। Rule #16/#17 violation; triage/labeler/pr-verifier pipeline poisoned।
- **Fix:** repo-side pre-create assert — `scripts/agents/validate_pr_metadata.py` (path-like title/body BLOCK — absolute, dotted-relative, এবং no-whitespace+known-extension heuristic; conventional `type(scope): description` title BLOCK (Rule #16); stub body BLOCK (Rule #17); গেট contract WARNING — body-তে exactly-one keyword ref (`Refs #N`) না থাকলে/১-এর বেশি হলে, title-এ `(#N)` না থাকলে; `--strict` warning-কে abort বানায়; `--format json` wrapper-দের জন্য)। Tests: `backend/tests/scripts/test_validate_pr_metadata.py` — literal #2156 evidence strings সহ 19 tests। Per-agent sandbox wrapper-ও এই validator-কে pre-POST এ call করে (fix যেখানে বাগ, সেখানেই)।
- **লেসন:** (১) shell-এ `"$F"` আর `"$(cat "$F")"`-এর পার্থক্য হলো path-vs-contents — bot wrapper-এ এই class-এর বাগ metadata-কে silently garbage করে কারণ আজকের CI title check warning-level; (২) "যা CI asynchronously ধরে তা pre-create এ fail-fast করাও" — gate contract (exactly-one `Refs #N`) validator-এ mirror করা হয়েছে; (৩) per-agent tooling repo-তে না থাকলেও, তার contract repo-visible হওয়া উচিত — shared validator + tests সব slot একসাথে রক্ষা করে।
