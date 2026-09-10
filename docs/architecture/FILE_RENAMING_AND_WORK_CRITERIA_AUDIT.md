# 📋 SupremeAI Comprehensive File Naming & Work-Criteria Alignment Audit

**Document Version:** 1.0.0  
**Date:** 2026-09-11  
**Status:** Canonical Architectural Blueprint  
**Scope:** Local Workspace, GitHub / Remote Tracking, Archived Artifacts, and Active Codebase (Frontend & Backend)

---

## Executive Summary

SupremeAI-এর সেলফ-ইভলভিং ও মাল্টি-এজেন্ট আর্কিটেকচারে কোডের প্রতিটি উপাদানের নামকরণ তার প্রকৃত **কার্যকারিতা, দায়িত্ব ও কাজের মানদণ্ড (Work Criteria & Technical Responsibility)** এর সাথে ১০০% সঙ্গতিপূর্ণ থাকা বাধ্যতামূলক। 

পূর্বে `docs/NAVIGATION_MISMATCH_MAP.md` অনুসারে বেশ কিছু বড় মাপের রূপক ও বিভ্রান্তিকর ফাইলের নাম রিনেম করে সফলভাবে ক্যানোনিকাল পাথে স্থানান্তর করা হয়েছিল (যেমন: `tierSStore` → `workspaceUiStateStore`, `EvolutionForgeWidget` → `SkillForgeWidget`, `self_improvement_agent` → `codebase_refactor_proposer` ইত্যাদি)।

এই অডিটে **লোকাল ফাইলসিস্টেম, গিট ইনডেক্স (`git ls-files`), রিমোট ব্রাঞ্চ ও পূর্ববর্তী হিস্ট্রি এবং সকল `archive` ডিরেক্টরি** পুঙ্খানুপুঙ্খভাবে স্ক্যান করে একটি সম্পূর্ণ ও নির্ভুল তালিকা প্রস্তুত করা হয়েছে।

---

## ১. Archive ডিরেক্টরি ও ফাইলসমূহের অডিট (Local & GitHub/Remote)

আমরা লোকাল ও রিমোটের সমস্ত `archive` পাথ বিশ্লেষণ করেছি:

| আর্কাইভ অবস্থান | ট্র্যাকিং স্ট্যাটাস | ফাইলের ধরন / বিবরণ | কাজের ক্রাইটেরিয়া ও সিদ্ধান্ত |
|---|---|---|---|
| `docs/archive/` | Git Tracked | `legacy_cloud_run_deployment.md`, `lessons_2026-08.md`, `lessons_2026-09.md`, `PATCH_NOTES_v2.md`, `PATCH_NOTES_v3.md` | **Immutable Audit Trail:** এগুলো ঐতিহাসিক রেফারেন্স এবং পূর্ববর্তী প্যাচ নোট। এগুলোর অভ্যন্তরীণ নাম পরিবর্তনের কোনো প্রয়োজন নেই। |
| `backend/database/migrations/archive/` | Local (Immutable) | ১৭টি ক্রমানুযায়ী হ্যান্ড-রিটেন SQL ফাইল (`01_initial_setup.sql` থেকে `21_render_account_preflight.sql`) | **Historical Schema Archive:** `backend/database/migrations/README.md` অনুসারে বর্তমানে **Alembic** (`backend/alembic_migrations/`) হলো একমাত্র সক্রিয় ও ক্যানোনিকাল মাইগ্রেশন ইঞ্জিন। এই SQL স্ক্রিপ্টগুলো অপরিবর্তনীয় রেফারেন্স হিসেবে `archive/`-এ সংরক্ষিত। |
| `scripts/archive/` & `scripts/archive/legacy_one_offs/` | Local / Preserved | ১২০+ টি এককালীন স্ক্রিপ্ট (যেমন `check_admin_console.js`, `find_client_files.py`, `supreme-docker-analyzer.py`, `clean_legacy_secrets.py`) | **Ad-hoc Historical Tools:** কোডবেসের পূর্ববর্তী ক্লিনিং ও অটোমেশনের স্ক্রিপ্ট যা ইতোমধ্যে `legacy_one_offs`-এ স্থানান্তরিত। এগুলো অ্যাক্টিভ প্রোডাকশনে ব্যবহৃত হয় না। |
| `backend/reports/archive/` | Local | `audit_progress.md`, `task_progress.md`, `_audit_baseline.txt`, টেস্ট লগস | **Audit Checkpoint Artifacts:** পূর্বের টেস্ট ও অডিটের হিস্টোরিক্যাল লগ। |
| `_archive/firebase_functions_removed_20260825/` | Git History | পূর্বে বিলুপ্ত ফায়ারবেস ক্লাউড ফাংশনসমূহ | **Cleaned & Purged:** গিট কমিট হিস্টোরিতে সংরক্ষিত। |

> **সিদ্ধান্ত:** আর্কাইভ ফোল্ডারগুলোর ফাইলসমূহ ঐতিহাসিক অডিট ট্রেইল হিসেবে অপরিবর্তিত থাকবে। মূল ফোকাস সক্রিয় কোডবেসের ওপর যেখানে মিসলিডিং ও রূপকীয় নাম এখনও রয়ে গেছে।

---

## ২. সক্রিয় কোডবেসের অবশিষ্টাংশ ফাইলের পূর্ণাঙ্গ তালিকা (Remaining Files To Be Renamed)

নিচে সক্রিয় কোডবেসের যে ফাইলগুলোর নাম তাদের প্রকৃত কাজের ক্রাইটেরিয়ার সাথে অসামঞ্জস্যপূর্ণ, তাদের পূর্ণাঙ্গ তালিকা দেওয়া হলো:

### ক. ফ্রন্টএন্ড লেয়ার (Frontend Components & Dashboard)

| # | বর্তমান ফাইল পাথ | প্রস্তাবিত ক্যানোনিকাল পাথ | কাজের ক্রাইটেরিয়া ও রিনেম করার কারণ (Rationale) |
|---|---|---|---|
| 1 | `frontend/src/components/LiveSujonBackground.tsx` | `frontend/src/components/AgentStateShaderBackground.tsx` | এটি কোনো ব্যক্তির নাম নয়; এটি WebGL2 GLSL ফ্র্যাগমেন্ট ও ভার্টেক্স শেডার সমৃদ্ধ একটি ডায়নামিক ক্যানভাস ব্যাকগ্রাউন্ড, যা এজেন্টের স্টেট পরিবর্তনের সাথে সাথে অ্যানিমেট করে। |
| 2 | `frontend/src/components/dashboard/SujonCoreCockpit.tsx` | `frontend/src/components/dashboard/AgentExecutionTelemetryCockpit.tsx` | এটি একটি রিয়েলটাইম WebSocket (`/ws/dashboard`) লগ স্ট্রিমিং, ফাইল-ট্রি এবং টার্মিনাল এক্সিকিউশন শেল মনিটর করার অ্যাডমিন ড্যাশবোর্ড ককপিট। |
| 3 | `frontend/src/components/SupremeComponents.tsx` | `frontend/src/components/ui/GlassUiPrimitives.tsx` | কোনো স্পেশাল ইঞ্জিন বা বিজনেস লজিক নেই; এটি শুধুমাত্র রিইউজেবল গ্লাস-মরফিজম (`supreme-glass`) কার্ড ও বাটন প্রিমিটিভস। UI Primitives ডিরেক্টরিতে স্থানান্তর যৌক্তিক। |
| 4 | `frontend/src/components/OperatorStudio.tsx` | `frontend/src/components/customer/CustomerSupportEditorStudio.tsx` | মূল ডেভেলপমেন্ট স্টুডিও হলো `AIStudio.tsx` এবং `IdeWorkspace.tsx`। এই কম্পোনেন্টটি নির্দিষ্টভাবে কাস্টমার সাপোর্ট চ্যাট প্যানেল, হোম ফিড ও কোড এডিটর সমন্বিত ইন্টারফেস। |

---

### খ. ব্যাকএন্ড এজেন্টস লেয়ার (Autonomous Agents)

| # | বর্তমান ফাইল পাথ | প্রস্তাবিত ক্যানোনিকাল পাথ | কাজের ক্রাইটেরিয়া ও রিনেম করার কারণ (Rationale) |
|---|---|---|---|
| 5 | `backend/agents/vulnerability_prophet.py` | `backend/agents/code_vulnerability_scanner_agent.py` | "Prophet" (ভবিষ্যদ্বাণী) একটি বিভ্রান্তিকর রূপক। বাস্তবে এটি AST ও রেজেক্স ভিত্তিক সিকিউরিটি স্ক্যানার যা SQLi, XSS, Path Traversal ইত্যাদি নিরাপত্তা ঝুঁকি শনাক্ত ও প্রিভেন্ট করে। |
| 6 | `backend/agents/churn_prophet.py` | `backend/agents/user_retention_risk_agent.py` | রূপকীয় নাম বাদ দিয়ে কাজের উদ্দেশ্য স্পষ্ট করা। এটি ইউজারের বিহেভিওরাল সিগন্যাল থেকে চুরন রিস্ক স্কোরিং এবং রিটেনশন স্ট্র্যাটেজি জেনারেট করে। |
| 7 | `backend/agents/insight_mage.py` | `backend/agents/data_trend_anomaly_agent.py` | "Mage" রূপক পরিহারযোগ্য। এর কাজ হলো ডেটাবেস থেকে Z-score আউটলায়ার এবং ট্রেন্ড অ্যানালাইসিস করে ইনসাইট রিপোর্ট তৈরি করা। |
| 8 | `backend/agents/devops/cloud_watchman.py` | `backend/agents/devops/multicloud_quota_monitor.py` | "Watchman" নয়; এটি Firebase, Vercel, GCP-এর বিলing কোটা এবং এরর রেট অ্যানোমালি ট্র্যাক করার মাল্টিক্লাউড মনিটরিং স্ক্রিপ্ট। |
| 9 | `backend/agents/devops/cost_sage.py` | `backend/agents/devops/llm_cost_optimizer.py` | রূপক "Sage" বাদ দিয়ে এটি স্পষ্টভাবে LLM টোকেন কনজাম্পশন, LiteLLM প্রোভাইডার কস্ট ট্র্যাক ও অপটিমাইজেশন নিশ্চিত করে। |

---

### গ. ব্যাকএন্ড সার্ভিসেস ও টুলস লেয়ার (Services & Tools)

| # | বর্তমান ফাইল পাথ | প্রস্তাবিত ক্যানোনিকাল পাথ | কাজের ক্রাইটেরিয়া ও রিনেম করার কারণ (Rationale) |
|---|---|---|---|
| 10 | `backend/services/rider_tracker.py` | `backend/services/delivery_fleet_tracker.py` | হেডারে এখনো হার্ডকোডেড রয়েছে "Paykari Bazar System"। কিন্তু এটি একটি জেনেরিক জিও-লোকেশন ও রাইডার ফ্লিট ট্র্যাকিং সার্ভিস। |
| 11 | `backend/tools/freebuff_client.py` | `backend/tools/cli_process_delegator.py` | "freebuff" একটি নির্দিষ্ট এক্সটার্নাল বাইনারি। এর মূল দায়িত্ব হলো অ্যাসিনক্রোনাস সিএলআই এক্সিকিউশন ও পাইপলাইন সাবপ্রসেসে ডেলিগেট করা। |
| 12 | `backend/tools/langchain_agent_example.py` | `backend/tools/launchdarkly_agent_adapter.py` | এটি কোনো `example` নয়, এটি LaunchDarkly AgentControl এবং LangChain-এর লাইভ প্রোডাকশন অ্যাডাপ্টার। টুলস ফোল্ডারে `_example` নাম রাখা বিভ্রান্তিকর। |
| 13 | `backend/tools/seed_database.py` | `scripts/db/seed_knowledge_fts.py` | এটি কোনো রানটাইম টুল নয়; এটি মূলত SQLite FTS5 ও ChromaDB নলেজ বেস সিডিং স্ক্রিপ্ট। এর সঠিক জায়গা `scripts/db/` ডিরেক্টরি। |

---

### ঘ. ব্যাকএন্ড এপিআই রাউটস লেয়ার (API Routes)

| # | বর্তমান ফাইল পাথ | প্রস্তাবিত ক্যানোনিকাল পাথ | কাজের ক্রাইটেরিয়া ও রিনেম করার কারণ (Rationale) |
|---|---|---|---|
| 14 | `backend/api/routes/healing.py` | `backend/api/routes/healing_stats.py` | এটি কোনো মূল সেলফ-হিলিং ইঞ্জিন নয়; কেবল `/health/predictions` এবং `/healing/stats` এপিআই রিটার্ন করে। মূল সার্ভিসের সাথে নামের ওভারল্যাপ দূর করতে রিনেম প্রয়োজন। |
| 15 | `backend/api/routes/codeflow.py` | `backend/api/routes/code_dependency_graph.py` | এটি কোডবেসের ফাইল বা পাথ পার্স করে ডিপেন্ডেন্সি গ্রাফ (Nodes ও Edges) রিটার্ন করে। |
| 16 | `backend/api/routes/site_actions.py` | `backend/api/routes/browser_action_registry.py` | এটি হেডলেস ব্রাউজার স্ক্র্যাপিং ও অ্যাকশন সিলেক্টরগুলোর অ্যাডমিন কনফিগারেশন রেজিস্ট্রি। |
| 17 | `backend/api/routes/tier_s_routes.py` | `backend/api/routes/workspace_feature_routes_shim.py` | মূল ফাইলটি ইতিমধ্যেই `workspace_feature_routes.py`-তে রিনেম করা হয়েছে; বর্তমান `tier_s_routes.py` শুধুমাত্র একটি শিম ফাইল। এটিকে পরিষ্কারভাবে শিম হিসেবে চিহ্নিত করা দরকার। |

---

## ৩. নন-ব্রেকিং মাইগ্রেশন কৌশল (Zero-Downtime Safe Execution Protocol)

সুপ্রিমএআই-এর কোর আর্কিটেকচারাল পলিসি অনুসারে:

```
[Old Legacy Path] ─────────── (Backward-Compatibility Shim: re-export)
       │
       ▼ (Forward all calls)
[New Canonical Path] ◀────── (All active tests, routes, and imports updated)
```

1. **নতুন ক্যানোনিকাল ফাইল সৃষ্টি:** প্রথমে প্রস্তাবিত নতুন ক্যানোনিকাল পাথে সম্পূর্ণ কোড ও আধুনিক টাইপিংসহ ফাইল তৈরি করা হবে।
2. **কমপ্যাটিবিলিটি শিম (Backward Compatibility Shim):** পুরোনো ফাইলটিকে মুছে ফেলা হবে না; বরং সেটিকে একটি হালকা রি-এক্সপোর্ট শিমে রূপান্তর করা হবে:
   - **TypeScript/React:** `export * from './NewCanonicalFile';`
   - **Python:** `from backend.module.new_canonical import *  # noqa: F401`
3. **কনজিউমার আপডেট:** সমস্ত অ্যাক্টিভ ফ্রন্টএন্ড পেজ, রাউট টেবিল (`backend/api/routers.py`), এবং টেস্ট স্যুটগুলোতে সরাসরি নতুন ক্যানোনিকাল পাথ পয়েন্ট করানো হবে।
4. **ভ্যালিডেশন:** `tsc --noEmit` এবং `pytest` চালিয়ে নিশ্চিত করা হবে যে পুরো কোডবেস শতভাগ ক্লিন ও গ্রিন রয়েছে।
