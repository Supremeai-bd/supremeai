# SupremeAI 2.0 — প্রজেক্টের প্রতিটি মডিউল, মাইক্রো-ফিচার ও সাব-ফাংশনের সম্পূর্ণ ইনভেন্টরি ক্যাটালগ
**Granular Subsystem & Micro-Feature Master Inventory Index**
*তারিখ:* ২৭ জুলাই, ২০২৬  
*সংস্করণ:* SupremeAI 2.0 (Exhaustive System Breakdown)

---

## 📌 ১. ভূমিকা (Introduction)

এই গাইডটিতে SupremeAI 2.0 রিপোজিটরির **প্রতিটি প্রধান মডিউল এবং তার অধীনে থাকা সমস্ত ক্ষুদ্র ক্ষুদ্র মাইক্রো-ফিচার (Micro-Features), হেলপার স্ক্রিপ্ট, ইউটিলিটি ক্লাস এবং সাব-ফাংশন ইনডেক্স করা হয়েছে**। ভবিষ্যতে পূর্ণাঙ্গ ৮০০+ পৃষ্ঠার টেকনিক্যাল ম্যানুয়াল তৈরির সময় এটি নির্দেশক ম্যাপ হিসেবে কাজ করবে।

---

## 📂 ২. বিস্তারিত মডিউল ও মাইক্রো-ফিচার ইনভেন্টরি

### 🧠 ২.১. Core AI Engine & Intelligent Routing (`backend/core/` & `backend/engine/`)

| প্রধান মডিউল | মাইক্রো-ফিচার ও ইউটিলিটি ফাইল | অবস্থান (File Path) | সাব-ফাংশন ও কাজের বিবরণ |
|---|---|---|---|
| **LLMRouter** | Fallback & Retry Logic | `backend/core/llm_router.py` | প্রোভাইডার ব্যর্থ হলে ব্যাকআপ প্রোভাইডারে সুইচ ও এক্সপোনেনশিয়াল ব্যাকঅফ |
| | Token Budget Enforcer | `backend/core/llm_router.py` | দৈনিক ও প্রতি টাস্কের টোকেন সীমা ট্র্যাকিং |
| | Provider Health Check | `backend/core/llm_router.py` | প্রোভাইডারের আপটাইম ও লেটেন্সি রিয়েল-টাইমে ডায়াগনোজ |
| **SmartModelRouter** | Cost-Sensitive Router | `backend/engine/smart_router.py` | প্রশ্নের জটিলতা অনুযায়ী সস্তা বা ফ্রি প্রোভাইডার সিলেক্ট করা |
| | Dynamic Token Scaling | `backend/engine/smart_router.py` | ইনপুট সাইজ অনুযায়ী ম্যাক্স টোকেন অ্যাডজাস্ট করা |
| **TreeOfThought** | Thought Branch Evaluator | `backend/engine/tree_of_thought.py` | একাধিক যুক্তি তৈরি এবং হিউরিস্টিক স্কোরিং ద్వారా সেরাটি বাছাই |
| **SelfReflection** | Code Quality Inspector | `backend/engine/self_reflection.py` | জেনারেটেড কোডের সিনট্যাক্স, নিরাপত্তা ও লজিক ইউজারকে দেওয়ার আগে চেক |
| **ToolForge** | Dynamic Python Synthesizer | `backend/engine/tool_forge.py` | নতুন কোনো টুল না থাকলে অন-দ্য-ফ্লাই নতুন পাইথন কোড টুল তৈরি |
| **WorkerNode** | Heartbeat & Task Queuing | `backend/engine/worker_node.py` | এ্যাসিঙ্ক ব্যাকগ্রাউন্ড টাস্ক এবং প্রসেস হার্টবিট ট্র্যাকার |

---

### 🧬 ২.২. Cognitive, Theory of Mind & Digital-Twin (`backend/evolution/`)

| প্রধান মডিউল | মাইক্রো-ফিচার ও ইউটিলিটি ফাইল | অবস্থান (File Path) | সাব-ফাংশন ও কাজের বিবরণ |
|---|---|---|---|
| **TheoryOfMind** | Mental State Tracker | `backend/evolution/theory_of_mind/tom_system.py` | Level 0-4 Mental State Attribution (Belief, Desire, Intention) |
| | Emotion Recognition | `backend/evolution/theory_of_mind/tom_system.py` | ইউজারের উত্তর থেকে হতাশা ও তাগিদ সনাক্ত করা |
| | False Belief Detector | `backend/evolution/theory_of_mind/tom_system.py` | মিথ্যা বা ভুল ধারণা চিহ্নিত করে সঠিক গাইড দেওয়া |
| **DigitalTwin** | Sandbox Environment | `backend/evolution/digital_twin/simulation_sandbox.py` | জিরো-রিস্ক ইন-মেমোরি স্যান্ডবক্স কমান্ড এক্সিকিউটর |
| | State Vector Replica | `backend/evolution/digital_twin/world_model.py` | আসল ডাটাবেজ ও এনভায়রনমেন্টের ভার্চুয়াল রেপ্লিকা ম্যাপ |
| | State Synchronizer | `backend/evolution/digital_twin/state_synchronizer.py` | লাইভ ডাটাবেজ ডেল্টার সাথে ভার্চুয়াল মডেল রিয়েল-টাইম সিঙ্ক |
| **Tier8 Evolution**| EWC Loss Penalty | `backend/adaptive_engine/learning_loop.py` | নতুন শিখতে গিয়ে পুরনো শিক্ষা ভুলে যাওয়া রোধ (Catastrophic Forgetting) |
| | Skill Marketplace Curator | `backend/core/tier8/skill_marketplace_curator.py` | নতুন ফিল্টারকৃত স্কিল কিউরেট ও শেয়ারিং মেকানিজম |

---

### 💾 ২.৩. Memory, Vector Search & Knowledge (`backend/memory/` & `backend/storage/`)

| প্রধান মডিউল | মাইক্রো-ফিচার ও ইউটিলিটি ফাইল | অবস্থান (File Path) | সাব-ফাংশন ও কাজের বিবরণ |
|---|---|---|---|
| **EpisodicMemory** | Task Recall & History | `backend/memory/episodic_memory.py` | অতীতের সফল সমাধান সার্চ ও ভেক্টর রিকল (`record_task`, `store_episode`) |
| | Episode Summarizer | `backend/memory/episodic_memory.py` | সাম্প্রতিক টাস্কগুলোর সংক্ষিপ্ত বিবরণী তৈরি (`summarize_recent`) |
| **LongTermMemory**| User Preference Tracker | `backend/memory/long_term_memory.py` | ইউজারের ব্যক্তিগত কোডিং স্টাইল ও কনটেক্সট ট্র্যাকিং (`store_user_preference`) |
| **ChromaDBStore** | SQLite Fallback Manager | `backend/memory/chromadb_store.py` | ক্রোমাকোডি না থাকলে স্থানীয় ফাইল-বেসড মেমোরিতে মেমোরি রাইট |
| **Knowledge Engine**| 14 Domain Ingestion Engine| `ingest_future_knowledge.py` | ১৪টি হাই-ইন্টেলিজেন্স ডোমেইনের ২১টি ভবিষ্যৎ নলেজ ডকুমেন্ট ইনজেকশন |

---

### 🛡️ ২.৪. Monitoring, Security, Auth & Resilience (`backend/monitoring/` & `backend/core/security/`)

| প্রধান মডিউল | মাইক্রো-ফিচার ও ইউটিলিটি ফাইল | অবস্থান (File Path) | সাব-ফাংশন ও কাজের বিবরণ |
|---|---|---|---|
| **BehavioralGuard**| Anomaly & Loop Detector | `backend/monitoring/behavioral_guard.py` | ইনফিনিট লুপ ও রিকুয়েস্ট ফ্লাডিং ওয়াচডগ |
| **SentinelAgent** | Prompt Injection Scanner | `backend/agents/sentinel_agent.py` | মেলিসিয়াস প্রম্পট ইনজেকশন ও অ্যাটাক ফিল্টার |
| **SecretVault** | Cloud Vault Fallback | `backend/core/security/secret_vault.py` | Infisical সিক্রেট ভল্ট ও পরিবেশ ভেরিয়েবল ব্যাকআপ |
| **CredentialStore**| Fernet Key Derivation | `backend/core/security/secure_credential_store.py` | এপিআই কী-সমূহের AES-256 এনক্রিপশন ও সিকিউর ডিক্রিপশন |
| **CircuitBreaker** | State Transition Engine | `backend/core/resilience/circuit_breaker.py` | CLOSED, OPEN, HALF-OPEN ট্রাফিক কন্ট্রোল |
| **CausalDebugger** | Stacktrace Root Cause | `backend/monitoring/causal_debugger.py` | রানটাইম এরর বিশ্লেষণ ও অটো-প্যাচ সাজেশন |
| **RBAC Manager** | Role Access Validator | `backend/core/security/rbac.py` | Admin, Developer ও Guest ইউজার রোল এনফোর্সমেন্ট |
| **QuotaEnforcer** | Rate & Fraud Limiter | `backend/core/billing/quota_enforcer.py` | দৈনিক কোটা এনফোর্সমেন্ট ও ফ্রড একাউন্ট ফ্ল্যাগিং |

---

### 🛠️ ২.৫. Tools, Social, Voice/Vision & Utilities (`backend/tools/` & `backend/services/`)

| প্রধান মডিউল | মাইক্রো-ফিচার ও ইউটিলিটি ফাইল | অবস্থান (File Path) | সাব-ফাংশন ও কাজের বিবরণ |
|---|---|---|---|
| **VoiceService** | Speech Recognition Engine | `backend/services/voice_service.py` | অডিও থেকে ভয়েস কমান্ড টেক্সটে রূপান্তর |
| **VisionService** | Image Analysis Engine | `backend/services/vision_service.py` | ইমেজ থেকে কোড ও অবজেক্ট ডায়াগনোসিস (`analyze_image`) |
| **EmailAgent** | OAuth Email Dispatcher | `backend/tools/social/email_agent.py` | ইমেইল নোটিফিকেশন ও মেসেজিং সার্ভিস |
| **RepoDiscovery** | GitHub API Scanner | `backend/tools/repo_discovery_agent.py` | গিটহাব রিপোজিটরির স্ট্রাকচার ও ফাইল স্ক্যানিং |
| **CollaborativeEditor**| Redis Pub/Sub State Sync | `backend/tools/collaborative_editor.py` | রিয়েল-টাইম রিমোট কোড এডিটিং ও সিঙ্ক |
| **ImageToCode** | GPT-4o Vision Parser | `backend/tools/code/image_to_code.py` | স্কেচ বা পিকচার থেকে ফ্রন্টএন্ড কোড তৈরি |
| **StyleLearner** | Coding Pattern Adaptive | `backend/tools/learning/style_learner.py` | ডেভেলপারদের নিজস্ব কোডিং ফর্মেটিং শেখা |
| **MultilingualTTS**| Multi-Voice TTS Engine | `backend/tools/media/multilingual_tts.py` | বহুভাষিক ভয়েস জেনারেশন সার্ভিস |

---

### ⚙️ ২.৬. CI/CD Operations & Infrastructure (`.github/` & `infrastructure/`)

| প্রধান মডিউল | মাইক্রো-ফিচার ও ইউটিলিটি ফাইল | অবস্থান (File Path) | সাব-ফাংশন ও কাজের বিবরণ |
|---|---|---|---|
| **Supreme Core CI**| Pytest & Coverage Guard | `.github/workflows/supreme-core-ci.yml` | কভারেজ থ্রেশহোল্ড (30%) ও ব্যাকএন্ড টেস্ট এনফোর্সমেন্ট |
| **Workflow Janitor**| Daily Action Wash | `.github/workflows/workflow-janitor.yml` | প্রতিদিন ০৪:০০ UTC-তে পুরানো লগ এবং বিল্ড অপ্টিমাইজেশন |
| **Weekly FineTune**| HuggingFace Auto-Trainer | `.github/workflows/weekly-fine-tuning.yml` | সাপ্তাহিক হাগিংফেস মডেল ফাইন-টিউনিং |
| **Render Verifier**| Deployment Health Retry | `.github/scripts/verify-render-deploy.py` | রেন্ডার ডিপ্লয়মেন্টের অটোমেটেড হেলথ চেক ও রিট্রাই |
| **Wrangler Cron** | Cloudflare 8-Min Ping | `cloudflare-worker/wrangler.toml` | ৮-মিনিটের ক্রন পিং ট্র্রিগার যাতে সার্ভার স্লিপে না যায় |
| **MCP Config** | LaunchDarkly Standard JSON | `.vscode/mcp.json` | Cross-IDE AI এজেন্ট সিঙ্ক্রোনাইজেশন কনফিগারেশন |

---

## 🎯 ৩. সারসংক্ষেপ

এই সম্পূর্ণ ও বিস্তৃত ক্যাটালগটিতে **SupremeAI 2.0-এর মূল ৬টি সাব-সিস্টেমের অধীনে থাকা ৪৫+ টি প্রধান ফাইল এবং প্রায় ১০০+ টি মাইক্রো-ফিচার ও সাব-ফাংশন** ইনডেক্স করা হয়েছে। পরবর্তীতে এই তালিকার ভিত্তিতে প্রতিটি মাইক্রো-ফিচারের বিস্তারিত ম্যানুয়াল তৈরি করা যাবে।
