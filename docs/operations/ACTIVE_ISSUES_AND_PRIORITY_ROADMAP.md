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
│                   SUPREMEAI ACTIVE ISSUE TIERS                         │
├────────────────────────────────────────────────────────────────────────┤
│ 🥇 1ST PRIORITY: Database as Truth & Dynamic Policy (#2377)           │
│ 🥈 2ND PRIORITY: Flexible Group Branching Protocol (#2378)             │
│ 🥉 3RD PRIORITY: Living Prompt Pipeline Implementation (#2397)         │
│ 🏅 4TH PRIORITY: Active Step-3 Group Consolidation (#2280 ➔ #2284)     │
│ 🛡️ 5TH PRIORITY: Safety-Critical Gates & Root Cleanups (#2379, #2385)  │
│ ⚠️ 6TH PRIORITY: Critical P1 Bug & Security Fixes (#2210, #2212)       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🥇 ৩. ১ম প্রায়োরিটি: ডাটাবেস অ্যাজ ট্রুথ ও ডাইনামিক প্রায়োরিটি ফ্রেমওয়ার্ক (1st Priority)

এজেন্টকে ৫০টি রুলস ফাইল মুখস্থ না করিয়ে ডাটাবেস থেকে ডাইনামিকভাবে পারমিশন ও প্রায়োরিটি এনফোর্স করার মূল ভিত্তি:

| ইস্যু ID | শিরোনাম | কাজের মূল উদ্দেশ্য | কেন ১ম প্রায়োরিটি? |
| :---: | :--- | :--- | :--- |
| **#2377** | `feat(architecture): Database as Operational Truth + Documents as Context` | Policy DB, MCP Tower Bridge, ও Capability Lifecycle (`IDEA ➔ PLANNED ➔ APPROVED ➔ LIVE`) প্রতিষ্ঠা করা। | এটি সক্রিয় হলে প্রতিটি কাজের স্ট্যাটাস ও ডাইনামিক প্রায়োরিটি স্বয়ংক্রিয়ভাবে ডাটাবেস ড্রাইভেন হবে — কোনো অন্ধ স্ট্যাটিক অনুমান থাকবে না। |

---

## 🥈 ৪. ২য় প্রায়োরিটি: ফ্লেক্সিবল গ্রুপ ব্রাঞ্চিং প্রোটোকল (2nd Priority)

আন্তঃ-এজেন্ট সমন্বয়হীনতা ও মাইক্রো-পিআরের সিআই জ্যাম সম্পূর্ণ নির্মূল করার প্রোটোকল:

| ইস্যু ID | শিরোনাম | প্রস্তাবিত সমাধান | কেন ২য় প্রায়োরিটি? |
| :---: | :--- | :--- | :--- |
| **#2378** | `feat(governance): Flexible Group Branching Protocol` | `1 Issue Group → 1 Branch → Multiple Issues/Agents → 1 PR` এবং স্বাধীন কাজে `1 Issue → 1 Branch → 1 PR`। `Issue ≠ Agent` নীতি কার্যকর। | পরবর্তী সব গ্রুপ কাজের ভিত্তি হবে এই প্রোটোকল। ৪টি আলাদা পিআরের বদলে ১টি গ্রুপ ব্রাঞ্চে কাজ হলে ৭৫% সিআই ও রিভিউ ওভারহেড কমে যাবে। |

---

## 🥉 ৫. ৩য় প্রায়োরিটি: লিভিং প্রম্পট পাইপলাইন ইমপ্লিমেন্টেশন (3rd Priority)

ক্যানোনাইজড আর্কিটেকচারাল স্পেক [ARCH-LIVING-PIPELINE-01.md](../architecture/ARCH-LIVING-PIPELINE-01.md)-এর বাস্তবায়ন:

| ইস্যু ID | শিরোনাম | বাস্তবায়নের ৩টি ফেজ | কেন ৩য় প্রায়োরিটি? |
| :---: | :--- | :--- | :--- |
| **#2397** | `feat(pipeline): implement Living Prompt Autonomous Pipeline (Phases 1–3)` | **Phase 1:** `master_cognitive_orchestrator` রিটায়ারমেন্ট।<br>**Phase 2:** ৩টি গার্ড গেট (`test_guard`, `self_merge`, `post_merge_watch`) লাইভ ওয়্যারিং।<br>**Phase 3:** জানিটর কাউন্টার অডিট ও লেবেল মাইগ্রেশন। | সিআই পাইপলাইনকে স্বয়ংসম্পূর্ণ, রেস-কন্ডিশন মুক্ত এবং শতভাগ সুসংগঠিত রাখতে ৩টি গেট কার্যকর করা অপরিহার্য। |
| **#2396** | `constitution: ARCH-LIVING-PIPELINE-01 rules.yml sync` | `rules.yml`-এ স্পেক রেফারেন্স যোগ করে `generate_agents_md.py` চালানো। | সংবিধান ও এজেন্টস গাইডের মধ্যে সিঙ্ক নিশ্চিত করে। |

---

## 🏅 ৬. ৪র্থ প্রায়োরিটি: সক্রিয় Step-3 গ্রুপ কোড কনসোলিডেশন (4th Priority)

Step-3-এর প্রথম দুটি কাজ (#2278 ও #2279) ইতোমধ্যে আজ সফলভাবে মার্জ হয়েছে। বাকি কাজগুলো ফ্লেক্সিবল গ্রুপ ব্রাঞ্চিং মডেলে সম্পন্ন হবে:

| সিকোয়েন্স | ইস্যু ID | কাজের শিরোনাম | মূল উদ্দেশ্য (লক্ষ্য) | স্ট্যাটাস |
| :---: | :---: | :--- | :--- | :--- :
| **seq:1** | **#2278** | `refactor(ai): consolidate 18 LLM routing layers` | `backend/tools/ensemble_router.py` ➔ canonical LLMGateway facade। | **✅ MERGED** |
| **seq:2** | **#2279** | `refactor(memory): consolidate 15 memory stores` | `backend/core/ai_memory/repository.py` pgvector consolidation। | **✅ MERGED** |
| **seq:3** | **#2280** | `refactor(browser): [Step-2.7] consolidate browser automation` | ১০টি Playwright লঞ্চ সাইট ও ডাবল রাউট মুছে ১টি Async সিঙ্গলটন করা (~৭,০০০ লাইন ছাঁটাই)। | Ready for Group Branch |
| **seq:4** | **#2282** | `chore(cleanup): [Step-2.8] consolidate docs/ folder` | ৪২৪টি ডক ফাইল থেকে ২,৬০,০০০ লাইন অপ্রয়োজনীয় ডকস ছাঁটাই করে ৩টি ক্যানোনিকাল ডক রাখা। | Ready for Group Branch |
| **seq:5** | **#2283** | `chore(cleanup): [Step-2.9] consolidate scripts/ folder` | ৪১৪টি স্ক্রিপ্ট থেকে ১,১৫,০০০ লাইন ছাঁটাই করে ২৫টি ক্লিন প্রোডাকশন CI স্ক্রিপ্ট রাখা। | Ready for Group Branch |
| **seq:6** | **#2284** | `refactor(frontend): [Step-2.10] consolidate frontend state/tokens` | ডুপ্লিকেট স্টেট, স্টোর ও সিএসএস স্ক্র্যাপ করে ২০,০০০ লাইন ফ্রন্টএন্ড কোড কমানো। | Ready for Group Branch |
| **seq:7** | **#2330** | `audit(simplification): [Step-3.7] audit consolidated layers` | সম্পূর্ণ Step-3 গ্রুপের ক্যাপাবিলিটি হার্ভেস্ট ও ১০১% বাস্তব লাভ অডিট। | Group Closeout |

---

## 🛡️ ৭. ৫ম প্রায়োরিটি: সেফটি গেট ও রুট অডিট ক্লিনআপ (5th Priority: Root-Audit Cleanups)

গিটহাব থেকে সরাসরি সংগৃহীত নতুন সিস্টেম ও কোড ক্লিনআপ ইস্যুসমূহ:

| ইস্যু ID | শিরোনাম | মূল কাজ | টিপস / প্রভাব |
| :---: | :--- | :--- | :--- |
| **#2379** | `[Phase-0] Wire 3 safety-critical CI gates (wired:false)` | `self-merge`, `test-guard`, `post-merge-watch` কার্যকর করা। | #2397-এর সাথে সমন্বিত। |
| **#2385** | `[Phase-0] Add test runner + CI build for mission-control` | ৯৭টি ফাইলের মিশন কন্ট্রোলে টেস্ট রানার যুক্ত করা। | ফ্রন্টএন্ড স্ট্যাবিলিটি। |
| **#2386** | `[Phase-1] Delete 15 dead CI scripts (56% of .github/scripts/)` | অপ্রয়োজনীয় সিআই স্ক্রিপ্ট ডিলিট ও ভ্যালিডেটর একীভূতকরণ। | সিআই জটিলতা হ্রাস। |
| **#2387** | `[Phase-1] Move pyerrorfix/ out of backend/ (36 files, 5,759 LOC)` | শূন্য কনজিউমার বিশিষ্ট pyerrorfix ব্যাকএন্ড থেকে সরানো। | বাউন্ডারি ক্লিনআপ। |
| **#2388** | `[Phase-1] Delete competitive_kit.py (1,573 LOC orphan)` | ৫টি কমিট সারভাইভ করা ডেড কোড ছাঁটাই। | ডেড-কোড ক্লিনআপ। |
| **#2389** | `[Phase-2] Delete or wire UniversalRulesEngine (1,891 LOC, 144 rules)` | রানটাইমে অব্যবহৃত ১৮৯১ লাইন রুলস ইঞ্জিন সিদ্ধান্ত। | রুলস একীভূতকরণ। |
| **#2383** | `[Phase-3] Consolidate 4 competing rule systems into 1 rules.yml` | ২৩৮টি রুলসকে ৪০টি কার্যকর রুলসে রূপান্তর। | সংবিধান রিঅর্গানাইজেশন। |
| **#2380** | `[Phase-1] Delete 21 dead frontend components + 5 zombie hooks` | ২৮০০ লাইন ডেড ফ্রন্টএন্ড কোড ছাঁটাই। | ফ্রন্টএন্ড ক্লিনআপ। |

---

## ⚠️ ৮. ৬ষ্ঠ প্রায়োরিটি: জটিল P1 বাগ ও সিকিউরিটি ফিক্স (6th Priority: Critical P1 Bugs)

| ইস্যু ID | শিরোনাম | সমস্যা ও সমাধান |
| :---: | :--- | :--- |
| **#2210** | `fix(auth): P1 token refresh is broken for mutating requests` | POST/PUT রিকোয়েস্টে এক্সপায়ার্ড টোকেন রি-সেন্ড ফিক্স। |
| **#2212** | `fix(realtime): P1 CommandCenter & Telemetry WebSocket auth` | ফ্রন্টএন্ড-ব্যাকএন্ড অথেনটিকেশন ফ্রেম কন্ট্রাক্ট মিসম্যাচ দূর করা। |
| **#2211** | `fix(swarm): P1 /swarm page renders permanently empty` | ফুল স্ন্যাপশট রেসপন্স পার্সার ফিক্স। |
| **#2209** | `fix(routes): P1 three intra-module route shadows` | GDPR রাইট-টু-ইরেজার এন্ডপয়েন্ট ও শেয়ার রুট শ্যাডো দূর করা। |
| **#2128** | `fix(security): #P1 plaintext credentials embedded in git URLs` | গিট রিমোট ইউআরএলে প্লেইনটেক্সট টোকেন বাদ দিয়ে সিক্রেট ভল্ট ব্যবহার করা। |

---

## 📋 ৯. স্বয়ংক্রিয় এজেন্টদের জন্য ডাইনামিক এক্সিকিউশন অর্ডার

যেকোনো কোডার বা প্ল্যানার এজেন্ট সেশন শুরু করলে ঠিক এই ক্রমানুসারে ডাইনামিকভাবে কাজ তুলে নেবে:

1. **Step 1 (1st Priority — #2377):** ডাটাবেস অ্যাজ অপারেশনাল ট্রুথ ও পলিসি ডিবি স্টেজ এগোও — যাতে পুরো সিস্টেমের স্টেট ও প্রায়োরিটি ডাইনামিক হতে পারে।
2. **Step 2 (2nd Priority — #2378):** ফ্লেক্সিবল গ্রুপ ব্রাঞ্চিং প্রোটোকল বাস্তবায়ন করো — যাতে পরবর্তী সব গ্রুপ কাজ `1 Group → 1 Branch → 1 PR` মডেলে চলে।
3. **Step 3 (3rd Priority — #2397):** লিভিং প্রম্পট পাইপলাইন (`ARCH-LIVING-PIPELINE-01`) বাস্তবায়ন সম্পন্ন করো (৩টি গার্ড গেট ওয়্যারিং সহ)।
4. **Step 4 (4th Priority — Step-3 Consolidation):** সক্রিয় Step-3 গ্রুপের অবশিষ্ট কাজগুলো (#2280 ব্রাউজার, #2282 ডকস, #2283 স্ক্রিপ্টস, #2284 ফ্রন্টএন্ড) নতুন গ্রুপ ব্রাঞ্চে সম্পন্ন করো।
5. **Step 5 (5th & 6th Priority):** রুট অডিট ক্লিনআপ (#2379, #2385, #2386) এবং P1 বাগ ফিক্সগুলোতে হাত দাও।

---
*ডকুমেন্ট সমাপ্ত — সুপ্রিমএআই ডাইনামিক অপারেশনাল রোডম্যাপ হিসেবে সংরক্ষিত।*
