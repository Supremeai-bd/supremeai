# SupremeAI — Risk-Tiered Autonomous Safety Pipeline Architecture
## "Simple by default, Deep by risk" (গভর্নড অটোনোমাস ভেরিফিকেশন আর্কিটেকচার)

**Document Type:** Architecture Blueprint & Operational Specification  
**Status:** Approved Architectural Standard  
**Date:** 2026-09-13  
**Alignment:** SupremeAI Core Constitution (#1 Eternal Brain, #5 Verification Before Trust, #7 Learning Requires Governance, #14 Sustainable Cost) & [AGENTS.md](./AGENTS.md) (Section 3: Governed Autonomy)

---

## ১. Executive Summary & মূল দর্শন (Philosophy)

SupremeAI-এর স্বয়ংক্রিয় পরিবর্তন ও সেলফ-ইভল্যুশন (Self-Evolution) কোনো **"অন্ধ স্বয়ংক্রিয় পরিবর্তন"** বা **"প্রতি ধাপে মানুষের অনুমোদনের চিরস্থায়ী জ্যাম (Approval Bottleneck)"** হতে পারে না। 

একই সাথে, একগাদা সিকিউরিটি এজেন্ট বসিয়ে সিস্টেমকে ধীরগতি (latency) ও ব্যয়বহুল (cost explosion) করা গ্রহণযোগ্য নয়। আমাদের মূল দর্শন:

> **"Simple by default, deep by risk."**  
> সাধারণ বা কম ঝুঁকির কাজে সিস্টেম হবে সুপারফাস্ট ও সস্তা; কিন্তু সংবেদনশীল বা উচ্চ ঝুঁকির কাজে কার্যকর হবে বহু-স্তরের গভীর প্রতিরোধ ও নিরপেক্ষ যাচাই।  
> **"SupremeAI নিজেকে অন্ধভাবে নিরাপদ মনে করবে না; SupremeAI নিজেকে ক্রমাগত পরীক্ষা (Continuously Verify) করবে।"**

---

## ২. The Dynamic Risk-Tiered Safety Pipeline

```text
                   Proposed Change / Autonomous Task
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │    L1: Rule/Safety Gate   │
                    │  (Deterministic Engine)   │
                    └─────────────┬─────────────┘
                                  │ PASS
                                  ▼
                    ┌───────────────────────────┐
                    │    L2: GitHub / CI Ground │
                    │   (Parallel Test Matrix)  │
                    └─────────────┬─────────────┘
                                  │ PASS
                                  ▼
                    ┌───────────────────────────┐
                    │ Risk Classifier & Router  │
                    └─────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼ (LOW RISK)            ▼ (MEDIUM RISK)         ▼ (HIGH RISK / CONSEQUENTIAL)
     [Fast-Path]             [Targeted Gate]        [Deep Multi-Layer Gate]
   Auto-Promote to         1 External Reviewer      L3: Adversarial Reviewer ("Assume Wrong")
   Canary/Staging          (or Browser Workflow)    + Headless Staging Browser Simulation
          │                       │                 + Security Impact Analysis
          │                       │                 + Explicit Governance / Human Gate
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │   Staged Canary Rollout   │
                    └─────────────┬─────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │   Runtime Observability   │
                    │   & pass^k Outcome Gate   │
                    └─────────────┬─────────────┘
                           ┌──────┴──────┐
                           ▼             ▼
                     ✅ Promote     ❌ Auto-Rollback
                     (Compound)      (Preserve Evidence)
```

---

## ৩. লেয়ারভিত্তিক দায়িত্ব ও ফ্রেমওয়ার্ক (Layer Responsibilities)

প্রতিটি লেয়ার কখনোই একই প্রশ্ন বা একই কাজ পুনরাবৃত্তি করবে না:

| Layer | মূল প্রশ্ন | প্রযুক্তিকরণ (Implementation) |
|---|---|---|
| **L1: Rule / Safety Gate** | *"এটা কি আমাদের নীতিমালায় এলাউড?"* | **Deterministic Code / AST Engine** (No-LLM fast path)। সিক্রেট লিক, ড্রপ কমান্ড, আরএলএস মিসিং চেক। |
| **L2: GitHub Testing Ground** | *"এটা কি বাস্তবে টেকনিক্যালি কাজ করে?"* | আইসোলেটেড ব্রাঞ্চ/পিআর, প্যারালাল টেস্ট (Unit/Integration), লিন্ট, বিল্ড, সাইকেল ড্রাফট। |
| **L3: Independent Reviewer** | *"আমরা কি কোনো গুরুত্বপূর্ণ কিছু মিস করেছি?"* | মূল এজেন্ট নয়, সম্পূর্ণ **ভিন্ন মডেল বা ফ্রেশ কন্টেক্সট**। |
| **Browser / Staging Runner** | *"বাস্তব ব্যবহারকারীর মতো ফ্লো কাজ করছে তো?"* | হেডলেস ব্রাউজার দিয়ে স্টার্ট-টু-ফিনিশ ইউজার ফ্লো টেস্ট। |
| **Canary / Runtime Monitor**| *"প্রোডাকশন ট্রাফিকের মাঝে সিস্টেম স্টেবল তো?"* | লাইভ টেলিমেট্রি এবং `pass^k` কনসিস্টেন্সি মনিটরিং। |
| **Learning & Evolution** | *"ভুল হলে পরের বার কীভাবে স্বয়ংক্রিয়ভাবে আটকাব?"* | প্রি-কগনিটিভ মেমোরি ও রুল ডাটাবেজে ব্যর্থতার প্যাটার্ন সিংক। |

---

## ৪. বিস্তারিত লেয়ার আর্কিটেকচার

### L1: Rule & Safety Gate (The Deterministic Shield)
* **LLM ছাড়া ডিটারমিনিস্টিক ইঞ্জিন:** রুল গেট চালানোর জন্য প্রতিবার মডেলকে টাকা দেওয়ার দরকার নেই। ৯৫% মৌলিক পলিসি সাধারণ পাইথন লজিক ও AST পার্সার দিয়ে যাচাই করা সম্ভব:
  ```python
  if secret_pattern_detected(diff):
      return BlockResult(REASON_SECRET_EXPOSURE)
  if "DROP TABLE" in sql or destructive_operation(diff):
      return BlockResult(REASON_DESTRUCTIVE_REQUIRES_APPROVAL)
  if tenant_isolation_violated(diff):
      return BlockResult(REASON_TENANT_LEAKAGE)
  ```
* **কখন LLM আসবে?** কেবল যখন নিয়মের ব্যাখ্যা দ্ব্যর্থক (Ambiguous) হবে বা জটিল কনটেক্সট যাচাইয়ের প্রয়োজন হবে। এটি ল্যাটেন্সি এবং খরচ দুটোকেই শূন্যের কোঠায় রাখে।

### L2: GitHub = The Experiment Surface
* গিটহাব কেবল কোড সংরক্ষণের জায়গা নয়, এটি আমাদের **নিয়ন্ত্রিত গবেষণাগার (Controlled Experiment Surface)**।
* কোনো সেলফ-ইভল্যুশন বা অটোনোমাস কোড সরাসরি প্রোডাকশনে আসবে না।
* **প্যারালাল এক্সিকিউশন:**
  ```text
            Rule Gate Passed
                   │
         ┌─────────┼─────────┐
         ▼         ▼         ▼
     Security    Tests    Architecture / Contracts
  ```
  এই ধাপগুলো প্যারালালে চলবে, ফলে চেকের গভীরতা বাড়লেও অপেক্ষার সময় (Latency) বাড়বে না।

### L3: Independent & "Adversarial Reviewer" Philosophy
* **Self-Confirmation Bias ধ্বংস:** যে AI কোড লিখেছে, সে কখনোই তার নিজের কোড নিরপেক্ষভাবে রিভিউ করতে পারে না।
* **"Assume this change is wrong. Try to prove it." (প্রমাণ করো কোডটি ভুল):**
  রিভিউয়ার কোনো অ্যাপ্রুভাল বট হবে না। তার প্রম্পট হবে আক্রমণাত্মক ও সমালোচনামূলক। সে খুঁজবে:
  1. *কীভাবে এটি ভেঙে ফেলা সম্ভব? (Edge Cases & Malformed Inputs)*
  2. *কোনো পারমিশন বাইপাস বা টেন্যান্ট ডাটা লিক হচ্ছে কি না?*
  3. *কোনো রেস কন্ডিশন (Race Condition) তৈরি হচ্ছে কি না?*
  4. *রোলব্যাক মেকানিজম ফেল করলে কী ঘটবে?*
  5. *ক্যাশ মিস বা আনবাউন্ডেড লুপে খরচ বা মেমরি বিস্ফোরণ হবে কি না?*

### Free-Tier AI Routing Strategy
* ফ্রি বা কমদামী মডেল (যেমন Gemini Free, Groq Llama) কখনোই একা **চুড়ান্ত সিদ্ধান্তদাতা (Final Authority)** হবে না।
* **ভূমিকা:** এরা হবে **অ্যাডিশনাল ওপিনিয়ন বা সতর্কবার্তা প্রেরক (Adversarial Signal)**। যদি কোনো কমদামী এক্সটারনাল মডেল সংশয় তোলে, সিস্টেম স্বয়ংক্রিয়ভাবে বিষয়টি ফ্ল্যাগ করবে এবং টেস্ট বা হিউম্যান গভর্ন্যান্সে পাঠাবে।

### In-Built Browser as a Live Verification Agent
* ব্রাউজার শুধু ওয়েব স্ক্র্যাপিংয়ের জন্য নয়—এটি আমাদের **প্রোডাকশন-ভ্যালিডেশন টুল**।
* কোডের ইউনিট টেস্ট পাস করলেও রিয়েল ইউজার ফ্লো ব্রাউজার এজেন্ট চালিয়ে যাচাই করা হবে:
  `Login Staging` ➔ `Navigate Component` ➔ `Trigger Workflow` ➔ `Inspect DOM & Network` ➔ `Capture Visual Evidence`।

---

## ৫. Risk-Tiered Routing Policy (ঝুঁকিভিত্তিক শ্রেণিবিন্যাস)

| Risk Tier | উদাহরণ | নির্ধারিত পাইপলাইন | অনুমোদন ও রোলআউট |
|---|---|---|---|
| **Low Risk** | ডক আপডেট, বিচ্ছিন্ন ইউনিট টেস্ট, ফরম্যাটিং, ইন্টারনাল ক্যাশ টিউনিং | L1 Deterministic Gate ➔ L2 Fast Unit Tests | স্বয়ংক্রিয় প্রমোশন, কোনো অতিরিক্ত AI কল নেই। |
| **Medium Risk** | ইন্টারনাল রিফ্যাক্টরিং, নন-ক্রিটিক্যাল রাউটিং লজিক, সাধারণ UX চেঞ্জ | L1 Gate ➔ L2 Full Matrix ➔ ১টি Independent AI Reviewer (বা ব্রাউজার টেস্ট) | স্টেজড ক্যানারি রোলআউট। |
| **High Risk** | অথেনটিকেশন, ডাটাবেজ স্কিমা, সিকিউরিটি বাউন্ডারি, বিলিং/কোটা, অটোনোমাস ইঞ্জিন সেলফ-মডিফিকেশন | L1 Gate ➔ L2 Full Matrix ➔ Adversarial AI Review ➔ Browser E2E ➔ Staging Test | **বাধ্যতামূলক হিউম্যান অ্যাপ্রুভাল (HITL)** + লাইভ রোলব্যাক গ্যারান্টি। |

---

## ৬. Verification ও Rollback গ্যারান্টি (Safety Contract)

প্রতিটি কনসিকুয়েনশিয়াল পরিবর্তনের জন্য নিম্নলিখিত এভিডেন্স সংরক্ষিত থাকবে:
1. **পূর্বের পরিচিত সুস্থ ভার্সন (Known-good baseline commit)**।
2. **প্রস্তাবিত পরিবর্তনের উদ্দেশ্য ও হাইপোথিসিস**।
3. **L2 ও L3 ভেরিফিকেশনের সমস্ত টেস্ট ও অ্যাডভারসারিয়াল লগ**।
4. **`pass^k` কনসিস্টেন্সি স্কোর (অন্তত ৩টি স্বাধীন ট্রায়ালে ধারাবাহিক সাফল্য)**।
5. **ফেইলিয়ারের সাথে সাথে জিরো-ডাউনটাইম অটোমেটিক রোলব্যাক পাথ**।

---

> **সংযোজন:** এই আর্কিটেকচার ব্লুপ্রিন্টটি SupremeAI-এর কোর মাস্টার প্ল্যান ও কনস্টিটিউশনের সাথে সিংক করা হয়েছে এবং পরবর্তী সমস্ত সেলফ-ইভল্যুশন ইঞ্জিনিয়ারিংয়ের জন্য অপরিবর্তনীয় নীতিমালা হিসেবে সংরক্ষিত হলো।
