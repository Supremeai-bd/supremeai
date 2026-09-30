# SupremeAI — AGENTS.md (Universal Operating Constitution & Agent Bootstrap)

> **Core Philosophy:** *যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।*  
> **The 99.99 / 0.01 Law:** Agent controls **HOW** (৯৯.৯৯% বাস্তবায়ন অটোনমি); Admin controls **WHERE, WHAT, ACCESS, LIMITS, STOPPING & MERGING** (০.০১% শাসন ও নাটাই)।

---

## ⚡ ৪-ধাপের বুটস্ট্র্যাপ ও অটোনোমাস লুপ (Bootstrap & Autonomous Loop)

সেশনে কাজ শুরুর সময় প্রতিটি এজেন্ট স্বয়ংক্রিয়ভাবে নিচের ক্রমে কাজ সম্পাদন করবে:

```text
[Step 1: Sync & Read] ──► [Step 2: MCP Heartbeat] ──► [Step 3: Script & Task Acquire] ──► [Step 4: Continuous Loop]
```

1. **Step 1: Sync & Read (সিঙ্ক ও সংবিধান পাঠ)**
   ```bash
   git fetch origin --prune && git status
   ```

2. **Step 2: Connect MCP Control Tower (ফ্লিট হার্টবিট ও অফলাইন ফলব্যাক)**
   - **১ম প্রায়োরিটি (1st Priority — Local `mcp.json` অটো-কনফিগ):**
     যেকোনো স্যান্ডবক্স বা ওয়ার্কস্পেস এজেন্ট কাজ শুরুর সময় প্রথমেই প্রজেক্টের রুটে বা তার নিজস্ব কনফিগ ডিরেক্টরিতে `mcp.json` ফাইলটির উপস্থিতি নিশ্চিত করবে। ফাইল না থাকলে এজেন্ট নিজেই স্বয়ংক্রিয়ভাবে তা তৈরি করে কন্ট্রোল টাওয়ারে যুক্ত হবে (কোনো ম্যানুয়াল সেটআপের প্রয়োজন নেই):
     ```json
     {
       "$schema": "https://json.schemastore.org/mcp",
       "mcpServers": {
         "supremeai-control-tower": {
           "type": "sse",
           "url": "https://supremeai-mcp-tower.onrender.com/sse",
           "transport": "sse"
         }
       }
     }
     ```
   - **২য় প্রায়োরিটি (2nd Priority — Direct URL ফলব্যাক):**
     ফাইল তৈরির ক্ষমতা না থাকলে সরাসরি **MCP Server URL** ব্যবহার করবে: `https://supremeai-mcp-tower.onrender.com/sse` (অথবা `/mcp`)।
   ```bash
   # সরাসরি হার্টবিট পাঠানো:
   python scripts/agents/mcp_tower_client.py heartbeat --slot <slot-id> --name <agent-id> --url https://supremeai-mcp-tower.onrender.com
   ```
   - **Graceful Offline Fallback (No SPOF):** রেন্ডার স্লিপিং বা টাওয়ার সাময়িক ডাউন থাকলে এজেন্ট আটকে থাকবে না — স্বয়ংক্রিয়ভাবে লোকাল অফলাইন মোডে কাজ শুরু করবে এবং ব্যাকগ্রাউন্ডে টাওয়ার ফিরলে রি-কানেক্ট করবে (জিরো ব্লকিং)।

3. **Step 3: Acquire Next Task (অটোনোমাস টাস্ক অ্যাকুইরি)**
   - এজেন্ট স্বয়ংক্রিয়ভাবে প্রায়োরিটি অনুযায়ী পরবর্তী কাজ তুলে নেবে:
     ```bash
     python scripts/agents/continuous_agent_loop.py --role <lane> --agent-name <agent-id>
     ```
   - **Auditor Fallback:** কিউতে কোনো open issue না থাকলে (if NO open issues) স্বয়ংক্রিয়ভাবে ফুল অডিট চালাবে এবং নতুন ইস্যু তৈরি করবে।
   - **Priority Auto-Escalation:** Loop চলার সময় automatically priorities check হবে — কোনো P0 না থাকলে P1→P0, P1 না থাকলে P2→P1 automatically promote হবে। এটা architecture-level automatically happens, agent-এর intervention লাগবে না।
   - **ফ্লিট ড্যাশবোর্ড পর্যবেক্ষণ:**
     ```bash
     python scripts/ci/task_dashboard.py
     ```

4. **Step 4: Continuous Autonomous Loop ও ডুয়াল ব্রাঞ্চিং পলিসি (Dual Branch Strategy)**
   - **গ্রুপ ইস্যু (`group:<name>`):** শেয়ার্ড গ্রুপ ব্রাঞ্চে (`group/<name>`) ক্রমানুসারে একাধিক এজেন্ট কাজ করবে। সম্পূর্ণ গ্রুপের কাজ শেষ হলে মাত্র ১টি সমন্বিত একক PR তৈরি হবে (`has-pr` লেবেল সহ)।
   - **স্বতন্ত্র/একক ইস্যু (Ungrouped):** নিজস্ব স্লট ব্রাঞ্চে (`agent-<slot>/<issue#>-<slug>`) কাজ হবে এবং সমাধান শেষে তাৎক্ষণিক একক PR খোলা হবে।
   - **Anti-Monopoly 2-Min Cooldown:** গ্রুপ সিকোয়েন্সে একাধিক এজেন্ট সক্রিয় থাকলে পরবর্তী ইস্যুতে ২ মিনিটের হ্যান্ডঅফ উইন্ডো প্রযোজ্য হবে যাতে অন্য এজেন্টরা সুযোগ পায়; আর একক এজেন্ট থাকলে কোনো বিলম্ব ছাড়াই সে কাজ চালিয়ে যাবে।
   - **Knowledge Sharing:** প্রতিটি টাস্ক বা অডিট শেষে এজেন্ট এই সিদ্ধান্ত কেন নিয়েছে (`why`) এবং অন্য সিদ্ধান্ত কেন নেয়নি (`alternatives_rejected`) — এই ২টি জ্ঞান ফিক্সড স্কিমায় (`{"task": "...", "agent": "...", "why": "...", "alternatives_rejected": [...]}`) সরাসরি কন্ট্রোল টাওয়ার মেমোরি/ডাটাবেসে (`POST /knowledge` বা `memory_record_task` টুল দিয়ে) পুশ করবে (জিরো গিট কনফ্লিক্ট)।

---

## 🏆 একক সংবিধান: ৬টি মৌলিক সার্বজনীন নিয়মাবলী (The 6 Universal Invariants)

| # | নিয়ম | মূল অর্থ ও এক-লাইনের সারমর্ম |
| :--- | :--- | :--- |
| **১** | **MISSION & CORE PHILOSOPHY** | ৯৯.৯৯% বাস্তবায়ন স্বাধীনতা, ০.০১% নাটাই অ্যাডমিনের হাতে; লক্ষ্য সিস্টেমকে দিনদিন উন্নত করা। |
| **২** | **FREE-TIER CONSTRAINT** | Render 512MB RAM সীমার মধ্যে কাজ; একক uvicorn worker ও মেমোরি ব্লোট প্রতিরোধ। |
| **৩** | **GRACEFUL DEGRADATION** | কোনো সার্ভিস বা ডাটাবেস ডাউন হলে সিস্টেম ক্র্যাশ করবে না; ফলব্যাক চেইন সচল থাকবে। |
| **৪** | **COSTGUARD & BUDGET** | কস্ট লিমিট পার হলে কাজ স্বয়ংক্রিয়ভাবে বন্ধ হবে (Fail-closed); মিথ্যা স্ট্যাটাস দেওয়া নিষিদ্ধ। |
| **৫** | **FLEET OBSERVABILITY** | প্রতিটি কাজের সিদ্ধান্ত ও লগের দৃশ্যমান প্রমাণ রাখা (`task_dashboard.py` পর্যবেক্ষণ)। |
| **৬** | **MANDATORY BANGLA/BANGLISH** | কোড কমেন্টসে `# বাংলা মন্তব্য:` এবং সমস্ত যোগাযোগ বাংলায় হওয়া বাধ্যতামূলক। |

---

### ১. মূল দর্শন ও এক্সিকিউশন অর্ডার (Core Philosophy & Execution Order)
প্রজেক্টের মূল দর্শন (৯৯.৯৯% বাস্তবায়ন অটোনমি / ০.০১% অ্যাডমিন নাটাই) কোনো অবস্থাতেই লঙ্ঘন করা যাবে না; সিস্টেমে কোথাও নীতি লঙ্ঘন বা আর্কিটেকচারাল ব্রেক চোখে পড়লে সাথে সাথে প্রায়োরিটি দিয়ে ফিক্স করতে হবে।

*বাধ্যতামূলক এক্সিকিউশন সিকোয়েন্স:*
```text
Discover → Resolve tenant/actor → Authorize/policy → Execute → Verify → Audit → Learn
```

### ২. জিরো-কস্ট ও ক্লাউড ফ্রি-টিয়ার সীমা (Free-Tier First-Class Constraint)
- Render ফ্রি টিয়ারের সীমাবদ্ধতা (~512MB RAM) কঠোরভাবে মানতে হবে; প্রোডাকশনে একক uvicorn worker এবং `LOW_MEMORY_MODE` বহাল থাকবে।
- মেমোরি ব্লোট বা অপ্রয়োজনীয় ভারী ডিপেন্ডেন্সি যুক্ত করা নিষিদ্ধ (`check_free_tier_limits.py` গেট দ্বারা যাচাইকৃত)।

### ৩. গ্রেসফুল ডিগ্রেডেশন ও রেজিলিয়েন্স (Graceful Degradation)
- কোনো একটি LLM প্রোভাইডার বা ডাটাবেস সাময়িক স্লিপ বা ডাউন হলে সিস্টেম ক্র্যাশ করবে না — ফলব্যাক চেইন ও সার্কিট ব্রেকার সচল থাকবে (কিউ প্রায়োরিটি: `asyncio ➔ redis ➔ celery`)।
- কোনো সার্ভিস ডাউন থাকলে ফেক হেলথ দেখানো নিষিদ্ধ (Honesty over polish) — সত্য স্ট্যাটাস প্রকাশ করতে হবে।

### ৪. কস্ট গার্ড ও বাজেট গার্ডিয়ান (CostGuard & Budget Limits)
- প্রতি টাস্কে বাজেট সুরক্ষায় `CostGuard` ও `auto_budget_guardian.py` সক্রিয় থাকবে; অনুমোদিত লিমিট পার হলে কাজ স্বয়ংক্রিয়ভাবে বন্ধ হবে (Fail-closed)।
- আনলিমিটেড বা অনিয়ন্ত্রিত এক্সটার্নাল এপিআই কল কঠোরভাবে নিষিদ্ধ।

### ৫. ফ্লিট অবজারভেবিলিটি ও ড্যাশবোর্ড (Fleet Observability)
- প্রতিটি এজেন্টের কাজের অগ্রগতি, স্লট লিজ ও সিদ্ধান্ত দৃশ্যমান থাকতে হবে।
- `python scripts/ci/task_dashboard.py` চালিয়ে ফ্লিটের লাইভ অবস্থা মনিটর করা যাবে।
- প্রতিটি ব্যর্থতা, পরিবর্তন ও অনুমোদনের মেশিন-ভেরিফায়েড এভিডেন্স বজায় রাখতে হবে।
- প্রতিটি টাস্ক বা অডিটে এই সিদ্ধান্ত কেন নিয়েছে (`why`) এবং অন্য সিদ্ধান্ত কেন নেয়নি (`alternatives_rejected`) — এই ২টি জ্ঞান ফিক্সড স্কিমায় সরাসরি কন্ট্রোল টাওয়ার মেমোরি/ডাটাবেসে পুশ করা বাধ্যতামূলক:
  ```json
  {"task": "<task-id>", "agent": "<agent-name>", "why": "<সিদ্ধান্তের কারণ>", "alternatives_rejected": ["<বিকল্প ও বাতিলের কারণ>"]}
  ```

### ৬. বাধ্যতামূলক বাংলা/বাংলিশ কোড কমেন্টস ও যোগাযোগ (Bengali/Banglish Invariant)
আমাদের পুরো টেক টিম বাংলাদেশি। তাই:
- কোডের ভেতরের সমস্ত গুরুত্বপূর্ণ লজিক ও সিদ্ধান্তের ব্যাখ্যায় `# বাংলা মন্তব্য:` বাধ্যতামূলক।
- অ্যাডমিনের সাথে কথোপকথন, পিআর ডেসক্রিপশন ও ইস্যু সামারি বাংলায় বা প্রাঞ্জল বাংলিশে হতে হবে।

---

_অ্যাডমিন চাইলে যেকোনো সময় `god.py` বা MCP Control Tower-এর মাধ্যমে পলিসি পরিবর্তন বা ইমার্জেন্সি স্টপ (নাটাই) প্রয়োগ করতে পারবেন।_
