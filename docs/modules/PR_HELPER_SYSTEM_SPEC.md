# SupremeAI Multi-Agent PR Helper & Autonomous Arbitration Specification
## Architecture: 4-Agent Sovereign Consensus Engine (Overriding Blind CI Gates)
**Module:** `core/pr_helper` / `core/guardian/arbitration`  
**Document Type:** Architectural Blueprint & Operational Standard  
**Status:** Approved Standard  
**Aligned Directives:**
- [AGENTS.md](file:///F:/supremeai/AGENTS.md) (#1 Scope & Safety, #2 Intent Over Examples, #3 Operational Zero-Gap, #4 Federated Decoupling, #13 Empirical Gate)
- [SUPREMEAI_CORE_CONSTITUTION.md](file:///F:/supremeai/docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md) (#1 Centralize Important Control, #4 Provider Sovereignty, #8 Verify Before Trust)
- [RISK_TIERED_AUTONOMOUS_SAFETY_PIPELINE.md](file:///F:/supremeai/docs/architecture/RISK_TIERED_AUTONOMOUS_SAFETY_PIPELINE.md) ("Simple by default, Deep by risk")

---

## ১. সমস্যা ও বাস্তবতা (The Fatal Blind Spot of CI/CD Gates)

GitHub Actions-এ ২৬টি বা ততোধিক জব প্যারালালে রান হতে পারে:
- `security`, `advanced-checks`, `backend-aggregate`, `backend-contract`, `frontend-tests`, `build`, `integration-test`, `docker`, `mcp-build`, `production-deploy`, ইত্যাদি।

### কেন ব্লাইন্ড CI স্ট্যাটাস চরম বিপজ্জনক ও অকার্যকর:
1. **ফলস গ্রিন অথচ আর্কিটেকচারাল ক্ষতি (False Green Trap):**
   - সবগুলো ২৬টি জব ১০০০০০০% সবুজ থাকতে পারে।
   - কিন্তু কোনো পিআরে যদি কোনো ক্রিটিক্যাল কনফিগ বা ব্যাকএন্ড URL বদলে দিয়ে এক্সটার্নাল কোনো আনভেরিফায়েড লিঙ্কে পয়েন্ট করানো হয় (`API_BASE_URL = "https://attacker.com"`), ব্লাইন্ড CI বলবে "All checks passed!" এবং স্বয়ংক্রিয়ভাবে কোড মার্জ করে দেবে। **এটি সিস্টেমের চূড়ান্ত ক্ষতি।**
2. **ফলস রেড অথচ প্রকৃত উন্নতি (False Red Trap):**
   - ধরা যাক, একজন ডেভেলপার বা এজেন্ট একটি অসাধারণ পারফরম্যান্স রিফ্যাক্টরিং বা আধুনিক সিকিউরিটি প্যাচ নিয়ে এসেছে।
   - কিন্তু মেইন ব্রাঞ্চের কোনো পুরোনো স্ট্যাব, অবসোলেট হার্ডকোডেড টেস্ট বা থার্ড-পার্টি রেট-লিমিটের কারণে CI-এর জবগুলো লাল (Failed) হয়ে গেল।
   - ব্লাইন্ড GitHub রুলস বলে দেবে: "Job failed, cannot merge!" ফলে একটি প্রকৃত **ইমপ্রুভমেন্ট (Improvement)** সিস্টেম থেকে বাতিল হয়ে পড়ে থাকে।

> **"২৬টি জব পাস কি ফেইল করেছে—সেটি অন্ধভাবে দেখে সিদ্ধান্ত নেওয়া যাবে না। প্রয়োজন এমন একটি অভ্যন্তরীণ ইন্টেলিজেন্ট কাউন্সিল, যারা বিশ্লেষণ করে রায় দিতে পারবে: পরিবর্তনটি কি প্রকৃত উন্নতি (Improvement) নাকি ক্ষতিকর অবনতি (Regression)?"**

---

## ২. দ্য ৪-এজেন্ট কাউন্সিল (The 4-Agent PR Helper Swarm)

PR Helper কোনো একক সাধারণ স্ক্রিপ্ট বা GitHub সেটিং নয়; এটি সুপ্রিমএআই সিস্টেমের **৪টি বিশেষায়িত অটোনোমাস এজেন্টের একটি আরবিট্রেশন কাউন্সিল (Arbitration Council)**:

```text
                                Pull Request Diff
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────────┐
    │              SupremeAI 4-Agent PR Arbitration Council                 │
    └───────┬───────────────────┬───────────────────┬───────────────────┬───┘
            │                   │                   │                   │
            ▼                   ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │ Agent 1:      │   │ Agent 2:      │   │ Agent 3:      │   │ Agent 4:      │
    │ Semantic Diff │   │ Security & URL│   │ Test Failure  │   │ Architectural │
    │ & Intent      │   │ Sentinel      │   │ Autopsy Agent │   │ Arbiter &     │
    │ Auditor       │   │               │   │               │   │ Synthesizer   │
    └───────┬───────┘   └───────┬───────┘   └───────┬───────┘   └───────┬───────┘
            │                   │                   │                   │
            └───────────────────┼───────────────────┼───────────────────┘
                                ▼
               Consensus / Decision Matrix Verdict:
               [IMPROVEMENT (Override CI)] vs [REGRESSION (Block)]
```

---

## ৩. প্রতিটি এজেন্টের সুনির্দিষ্ট ভূমিকা ও ম্যান্ডেট

### Agent 1: Semantic Diff & Intent Auditor (উদ্দেশ্য ও কনটেক্সট বিশ্লেষক)
* **ম্যান্ডেট:** "পিআরের পেছনের আসল উদ্দেশ্য কী?"
* **কার্যপ্রণালী:**
  - পিআরের টাইটেল, লিংকড ইস্যু এবং কোড ডিফের সেমান্টিক মিনিং এনালাইসিস করা (Abstract Syntax Tree / AST লেভেলে)।
  - পরিবর্তনটি কি কোনো নতুন সক্ষমতা যোগ করছে, বাগ ফিক্স করছে, নাকি ডেড কোড পরিষ্কার করছে?
  - কোডের ইনটেন্ট কি [AGENTS.md](file:///F:/supremeai/AGENTS.md)-এর "Operational Zero-Gap" ও ডোমেইন নিয়মের সাথে সঙ্গতিপূর্ণ?
* **আউটপুট:** `IntentClassification: { type: "Fix" | "Feature" | "Refactor", scope: "backend/core", is_substantive: bool }`

### Agent 2: Security & URL Sentinel (প্রতিরক্ষা ও এক্সফিল্ট্রেশন গার্ড)
* **ম্যান্ডেট:** "এখানে কোনো লুকানো নিরাপত্তা ঝুঁকি, ব্যাকডোর বা ক্ষতিকর URL পরিবর্তন আছে কি?"
* **কার্যপ্রণালী:**
  - ডিফের মধ্যে যেকোনো URL, হোস্টনেম, আইপি বা এন্ডপয়েন্ট মিউটেশন স্ক্যান করা।
  - অনুমোদিত হোস্টলিস্ট (`ALLOWED_HOSTS`, `SUPREMEAI_DOMAINS`, ক্লাউড প্রোভাইডার) ব্যতীত কোনো নতুন বা আনভেরিফায়েড এক্সটার্নাল URL ইনজেক্ট হলে **২৬টি জব গ্রিন থাকলেও সরাসরি VETO (ব্লক) দেবে**।
  - কোনো সিক্রেট, এপিআই কি, বা পারমিশন বাউন্ডারি বাইপাস শনাক্ত করা।
* **আউটপুট:** `SecurityVerdict: { status: "SAFE" | "VETO", risk_score: 0.0 - 1.0, url_mutations: [...] }`

### Agent 3: Test Failure Autopsy Agent (ব্যর্থতার ময়নাতদন্তকারী)
* **ম্যান্ডেট:** "CI-এর যে জবগুলো ফেইল করেছে, সেগুলো কি এই পিআরের কারণে নাকি পুরোনো সিস্টেমের জ্যাম?"
* **কার্যপ্রণালী:**
  - CI-এর ফেইল হওয়া জবগুলোর লগ এবং স্ট্যাক ট্রেস গভীরভাবে বিশ্লেষণ করা।
  - **ফলস পজিটিভ শনাক্তকরণ:** ফেইলরটি কি ফ্ল্যাকি টেস্ট, এক্সটার্নাল রেট-লিমিট (Render/Upstash/GitHub), নাকি মেইন ব্রাঞ্চের প্রি-এক্সিস্টিং বাগ?
  - **প্রকৃত রিগ্রেশন শনাক্তকরণ:** পিআরের কোড চেঞ্জের কারণে সরাসরি কোনো ফাংশন ভেঙেছে কি না?
  - যদি দেখা যায় পিআরের কোড সম্পূর্ণ সঠিক কিন্তু পুরোনো কোনো আউটডেটেড টেস্ট এসার্ট করার কারণে CI লাল হয়েছে, তবে এই এজেন্ট রায় দেয়: `CI_FAILURE_IRRELEVANT` (ফলস অ্যালার্ম)।
* **আউটপুট:** `AutopsyReport: { is_regression: bool, failing_jobs_culprit: "PR_CODE" | "LEGACY_FLAKE" | "UPSTREAM_ENV" }`

### Agent 4: Architectural Arbiter & Synthesizer (সর্বোচ্চ আরবিটার)
* **ম্যান্ডেট:** "সবকিছু মিলিয়ে এটি কি একটি Improvement নাকি Regression?"
* **কার্যপ্রণালী:**
  - পূর্ববর্তী ৩টি এজেন্টের রিপোর্ট সিন্থেসাইজ করা।
  - **The Golden Rule:**
    - যদি `Security Sentinel == VETO` ➔ **অবিলম্বে রিজেক্ট (কোনো ছাড় নেই, CI গ্রিন হলেও লাভ নেই)**।
    - যদি `Autopsy Agent == LEGACY_FLAKE / UPSTREAM_ENV` এবং `Semantic Diff == IMPROVEMENT` এবং `Security == SAFE` ➔ **২৬টি জব ফেল করলেও পিআরকে "IMPROVEMENT" ঘোষণা করবে এবং মার্জ অনুমোদন করবে!**
    - যদি `Autopsy Agent == PR_CODE (is_regression: true)` ➔ **রিগ্রেশন চিহ্নিত করে পিআর ব্লক করবে এবং সুনির্দিষ্ট ফিক্স কমেন্ট করবে**।
* **আউটপুট:** `FinalArbitrationVerdict: { verdict: "MERGE_IMPROVEMENT" | "BLOCK_REGRESSION", override_ci: bool, reasoning: str }`

---

## ৪. ডিসিশন ম্যাট্রিক্স (The Decision Matrix)

| CI স্ট্যাটাস (২৬টি জব) | Security Sentinel | Intent & Diff | Autopsy Result | চূড়ান্ত সিদ্ধান্ত | ব্যাখ্যা |
|---|---|---|---|---|---|
| 🟢 **ALL GREEN** | 🔴 **VETO (URL leak)** | Any | Passed | ❌ **BLOCK & REJECT** | CI ব্লাইন্ডলি গ্রিন ছিল, কিন্তু ক্ষতিকর URL/সিক্রেট পরিবর্তনের চেষ্টা হয়েছে। |
| 🟢 **ALL GREEN** | 🟢 **SAFE** | Improvement | Passed | ✅ **MERGE** | স্বাভাবিক নিরাপদ মার্জ। |
| 🔴 **26 JOBS FAILED** | 🟢 **SAFE** | Valid Improvement | Legacy Flake / Unrelated Bug | 🏆 **MERGE (OVERRIDE CI)** | আসল কোডে কোনো রিগ্রেশন নেই; পুরোনো ফেইলিং জবের ফাঁদ ভেঙে সিস্টেম কোড গ্রহণ করবে। |
| 🔴 **1+ JOBS FAILED** | 🟢 **SAFE** | Intent Broken | PR Code Culprit (Regression) | ❌ **BLOCK & REPORT** | পরিবর্তনটি সিস্টেমের কন্ট্রাক্ট ভেঙেছে, রিগ্রেশন ফিক্স প্রয়োজন। |

---

## ৫. বাস্তবায়ন কাঠামো (Implementation Blueprint)

এই ৪-এজেন্ট কাউন্সিল আমাদের নিজস্ব কোডবেসে স্বয়ংক্রিয় পাইপলাইন হিসেবে থাকবে:
1. **ইন্টিগ্রেশন পয়েন্ট:** `core/guardian/arbitration/pr_council.py`
2. **কন্ট্রোল টাওয়ার সংযোগ:** `backend/api/routes/control_tower` থেকে `guardian_evaluate_pr` কল করার সময় এই ৪-এজেন্ট কাউন্সিল এক্সিকিউট হবে।
3. **প্রমাণ ও অডিট ট্রেইল:**
   - প্রতিটি রায়ের পূর্ণাঙ্গ অডিট লগ `docs/audits/pr_evaluations/PR_<ID>_ARBITRATION.md`-এ লেখা হবে।
   - গিটহাব পিআরে ৪ জন এজেন্টের সমন্বিত আরবিট্রেশন রায় কমেন্ট হিসেবে পোস্ট হবে।
