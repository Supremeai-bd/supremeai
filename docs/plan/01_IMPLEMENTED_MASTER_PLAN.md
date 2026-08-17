# Implemented Plans Master Document

### Source: 01-03_foundation_security.md


প্রথমে স্তর ১ (কোর আর্কিটেকচার ও নিরাপত্তা) এর বিস্তারিত ম্যাপ দিচ্ছি।

স্তর ১: কোর আর্কিটেকচার ও নিরাপত্তা (Foundation & Security)
দফা ১: পাইপলাইন অপ্টিমাইজেশন (CI/CD)
উদ্দেশ্য: কোড পুশ করলেই অটো-টেস্ট এবং ক্লাউড রান-এ ডিপ্লয়মেন্ট।

ফাইল ম্যাপ:

.github/workflows/deploy.yml: মেইন সিআই/সিডি পাইপলাইন কনফিগারেশন।

scripts/setup_ci_runner.py: অটোমেটেড রানার সেটআপ।

কাজ: গিটহাব অ্যাকশনস-এর মাধ্যমে গুগল ক্লাউড রান ইন্টিগ্রেশন এবং ডকার বিল্ড অটোমেশন।

দফা ২: ইউজার প্রোফাইলিং ও গোল অ্যালাইনমেন্ট
উদ্দেশ্য: ইউজারের চাহিদা বুঝে কাজের ধরন ঠিক করা।

ফাইল ম্যাপ:

backend/core/user_profiler.py: ইউজারের ডাটা অ্যানালাইজার।

backend/core/intent_parser.py: ইউজারের কমান্ড ও গোল (Fast/Learn/Pro) পার্স করার ইঞ্জিন।

data/user_profiles.db: ইউজার প্রেফারেন্স স্টোরেজ।

কাজ: অনবোর্ডিং ফ্লো এবং ইউজার প্রোফাইল ডাটাবেস স্কিমা তৈরি।

দফা ৩: হিউম্যান-ইন-দ্য-লুপ (HITL) এপ্রুভাল
উদ্দেশ্য: গুরুত্বপূর্ণ সিদ্ধান্তের আগে অ্যাডমিন পারমিশন।

ফাইল ম্যাপ:

backend/api/approval_manager.py: পারমিশন রিকোয়েস্ট লজিক।

frontend/src/components/AdminConsole.tsx: ড্যাশবোর্ড নোটিফিকেশন ইন্টারফেস।

backend/models/pending_tasks.py: এপ্রুভালের জন্য অপেক্ষমান কাজের রেকর্ড।

কাজ: এপ্রুভাল ওয়ার্কফ্লো এবং ড্যাশবোর্ড নোটিফিকেশন হাব তৈরি।


---

### Source: 04-07_Brain & Efficiency.md

স্তর ২: অটোনোমাস লার্নিং ও রিসোর্স ম্যানেজমেন্ট (Brain & Efficiency)
দফা ৪: এক্সপেরিয়েন্স ডাটাবেস (Experience DB)
উদ্দেশ্য: সফল সলিউশন ও এরর প্যাটার্ন সেভ করা যাতে সিস্টেম তার নিজের মেমরি থেকেই পরবর্তীতে সমাধান দিতে পারে।

ফাইল ম্যাপ:

backend/adaptive_engine/experience_db.py: ডাটাবেস হ্যান্ডলার।

backend/core/semantic_cache.py: প্রম্পট ও রেসপন্স পেয়ারিংয়ের জন্য সেমান্টিক ক্যাশ।

data/experience.db: SQLite বা পোর্সেল ডাটাবেস ফাইল (সাকসেসফুল কেস স্টাডিজের ভাণ্ডার)।

কাজ: নতুন প্রম্পটের উত্তরের সাথে আগের সফল কাজের প্যাটার্ন মিলিয়ে রিয়েল-টাইম ডিসিশন ইঞ্জিন তৈরি করা।

দফা ৫: স্মার্ট কস্ট-অপ্টিমাইজেশন ইঞ্জিন (Cost-Economizer)
উদ্দেশ্য: প্রতিটি টাস্কের জন্য সবচেয়ে সাশ্রয়ী পথ (ফ্রি বা লোকাল মডেল) খুঁজে বের করা।

ফাইল ম্যাপ:

backend/engine/cost_optimizer.py: টাস্ক অ্যানালাইজার (ফ্রি vs পেইড ডিসিশন মেকার)।

backend/models/model_router.py: লোকাল মডেল (Ollama/WebLLM) বনাম এক্সটার্নাল এপিআই রাউটার।

backend/utils/api_tracker.py: প্রতিদিনের খরচ এবং ফ্রি লিমিট মনিটর করা।

কাজ: টাস্কের জটিলতা অনুযায়ী এপিআই কল ডাইভার্ট করা এবং খরচ সাশ্রয় করা।

দফা ৬: অটোনোমাস নেটওয়ার্কিং (VPN/Proxy)
উদ্দেশ্য: স্ক্র্যাপিং লিমিটেশন বা আইপি ব্লক বাইপাস করা।

ফাইল ম্যাপ:

backend/tools/vpn_switcher.py: ভিপিএন/প্রক্সি কনফিগারেশন এবং সুইচিং লজিক।

backend/tools/browser_stealth.py: ফিঙ্গারপ্রিন্ট মাস্কিং এবং হিউম্যান বিহেভিয়ার সিমুলেশন।

config/proxy_list.json: প্রক্সি সার্ভার ও ভিপিএন লোকেশন ডাটা।

কাজ: স্ক্র্যাপিং বা ওয়েব এক্সেসের সময় স্বয়ংক্রিয়ভাবে আইপি/ভিপিএন রোটেশন করা।

দফা ৭: স্যান্ডবক্সড টেস্টিং লজিক (Self-Validation)
উদ্দেশ্য: প্রোডাকশনে কোড পুশ করার আগে আইসোলেটেড এনভায়রনমেন্টে পরীক্ষা করা।

ফাইল ম্যাপ:

backend/core/cloud_sandbox_orchestrator.py: ক্লাউড রান বা ডকার কন্টেইনারে কোড এক্সিকিউশন।

backend/scripts/self_healing_tests.py: অটোমেটেড ইউনিট টেস্ট জেনারেশন ও রানার।

backend/core/error_remediation.py: টেস্ট ফেইল করলে এরর ফিক্স করার সেলফ-হিলিং স্ক্রিপ্ট।

কাজ: নতুন কোডকে স্যান্ডবক্সে রান করা, ফেইল করলে অটো-ফিক্স করা এবং পাস করলে এপ্রুভালের জন্য ড্যাশবোর্ডে পাঠানো।


---

### Source: 07-10_Scalability & BYOC.md

স্তর ৩: ডিস্ট্রিবিউটেড ইকোসিস্টেম (Scalability & BYOC)
দফা ৮: ইউনিভার্সাল BYOC (Bring Your Own Cloud) হাব
উদ্দেশ্য: ইউজারের নিজস্ব ক্লাউড রিসোর্স (GCP, AWS, Azure, DigitalOcean) কে SupremeAI-এর প্রসেসিং পাওয়ার হিসেবে যুক্ত করা।

ফাইল ম্যাপ:

backend/byoc/cloud_connector.py: বিভিন্ন ক্লাউড প্রোভাইডারের API অথেন্টিকেশন ও কানেক্টর।

backend/byoc/resource_manager.py: ইউজারের কোন ক্লাউডে কতটা ফ্রি রিসোর্স অবশিষ্ট আছে তার ট্র্যাকিং।

backend/byoc/container_orchestrator.py: ডকার কন্টেইনারের মাধ্যমে ইউজারের ক্লাউডে অটোমেটিক সার্ভিস ডিপ্লয়মেন্ট।

কাজ: ইউজার ড্যাশবোর্ডে ক্লাউড ক্রেডেনশিয়াল যোগ করা এবং সিস্টেমের টাস্কগুলোকে ইউজারের নিজস্ব ইনফ্রাস্ট্রাকচারে ডিস্ট্রিবিউট করা।

দফা ৯: স্কিল স্টোর (Skill Store) ও অটো-কনফিগারেশন
উদ্দেশ্য: কোডিং ছাড়াও ভিডিও এডিটিং, ডেটা অ্যানালাইসিস বা অন্য কাজের জন্য প্রয়োজনীয় টুলস অটোমেটিক কনফিগার করা।

ফাইল ম্যাপ:

backend/skills/skill_registry.py: নতুন স্কিল বা টুলের লিস্ট ও মেটাডাটা।

backend/skills/provisioner.py: নির্দিষ্ট স্কিলের জন্য প্রয়োজনীয় ডিপেন্ডেন্সি বা টুলস (যেমন: FFmpeg, ImageMagick) ইউজারের ক্লাউডে ইন্সটল করা।

frontend/src/pages/SkillStore.tsx: ইউজার ইন্টারফেস যেখানে নতুন স্কিল দেখা ও এনাবল করা যাবে।

কাজ: 'প্লাগ অ্যান্ড প্লে' অভিজ্ঞতা তৈরি—ইউজার জাস্ট সিলেক্ট করবে, সিস্টেম ব্যাকগ্রাউন্ডে টুলস কনফিগার করে কাজ শুরু করবে।

দফা ১০: রিসোর্স ব্রিজ (P2P Sharing)
উদ্দেশ্য: কমিউনিটির মধ্যে অব্যবহৃত ক্লাউড রিসোর্স শেয়ারিং করে একটি ডিস্ট্রিবিউটেড নেটওয়ার্ক তৈরি করা।

ফাইল ম্যাপ:

backend/p2p/resource_broker.py: কার রিসোর্স খালি আছে এবং কে ধার নিতে চায় তার ম্যাচমেকিং লজিক।

backend/p2p/credit_system.py: রিসোর্স শেয়ারিংয়ের বিনিময়ে ক্রেডিট বা পয়েন্ট হিসাব করার লেজার।

backend/p2p/secure_tunnel.py: শেয়ার করা রিসোর্সের নিরাপত্তা নিশ্চিত করার জন্য এনক্রিপ্টেড টানেল।

কাজ: একটি সেফ এবং সিকিউর ব্রিজ তৈরি করা যাতে ইউজারের প্রজেক্ট সিকিউরিটি ঠিক রেখে রিসোর্স শেয়ারিং করা যায়।


---

### Source: 11-15_Evolution.txt

স্তর ৪: সিস্টেম ইভোলিউশন ও স্মার্ট টুলিং (Evolution)
দফা ১১: সিস্টেম সেলফ-হিলিং (Self-Healing Engine)
উদ্দেশ্য: সিস্টেমের নিজস্ব ক্রাশ, এরর বা ব্যর্থ হওয়া ডিপ্লয়মেন্টগুলোকে অটোমেটিক ডিটেক্ট করে সমাধান করা।

ফাইল ম্যাপ:

backend/core/health_monitor.py: লাইভ সিস্টেম হেলথ এবং এরর লগ মনিটর।

backend/core/self_healing_agent.py: লগ এনালাইসিস করে স্ট্যাক ওভারফ্লো বা কমন এরর ফিক্স করার স্ক্রিপ্ট।

backend/models/error_remediation_db.py: অতীতে ঠিক করা এররগুলোর প্যাটার্ন বা নলেজবেস।

কাজ: কোনো সার্ভিস ডাউন হলে সিস্টেমের ব্যাকএন্ড এআই অটোমেটিক সেই সার্ভিসের কোড বা কনফিগারেশন রিবিল্ড বা রিস্টার্ট করবে।

দফা ১২: অটোমেটেড অডিট ও কস্ট-কাটিং (Cost-Auditor)
উদ্দেশ্য: প্রতি কাজের খরচ ট্র্যাক করা এবং কিভাবে আরও সাশ্রয়ী বা ফ্রি উপায়ে কাজটি করা যায় তার রিপোর্ট দেওয়া।

ফাইল ম্যাপ:

backend/monitoring/cost_auditor.py: প্রতিটি এপিআই কল বা ক্লাউড রিসোর্সের খরচ গণনা।

backend/reports/optimization_engine.py: খরচ কমানোর পরামর্শ তৈরি এবং ড্যাশবোর্ডে পুশ করা।

frontend/src/components/CostDashboard.tsx: খরচ ও সাশ্রয়ের ভিজ্যুয়াল গ্রাফ।

কাজ: সিস্টেম নিয়মিত অডিট করবে যে কোনো পেইড এপিআই কি ফ্রি অল্টারনেটিভ দিয়ে প্রতিস্থাপন করা সম্ভব কি না।

দফা ১৩: স্ন্যাপশট লার্নিং (Scout & Scholar Loop)
উদ্দেশ্য: নতুন ওয়েব টেকনোলজি, লাইব্রেরি বা গিটহাব রিপো থেকে জ্ঞান আহরণ করা।

ফাইল ম্যাপ:

backend/scout/web_crawler_agent.py: প্রি-সেভড এবং নতুন ওয়েবসাইট থেকে তথ্য সংগ্রহকারী এজেন্ট।

backend/scout/knowledge_extractor.py: সংগৃহীত তথ্য থেকে দরকারী কোড বা লজিক বের করে নেওয়া।

backend/adaptive_engine/learning_loop.py: এই জ্ঞানকে নতুন "স্কিল" বা "লজিক" হিসেবে সিস্টেমে ইনজেক্ট করা।

কাজ: এআই নিজেই নিয়মিত নতুন তথ্য শিখবে এবং নিজের লজিক আপডেট করবে (পারমিশন বেসড)।

দফা ১৪: মডেল রাউটিং (Intelligent Model Switcher)
উদ্দেশ্য: টাস্কের জটিলতা অনুযায়ী লোকাল বনাম ক্লাউড এআই মডেলের মধ্যে সুইচ করা।

ফাইল ম্যাপ:

backend/engine/model_dispatcher.py: টাস্ক বুঝে মডেল নির্বাচন করার লজিক (সহজ কাজ = লোকাল, জটিল কাজ = Gemini/GPT)।

backend/models/local_model_handler.py: লোকাল মডেল (যেমন: Ollama) কানেকশন ও ম্যানেজমেন্ট।

config/routing_policy.json: কোন ধরনের টাস্ক কোন মডেল দিয়ে রান করবে তার রুলবুক।

কাজ: অপ্রয়োজনীয় এপিআই খরচ কমানো এবং কাজের গতির ভারসাম্য নিশ্চিত করা।

দফা ১৫: অটোনোমাস ইভোলিউশন (Self-Evolution)
উদ্দেশ্য: পূর্ববর্তী ১৪টি দফার ডেটা এবং অভিজ্ঞতার ভিত্তিতে সিস্টেমের নিজস্ব নতুন ফিচার বা আর্কিটেকচার আপডেট করা।

ফাইল ম্যাপ:

backend/evolution/master_planner.py: সিস্টেমের সার্বিক পারফরম্যান্স বিশ্লেষণ করে নিজেই নিজেকে আপডেট করার পরিকল্পনা তৈরি।

backend/evolution/auto_update_manager.py: নিজের কোডবেসে প্যাচ বা নতুন মডিউল অটো-ইমপ্লিমেন্ট করা (অবশ্যই হিউম্যান এপ্রুভাল সাপেক্ষে)।

docs/evolution_log.md: সিস্টেমের বিবর্তনের সম্পূর্ণ ইতিহাস।

কাজ: সিস্টেম নিজে থেকে নতুন কোনো স্কিল বা এফিসিয়েন্সি বাড়ানোর আইডিয়া অ্যাডমিনকে প্রস্তাব করবে এবং এপ্রুভালের পর তা নিজে ইমপ্লিমেন্ট করবে।


---

### Source: 15_step_plan.md

🏛️ SupremeAI: পূর্ণাঙ্গ ও আপডেটকৃত ১৫-দফা পরিকল্পনা
স্তর ১: কোর আর্কিটেকচার ও নিরাপত্তা (Foundation & Security)
১. পাইপলাইন অপ্টিমাইজেশন: সিআই/সিডি (CI/CD) অটোমেশন এবং গিটহাব অ্যাকশনস-এর মাধ্যমে কোড-টু-ক্লাউড অটো-ডিপ্লয়মেন্ট পাইপলাইন ও এনভায়রনমেন্ট সেটআপ।
২. ইউজার প্রোফাইলিং ও গোল অ্যালাইনমেন্ট: অনবোর্ডিংয়ের সময় ইউজারের কাজের ধরন ও উদ্দেশ্য (Fast Track/Learning/Production) বুঝে প্রোফাইল তৈরি।
৩. হিউম্যান-ইন-দ্য-লুপ (HITL) এপ্রুভাল: প্রতিটি স্পর্শকাতর কাজ (কোড পুশ, নতুন সাইট ভিজিট, স্কিল জেনারেশন) সম্পন্ন করার আগে ড্যাশবোর্ডে পারমিশন রিকোয়েস্ট ওয়ার্কফ্লো।

স্তর ২: অটোনোমাস লার্নিং ও রিসোর্স ম্যানেজমেন্ট (Brain & Efficiency)
৪. এক্সপেরিয়েন্স ডাটাবেস (Experience DB): সফল সলিউশন ও প্যাটার্ন সেভ করা, যাতে সিস্টেম পুনরায় একই ভুল না করে নিজের মেমরি থেকে সমাধান দিতে পারে।
৫. স্মার্ট কস্ট-অপ্টিমাইজেশন ইঞ্জিন: প্রতিটি কাজের জন্য "ফ্রি vs পেইড" অপশন বাছাইকারী ইঞ্জিন (লোকাল মডেল > BYOC > প্রিমিয়াম এপিআই)।
৬. অটোনোমাস নেটওয়ার্কিং (VPN/Proxy): ভিপিএন এবং আইপি রোটেশনের মাধ্যমে স্ক্র্যাপিং লিমিটেশন বাইপাস এবং ট্রাস্ট স্কোর রক্ষা।
৭. স্যান্ডবক্সড টেস্টিং লজিক: প্রোডাকশনে যাওয়ার আগে ক্লাউড স্যান্ডবক্সে কোড রান করে সেলফ-টেস্টিং ও এরর হিলিং।

স্তর ৩: ডিস্ট্রিবিউটেড ইকোসিস্টেম (Scalability & BYOC)
৮. ইউনিভার্সাল BYOC হাব: গিটহাব ছাড়াও Google Cloud, AWS, Azure এবং পার্সোনাল স্টোরেজকে একটি কমন রিসোর্স পুল হিসেবে ব্যবহার করা।
৯. স্কিল স্টোর ও অটো-কনফিগারেশন: ইউজারের ক্লাউডে স্বয়ংক্রিয়ভাবে ওপেন-সোর্স টুল (যেমন- FFmpeg, Stable Diffusion) ডিপ্লয় ও কনফিগার করা।
১০. রিসোর্স ব্রিজ (P2P Sharing): ইউজারদের মধ্যে অব্যবহৃত ক্লাউড রিসোর্স শেয়ারিং করে একটি ডিস্ট্রিবিউটেড নেটওয়ার্ক তৈরি।

স্তর ৪: সিস্টেম ইভোলিউশন ও স্মার্ট টুলিং (Evolution)
১১. সিস্টেম সেলফ-হিলিং: এরর প্যাটার্ন ডাটাবেস ব্যবহার করে সিস্টেমের নিজস্ব ক্রাশ বা এরর শনাক্ত ও সংশোধন।
১২. অটোমেটেড অডিট ও কস্ট-কাটিং: সিস্টেমের কাজের ওপর নিয়মিত কস্ট ও পারফরম্যান্স অডিট এবং খরচ কমানোর রিপোর্ট জেনারেট।
১৩. স্ন্যাপশট লার্নিং (Scout & Scholar Loop): ইন্টারনেট থেকে নতুন জ্ঞান আহরণ ও পারমিশন-বেসড লার্নিং সেশন।
১৪. মডেল রাউটিং: কাজের ধরণ অনুযায়ী লোকাল মডেল (WebLLM) এবং এক্সটার্নাল এআই-এর মধ্যে বুদ্ধিমত্তার সাথে সুইচ করা।
১৫. অটোনোমাস ইভোলিউশন: উপরের সবকিছুর সমন্বয়ে সিস্টেমের নিজস্ব স্বয়ংক্রিয় আপডেট এবং নতুন ফিচার বা স্কিল তৈরি।

এই ১৫টি দফা এখন আপনার সুপ্রিম এআই-এর "মাস্টার ব্লুপ্রিন্ট"।


---

### Source: auto_pr_pipeline.md

# 🛠️ Auto PR Pipeline Specification (Implemented)

> **Status:** ✅ Fully Implemented (2026-07-26)  
> **Location:** `backend/tools/code/auto_pr_pipeline.py`, `backend/core/security/guardian_ai.py`

---

## 2. Technical Implementation Details

### A. Guardian AI Security Scan (`backend/core/security/guardian_ai.py`)
- Core method `scan_code(code: str)` runs code analysis before commit or push operations.
- Intercepts unsafe code blocks (e.g. potential code injections, hardcoded secrets, shell syntax violations).
- Integrates with `OutputSanitizer` to clean up payloads before git branch allocation.

### B. Auto PR Pipeline Orchestrator (`backend/tools/code/auto_pr_pipeline.py`)
- **Execution Pipeline Steps:**
  1. Validates input fix patch string using `GuardianAI`.
  2. Spawns isolated shell command or python-git process to create patch branches.
  3. Commits fixes and creates GitHub pull requests targetting the destination branch.
- **Bengali Logic Comments:**
  ```python
  # গিট ব্রাঞ্চ তৈরি এবং রিমোট রিপোজিটরিতে কোড পুশ করার প্রাক-প্রস্তুতি লজিক
  # পুশ করার পূর্বে Guardian AI দিয়ে পুরো কোড অটো-স্ক্যান করা হয়
  ```

---

## 3. Verification & Tests

Executed from the backend root using:
```bash
poetry run pytest tests/test_auto_pr_pipeline.py
```
Tests assert security screening triggers, git branch execution safety, mock PR submission, and result structures.


---

### Source: causal_reasoning_engine.md

# 🔎 Causal Reasoning Engine Specification (Implemented)

> **Status:** ✅ Fully Implemented (2026-07-26)  
> **Location:** `backend/brain/causal/interventions.py`, `backend/brain/causal/discovery.py`, `backend/brain/causal/root_cause.py`

---

## 2. Technical Implementation Details

### A. Intervention Tracker (`backend/brain/causal/interventions.py`)
- Tracks actions taken on the system (`DEPLOYMENT`, `CONFIG_CHANGE`, `SCALE_OUT`).
- Logs a timeline snapshot containing pre-intervention and post-intervention system performance metrics (e.g. latency, error rate, CPU load).

### B. Causal Discovery Engine (`backend/brain/causal/discovery.py`)
- Takes telemetry data and evaluates relationships using statistical correlation and time-lag analysis.
- Generates a directed causal graph (DAG) representing system dependencies.
- **Bengali Logic Comments:**
  ```python
  # সংগৃহীত মেট্রিক্স ডেটা থেকে ভেরিয়েবলগুলোর মধ্যে কার্যকারণ সম্পর্ক (Causal Link) খুঁজে বের করার লজিক
  ```

### C. Root Cause Analyzer (`backend/brain/causal/root_cause.py`)
- Uses Pearl's Do-Calculus to simulate interventions on candidate failure nodes.
- Computes causal effects and confidence scores to isolate true root causes from downstream symptoms.
- Returns actionable remediation paths (e.g. recommend database index update instead of container scale-out).

---

## 3. Verification & Tests

Executed from the backend root using:
```bash
poetry run pytest tests/test_causal_engine.py
```
Tests assert causal link generation accuracy, do-calculus calculation math, and diagnostic predictions under synthetic load anomalies.


---

### Source: dynamic_ttl_caching.md

# ⚡ Dynamic TTL Caching Engine Specification (Implemented)

> **Status:** ✅ Fully Implemented (2026-07-26)  
> **Location:** `backend/core/cache/autocache_proxy.py`

---

## 1. Executive Summary

The **AutoCacheProxy** dynamic TTL engine replaces static cache lifetime allocation with prompt-inferred dynamic TTL assignment, reducing redundant backend database and external LLM API calls by up to 90%.

---

## 2. Technical Implementation Details

### A. Dynamic Cache Handler (`AutoCacheProxy`)
- **Category Inference Rules:** Evaluates incoming prompt queries to match specialized TTL metrics mapping:
  - **`static_docs` (24 Hours / 86,400s):**
    - Triggers: `doc`, `guide`, `tutorial`, `readme`, `manifest`, `api specification`.
  - **`skills_catalog` (12 Hours / 43,200s):**
    - Triggers: `skill`, `catalog`, `tools`, `capabilities`, `list skills`.
  - **`code_gen` (1 Hour / 3,600s):**
    - Triggers: `def `, `class `, `function`, `code`, `bug`, `refactor`, `patch`.
  - **`ai_chat` (30 Minutes / 1,800s):**
    - Default conversational prompts.
  - **`user_dashboard` (0 Seconds / Bypass Cache):**
    - Triggers: `dashboard`, `balance`, `profile`, `account`, `realtime`, `stats`.
- **Bengali Logic Comments:**
  ```python
  # প্রম্পটের ধরণ নির্ধারণ করে ডাইনামিক ক্যাশ টাইমআউট (TTL) অ্যাসাইন করার লজিক
  # ড্যাশবোর্ড বা ব্যালেন্স সংক্রান্ত তথ্যের জন্য ক্যাশ এড়ানো হয় যাতে ইউজার রিয়েল-টাইম ডেটা পায়
  ```

### B. Redis Integration
- Integrates with standard Redis key-value store using pipeline operations.
- Intercepts requests by checking cache keys formatted as `cache:{prompt_hash}`.
- Sets expiration parameters during insertions via `redis_client.setex(key, ttl, value)`.

---

## 3. Verification & Tests

Executed from the backend root using:
```bash
poetry run pytest tests/test_dynamic_ttl_cache.py
```
Tests assert TTL durations are correctly mapped depending on query types, dashboard requests bypass cache, and expiration bounds are respected in Redis mock.


---

### Source: GCLOUD WITH Cloudflare.md

সুপ্রিম এআই (SupremeAI) প্রজেক্টের জিরো মেইনটেইন্যান্স এবং ক্লাউড-ফার্স্ট আর্কিটেকচারের জন্য Cloudflare R2 একটি নিখুঁত সিদ্ধান্ত। এর 10GB ফ্রি স্টোরেজ এবং আনলিমিটেড ইগ্রেস (Egress) ব্যান্ডউইথ আপনার প্রজেক্টের হোস্টিং খরচ পুরোপুরি শূন্যে নামিয়ে আনবে।

গুগল ক্লাউড রান (Cloud Run)-এর মেমোরি এবং প্রসেসিং পাওয়ার বাঁচাতে আমরা এখানে Pre-signed URL মেকানিজম ব্যবহার করব। এতে ইউজাররা ফাইল ব্যাকএন্ডের ভেতর দিয়ে না পাঠিয়ে, সরাসরি ক্লাউডফ্লেয়ারের সার্ভারে আপলোড করতে পারবেন।

নিচে Cloudflare R2-এর সম্পূর্ণ সেটআপ এবং ইন্টিগ্রেশন প্ল্যান ধাপে ধাপে দেওয়া হলো

ধাপ ১ Cloudflare ড্যাশবোর্ডে R2 বাকেট সেটআপ
Cloudflare ড্যাশবোর্ডে লগইন করে বামদিকের মেনু থেকে R2 Object Storage-এ যান।

Create Bucket-এ ক্লিক করে একটি বাকেট তৈরি করুন (যেমন supremeai-assets)। Location Automatic রাখতে পারেন।

বাকেট তৈরি হলে ডানদিকে Manage R2 API Tokens-এ ক্লিক করুন।

Create API token নির্বাচন করুন

Permissions Object Read & Write নির্বাচন করুন।

Specify bucket(s) শুধু আপনার তৈরি করা বাকেটটি সিলেক্ট করুন (সিকিউরিটির জন্য)।

টোকেন তৈরি হলে নিচের ৩টি তথ্য কপি করে নিরাপদে সংরক্ষণ করুন

Access Key ID

Secret Access Key

S3 API Endpoint (এটি দেখতে অনেকটা এমন হবে httpsaccount_id.r2.cloudflarestorage.com)

ধাপ ২ এনভায়রনমেন্ট ভ্যারিয়েবল ও সিক্রেট সিঙ্ক
আপনার লোকাল .env ফাইলে নিচের ভ্যারিয়েবলগুলো যুক্ত করুন। প্রোডাকশনের জন্য এগুলোকে ফায়ারবেস ফায়ারস্টোরের primary_vault ডকুমেন্টে অ্যাড করে দিন, যাতে আপনার sync_secrets.py স্ক্রিপ্টটি এগুলোকে অটোমেটিক পুল করে নিতে পারে।

Code snippet
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY=your_r2_access_key
R2_SECRET_KEY=your_r2_secret_key
R2_BUCKET_NAME=supremeai-assets
R2_PUBLIC_URL=httpspub-xxxxxxxx.r2.dev # (অপশনাল পাবলিক অ্যাক্সেসের জন্য Custom Domain)
ধাপ ৩ ব্যাকএন্ডে Boto3 (S3 Client) ইন্টিগ্রেশন
R2 যেহেতু S3-কমপ্যাটিবল, তাই পাইথনের অফিশিয়াল এডব্লিউএস লাইব্রেরি boto3 এখানে দারুণ কাজ করবে।

১. লাইব্রেরি ইনস্টল করুন
আপনার backend ডিরেক্টরিতে গিয়ে ডিপেনডেন্সি আপডেট করুন

Bash
poetry add boto3
২. স্টোরেজ সার্ভিস ক্লাস তৈরি করুন (backendstorager2_storage_client.py)

Python
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from loguru import logger

class R2StorageClient
    def __init__(self)
        account_id = os.getenv(R2_ACCOUNT_ID)
        access_key = os.getenv(R2_ACCESS_KEY)
        secret_key = os.getenv(R2_SECRET_KEY)
        self.bucket_name = os.getenv(R2_BUCKET_NAME)

        # Cloudflare R2 Endpoint
        endpoint_url = fhttps{account_id}.r2.cloudflarestorage.com

        self.s3_client = boto3.client(
            s3,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=auto, # R2 uses 'auto'
            config=Config(signature_version=s3v4)
        )

    def generate_presigned_upload_url(self, object_name str, file_type str, expiration=3600)

        ক্লায়েন্টকে সরাসরি R2-তে ফাইল আপলোড করার জন্য একটি সাময়িক URL তৈরি করে দেয়।

        try
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket' self.bucket_name,
                    'Key' object_name,
                    'ContentType' file_type
                },
                ExpiresIn=expiration
            )
            return response
        except ClientError as e
            logger.error(fError generating presigned URL {e})
            return None

    def generate_presigned_download_url(self, object_name str, expiration=3600)

        প্রাইভেট ফাইল ডাউনলোডের জন্য টেম্পোরারি URL জেনারেট করে।

        try
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket' self.bucket_name,
                    'Key' object_name
                },
                ExpiresIn=expiration
            )
            return response
        except ClientError as e
            logger.error(fError generating download URL {e})
            return None
ধাপ ৪ FastAPI রাউটার তৈরি (backendapiroutesmedia.py)
এবার ফ্রন্টএন্ড বা স্টুডিও ক্লায়েন্ট থেকে এই URL রিকোয়েস্ট করার জন্য একটি এপিআই এন্ডপয়েন্ট তৈরি করুন।

Python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from storage.r2_storage_client import R2StorageClient
from core.auth_middleware import require_auth_token # আপনার কাস্টম অথ মিডলওয়্যার

router = APIRouter()
storage_client = R2StorageClient()

class UploadRequest(BaseModel)
    file_name str
    file_type str
    folder str = skills_bundles # ডিফল্ট ফোল্ডার

@router.post(generate-upload-url)
async def get_upload_url(request UploadRequest, user=Depends(require_auth_token))
    # ইউনিক ফাইলের পাথ তৈরি (যাতে নাম ক্ল্যাশ না করে)
    import uuid
    safe_filename = f{request.folder}{user['id']}{uuid.uuid4().hex}_{request.file_name}

    upload_url = storage_client.generate_presigned_upload_url(
        object_name=safe_filename,
        file_type=request.file_type
    )

    if not upload_url
        raise HTTPException(status_code=500, detail=Could not generate upload URL)

    return {
        upload_url upload_url,
        file_path safe_filename, # আপলোড শেষে ডাটাবেসে সেভ করার জন্য
        public_url f{os.getenv('R2_PUBLIC_URL')}{safe_filename} # যদি বাকেট পাবলিক হয়
    }
ধাপ ৫ React Studio Client থেকে সরাসরি আপলোড
ফ্রন্টএন্ড (ReactVite) থেকে ফাইলটি ব্যাকএন্ডে না পাঠিয়ে, জেনারেট করা Pre-signed URL ব্যবহার করে সরাসরি Cloudflare R2-তে আপলোড করার লজিক

JavaScript
 srcservicesstorageApi.ts

export const uploadFileToR2 = async (file File) = {
    try {
         ১. ব্যাকএন্ড থেকে প্রে-সাইন্ড আপলোড ইউআরএল নিয়ে আসা
        const response = await fetch(`${API_BASE_URL}apiv1mediagenerate-upload-url`, {
            method 'POST',
            headers {
                'Content-Type' 'applicationjson',
                'Authorization' `Bearer ${getAuthToken()}`
            },
            body JSON.stringify({
                file_name file.name,
                file_type file.type,
                folder custom_skills
            })
        });

        const { upload_url, file_path } = await response.json();

         ২. সরাসরি Cloudflare R2-তে ফাইল আপলোড (ব্যাকএন্ড বাইপাস করে)
        const uploadResponse = await fetch(upload_url, {
            method 'PUT',
            headers {
                'Content-Type' file.type,
            },
            body file
        });

        if (!uploadResponse.ok) {
            throw new Error(Failed to upload file directly to R2);
        }

         ৩. সফল হলে ফাইলের পাথ রিটার্ন করা (যা Supabase ডাটাবেসে সেভ হবে)
        return file_path;

    } catch (error) {
        console.error(Upload Error, error);
        throw error;
    }
};
এই আর্কিটেকচারের সুবিধা

Zero Backend Load ইউজার 1GB সাইজের ফাইল আপলোড করলেও আপনার FastAPI এবং Cloud Run-এর মেমোরি 0% ব্যবহৃত হবে।

Speed সরাসরি Cloudflare-এর গ্লোবাল এজ নেটওয়ার্কে ফাইল আপলোড হওয়ায় স্পিড অনেক বেশি পাওয়া যাবে।


---

### Source: implementation_plan.md

# 🏛️ SupremeAI 2.0 — চূড়ান্ত বাস্তবায়ন পরিকল্পনা (v3 — Tooling Finalized)
### Source: `docs/-01-admin's plan/next step/` — 15-Step Master Blueprint
### Status: ✅ ALL DECISIONS LOCKED — READY FOR EXECUTION

---

## ✅ Design Decisions (All Locked)

| Question | Decision |
|---|---|
| **VPN/Proxy** | Hybrid: Free proxies default, Premium (Bright Data) for sensitive ops only |
| **P2P Credits** | Credit/Reputation system + **Global Kill-Switch (default: OFF)** |
| **BYOC Phase 1** | GCP-only (existing infra) |
| **Evolution Branch** | `feature/auto-<timestamp>` → HITL → `develop` (never direct to `main`) |
| **Model Gateway** | **LiteLLM** — single interface for 100+ models |
| **Agentic Flow** | **LangGraph** for stateful loops, **CrewAI** for multi-agent crews |
| **Vector DB** | **ChromaDB** (local/dev) + **Qdrant** (production scale) |
| **BYOC IaC** | **Terraform** for GCP resource provisioning |
| **Observability** | **LangSmith** (AI traces) + **Prometheus + Grafana** (system metrics) |

---

## 🗺️ Tooling Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    SupremeAI 2.0 — Tool Stack               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🧠 AI LAYER                                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LiteLLM Gateway  ←── single API for 100+ models    │  │
│  │  ├── Ollama (local, free)                            │  │
│  │  ├── OpenRouter (free tier)                          │  │
│  │  ├── Gemini Flash / Pro                              │  │
│  │  ├── GPT-4o / GPT-4o-mini                           │  │
│  │  └── DeepSeek / Mistral / Claude                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  🤖 AGENTIC LAYER                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LangGraph  ←── Stateful loops (self-healing, HITL) │  │
│  │  CrewAI     ←── Multi-agent crews (Master Planner)  │  │
│  │  ├── AuditorAgent  (cost & performance audit)        │  │
│  │  ├── CoderAgent    (patch generation)                │  │
│  │  ├── TesterAgent   (sandbox test runner)             │  │
│  │  └── PlannerAgent  (proposal generation)             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  🗄️ MEMORY LAYER                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ChromaDB  ←── local/dev semantic search             │  │
│  │  Qdrant    ←── production vector search              │  │
│  │  SQLite/Firestore ←── structured data                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ☁️ INFRASTRUCTURE LAYER                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Terraform  ←── GCP resource provisioning (BYOC)    │  │
│  │  K3s        ←── (Phase 2) lightweight Kubernetes     │  │
│  │  Docker     ←── sandbox containers (Step 7)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  📊 OBSERVABILITY LAYER                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LangSmith     ←── AI decision trace & reasoning    │  │
│  │  Prometheus    ←── metrics collection               │  │
│  │  Grafana       ←── metrics visualization            │  │
│  │  Sentry (✅)   ←── error tracking (already active)  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Dependency Status Table

| Tool | Already in `pyproject.toml`? | Action |
|------|------------------------------|--------|
| `prometheus-client` | ✅ YES (`^0.20.0`) | Wire to Grafana only |
| `chromadb` | ✅ YES (`^0.4.0`, ml group) | Use in Experience DB |
| `qdrant-client` | ✅ YES (`^1.9.0`, ml group) | Use in production |
| `sentence-transformers` | ✅ YES (ml group) | Vector embeddings |
| `playwright` + `playwright-stealth` | ✅ YES (tools group) | Browser stealth (Step 6) |
| `docker` SDK | ✅ YES (tools group) | Sandbox (Step 7) |
| `boto3` | ✅ YES (tools group) | AWS (Phase 2 BYOC) |
| `litellm` | ❌ MISSING | **Add to core deps** |
| `langgraph` | ❌ MISSING | **Add to ml group** |
| `crewai` | ❌ MISSING | **Add to ml group** |
| `langsmith` | ❌ MISSING | **Add to tools group** |
| `grafana` | N/A (external service) | Docker Compose setup |
| `terraform` | N/A (CLI tool) | `infrastructure/terraform/` |

### `pyproject.toml` additions needed:
```toml
[tool.poetry.dependencies]
# নতুন AI গেটওয়ে — সব মডেলের জন্য একটি ইন্টারফেস
litellm = "^1.40.0"

[tool.poetry.group.ml.dependencies]
# অটোনোমাস এজেন্টিক ফ্লো-র জন্য
langgraph = "^0.2.0"
crewai = "^0.80.0"

[tool.poetry.group.tools.dependencies]
# AI সিদ্ধান্ত ট্রেসিং-এর জন্য
langsmith = "^0.1.0"
```

---

## 🔷 Layer 1: Foundation & Security (Steps 1–3)

---

### Step 1 — CI/CD Pipeline Optimization
**Status:** ✅ Partially Built | **New Tool:** None

#### [MODIFY] `.github/workflows/monorepo_ci_cd.yml`
```diff
+ - name: Cache pip/pnpm dependencies
+   uses: actions/cache@v4
+ - name: Smoke test post-deploy
+   run: curl -f ${{ secrets.CLOUD_RUN_URL }}/health || exit 1
+ - name: Discord deploy notification
+   uses: sarisia/actions-status-discord@v1
+   with: { webhook: ${{ secrets.DISCORD_WEBHOOK }} }
```

#### [NEW] `scripts/setup_ci_runner.py`

---

### Step 2 — User Profiling & Goal Alignment
**Status:** ⚠️ Missing | **New Tool:** LiteLLM (for intent classification)

#### [NEW] `backend/core/user_profiler.py`
```python
# ব্যবহারকারীর লক্ষ্য বিশ্লেষণ করে মোড নির্ধারণ
# LiteLLM দিয়ে fast local model ব্যবহার করে classification
import litellm

class UserProfiler:
    MODES = ["FAST_TRACK", "LEARNING", "PRODUCTION"]

    async def classify_user(user_id: str) -> UserProfile
    async def update_from_history(user_id: str, task: Task) -> None
```

#### [MODIFY] [adaptive_engine/intent_parser.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/adaptive_engine/intent_parser.py)
- Add `extract_goal(prompt) -> UserGoal` using LiteLLM local model

#### [MODIFY] [api/routes/onboarding.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/api/routes/onboarding.py)
- `POST /onboarding/profile`, `GET /onboarding/mode`

---

### Step 3 — Human-in-the-Loop (HITL) Approval ⚡ BUILD FIRST
**Status:** ❌ Missing | **New Tool:** LangGraph (approval state machine)

> [!IMPORTANT]
> HITL must be built first. Every step that involves autonomous action (VPN switch, evolution patch, domain craw


---

## 🤖 AI Execution & Automation History

> **Audit Note:** More than 130+ AI-generated execution logs (walkthrough.md, 	ask.md, implementation_plan.md generated by UUID-based agent runs) have been audited. 

All essential technical architectures, codebase logic, and configuration setups from those AI sessions have been successfully extracted and merged into the Core Features sections above (e.g., Causal Reasoning Engine, Auto PR Pipeline, Dynamic TTL Caching).

To maintain a clean and Zero-Gap architecture, the redundant raw logs (which only contained task checklists and step-by-step chat history) have been purged. The current document now acts as the Single Source of Truth for all implemented features.
