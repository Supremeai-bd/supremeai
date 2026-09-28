# Confusing Names & Duplicate Modules Inventory
*(একই কাজ ২ রকম নাম · ২ রকম কাজ একই নাম — সম্পূর্ণ অডিট ও কনসোলিডেশন পরিকল্পনা)*

> **স্ট্যাটাস:** সক্রিয় ড্রাফট (Step-3 Consolidation Roadmap)  
> **উদ্দেশ্য:** কোডবেসের সমস্ত ডুপ্লিকেট, বিভ্রান্তিকর নাম, এবং একই ফিচারের একাধিক কপি একত্রিত (consolidate) করে সিঙ্গেল সোর্স অব ট্রুথ প্রতিষ্ঠা করা।

---

## 🔍 ১. ক্যাটাগরি ১: ২ রকম কাজ, কিন্তু হুবহু একই নাম (Same Name, Conflicting/Confusing Purpose)

এই ফাইলগুলোর নাম একই হওয়ায় ইম্পোর্ট করার সময় বা রেফারেন্স দেওয়ার সময় বিভ্রান্তি তৈরি হয়:

| ফাইলের নাম | বর্তমান একাধিক পাথ (Occurrences) | সমস্যা ও বিভ্রান্তি | প্রস্তাবিত সমাধান (Resolution) |
| :--- | :--- | :--- | :--- |
| **`app.py`** | 1. `backend/app.py`<br/>2. `backend/core/app.py` | রুটে একটি FastAPI অ্যাপ আছে, আবার `core/` ডিরেক্টরিও আরেকটি অ্যাপ ইনিশিয়ালাইজ করে। | `backend/main.py` ও `backend/app.py`-কে সিঙ্গেল এন্ট্রি পয়েন্ট বানিয়ে `backend/core/app.py` ছাঁটাই করা। |
| **`autonomous_agent.py`** | 1. `backend/agents/autonomous_agent.py`<br/>2. `backend/brain/autonomous_agent.py` | দুটি ভিন্ন লেয়ারে দুটি অটোনোমাস এজেন্ট ক্লাস রয়েছে যা একই ফাংশনালিটি ডুপ্লিকেট করে। | `backend/brain/` লেয়ারকে ক্যানোনিকাল রেখে `backend/agents/autonomous_agent.py` রিটায়ার করা। |
| **`sentinel_agent.py`** | 1. `backend/agents/sentinel_agent.py`<br/>2. `backend/core/sentinel_agent.py` | সেন্টিনেল হেলথ এজেন্টের দুটি আলাদা ইমপ্লিমেন্টেশন। | `backend/core/sentinel_agent.py`-কে সেন্ট্রাল রেখে অপরটি ডিলিট করা। |
| **`agent_registry.py`** | 1. `backend/core/agent_registry.py`<br/>2. `backend/core/agents/framework/agent_registry.py`<br/>3. `backend/api/routes/agent_registry.py` | একই প্যাকেজের সাব-ফোল্ডারে ৩টি আলাদা এজেন্ট রেজিস্ট্রি ফাইল! | ফ্রেমওয়ার্ক রেজিস্ট্রিকে কোরের সাথে মার্জ করে একটি সিঙ্গেল ক্যানোনিকাল রেজিস্ট্রি রাখা। |
| **`engine.py`** | 1. `backend/context/engine.py`<br/>2. `backend/context_engine/engine.py`<br/>3. `backend/services/hitl/engine.py` | `context` এবং `context_engine` দুটি প্রায় একই নামের ফোল্ডারে দুটি `engine.py`! | `context_engine` ফোল্ডারটিকে `backend/context/`-এ কনসোলিডেট করা। |
| **`Header.tsx`** | 1. `frontend/src/components/Header.tsx`<br/>2. `frontend/src/components/core/Header.tsx`<br/>3. `frontend/src/components/dashboard/Header.tsx` | ফ্রন্টএন্ডে ৩টি আলাদা হেডার কম্পোনেন্ট ছড়িয়ে আছে। | `components/core/Header.tsx`-কে একমাত্র রি-ইউজেবল হেডার বানিয়ে বাকিগুলো একত্রিত করা। |

---

## 🤹 ২. ক্যাটাগরি ২: একই কাজ, কিন্তু ২ রকম নাম (Same Functionality, Synonymous/Duplicate Names)

একই কাজ বা উদ্দেশ্য সম্পন্ন করার জন্য বিভিন্ন জায়গায় আলাদা নামে কোড ডুপ্লিকেট করা হয়েছে:

| ফাংশনালিটি / উদ্দেশ্য | কোডবেসে বিদ্যমান ডুপ্লিকেট ফাইলসমূহ | সমস্যা | সমাধান |
| :--- | :--- | :--- | :--- |
| **Browser & Web Scraper** | • `backend/services/scraper/web_scraper.py`<br/>• `backend/tools/browser/web_scraper.py`<br/>• `skills/dynamic/web_scraper.py` | একই স্ক্র্যাপিং লজিক ৩টি ভিন্ন ডিরেক্টরিতে ৩টি ফাইলে কপি-পেস্ট করা। | `backend/services/scraper/` কে ক্যানোনিকাল স্ক্র্যাপার সার্ভিস হিসেবে রেখে বাকিগুলো র‍্যাপার করা বা মোছা। |
| **Analytics Agent (Churn)** | • `backend/agents/churn_prophet.py`<br/>• `backend/tools/analytics/churn_prophet.py` | চার্ন প্রেডিকশনের একই কোড এজেন্ট এবং টুলস দুটোতেই আলাদা নামে রাখা। | `tools/analytics/` ডিরেক্টরিকে ক্যানোনিকাল রাখা। |
| **Analytics Agent (Insight)** | • `backend/agents/insight_mage.py`<br/>• `backend/tools/analytics/insight_mage.py` | ইনসাইট জেনারেশনের একই কোড ডুপ্লিকেট। | একটি ক্যানোনিকাল মডিউলে কনসোলিডেট করা। |
| **Task Contracts** | • `backend/core/task_contract.py`<br/>• `backend/core/queue/task_contract.py`<br/>• `backend/external_agents/contracts/task_contract.py` | ৩ জায়গায় টাস্ক কন্ট্রাক্ট আলাদা করে ডিফাইন করা। | `backend/core/task_contract.py`-কে সিঙ্গেল সোর্স অব ট্রুথ বানানো। |
| **Telemetry & Observability** | • `backend/core/llm/telemetry.py`<br/>• `backend/core/observability/telemetry.py`<br/>• `backend/scout/telemetry.py` | ৩ জায়গায় আলাদা আলাদা টেলিমেট্রি লগিং। | `core/observability/telemetry.py`-এর আওতায় নিয়ে আসা। |

---

## 📦 ৩. ক্যাটাগরি ৩: ১৬টি ডেমো / স্যাম্পল ফাইল (১৬ Demo/Sample Inventory Recap)

পূর্বের অডিটে চিহ্নিত ১৬টি ফাইলের একশন প্ল্যান:
1. **মুছে ফেলার জন্য ৬টি ডেমো ফাইল:**
   - `backend/core/messaging/demo_messaging.py`
   - `backend/core/intelligence/demo_intelligence.py`
   - `scripts/demo_agent_communication.py`
   - `backend/tests/fixtures/sample_payloads.py` (মক ফিক্সচারে ডুপ্লিকেট)
   - `backend/examples/sample_client.py`
   - `backend/examples/simple_workflow.py`
2. **কনসোলিডেট করার জন্য ৪টি মক ফাইল:**
   - টেস্ট স্যুটে ছড়িয়ে থাকা ৪টি ডুপ্লিকেট স্যাম্পল ফিক্সচারকে `backend/tests/fixtures/` এর সেন্ট্রাল ফিক্সচারে নিয়ে আসা।
3. **রাখার জন্য ৬টি টেমপ্লেট:**
   - `.env.example`, `.env.test.example`, ইত্যাদি কনফিগ গাইড হিসেবে অক্ষত থাকবে।

---

## 🎯 ৪. Step-3 কনসোলিডেশন একশন প্ল্যান (Step-3 Execution Strategy)

এই অডিট রিপোর্ট অনুযায়ী Step-3 (কনসোলিডেশন ফেজ)-এ ক্রমানুসারে কাজ হবে:
1. **Step-3.1:** ক্যাটাগরি ১-এর ফাইল রিনেম ও কনসোলিডেশন (`app.py`, `autonomous_agent.py`, `sentinel_agent.py`)।
2. **Step-3.2:** ক্যাটাগরি ২-এর স্ক্র্যাপার ও এনালিটিক্স ডুপ্লিকেট মার্জ (`web_scraper.py`, `churn_prophet.py`)।
3. **Step-3.3:** ১৬টি ডেমো/স্যাম্পল ফাইলের ডেড পাইথন কোড ছাঁটাই ও ফিক্সচার একীভূতকরণ।
4. **Step-3.4:** ফ্রন্টএন্ডের ৩টি `Header.tsx` এবং ডুপ্লিকেট কম্পোনেন্ট কনসোলিডেশন।
5. **Step-3.5:** ফাইনাল অডিট — কোনো ব্রোকেন ইম্পোর্ট নেই এবং টেস্ট ১০০% সবুজ।
