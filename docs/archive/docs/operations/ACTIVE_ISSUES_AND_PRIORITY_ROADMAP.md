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
4. **Auditors Ripple Effect Rule — অডিটরের রিপল ইফেক্ট নিয়ম (Universal Priority Law):** যখনই নতুন ইস্যু তৈরি বা প্রায়োরিটি নির্ধারণ হবে, অডিটর জিজ্ঞেস করবে — *"এটা শেষ হলে বাকি কতগুলো কাজ সহজ, দ্রুত বা অপ্রয়োজনীয় হয়ে যাবে?"* যে কাজের Positive Ripple Effect বাকি সবচেয়ে বেশি কাজে ছড়িয়ে পড়ে, সেটাই সর্বোচ্চ priority পাবে। **"যে কাজ বাকি সবকিছুকে সহজ করে, সেটাই আগে।"**
5. **GitHub Issues as Live Operational Truth (ডকুমেন্টেশনের চেয়ে লাইভ ইস্যু প্রধান):** স্ট্যাটিক মার্কডাউন ডকুমেন্টের স্থূলতা (Docs Bloat) কমানো এবং বড় বড় অডিট ফাইন্ডিংসকে ফাইলের ভেতর বন্দি না রেখে সরাসরি গিটহাব ইস্যুতে রূপান্তর করাই আমাদের টেক টিমের মূল দর্শন। GitHub Issues-ই আমাদের সবচেয়ে বড়, সক্রিয় এবং জীবন্ত অপারেশনাল ডকুমেন্টেশন। প্রতিটি চিহ্নিত সমস্যা ডকসে ফেলে না রেখে সুস্পষ্ট সিকোয়েন্স, ডিপেন্ডেন্সি এবং প্রায়োরিটিসহ গিটহাব ইস্যুতে সংরক্ষিত থাকবে।

> ### 🔴 লিভিং নোট: অডিটরের রিপল ইফেক্ট নিয়মের ৩টি চেকপয়েন্ট (Auditors Universal Priority Checkpoint)
> *"যে কাজ বাকি সবকিছুকে সহজ করে, সেটাই আগে।"*
> * **চেকপয়েন্ট ১ — ডাউনস্ট্রিম কাউন্ট:** এটা শেষ হলে বাকি কতটি কাজ সহজ হবে? → বেশি হলে priority বাড়াও।
> * **চেকপয়েন্ট ২ — ব্লকার টেস্ট:** এটা না করলে বাকি কাজ কোথায় আটকে থাকবে? → BLOCKER হলে সর্বোচ্চ priority।
> * **চেকপয়েন্ট ৩ — ভ্যালু ছড়ানোর পরিসর:** এটার value কি শুধু নিজের মধ্যে শেষ, নাকি পুরো সিস্টেমে ছড়িয়ে পড়ে? → Ripple বেশি হলে আগে করো।

---

## 🚦 ২. ডাইনামিক প্রায়োরিটি এক্সিকিউশন ম্যাট্রিক্স (Dynamic Priority Tiers)

```text
┌────────────────────────────────────────────────────────────────────────┐
│             SUPREMEAI ACTIVE EXECUTION MATRIX (LIVE ROADMAP)           │
├────────────────────────────────────────────────────────────────────────┤
│ ✅ TIER 1: COMPLETED CORE FOUNDATION (Merged to main)                  │
│    • #2399 — Connected Ecosystem Graph & MCP Unified Governance (PR #2400) │
│    • #2377 — Database as Operational Truth + Documents as Context (PR #2407)│
│    • #2378 — Flexible Group Branching Protocol (PR #2401)              │
│    • #2397 & #2396 — Living Prompt Autonomous Pipeline & Rules Sync    │
│    • #2408 — Predecessor Group Merge Hold Engine (PR #2409)            │
├────────────────────────────────────────────────────────────────────────┤
│ 🎯 TIER 2: ACTIVE FOUNDATION CLOSEOUT (চলমান ও পরবর্তী কাজ):           │
│    • #2403 — Reusability Audit & Toolkit CLI (PR #2426 in Review)     │
│    • #2404 — Live Production Env Audit (Render, Supabase, Cloudflare)  │
│    • #2405 — Capability Golden Benchmark & Parity Verification        │
│    • #2406 — ADR Lock & Zero-Garbage CI Prevention Guard               │
├────────────────────────────────────────────────────────────────────────┤
│ 🚀 TIER 3: PIPELINE RESTORATION & INFRA RUNTIME STABILITY:             │
│    • #2421 — PR Gate Real Test Restoration & Deploy Train with Rollback│
│    • #2425 — Prevent Issue Ops Storm on Sequential Bot Labeling        │
├────────────────────────────────────────────────────────────────────────┤
│ 🏛️ TIER 4: ARCHITECTURAL CAPABILITY CONSOLIDATION (Audit-Driven Issues)│
│    • #2427 — Starved Kernel & Memory RPC Zoo / 4-Writer Unification    │
│    • #2428 — Browser Playwright Singleton & Shadowed Route De-dup      │
│    • #2429 — MCP Tower & Python Policy Single Source of Truth          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 ৩. সক্রিয় কাজের ইনভেন্টরি ও এক্সিকিউশন সিকোয়েন্স (Live Issues Inventory)

### ক. ফাউন্ডেশন ও ক্লোজআউট ট্র্যাক (Foundation Closeout — Group Staging)

| ক্রম | ইস্যু ID | শিরোনাম | কাজের মূল উদ্দেশ্য | বর্তমান স্ট্যাটাস |
| :---: | :---: | :--- | :--- | :--- |
| **১** | **#2403** | `audit(cleanup): [Step-foundation-closeout.1] Reusability Audit & 497 Scripts Intelligent Re-creation` | ৪৯৭টি স্ক্রিপ্টকে ইন্টেলিজেন্ট টুলকিটে রূপান্তর ও ১০৪টি স্ক্রিপ্টের ডিটারমিনিস্টিক রান-ভ্যালু অডিট। | **PR #2426 (Green, in Review)** |
| **২** | **#2404** | `audit(infra): [Step-foundation-closeout.2] Live Production Environment Audit & Cloud Health Verification` | Render 512MB RAM, Supabase, Cloudflare, Redis ও Infisical-এর লাইভ কানেকশন অডিট। | **Queue: Pending #2403** |
| **৩** | **#2405** | `audit(quality): [Step-foundation-closeout.3] Capability Golden Benchmark & Intelligence Parity` | `knowledge/goldset.json`-এর বিপরীতে ক্লিনআপ-পরবর্তী বুদ্ধিমত্তা ও কোয়ালিটি রক্ষা। | **Queue: Pending #2404** |
| **৪** | **#2406** | `feat(governance): [Step-foundation-closeout.4] Architecture Decision Records (ADR) Lock` | `docs/master_docs`-এ ADR ফরম্যাট লক ও সিআই-তে zero-garbage-guard সংস্থাপন। | **Queue: Pending #2405** |

---

### খ. সিআই ও ইনফ্রাস্ট্রাকচার স্ট্যাবিলিটি ট্র্যাক (Pipeline Restoration & Deploy Train)

| ক্রম | ইস্যু ID | শিরোনাম | কাজের মূল উদ্দেশ্য | প্রায়োরিটি |
| :---: | :---: | :--- | :--- | :---: |
| **১** | **#2421** | `feat(architecture): Pipeline Restoration & Evolution — Real Tests, Frontend Guard & Deploy Train` | `pr.yml`-এ আসল ব্যাকএন্ড টেস্ট ও ফ্রন্টএন্ড টাইপচেক রিস্টোর করা, মার্জ ট্রেন বাদ দেওয়া এবং রোলব্যাক-সক্ষম Deploy Train প্রতিষ্ঠা। | **P1-High** |
| **২** | **#2425** | `fix(ci): Issue Ops Storm & Concurrency Cancellation Thrashing on Sequential Bot Labeling` | বটের সিকোয়েনশিয়াল লেবেলিংয়ের কারণে সৃষ্ট ১৩টি অযথা ২-সেকেন্ডের ওয়ার্কফ্লো স্টর্ম বন্ধ করা। | **P1-High** |

---

### গ. কোর আর্কিটেকচার ও সাবসিস্টেম কনসোলিডেশন ট্র্যাক (Capability Preservation)

| ক্রম | ইস্যু ID | শিরোনাম | কাজের মূল উদ্দেশ্য | প্রায়োরিটি |
| :---: | :---: | :--- | :--- | :---: |
| **১** | **#2427** | `refactor(architecture): Capability Consolidation & Pruning — Starved Kernel & Memory RPC Zoo` | ৪টি মেমোরি রাইটারকে একমাত্র `CascadeMemoryService`-এ আনা এবং সেন্ট্রাল কার্নেলে সক্ষমতা যুক্ত করা। | **P1-High** |
| **২** | **#2428** | `refactor(browser): Single Async Playwright Singleton, Route Deduplication & Interactive Hardening` | ১০টি প্লে-রাইট লঞ্চ সাইটকে একক সিঙ্গেলটনে রূপান্তর ও ৭১টি ডাবল মাউন্টেড রাউট পরিষ্কার করা। | **P2-Medium** |
| **৩** | **#2429** | `feat(mcp): Unify TypeScript Tower & Python MCP Policy Engine, Eliminate Drift & Single Client Registry` | টাওয়ার ও পাইথনের দ্বৈত পলিসি ইঞ্জিন একীভূত করে সিঙ্গেল সোর্স অব ট্রুথ প্রতিষ্ঠা। | **P2-Medium** |

---

## 📋 ৪. স্বয়ংক্রিয় এজেন্টদের জন্য নতুন এক্সিকিউশন অর্ডার

যেকোনো কোডার বা প্ল্যানার এজেন্ট সেশন শুরু করলে ডকস ফাইলে সময় নষ্ট না করে সরাসরি লাইভ গিটহাব ইস্যুতে কাজ করবে:
1. **Tier 2 Complete:** PR #2426 মার্জ করে #2404 ➔ #2405 ➔ #2406 ক্রমানুসারে ক্লোজআউট শেষ করো।
2. **Tier 3 Pipeline Fix (#2421 & #2425):** `pr.yml`-এ রিয়েল টেস্ট ও Deploy Train চালু করে সিস্টেমকে সার্বক্ষণিক নিরাপদ করো।
3. **Tier 4 Subsystem Consolidation (#2427, #2428, #2429):** কার্নেল, মেমোরি ও ব্রাউজার সাবসিস্টেমের জট ছাড়িয়ে আর্কিটেকচার ৫০% হালকা ও দ্বিগুণ শক্তিশালী করো।

---
*ডকুমেন্ট সমাপ্ত — সুপ্রিমএআই ডাইনামিক লাইভ ইস্যু রোডম্যাপ হিসেবে সংরক্ষিত।*
