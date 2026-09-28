# SupremeAI — Active Issues Inventory & Priority Execution Roadmap
## (সক্রিয় ইস্যু ইনভেন্টরি, ডাইনামিক প্রায়োরিটি ম্যাট্রিক্স ও একশন রোডম্যাপ)

> **ডকুমেন্ট আইডি:** OPS-ACTIVE-ISSUES-01  
> **তারিখ:** ২০২৬-০৯-২৮ · **স্ট্যাটাস:** সক্রিয় অপারেশনাল রোডম্যাপ (Active Dynamic Standard)  
> **সোর্স অব ট্রুথ:** GitHub Issues Live State (`gh issue list --state open`)  
> **কোর প্রিন্সিপল:** *"Structural Reorganization over Blind Green — আগে আর্কিটেকচার ও পাইপলাইন গুছিয়ে নাও, গ্রিন রেজাল্ট বাই-প্রোডাক্ট হিসেবে একবারে নিখুঁতভাবে চলে আসবে।"*

---

## 🎯 ১. ভূমিকা ও কার্যনির্বাহী দর্শন (Executive Overview)

সুপ্রিমএআই রিপোজিটরির সক্রিয় ওপেন ইস্যুগুলোর মধ্যে সিস্টেমের স্থায়িত্ব, আর্কিটেকচারাল রিফ্যাক্টরিং এবং অপারেশনাল প্রায়োরিটির ভিত্তিতে কাজগুলোকে ডাইনামিক টিয়ারে (Dynamic Tiers) বিন্যস্ত করা হলো।

### কাজের মূল চার্টার (Operational Principles):
1. **Structural Reorganization over Blind Green (মৌলিক নীতি):** সিআই পাইপলাইন গ্রিন করা অবশ্যই অত্যন্ত জরুরি; কিন্তু পাইপলাইনকে কাঠামোগতভাবে সুসংগঠিত (Reorganized & Cleanly Structured) না করে শুধু সাময়িকভাবে বা অন্ধভাবে টেস্ট পাস করানোর চেষ্টা করা দীর্ঘমেয়াদে আরও বেশি ক্ষতিকর। সিআই রিঅর্গানাইজেশনের সুস্পষ্ট আর্কিটেকচারাল প্ল্যান থাকলে—সিআই-কে আগে গুছিয়ে নেওয়া অন্ধ গ্রিনের চেয়ে বহুগুণ বেশি গুরুত্বপূর্ণ। পাইপলাইন সুসংগঠিত হলে গ্রিন রেজাল্ট স্থায়ী হয় এবং কোনো ভঙ্গুর জোড়াতালি ছাড়াই প্রতিটি ইস্যু একবারে সফলভাবে ল্যান্ড করে।
2. **Flexible Group Branching Model (#2378):** 
   - **Connected Work (সংযুক্ত গ্রুপ কাজ):** `1 Issue Group → 1 Group Branch → Multiple Issues/Agents → 1 PR → Group-level Verification`
   - **Independent Work (একক স্বাধীন কাজ):** `1 Standalone Issue → 1 Dedicated Branch → 1 PR`
3. **Database as Operational Truth (#2377):** স্ট্যাটিক ফাইলে নয়, লাইভ অপারেশনাল সত্য, প্রায়োরিটি ও সক্ষমতার লাইফসাইকেল ডাটাবেস ও পলিসি ইঞ্জিন দ্বারা ডাইনামিকভাবে পরিচালিত হবে।

> ### 💡 লিভিং নোট: সিআই রিঅর্গানাইজেশন দর্শনের সার্বজনীন প্রয়োগ (The Living Principle)
> *"অন্ধভাবে সিআই গ্রিন করা একটি ক্ষণস্থায়ী লক্ষণ-ভিত্তিক চিকিৎসা; কিন্তু সিআই পাইপলাইনকে সুসংগঠিত করা হলো স্থায়ী কাঠামোগত সমাধান।"*
> * **কেন এটি সকল ইস্যুতে প্রযোজ্য:** Step-3 কোড কনসোলিডেশন, গভর্নেন্স রিফর্ম (#2378, #2377), নতুন পাইপলাইন (#2397) কিংবা P1 সিকিউরিটি ফিক্স—যেকোনো কাজের ক্ষেত্রেই যদি ডিপেন্ডেন্সি গেট, সেন্টিনেল রুট ট্র্যাকিং ও রোলআপ লজিক আগে পরিপাটি থাকে, তবে কোডারদের সিআই ভাঙা নিয়ে ড্রাইভ-বাই যুদ্ধ করতে হয় না।
> * **ডাইনামিক প্রায়োরিটি রুল:** প্রতিটি ইস্যু পর্যালোচনার সময় অন্ধ গ্রিনের চেয়ে আর্কিটেকচারাল সুসংবদ্ধতাকে অগ্রাধিকার দিয়ে ডাইনামিকভাবে র‍্যাঙ্কিং নির্ধারিত হবে।

---

## 🚦 ২. ডাইনামিক প্রায়োরিটি এক্সিকিউশন ম্যাট্রিক্স (Dynamic Priority Tiers)

```text
┌────────────────────────────────────────────────────────────────────────┐
│             SUPREMEAI ACTIVE EXECUTION MATRIX (THE FOUNDATION)         │
├────────────────────────────────────────────────────────────────────────┤
│ 🎯 ACTIVE CORE FOUNDATION (একমাত্র এই ৫টি ইস্যুতে কাজ চলবে):             │
│    ১. #2399 — Connected Ecosystem Graph & MCP Unified Governance       │
│    ২. #2377 — Database as Operational Truth + Documents as Context     │
│    ৩. #2378 — Flexible Group Branching Protocol                        │
│    ৪. #2397 — Living Prompt Autonomous Pipeline Implementation         │
│    ৫. #2396 — Constitution rules.yml Single Source of Truth Sync       │
├────────────────────────────────────────────────────────────────────────┤
│ 💤 DEFERRED BACKLOG / LOW PRIORITY (পুনর্বিবেচনার অপেক্ষায় স্থগিত):   │
│    • Step-3 Legacy Consolidation (#2280, #2282, #2283, #2284)          │
│    • Root-Audit & Script Cleanups (#2379, #2385, #2386, #2387, ...)   │
│    • Legacy P1 Bugs & Route Fixes (#2210, #2212, #2211, #2209, ...)    │
│    (ফাউন্ডেশনের ৫টি কাজ শেষ হওয়ার পর নতুন গ্রাফের আলোকে নতুন করে ভাবা হবে)│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 ৩. সক্রিয় কোর ফাউন্ডেশন (Active Core Foundation — The 5 Essential Issues)

সিস্টেমের মেরুদণ্ড, ডাটাবেস সত্য ও সুসংগঠিত সিআই কাঠামো গড়ে তুলতে শুধুমাত্র এই ৫টি ইস্যুতে সমস্ত মনোযোগ কেন্দ্রীভূত থাকবে:

| ক্রম | ইস্যু ID | শিরোনাম | কাজের মূল উদ্দেশ্য | কেন এখন অপরিহার্য? |
| :---: | :---: | :--- | :--- | :--- |
| **১** | **#2399** | `feat(architecture): SupremeAI Connected Ecosystem Graph — 3-Layer Model (Core ➔ 10 Domains ➔ Nodes) & MCP Unified Governance` | ৩-স্তর নেটওয়ার্ক গ্রাফ (Core, 10 Domains, Nodes), নোড ও এজের ৮টি গোল্ডেন প্রশ্ন এবং সেন্ট্রাল MCP সার্ভারের সাথে এজেন্টদের বাধ্যতামূলক সংযোগ। | **রিফ্যাক্টরিংয়ের মূল ভিত্তি:** পুরো সুপ্রিমএআই কীভাবে সংযুক্ত থাকবে তার ম্যাপিং। এটি ছাড়া অন্য কোথাও কাজ করলে অপ্রয়োজনীয় ডুপ্লিকেশন বা ভুল এবস্ট্রাকশন তৈরি হবে। |
| **২** | **#2377** | `feat(architecture): Database as Operational Truth + Documents as Context` | Policy DB, MCP Tower Bridge, ও Capability Lifecycle (`IDEA ➔ PLANNED ➔ APPROVED ➔ LIVE`) প্রতিষ্ঠা করা। | **ডাইনামিক অপারেশনাল ট্রুথ:** এজেন্টকে ৫০টি রুলস ফাইল পড়তে হবে না, ডাটাবেস থেকেই ডাইনামিক প্রায়োরিটি ও পারমিশন নির্ধারিত হবে। |
| **৩** | **#2378** | `feat(governance): Flexible Group Branching Protocol` | `1 Issue Group → 1 Branch → Multiple Issues/Agents → 1 PR` এবং স্বাধীন কাজে `1 Issue → 1 Branch → 1 PR`। `Issue ≠ Agent` নীতি কার্যকর। | **সিআই ও ব্রাঞ্চিং শৃঙ্খলা:** ৪টি মাইক্রো-পিআরের বদলে ১টি গ্রুপ ব্রাঞ্চে কাজ হলে ৭৫% সিআই জ্যাম ও কনফ্লিক্ট চিরতরে বন্ধ হবে। |
| **৪** | **#2397** | `feat(pipeline): implement Living Prompt Autonomous Pipeline (Phases 1–3)` | **Phase 1:** `master_cognitive_orchestrator` রিটায়ারমেন্ট।<br>**Phase 2:** ৩টি গার্ড গেট (`test_guard`, `self_merge`, `post_merge_watch`) লাইভ ওয়্যারিং।<br>**Phase 3:** জানিটর কাউন্টার অডিট ও লেবেল মাইগ্রেশন। | **স্বয়ংসম্পূর্ণ সিআই:** পাইপলাইনকে রেস-কন্ডিশন মুক্ত, স্বচ্ছ ও স্বয়ংক্রিয় করতে ৩টি সেফটি গেট ওয়্যারিং সম্পন্ন করা। |
| **৫** | **#2396** | `constitution: ARCH-LIVING-PIPELINE-01 rules.yml sync` | `rules.yml`-এ স্পেক রেফারেন্স যোগ করে `generate_agents_md.py` চালানো। | **সংবিধান সিঙ্ক:** লিভিং পাইপলাইনের নিয়মাবলী সংবিধানের সাথে সম্পূর্ণ সিঙ্কে রাখা। |

---

## 💤 ৪. স্থগিত ব্যাকলগ ও পুনর্বিবেচনা কিউ (Deferred Backlog / Low Priority)

> ### ⚠️ কৌশলগত সিদ্ধান্ত (Strategic Rationalization):
> *"কোর ফাউন্ডেশনের ৫টি কাজ (ইকোসিস্টেম গ্রাফ, ডাটাবেস সত্য, গ্রুপ ব্রাঞ্চিং ও লিভিং পাইপলাইন) সম্পন্ন হওয়ার পর পুরো সিস্টেমের নোড, এজ ও কার্যপ্রণালী আমূল বদলে যাবে। তাই বর্তমানের বাকি ইস্যুগুলো নিয়ে পুরাতন ধাঁচে কাজ করা অর্থহীন এবং দ্বিগুণ শ্রমের অপচয়। ফাউন্ডেশন সম্পন্ন হওয়ার পর এই ইস্যুগুলোকে নতুন গ্রাফ ও ৮টি গোল্ডেন প্রশ্নের আলোকে নতুন করে মূল্যায়ন (Re-evaluated) করা হবে।"*

নিচের সকল ইস্যু বর্তমানে **স্থগিত / Low Priority** হিসেবে চিহ্নিত করা হলো:

### ক. Step-3 লিগ্যাসি কোড কনসোলিডেশন (Deferred)
* **#2280** — `refactor(browser): [Step-2.7] consolidate browser automation` (গ্রাফে ব্রাউজার ডোমেইন ম্যাপিংয়ের পর পুনর্মূল্যায়ন)
* **#2282** — `chore(cleanup): [Step-2.8] consolidate docs/ folder` (কোর গ্রাফ রেজিস্ট্রি তৈরি হলে ডকস কনসোলিডেশন স্বয়ংক্রিয়ভাবে সহজ হবে)
* **#2283** — `chore(cleanup): [Step-2.9] consolidate scripts/ folder` (সিআই রিঅর্গানাইজেশনের আওতায় সমন্বিত হবে)
* **#2284** — `refactor(frontend): [Step-2.10] consolidate frontend state/tokens` (কোর স্টেট মডেল ফাইনাল হলে ফ্রন্টএন্ড সাজানো হবে)
* **#2330** — `audit(simplification): [Step-3.7] audit consolidated layers`

### খ. রুট-অডিট ও স্ক্রিপ্ট ক্লিনআপ (Deferred)
* **#2379** — `[Phase-0] Wire 3 safety-critical CI gates` (#2397-এ অন্তর্ভুক্ত)
* **#2385** — `[Phase-0] Add test runner + CI build for mission-control`
* **#2386** — `[Phase-1] Delete 15 dead CI scripts (56% of .github/scripts/)`
* **#2387** — `[Phase-1] Move pyerrorfix/ out of backend/ (36 files, 5,759 LOC)`
* **#2388** — `[Phase-1] Delete competitive_kit.py (1,573 LOC orphan)`
* **#2389** — `[Phase-2] Delete or wire UniversalRulesEngine (1,891 LOC, 144 rules)`
* **#2383** — `[Phase-3] Consolidate 4 competing rule systems into 1 rules.yml`
* **#2380** — `[Phase-1] Delete 21 dead frontend components + 5 zombie hooks`

### গ. লিগ্যাসি P1 বাগ ও রাউট ফিক্স (Deferred)
* **#2210** — `fix(auth): P1 token refresh is broken for mutating requests`
* **#2212** — `fix(realtime): P1 CommandCenter & Telemetry WebSocket auth`
* **#2211** — `fix(swarm): P1 /swarm page renders permanently empty`
* **#2209** — `fix(routes): P1 three intra-module route shadows`
* **#2128** — `fix(security): #P1 plaintext credentials embedded in git URLs`

---

## 📋 ৫. স্বয়ংক্রিয় এজেন্টদের জন্য নতুন এক্সিকিউশন অর্ডার

যেকোনো কোডার বা প্ল্যানার এজেন্ট সেশন শুরু করলে শুধুমাত্র নিচের ৪-৫টি ফাউন্ডেশন স্টেপে ক্রমানুসারে কাজ করবে (বাকি কোনো ইস্যুতে হাত দেওয়া সম্পূর্ণ নিষিদ্ধ):

1. **Step 1 (#2399):** ৩-স্তর কানেক্টেড ইকোসিস্টেম গ্রাফ রেজিস্ট্রি তৈরি ও MCP কন্ট্রোল টাওয়ার সংযোগ নিশ্চিত করো।
2. **Step 2 (#2377):** ডাটাবেস অ্যাজ অপারেশনাল ট্রুথ ও পলিসি ডিবি ইন্টিগ্রেশন সম্পন্ন করো।
3. **Step 3 (#2378):** ফ্লেক্সিবল গ্রুপ ব্রাঞ্চিং প্রোটোকল বাস্তবায়ন করো (`scripts/agents/acquire_role_slot.py` ও সিআই রুলস)।
4. **Step 4 (#2397 & #2396):** লিভিং প্রম্পট পাইপলাইনের ৩টি ফেজ সম্পন্ন ও `rules.yml` সিঙ্ক করো।
5. **Step 5 (Re-evaluation Phase):** ফাউন্ডেশন শেষ হলে স্থগিত থাকা বাকি সব ইস্যুকে নতুন গ্রাফের ৮টি গোল্ডেন প্রশ্ন দিয়ে রি-অডিট করো—অনেকগুলো স্বয়ংক্রিয়ভাবে ড্রপ হবে বা নতুন গ্রুপ হিসেবে আত্মপ্রকাশ করবে।

---
*ডকুমেন্ট সমাপ্ত — সুপ্রিমএআই ডাইনামিক অপারেশনাল রোডম্যাপ হিসেবে সংরক্ষিত।*
