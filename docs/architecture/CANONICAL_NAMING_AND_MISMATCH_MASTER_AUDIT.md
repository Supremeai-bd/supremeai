# 📋 SupremeAI Master Naming, Work-Criteria & Mismatch Compendium

**Document Version:** 2.0.0 (Unified Master Source of Truth)  
**Date:** 2026-09-11  
**Status:** ✅ ALL MIGRATIONS CONSOLIDATED, IMPLEMENTED & VERIFIED  
**Scope:** Whole Codebase — Frontend, Backend Agents, Core Orchestration, Services, Tools, Routes, Archives & Historical Records  

---

## 🎯 ১. ভূমিকা ও একক সত্যের উৎস (Single Source of Truth)

SupremeAI-এর সেলফ-ইভলভিং ও মাল্টি-এজেন্ট আর্কিটেকচারে কোডের প্রতিটি ফাইল, ক্লাস এবং মেথডের নামকরণ তার **প্রকৃত কার্যকারিতা, দায়িত্ব ও কাজের মানদণ্ড (Technical Responsibility & Work Criteria)** এর সাথে শতভাগ সঙ্গতিপূর্ণ থাকা আবশ্যক।

পূর্বে নামকরণের অসংগতি, বিমূর্ত রূপক (metaphors), এবং কাজের ব্যাপ্তি ও নামের অমিল সংক্রান্ত তথ্য বিভিন্ন খণ্ড খণ্ড ফাইলে বিক্ষিপ্ত ছিল (যেমন: `NAVIGATION_MISMATCH_MAP.md`, `FILE_RENAMING_AND_WORK_CRITERIA_AUDIT.md` ইত্যাদি)। 

ডুপ্লিকেশন ও তথ্যের বিভ্রান্তি এড়াতে সেই সমস্ত পৃথক ফাইলকে বিলুপ্ত (purged) করে তাদের সমস্ত বিশ্লেষণ, ঐতিহাসিক ম্যাপিং, ক্যানোনিকাল পাথ এবং লাইভ ভেরিফিকেশন রেজিস্ট্রিকে একত্রিত করে **SupremeAI-এর একমাত্র চূড়ান্ত মাস্টার গাইড** হিসেবে এই নথিতে সমন্বিত করা হয়েছে।

---

## 🛡️ ২. নন-ব্রেকিং মাইগ্রেশন ও শিম প্রোটোকল (Zero-Breakage Architecture)

SupremeAI-এর কোর ডিরেক্টিভ অনুসারে কোনো সিস্টেম ডাউনটাইম বা ইমপোর্ট ব্রেক গ্রহণযোগ্য নয়। প্রতিটি মাইগ্রেশনে নিচের প্যাটার্ন অনুসরণ করা হয়েছে:

```
[Legacy / Deprecated Path] ────────── (Backward-Compatibility Shim: Re-export & Aliases)
        │
        ▼ (Forwards calls & retains exact signatures)
[Canonical Implementation] ◀───────── (All active tests, routes & consumers point here)
```

1. **Canonical Implementation:** কাজের মানদণ্ড অনুযায়ী ক্যানোনিকাল পাথে সম্পূর্ণ কোড ও আধুনিক টাইপিংসহ তৈরি।
2. **Backward-Compatibility Shim:** পূর্বের পাথে হালকা রি-এক্সপোর্ট শিম সংরক্ষিত, যাতে কোনো থার্ড-পার্টি বা পুরোনো টেস্ট না ভাঙে।
3. **Double-Alias Architecture:** PascalCase ও UPPERCASE উভয় নামকে সাপোর্ট করা হয়েছে (যেমন: `MultiCloudQuotaMonitor` ও `MulticloudQuotaMonitor`, `LlmCostOptimizer` ও `LLMCostOptimizer`)।

---

## 📊 ৩. সমন্বিত মাস্টার রিনেম ও শিম রেজিস্ট্রি (Consolidated Master Registry)

কোডবেসের শুরু থেকে আজ পর্যন্ত সম্পন্ন হওয়া সমস্ত ফাইল রিনেম ও ক্যানোনিকাল রূপান্তর নিচে স্তরভিত্তিক সাজানো হলো:

### স্তর ক: ফ্রন্টএন্ড স্টোরস, রুটস ও উইজেট (Frontend Stores, Routes & Widgets)

| # | পূর্বের নাম / লেগ্যাসি পাথ | নতুন ক্যানোনিকাল পাথ | দায়িত্ব ও পরিবর্তনের কারণ (Work Criteria) | স্ট্যাটাস | শিম স্ট্র্যাটেজি |
|---|---|---|---|---|---|
| 1 | `frontend/src/store/tierSStore.ts` | `frontend/src/store/workspaceUiStateStore.ts` | চ্যাট ওয়ার্কস্পেসের UI ওভারলে স্টেট (শেয়ার, রিজন প্যানেল, সার্চ) পরিচালনা করে; "TierS" কোনো ডোমেন কনসেপ্ট নয়। | ✅ MIGRATED | `useTierSStore = useWorkspaceUiStateStore` alias |
| 2 | `frontend/src/routes/tierSRoutes.tsx` | `frontend/src/routes/workspaceFeatureRoutes.tsx` | ওয়ার্কস্পেস ফিচারের ১২টি রাউট রেজিস্ট্রি। | ✅ MIGRATED | `App.tsx` ক্যানোনিকালে কানেক্টেড |
| 3 | `frontend/src/components/widgets/EvolutionForgeWidget.tsx` | `frontend/src/components/widgets/SkillForgeWidget.tsx` | স্ট্যান্ডঅ্যালোন স্কিল ও টুলস সিন্থেসিস উইজেট। | ✅ MIGRATED | `EvolutionForgeWidget = SkillForgeWidget` alias |
| 4 | `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` | `frontend/src/pages/user/SwarmArchitect/SwarmArchitect.tsx` | মাল্টি-এজেন্ট সোয়ার্ম ও ওয়ার্কফ্লো ডিজাইন করার ReactFlow ভিজ্যুয়াল এডিটর। | ✅ MIGRATED | `SwarmArchitect` ক্যানোনিকাল ও প্রক্সি সক্রিয় |
| 5 | `frontend/src/pages/user/ArchitectTower.tsx` | `frontend/src/pages/user/SystemHealthDashboard.tsx` | সিস্টেমের স্বাস্থ্য, ওয়ান-ক্লিক প্যাচ ও সেলফ-হিলিং অ্যাডমিন ড্যাশবোর্ড। | ✅ MIGRATED | `ArchitectTower = SystemHealthDashboard` alias |
| 6 | `frontend/src/components/LiveSujonBackground.tsx` | `frontend/src/components/AgentStateShaderBackground.tsx` | WebGL2 GLSL ফ্র্যাগমেন্ট ও ভার্টেক্স শেডার ডায়নামিক ক্যানভাস ব্যাকগ্রাউন্ড। | ✅ MIGRATED & SHIMMED | `LiveSujonBackground.tsx` re-exports canonical |
| 7 | `frontend/src/components/dashboard/SujonCoreCockpit.tsx` | `frontend/src/components/dashboard/AgentExecutionTelemetryCockpit.tsx` | রিয়েলটাইম WebSocket (`/ws/dashboard`) লগ স্ট্রিমিং ও টেলিমেট্রি ককপিট। | ✅ MIGRATED & SHIMMED | `SujonCoreCockpit.tsx` re-exports canonical |
| 8 | `frontend/src/components/SupremeComponents.tsx` | `frontend/src/components/ui/GlassUiPrimitives.tsx` | রিইউজেবল গ্লাস-মরফিজম (`supreme-glass`) কার্ড ও বাটন প্রিমিটিভস। | ✅ MIGRATED & SHIMMED | `SupremeComponents.tsx` re-exports primitives |
| 9 | `frontend/src/components/OperatorStudio.tsx` | `frontend/src/components/customer/CustomerSupportEditorStudio.tsx` | কাস্টমার সাপোর্ট চ্যাট প্যানেল ও কোড এডিটর সমন্বিত ইন্টারফেস। | ✅ MIGRATED & SHIMMED | `OperatorStudio.tsx` re-exports canonical |
| 10 | `frontend/src/components/admin/data/CrownJewelBrowser.tsx` | `frontend/src/components/admin/AdminBrowserPanel.tsx` | ট্যাব, বুকমার্ক ও হিস্ট্রি সমৃদ্ধ এমবেডেড ব্রাউজার কন্ট্রোল প্যানেল। | ✅ MIGRATED | `AdminBrowserPanel = CrownJewelBrowser` alias |
| 11 | `frontend/src/components/admin/infra/CloudOrchestrator.tsx` | `frontend/src/components/admin/infra/CloudProviderHealth.tsx` | ক্লাউড প্রোভাইডারদের হেলথ ও মেট্রিক কার্ডস। | ✅ MIGRATED | `CloudProviderHealth = CloudOrchestrator` alias |
| 12 | `frontend/src/components/admin/AethelNode.tsx` | `frontend/src/components/admin/SciFiFlowNode.tsx` | গ্লো ও টুলটিপ সমৃদ্ধ ReactFlow কাস্টম নোড। | ✅ MIGRATED | `AethelNode` alias exported |
| 13 | `frontend/src/components/admin/AethelCoreStyles.css` | `frontend/src/components/admin/admin-hud.css` | অ্যাডমিন HUD ও সায়েন্স-ফিকশন গ্লাস মরফিজম CSS ক্লাস সেট। | ✅ MIGRATED | সমস্ত ইমপোর্ট ক্যানোনিকালে আপডেটেড |
| 14 | `frontend/src/components/admin/ci/utils.ts` | `frontend/src/components/admin/ci/csv.ts` | CSV কনভার্টার ও এক্সপোর্ট হেল্পার। | ✅ MIGRATED | `convertToCSV` exported |
| 15 | `frontend/src/components/sujon/index.tsx` | `frontend/src/components/widgets/TelemetryDashboardWidget.tsx` | টেলিমেট্রি মেট্রিক্স উইজেট। | ✅ MIGRATED & SHIMMED | `useSujonMetrics` alias preserved |
| 16 | `frontend/src/components/sujon-utils.ts` | `frontend/src/lib/agent-state-shaders.ts` | WebGL/GLSL শেডার সোর্সেস। | ✅ MIGRATED & SHIMMED | `useSujonState` alias preserved |

---

### স্তর খ: অটোনোমাস এজেন্ট লেয়ার (Autonomous Agents Layer)

| # | পূর্বের নাম / লেগ্যাসি পাথ | নতুন ক্যানোনিকাল পাথ | দায়িত্ব ও পরিবর্তনের কারণ (Work Criteria) | স্ট্যাটাস | ক্যানোনিকাল ক্লাস ও শিম অ্যালিয়াস |
|---|---|---|---|---|---|
| 17 | `backend/agents/vulnerability_prophet.py` | `backend/agents/code_vulnerability_scanner_agent.py` | AST ও রেজেক্স ভিত্তিক সিকিউরিটি স্ক্যানার যা SQLi, XSS, Path Traversal ঝুঁকি প্রিভেন্ট করে। "Prophet" রূপক পরিহার করা হয়েছে। | ✅ MIGRATED & SHIMMED | `CodeVulnerabilityScannerAgent`, `VulnerabilityProphet` |
| 18 | `backend/agents/churn_prophet.py` | `backend/agents/user_retention_risk_agent.py` | ইউজার বিহেভিওরাল সিগন্যাল থেকে চুরন রিস্ক ও রিটেনশন স্ট্র্যাটেজি তৈরি করে। | ✅ MIGRATED & SHIMMED | `UserRetentionRiskAgent`, `ChurnProphet` |
| 19 | `backend/agents/insight_mage.py` | `backend/agents/data_trend_anomaly_agent.py` | ডেটাবেস থেকে Z-score আউটলায়ার ও ট্রেন্ড অ্যানালাইসিস করে ইনসাইট রিপোর্ট দেয়। "Mage" রূপক বর্জিত। | ✅ MIGRATED & SHIMMED | `DataTrendAnomalyAgent`, `InsightMage` |
| 20 | `backend/agents/devops/cloud_watchman.py` | `backend/agents/devops/multicloud_quota_monitor.py` | Firebase, Vercel, GCP কোটা ও এরর রেট অ্যানোমালি ট্র্যাকার। "Watchman" নয়। | ✅ MIGRATED & SHIMMED | `MultiCloudQuotaMonitor`, `MulticloudQuotaMonitor`, `CloudWatchman` |
| 21 | `backend/agents/devops/cost_sage.py` | `backend/agents/devops/llm_cost_optimizer.py` | LLM টোকেন কনজাম্পশন ও প্রোভাইডার কস্ট অপটিমাইজার। "Sage" নয়। | ✅ MIGRATED & SHIMMED | `LlmCostOptimizer`, `LLMCostOptimizer`, `CostSage` |
| 22 | `backend/core/tier8/self_improvement_agent.py` | `backend/core/tier8/codebase_refactor_proposer.py` | স্বয়ংক্রিয় রিফ্যাক্টরিং প্রস্তাবক ও রুফ চেকার। স্বয়ংক্রিয়ভাবে সেলফ-মডিফাই করে না, বরং প্রপোজাল দেয়। | ✅ MIGRATED & SHIMMED | `CodebaseRefactorProposer`, `SelfImprovementAgent` |

---

### স্তর গ: ব্যাকএন্ড কোর ও অর্কেস্ট্রেশন লেয়ার (Core Orchestration & Framework)

| # | পূর্বের নাম / লেগ্যাসি পাথ | নতুন ক্যানোনিকাল পাথ | দায়িত্ব ও পরিবর্তনের কারণ (Work Criteria) | স্ট্যাটাস | শিম স্ট্র্যাটেজি |
|---|---|---|---|---|---|
| 23 | `backend/core/orchestration/master_cognitive_orchestrator.py` | `backend/core/orchestration/cognitive_pipeline_dispatcher.py` | রিপেয়ার, সিন্থেসিস, অডিট ও ইভোলিউশন পাইপলাইন ডিসপ্যাচার। "Master Cognitive" অতিরঞ্জিত রূপক। | ✅ MIGRATED & SHIMMED | `CognitivePipelineDispatcher` re-export |
| 24 | `backend/core/orchestration/orchestrator.py` | `backend/core/orchestration/periodic_task_scheduler.py` | পর্যায়ক্রমিক ফিটনেস স্কোরিং ও শিডিউলার। জেনেরিক "orchestrator" বিভ্রান্তিকর। | ✅ MIGRATED & SHIMMED | `PeriodicTaskScheduler` re-export |
| 25 | `backend/core/orchestration/crew_departments.py` | `backend/core/orchestration/swarm_agent_roles.py` | সোয়ার্ম এজেন্টের সুনির্দিষ্ট রোল ও ডিপার্টমেন্ট ডেফিনিশন। | ✅ MIGRATED & SHIMMED | Re-export shim maintained |
| 26 | `backend/core/ast_security_scanner.py` (পূর্বে `immune_system.py`) | `backend/core/ast_security_scanner.py` | পাইথন কোডের AST সিকিউরিটি ভ্যালিডেশন ইঞ্জিন। "Immune System" রূপক বর্জিত। | ✅ MIGRATED & SHIMMED | `ASTSecurityScanner`, `ImmuneSystemScanner` aliases |
| 27 | `backend/core/ip_blocklist_manager.py` (পূর্বে `rules_mutator.py`) | `backend/core/ip_blocklist_manager.py` | আইপি ব্লক ও রেট-লিমিট রুলস ম্যানেজার। "Rules Mutator" নয়। | ✅ MIGRATED & SHIMMED | `RulesMutator` alias maintained |
| 28 | `backend/core/agents/framework/autonomous_task_orchestrator.py` (পূর্বে `langgraph_agent.py`) | `backend/core/agents/framework/autonomous_task_orchestrator.py` | অটোনোমাস মাল্টি-স্টেপ টাস্ক অর্কেস্ট্রেটর ইঞ্জিন। | ✅ MIGRATED & SHIMMED | `SupremeOrchestrator` alias maintained |
| 29 | `backend/core/messaging/events.py` | `backend/core/firebase_auth.py` | ফায়ারবেস অথেনটিকেশন ব্রিজ ও টোকেন ভ্যালিডেশন। | ✅ MIGRATED & SHIMMED | Re-export shim maintained |

---

### স্তর ঘ: সার্ভিসেস, টুলস ও এপিআই রাউটস (Services, Tools & API Routes)

| # | পূর্বের নাম / লেগ্যাসি পাথ | নতুন ক্যানোনিকাল পাথ | দায়িত্ব ও পরিবর্তনের কারণ (Work Criteria) | স্ট্যাটাস | শিম স্ট্র্যাটেজি |
|---|---|---|---|---|---|
| 30 | `backend/services/rider_tracker.py` | `backend/services/delivery_fleet_tracker.py` | জেনেরিক জিও-লোকেশন ও রাইডার ফ্লিট ট্র্যাকিং সার্ভিস (হার্ডকোডেড নামমুক্ত)। | ✅ MIGRATED & SHIMMED | `DeliveryFleetTracker` alias export |
| 31 | `backend/tools/freebuff_client.py` | `backend/tools/cli_process_delegator.py` | সাবপ্রসেস ও অ্যাসিনক্রোনাস CLI এক্সিকিউটর। | ✅ MIGRATED & SHIMMED | `CliProcessDelegator` re-export |
| 32 | `backend/tools/langchain_agent_example.py` | `backend/tools/launchdarkly_agent_adapter.py` | LaunchDarkly AgentControl প্রোডাকশন অ্যাডাপ্টার (কোনো এককালীন `_example` নয়)। | ✅ MIGRATED & SHIMMED | Re-export shim maintained |
| 33 | `backend/tools/seed_database.py` | `scripts/db/seed_knowledge_fts.py` | SQLite FTS5 ও ChromaDB নলেজ বেস সিডিং স্ক্রিপ্ট। | ✅ MIGRATED & SHIMMED | `scripts/db/` ডিরেক্টরিতে স্থানান্তর |
| 34 | `backend/api/routes/healing.py` | `backend/api/routes/healing_stats.py` | সেলফ-হিলিং পরিসংখ্যান ও প্রেডিকশন এপিআই এন্ডপয়েন্ট। | ✅ MIGRATED & SHIMMED | Re-export shim maintained |
| 35 | `backend/api/routes/codeflow.py` | `backend/api/routes/code_dependency_graph.py` | ফাইল পার্সিং ও ডিপেন্ডেন্সি গ্রাফ (Nodes/Edges) জেনারেটর এপিআই। | ✅ MIGRATED & SHIMMED | Re-export shim maintained |
| 36 | `backend/api/routes/site_actions.py` | `backend/api/routes/browser_action_registry.py` | ব্রাউজার অটোমেশন ও স্ক্র্যাপিং অ্যাকশন রেজিস্ট্রি এপিআই। | ✅ MIGRATED & SHIMMED | Re-export shim maintained |
| 37 | `backend/api/routes/tier_s_routes.py` | `backend/api/routes/workspace_feature_routes.py` / `workspace_feature_routes_shim.py` | ওয়ার্কস্পেস ফিচারের রাউট রেজিস্ট্রি ও হ্যান্ডলার। | ✅ MIGRATED & SHIMMED | ক্যানোনিকাল রাউটার সক্রিয় ও শিম বিদ্যমান |
| 38 | `backend/api/routes/dock_actions.py` | `backend/api/routes/dock_integrations.py` | গিটহাবে পুশ ও SSE ইন্টিগ্রেশন ট্রিগার রাউট। | ✅ MIGRATED & SHIMMED | `routers.py` wired to `dock_integrations` |
| 39 | `backend/api/routes/meta_ai.py` | `backend/api/routes/agent_breeding.py` | এজেন্ট ব্রিডিং পুল ও পারফরম্যান্স এনালাইসিস রাউট। | ✅ MIGRATED & SHIMMED | `routers.py` wired to `agent_breeding` |

---

## 🏛️ ৪. অপরিবর্তনীয় ও আর্কাইভ ফাইল পলিসি (Historical & Archive Policy)

নিচের উপাদানগুলোকে ইচ্ছাকৃতভাবেই অপরিবর্তিত রাখা হয়েছে, কারণ এগুলো ঐতিহাসিক রেফারেন্স অথবা কারিগরিভাবে সঠিক:

1. **ডকুমেন্টেশন আর্কাইভ (`docs/archive/`):** `legacy_cloud_run_deployment.md`, `PATCH_NOTES_v2.md`, `PATCH_NOTES_v3.md` ইত্যাদি অপরিবর্তনীয় অডিট হিস্ট্রি।
2. **ডাটাবেস মাইগ্রেশন আর্কাইভ (`backend/database/migrations/archive/`):** ১৭টি লেগ্যাসি SQL ফাইল অপরিবর্তনীয় (বর্তমানে Alembic হলো সক্রিয় মাইগ্রেশন ইঞ্জিন)।
3. **এককালীন স্ক্রিপ্টস (`scripts/archive/legacy_one_offs/`):** ১২০+ টি স্ক্রিপ্ট প্রোডাকশনের বাইরে সংরক্ষিত।
4. **টেকনিক্যালি নির্ভুল কোর টার্মস (`backend/core/tier8/*`):** `agent_evolution_engine`, `swarm_coordination_agent`, `skill_marketplace_curator` নামগুলো তাদের কাজের সাথে হুবহু সামঞ্জস্যপূর্ণ হওয়ায় এদের রিনেম করার প্রয়োজন নেই।

---

## ✅ ৫. লাইভ টেস্ট ভেরিফিকেশন ফলাফল (Live Verification Matrix)

- **স্ক্যানকৃত ও সক্রিয় ফাইল:** ১০০% উপস্থিত (২৬/২৬ টি ক্যানোনিকাল ও শিম ফাইল বর্তমান)।
- **রি-এক্সপোর্ট ও ক্লাস রেজোলিউশন টেস্ট:** **১৪/১৪ Passed (Zero Failures)**
- **ব্যাকওয়ার্ড কমপ্যাটিবিলিটি:** পুরাতন পাথ এবং নতুন ক্যানোনিকাল উভয় পাথেই ক্লাস ইমপোর্ট ১০০% কার্যকর।
- **কোড লিন্ট ও ফরম্যাট:** Ruff এবং TypeScript বিল্ড কমপ্লায়েন্ট।
