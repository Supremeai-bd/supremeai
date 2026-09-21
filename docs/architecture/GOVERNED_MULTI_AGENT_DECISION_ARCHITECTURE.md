# SupremeAI — Governed Multi-Agent Control & Autonomous Decision Architecture
## Cost-Minimized Execution, Continuous Security & Layered Challenge Matrix

**Document Type:** Architecture Blueprint & Operational Decision Engine  
**Status:** Approved Architectural Standard  
**Date:** 2026-09-13  
**Alignment:** SupremeAI Core Constitution (#1 Eternal Brain, #2 Capability Sovereignty, #5 Tenant Ownership, #6 Think Before Acting, #8 Verify Before Trust, #9 Optimize Cost Without Limiting User Choice) & [AGENTS.md](./AGENTS.md)

---

## ১. Executive Philosophy & The Paradigm Shift

SupremeAI কোনো একক চ্যাটবট বা এলোমেলো সিকিউরিটি এজেন্টের জটিল মেস নয়। এটি একটি **গভর্নড অটোনোমাস ডিসিশন ফ্রেমওয়ার্ক (Governed Autonomous Decision Framework)**।

আমাদের দুটি নতুন মাইলফলক নীতি:

1. **"Cost-Minimized Execution" (নট অনলি Zero-Cost):**
   * "Zero Cost" কোনো অন্ধ বা ডগম্যাটিক গোঁড়ামি নয় যা কোয়ালিটি বা ইউজারের স্পষ্ট ইচ্ছাকে নষ্ট করবে। 
   * আমাদের লক্ষ্য: **"Lowest reasonable cost that still satisfies correctness, reliability, security, latency, authorization, and user requirements."**
   * যদি ইউজার বেস্ট রেজাল্ট চান এবং ফ্রি টিয়ার সেই কোয়ালিটি নিশ্চিত করতে না পারে, তবে সিস্টেম ইউজারের চয়েসকে সম্মান জানিয়ে পেইড পাথ নেবে। কিন্তু যেখানে জিরো-কস্ট ব্রাউজার, লোকাল লজিক, ক্যাশ বা MCP দিয়ে একই কাজ ১০০% কোয়ালিটিতে সম্ভব, সেখানে কখনো পেইড টোকেন অপচয় করা যাবে না।

2. **"Continuous & Context-Aware Security" (নট অনলি অ্যাট-রিলিজ স্ক্যানার):**
   * সিকিউরিটি শুধু রিলিজের আগের কোনো চেকলিস্ট নয়—এটি একটি চলমান অবস্থা (Continuous State)।
   * সবচেয়ে বড় বিষয়: **SupremeAI-এর নিজস্ব প্ল্যাটফর্ম সিকিউরিটি এবং ইউজারের প্রজেক্টের সিকিউরিটি কনটেক্সট সম্পূর্ণ আলাদা ও আইসোলেটেড।**

---

## ২. The 7 Core Agent Roles & Their Fundamental Questions

সিস্টেমের ৭টি কোর রেসপনসিবিলিটি—যাদের ভারী স্বয়ংক্রিয় এজেন্ট বানিয়ে সিস্টেম স্লো করা হবে না; বরং বেশিরভাগই লাইটওয়েট ডিটারমিনিস্টিক রুলস ও পলিসি ইঞ্জিনে চলবে, কেবল জটিল বা অ্যাম্বিগুয়াস কেসে শক্তিশালী মডেল ডাকবে:

| Agent / Role | মূল প্রশ্ন (The Fundamental Question) | মেকানিজম / টেকনোলজি |
|---|---|---|
| **1. Rule / Safety Gate** | *"এটা কি আমাদের নীতিমালায় অনুমোদিত (Allowed)?"* | Deterministic AST/Regex Gate + Scope Classifier (No-LLM fast path) |
| **2. Cost & Resource Optimizer** | *"একই কাজ কম খরচে ও সমমানের কোয়ালিটিতে কীভাবে করা যায়?"* | Capability Ladder, Semantic Cache, Deduplication Engine, Batch Router |
| **3. Continuous Security Agent** | *"বাইরে থেকে সিস্টেম বা ইউজারের উপর কীভাবে আক্রমণ (Attack/Exploit) হতে পারে?"* | SAST/DAST, SSRF/Prompt-Injection Guard, Threat Model, Continuous Scanner |
| **4. Testing & CI Ground** | *"এটা কি বাস্তবেই টেকনিক্যালি কাজ করছে?"* | GitHub Actions / Isolated Branch, Parallel Test Matrix, Build Verification |
| **5. Independent Reviewer** | *"আমরা কী ভুল মিস করেছি? (Assume this is wrong, prove it)"* | Adversarial Context, Distinct LLM Provider (Cross-checking) |
| **6. Runtime Observability & Monitor** | *"প্রোডাকশন ট্রাফিকের মাঝে এখনও কি সিস্টেম স্টেবল ও পারফর্মিং?"* | Telemetry Bus, `pass^k` consistency gate, Auto-Rollback triggers |
| **7. Learning & Synaptic Agent** | *"এই ঘটনা বা ফেইলিয়ার থেকে কী শিখে স্থায়ীভাবে মেমরিতে যোগ করব?"* | Governed Learning Loop, Experience DB, Pre-cognitive Patterns |

---

## ৩. The Governed Planning Flow: Safety Cannot Be Optimized Away

কস্ট অপ্টিমাইজার কখনো সেফটি গেটকে বাইপাস বা দুর্বল করতে পারবে না:

```text
                        User / Autonomous Intent
                                   │
                                   ▼
                      Scope & Risk Classification
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
            Cost & Capability             Safety & Rule
             Planner (Ladder)                 Gate
                     │                           │
                     └─────────────┬─────────────┘
                                   ▼
                       Unified Execution Plan
                                   │
                                   ▼
                        Cross-Agent Challenge
                     (Security vs Cost vs Scope)
                                   │
                                   ▼
                        Execution & Verification
                      (Browser / MCP / CI / Staging)
```

> **লৌহকঠিন নিয়ম:** কস্ট এজেন্ট কখনো বলতে পারবে না: *"সিকিউরিটি স্ক্যান বা ব্যাকআপ এক্সপেনসিভ, তাই বাদ দাও।"*—**Safety requirements cannot be optimized away.**

---

## ৪. The Cost Optimization Ladder (কস্ট মিনিমাইজেশন ল্যাডার)

কোনো টাস্ক এক্সিকিউশনের সময় কস্ট অপ্টিমাইজার ধাপে ধাপে সলিউশন খুঁজবে:

```text
1. Existing Cached Result / Duplicate Reasoning Reuse ($0)
             ↓
2. Local Computation / AST / Deterministic Logic ($0)
             ↓
3. Headless Browser (Authenticated Session / Dom Automation) ($0)
             ↓
4. Existing Internal Tool / Plugin / MCP Capability ($0)
             ↓
5. Zero-Cost / Free-Tier Provider (Gemini Free / Groq / Ollama Local) ($0)
             ↓
6. Low-Cost Commercial Tier (DeepSeek / Claude Haiku / GPT-4o-mini) ($)
             ↓
7. Frontier / High-End Paid Reasoning (GPT-4o / Claude 3.5 Sonnet / o1) ($$$)
```

### অতিরিক্ত অপ্টিমাইজেশন পাওয়ার:
* **Duplicate Work Detection:** এজেন্ট A ইতিমধ্যে ডেটা X ফেচ করেছে, এজেন্ট B আবার X ফেচ করতে গেলে ক্যাশড রেজাল্ট সরবরাহ করবে।
* **Duplicate Reasoning Reuse:** মডেল A একটি জটিল স্ট্রাকচার্ড অ্যানালাইসিস বের করেছে, মডেল B-কে তা রি-রান করতে না দিয়ে এভিডেন্স রিইউজ করবে।
* **Batch Optimization:** ১০টি আলাদা নেটওয়ার্ক কলের বদলে ১টি ব্যাচ রিকোয়েস্ট।

---

## ৫. The Multi-Project Continuous Security Agent

### ১. আইসোলেশন ও স্কোপ বাউন্ডারি:
```text
SupremeAI Core System
   │
   ├── Platform Security Agent (Protects SupremeAI Infrastructure)
   │
   ├── Tenant A (User Project A)
   │      └── Project-Scoped Security Agent (Isolated rules & attack surface)
   │
   └── Tenant B (User Project B)
          └── Project-Scoped Security Agent
```

### ২. ৪-ডাইমেনশনাল থ্রেট কভারেজ:
1. **External Attack Surface:** Exposed endpoints, insecure CORS, misconfigured admin dashboards, open buckets, leaked tokens.
2. **Code Vulnerabilities:** SQL injection, SSRF (রেডাইরেক্ট রি-ভ্যালিডেশনসহ), command injection, path traversal, unsafe deserialization.
3. **AI-Specific Attacks (The AI Frontier):**
   * Prompt Injection & Indirect Prompt Injection (দূষিত ওয়েব কন্টেন্ট থেকে কমান্ড ইনজেকশন)।
   * Tool / MCP Injection & Malicious Tool Escalation।
   * Data vs Instruction Confusion।
   * Agent Hijacking & Secret Exfiltration।
4. **Infrastructure Security:** Database direct access, Redis unauthenticated port, overly broad IAM permissions.

---

## ৬. The Multi-Agent Challenge Matrix (এজেন্টদের পারস্পরিক ভারসাম্য)

SupremeAI-এর সবচেয়ে ম্যাচিউর বৈশিষ্ট্য হলো এজেন্টরা একে অপরকে অন্ধভাবে মেনে নেবে না—তারা একে অপরকে চ্যালেঞ্জ করবে:

```text
[টাস্ক সিনারিও: "একটি ওয়েব পোর্টাল থেকে ইন্টারনাল রিপোর্ট সংগ্রহ করা"]

Cost Optimizer:
"Browser সেশন ব্যবহার করলে API খরচ = $0।"

Security Agent:
"চ্যালেঞ্জ: ব্রাউজার সেশনে ক্রিপ্টোগ্রাফিক সেশন টোকেন এক্সপোজ হওয়ার ঝুঁকি আছে কি না? 
কুকিজ বা লোকালস্টোরেজে ক্রিটিক্যাল ক্রেডেনশিয়াল থাকলে ব্রাউজার সেশন আইসোলেটেড স্যান্ডবক্সে রান করতে হবে।"

Safety / Rule Agent:
"ইউজারের রোল এবং টেন্যান্ট পারমিশন চেক করা হয়েছে: অ্যাক্সেস অনুমোদিত।"

Verification Agent:
"হেডলেস ব্রাউজার দিয়ে টেস্ট ফ্লো চালানো হয়েছে: ডেটা স্ক্রিন থেকে রিসিভ হয়েছে, কোনো সেশন লিক ঘটেনি।"

=====> চূড়ান্ত সিদ্ধান্ত: আইসোলেটেড ব্রাউজার স্যান্ডবক্স ব্যবহার করা হবে ($0 খরচ + ১০০% সিকিউরিটি)।
```

যদি সিকিউরিটি বলে **"রিস্ক আনএক্সেপ্টেবল"**, তবে কস্ট জিরো হলেও তা সরাসরি বাতিল হবে এবং নিরাপদ অল্টারনেটিভ গ্রহণ করা হবে।

---

## ৭. MCP (Model Context Protocol) — The Governed Distribution Fabric

MCP কোনো স্বঘোষিত অথোরিটি নয়—এটি হলো ব্রেইনের সেন্ট্রাল ডিস্ট্রিবিউশন ও রাউটিং চ্যানেল:
* **ডিসকভারি:** প্ল্যাটফর্মে কী কী ক্যাপাবিলিটি, প্লাগইন, এপিআই আছে তা সেন্ট্রাল রেজিস্ট্রি দিয়ে রিপ্রেজেন্ট করবে।
* **কনট্রোল:** কোনো ক্যাপাবিলিটি রান করার আগে পলিসি এবং পারমিশন গেট এনফোর্সড হবে।
* **নো সাইডচ্যানেল:** সরাসরি ইউআরএল বা আনরেজিস্টার্ড ব্যাকডোর তৈরি হতে দেওয়া হবে না।

---

> **সংরক্ষণ স্থিতি:** এই আর্কিটেকচারাল ডকুমেন্টটি SupremeAI-এর কোর অটোনোমাস ডিসিশন ইঞ্জিন ও মাল্টি-এজেন্ট ইন্টারঅ্যাকশনের ভিত্তি হিসেবে সংরক্ষিত হলো।
