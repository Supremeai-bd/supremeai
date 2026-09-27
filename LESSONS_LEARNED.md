# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

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

## 2026-09-27 — 🧭 Lane Boundary: Planner Opens PRs (L1 Violation — Rule Gap, Closed) (#1864)


- **সমস্যা:** `agent-1-planner` দুটি PR (#1805, #1851) খুলেছিল — planner lane-এর ম্যান্ডেট হলো audit + GitHub issues only, PR নয়। Root cause ছিল agent-এর স্মৃতিভ্রংশতা নয় বরং **rule gap**: charter-এর planner row-তে `docs/plans/` ownership দেওয়া ছিল কিন্তু "Forbidden" কলামে PR খোলা নিষিদ্ধ ছিল না — "plan-doc ownership" কে "plan-doc PR authority" হিসেবে পড়া সম্ভব ছিল।
- **ফিক্স:** (১) Charter hardening — planner = **issue-output lane**, branch slot নেই, PR খোলা স্পষ্টভাবে forbidden; প্ল্যান ডকুমেন্ট `handoff:coder` issue-এর মাধ্যমে coder lane land করবে (charter §1 planner row + new invariant #23)। (২) **Machine guard** (আলাদা issue): PR gate এখন `planner-*` branch থেকে খোলা PR ব্লক করবে — নিয়ম এখন enforcement-নির্ভর, memory-নির্ভর নয়। (৩) এই ledger entry — ভুল একবার, শিক্ষা স্থায়ী।
- **লেসন:** সীমানা-নিয়ম (lane boundary) চার্টারে "allowed" লেখা যথেষ্ট নয় — যে behavior নিষিদ্ধ, সেটা Forbidden কলামে + machine guard-এ স্পষ্ট থাকতে হবে। **"Allowed scope" ≠ "authority to land"**: discovery/specification authority আর landing authority ভিন্ন জিনিস — ecosystem-এ এক lane খুঁজে দেয়, অন্য lane বানায়, আরেক lane বসায়।

## 2026-09-27 — 🧩 Monkeypatch-Proof Dependency Resolution: function-level `from`-import শ্যাডো-attribute বাইপাস (#2098)

- **Issue:** #2098 — CI-only 4× `"Event loop is closed"` failure in core-unit rate-limit tests; local runs সবসময় pass করত।
- **সমস্যা:** `_check_rate_limit`-এর ভেতরে function-level `from core.cache.redis_manager import redis_manager` লেখা হয়েছিল। `core/cache/__init__.py` singleton-টিকে submodule-এর নিজ নামে re-export করে, ফলে CI-র import sequence-এ import টি **shadowed package attribute** resolve করে — test-এর module-attr monkeypatch সম্পূর্ণ বাইপাস হয়ে গিয়ে REAL singleton-এ পৌঁছায়। প্রমাণ: CI log-এ `⚡ Serverless Upstash Redis REST Provider Active` পুরো run-এ ঠিক ১ বার, সেটাও *টেস্টের ভেতরেই* — fake-এর `eval_calls == 0`।
- **Fix:** `backend/core/middleware/security.py`-এ sys.modules-first resolution (`_get_redis_manager()`) — call-time-এ সবসময় আসল module object-এর (patch-করা) attribute দেয়; production-এ দুই পথই একই singleton, behavior identical। PR #2110।
- **লেসন:** (১) `package/__init__`-এ same-name re-export থাকলে function-level `from package.module import name` **patch-proof নয়** — test যা monkeypatch করে সেটি বাইপাস হতে পারে; (২) monkeypatch-target dependency call-site-এ `sys.modules` lookup বা `import package.module as m; m.name` আকারে resolve করো; (৩) "dependency-র init log ঠিক টেস্টের ভেতরে ১ বার" মানেই real dependency টেস্ট চলাকালীন initialize হয়েছে — patch bypass-এর smoking gun।

## 2026-09-12 — ⚡ MANDATORY RULE #1: Zero Local-Machine Dependency & Start-of-Conversation Recall Mandate

- **সমস্যা:** ম্যানুয়াল লোকাল পিসি ও লোকাল টার্মিনালনির্ভর নির্দেশ বা প্লাগইন কনফিগারেশন দিলে তা ক্লাউড-ফার্স্ট/প্রডাকশন আর্কিটেকচার এবং ব্যবহারকারীর ওয়ার্কফ্লোকে ব্যাহত করে।
- **ফিক্স:** `AGENTS.md`-এর চূড়ায় **MANDATORY RULE #1** সংস্থাপিত করা হয়েছে—১% কাজ বা প্ল্যানিংও লোকাল পিসির ওপর নির্ভর করা যাবে না। প্রতিটি এআই এজেন্টকে প্রতি কনভার্সেশনের শুরুতে Rule #1 রিফাইন ও এনফোর্স করতে হবে। সব সার্ভিস (Backend, Frontend, MCP, CI/CD) প্রথম দিন থেকেই ১০০% অটোমেটেড ক্লাউড-নেটিভ প্রডাকশন ইঞ্জিনে চলবে (No Exception)।
- **লেসন:** জিরো লোকাল ডিপেন্ডেন্সি ও কনভার্সেশনের শুরুতে বাধ্যতামূলক রিকল হলো SupremeAI-এর এক নম্বর সাংবিধানিক নিয়ম।

## 2026-09-12 — 🏛️ Core Philosophy Reinforcement: Zero-Hardcoding Mandate & System-Wide Universal Rule Scoping


- **সমস্যা:** কোডবেস বা সিস্টেমে যেকোনো হার্ডকোডেড ভ্যালু (লজিক, প্রম্পট, ইউআরএল, কনফিগারেশন, পলিসি) ফ্লেক্সিবিলিটি নষ্ট করে। একই সাথে কোনো একটি সুনির্দিষ্ট মডিউল (যেমন: MCP Server) নিয়ে শেখা নিয়ম বা নির্দেশ সেকশন-আইসোলেটেড মনে করার ঝুঁকি তৈরি হতে পারে।
- **ফিক্স:** `AGENTS.md` (Section 1)-এ ২টি মৌলিক সার্বজনীন ফিলোসোফি আপডেট করা হয়েছে: (১) **Zero-Hardcoding Mandate** — সিস্টেমে কোনো কিছুই হার্ডকোড করা যাবে না; সব ড্যাশবোর্ড/ডিবি থেকে ডাইনামিকভাবে নিয়ন্ত্রণযোগ্য হতে হবে; (২) **Universal Rule Scoping** — একটি মডিউলে শেখা নিয়ম বা গার্ডরেল কখনো আইসোলেটেড থাকবে না, তা Backend, Frontend, AI Agents, Docs, CI/CD জুড়ে **সামগ্রিক SupremeAI প্রজেক্টে সার্বজনীনভাবে (System-Wide)** কার্যকর হবে।
- **লেসন:** হার্ডকোডিং মুক্ত ডাইনামিক ডিজাইন এবং সিস্টেম-ওয়াইড ইউনিভার্সাল রুল স্কোপিং হলো SupremeAI-এর ক্যানোনিকাল আর্কিটেকচারের মূল ভিত্তি।
| 2026-09-27 | #2249 | Phase-2.1: retire second parallel LLM provider stack (services/llm providers.py 852L + llm_router.py 987L) with 15 production callers uniformly consuming result.get('content') while route() returned a RouteResult dataclass (no .get) — none of the callers ever received LLM text | Strangler Fig: migrate all 15 callers to brain/model_router.ModelRouter.async_route_and_generate (kwargs pass through gateway **kwargs -> litellm), map consumption to the facade dict contract (result.get('text')), delete services/llm entirely, retarget test mocks to the real contract, drop dead images=[...] kwargs (git archaeology proved no provider consumed them), regenerate route/capability evidence | 1) Before any dead-code retirement claim, grep the exact import lines (substring scans over-report); 2) When migrating an API, check the RETURN-type contract at every call site — mocks in tests can codify a contract the real implementation never had; 3) GitHub /branches commit dates live at .commit.commit.committer.date (not .commit.committer.date) — the /commits shape differs; 4) RouteResult-style dataclasses vs dict contracts: prefer one canonical result type across the stack |

