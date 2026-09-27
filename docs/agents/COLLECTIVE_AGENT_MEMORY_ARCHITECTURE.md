# SupremeAI — Collective Agent Memory & Problem-Solving Layer Architecture

> **Axiom:**  
> **“কোনো agent সমস্যায় পড়লে আগে দেখবে—SupremeAI এই সমস্যাটা আগে দেখেছে কি না। না দেখে নতুন করে একই যুদ্ধ শুরু করবে না। আর solution না থাকলে শুধু problem solve করার চেষ্টা করবে না; future agents-এর জন্য একটা usable পথও তৈরি করবে।”**
>
> **Core Principle:**  
> **Search Before Solving · Pave Before Leaving · Gap Before Guessing**  
> No agent solves in isolation. Collective intelligence transforms individual mistakes into permanent system strengths.

---

## 1. Executive Summary: The Collective Problem-Solving Layer

SupremeAI MCP Tower কেবল একটি Agent Control Tower নয়; এটি এজেন্টদের **“Collective Memory + Collective Problem-Solving Layer”**।

```text
                    SUPREMEAI MCP TOWER
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   AGENT CONTROL       COLLECTIVE         CAPABILITY
   / GOVERNANCE          MEMORY             DISCOVERY
        │                  │                  │
        │          ┌───────┼────────┐         │
        │          │       │        │         │
        │       Problems Solutions Attempts  Gaps
        │          │       │        │         │
        └──────────┴───────┼────────┴─────────┘
                           │
                     AGENT MCP API
                           │
                    EVERY AGENT
```

---

## 2. The Universal Connection Contract (Adapter-Neutral)

**“সব agent-কে একই literal `mcp.json` file ব্যবহার করতেই হবে”**—এটি কোনো রিজিড বাধ্যবাধকতা নয়। এজেন্ট Cursor-এ থাকতে পারে, Codespaces-এ থাকতে পারে, Gitpod-এ থাকতে পারে, বা নিজস্ব লোকাল স্যান্ডবক্সে থাকতে পারে।

> **Contract Rule:**  
> **Every agent MUST have a valid MCP Tower connection contract.**

```text
mcp.json / .env / CLI bootstrap / SDK bootstrap / Platform adapter
                      ↓
           Agent → MCP Tower (Mandatory)
```
- **Local IDE:** Workspace রুট ফোল্ডারে `mcp.json` দিয়ে `supremeai-control-tower` রান হয়।
- **Remote / Worker:** `MCP_TOWER_URL` এনভায়রনমেন্ট ভেরিয়েবল বা SDK কল দিয়ে কানেক্ট ও ৪৫-সেকেন্ড হার্টবিট চালু রাখে।

---

## 3. Experience Record: শুধু Answer নয়, সম্পূর্ণ অভিজ্ঞতা

SupremeAI শুধু `problem → answer` সংরক্ষণ করে না। এখানে সংরক্ষিত হয় একটি পূর্ণাঙ্গ **Experience Record**:

```text
Problem
 ↓
Context (repo, module, runtime, dependencies)
 ↓
Attempts (what was tried)
 ↓
Failures (what failed and why)
 ↓
Successful Solution (exact approach, diff, command)
 ↓
Evidence (test outputs, benchmark deltas)
 ↓
Verification (status & confidence score)
 ↓
Reusable Conditions (when to apply, prerequisites)
 ↓
Limitations (where not to apply)
 ↓
Future Path (next steps or follow-ups)
```

---

## 4. The Canonical Memory Model

ডাটাবেসে (Supabase pgvector / Qdrant / SQLite fallback) ৩টি মূল সত্ত্বা ট্র্যাক হয়:

1. **ProblemCase:**
   - Fingerprint (error signature, exception class, call-stack hash)
   - Context (language, framework, platform, dependency versions)
   - Symptoms (terminal output, failing test name)
2. **SolutionPattern:**
   - Approach & Code changes
   - Prerequisites & Environment requirements
   - Verification status:
     - `UNVERIFIED`: সদ্য প্রস্তাবিত
     - `EXPERIMENTAL`: প্রাথমিক পরীক্ষায় উত্তীর্ণ
     - `VERIFIED`: টেস্ট ও গেট দ্বারা প্রমাণিত
     - `RECOMMENDED`: প্রোডাকশন-গ্রেড সেরা সমাধান
     - `DEPRECATED`: কোডবেসের পরিবর্তনে অপ্রচলিত
     - `FAILED`: পূর্বে চেষ্টা করে ব্যর্থ হওয়া পথ
   - Compatibility Matrix:
     - `COMPATIBLE` (একই রিপো, একই মডিউল, একই ভার্সন)
     - `PARTIALLY_COMPATIBLE` (এডাপ্টেশন প্রয়োজন)
     - `NOT_COMPATIBLE` (প্রযোজ্য নয়)
3. **AttemptRecord:**
   - কোন এজেন্ট কোন অ্যাপ্রোচ ট্রাই করেছিল
   - কেন ব্যর্থ হয়েছিল এবং তার এভিডেন্স

---

## 5. দুইভাবে রাস্তা তৈরি (The Two Pathways)

```text
                     PROBLEM DISCOVERED
                             │
                             ▼
                 [ Search Collective Memory ]
                             │
              ┌──────────────┴──────────────┐
              │                             │
          [ FOUND ]                    [ NOT FOUND ]
              │                             │
              ▼                             ▼
       Path A: Reuse                 Path B: Solution Gap
              │                             │
   ┌──────────────────────┐      ┌──────────────────────┐
   │ Check Compatibility  │      │ Record Gap & Context │
   │ Adapt Proven Recipe  │      │ Try Candidates       │
   │ Verify Locally       │      │ Note Missing Cap.    │
   └──────────┬───────────┘      └──────────┬───────────┘
              │                             │
              │                             ▼
              │                  ┌──────────────────────┐
              │                  │ Solved?              │
              │                  │ YES: Verified Sol.   │
              │                  │ NO: Future Path / GAP│
              │                  └──────────┬───────────┘
              └──────────────┬──────────────┘
                             ▼
                     [ SAFE DELIVERY ]
```

### Path A — Existing Solution (পুনর্ব্যবহার)
- পরিচিত সমস্যা হলে পূর্ববর্তী প্রমাণিত সমাধানটি অ্যাডাপ্ট করে ভেরিফাই করা হয়। ফলে ১০ জন এজেন্টকে একই সমস্যার জন্য ১০ বার শূন্য থেকে কাজ করতে হয় না।

### Path B — No Solution Yet (Solution Gap & New Pathway)
- যদি মেমোরিতে কোনো সমাধান না থাকে, সিস্টেম একটি **Solution Gap** তৈরি করে।
- এজেন্ট সমাধান করতে গিয়ে যা যা চেষ্টা করেছে এবং ব্যর্থ হয়েছে (`what_failed`), কোন ক্যাপাসিটি মিসিং ছিল, এবং সম্ভাব্য ভবিষ্যৎ পথ কী—সব রেকর্ড করে।
- **ফলশ্রুতি:** পরবর্তী এজেন্ট এসে যখন সার্চ করবে, সে আর ব্ল্যাঙ্ক পেজ থেকে শুরু করবে না; সে দেখতে পাবে পূর্বে কোন কোন ভুল পথ পরিহার করা হয়েছে এবং কোন পথে এগোনো উচিত!

---

## 6. Memory Scopes Isolation (সিকিউরিটি ও প্রাইভেসি সীমানা)

কালেক্টিভ মেমোরিতে ৪টি সম্পূর্ণ স্বাধীন স্কোপ বজায় রাখা হয়:

| স্কোপ | কার ডেটা | শেয়ারিং নিয়ম |
| :--- | :--- | :--- |
| **USER MEMORY** | ইউজারের ব্যক্তিগত চ্যাট, পছন্দ ও ডেটা | সম্পূর্ণ প্রাইভেট; কোনো এজেন্টের ইঞ্জিনিয়ারিং মেমোরিতে যাবে না |
| **TENANT MEMORY** | অর্গানাইজেশন-নির্দিষ্ট কনফিগ ও স্টেট | কঠোরভাবে টেন্যান্ট-আইসোলেটেড |
| **PROJECT / SYSTEM MEMORY** | রিপোজিটরির আর্কিটেকচার, পলিসি ও কোডবেস স্টেট | প্রজেক্ট সদস্যদের জন্য উন্মুক্ত |
| **AGENT EXPERIENCE MEMORY** | প্রযুক্তিগত সমাধান, বাগ ফিক্স, এরর সিগনেচার, গ্যাপস | সমস্ত এজেন্টের জন্য উন্মুক্ত কালেক্টিভ বুদ্ধিমত্তা |

---

## 7. Universal Agent Rules: "Before Solve" & "After Solve"

### 🔍 Rule: Before Solve (সমাধানের পূর্বে)
> **Before solving a non-trivial problem, search the MCP Tower for relevant prior experience, known solutions, failed attempts, and available capabilities. Do not repeat known failed approaches without a reason.**

### 📝 Rule: After Solve (সমাধানের পর)
> **After solving a sound, non-trivial, or failure-derived issue, record the Experience Record (Problem, Solution, Evidence, Verification, Lessons) to pave the pathway for future agents.**
> *(অপ্রয়োজনীয় তুচ্ছ কাজ মেমোরিতে জমিয়ে নয়েজ তৈরি করা নিষিদ্ধ।)*

---

## 8. SupremeAI-এর নতুন Collective Intelligence Loop

```text
Problem বুঝো
  ↓
Previous Experience খোঁজো (MCP Tower / Database)
  ↓
Capability খোঁজো
  ↓
Run চালাও
  ↓
Verify করো (Trust Level নিরূপণ)
  ↓
Memory-তে রাখো (Experience Record)
  ↓
Gap থাকলে নতুন পথ তৈরি করো (Future Path)
  ↓
Approval & Merge ↺
```

---

## 9. CLI ও MCP ইন্টারফেস

এজেন্টরা টার্মিনাল বা MCP টুলের মাধ্যমে সরাসরি যোগাযোগ করবে:
- **Search:** `python scripts/agents/agent_solution_memory.py search --query "<symptom>"`
- **Record:** `python scripts/agents/agent_solution_memory.py record --task-id "<id>" --problem "..." --solution "..." --lesson "..." --status "VERIFIED"`
- **Create Gap:** `python scripts/agents/agent_solution_memory.py gap --task-id "<id>" --problem "..." --failed-attempts "..." --missing-capability "..." --future-path "..."`
