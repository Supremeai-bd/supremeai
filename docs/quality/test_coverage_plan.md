# 🧪 SupremeAI 2.0 — Test Coverage Master Plan

এই ডকুমেন্টে প্রজেক্টের বর্তমান টেস্ট কভারেজ স্থিতি, ইতিমধ্যে যুক্ত থাকা টেস্ট কেসসমূহ এবং কোডবেসকে ১০০% নিখুঁত করতে যে যে টেস্টগুলো আরও যুক্ত করা প্রয়োজন তা তালিকাভুক্ত করা হলো।

> [!NOTE]
> **টেস্ট রান তথ্য:** Python 3.11.15, pytest-9.1.1 | rootdir: `backend/` | **মোট collected: 2570 items**
> **শেষ আপডেট:** 2026-07-20 11:43 BDT | টেস্ট সুইট: ✅ Collection errors মুক্ত | `test_lifespan.py` এর সকল ফেইলিওর ফিক্স করা হয়েছে (৮/৮ পাস)।

---

## 📊 সারসংক্ষেপ (Coverage Summary)

| মেট্রিক | মান |
|---------|-----|
| মোট টেস্ট ফাইল (backend/tests/) | **285+ ফাইল** |
| মোট টেস্ট ফাইল (root/tests/) | **25 ফাইল** |
| Admin test files | **1 ফাইল** |
| মোট collected টেস্ট (সর্বশেষ রান) | **3211** (3084 passed, 127 skipped) |
| Collection Error | **0** |
| **প্রকৃত রিপো-ওয়াইড কভারেজ (combined: core+api+tools+ws+workers)** | **~51%** (2026-08-13 মাপা) |
| আগের ভুল মাপ: শুধু `core/` এর কভারেজ | **~38%** (ব্লাইন্ড স্পট ছিল) |
| CI গেট (combined) | **≥ 30%** (ধাপে ধাপে 40→50→60-এ তোলার পরিকল্পনা) |
| ব্যর্থ (F) টেস্ট | **0** (সর্বশেষ রান) |
| Skip (s) টেস্ট | **127** |

> [!IMPORTANT]
> **2026-08-13 আপডেট (AUDIT-কভারেজ-স্কোপ):** আগে coverage শুধু `backend/core/` মাপা হতো
> (`source = ["core"]`), ফলে `api/`, `tools/`, `ws/`, `workers/` প্যাকেজের প্রকৃত
> লাইন-কভারেজ কখনো গণনা হতো না — এটি একটি বড় ব্লাইন্ড স্পট ছিল। এখন coverage source
> বাড়িয়ে `core, api, tools, ws, workers` করা হয়েছে এবং স্কোপ-বাড়ানোর পর প্রকৃত
> রিপো-ওয়াইড কভারেজ দাঁড়িয়েছে **~51%**। সুতরাং পুরানো "~92.7%" সংখ্যাটি ভুল ছিল
> (সেটি ছিল pass rate, coverage নয়)। CI গেট সাময়িকভাবে 30-এ রাখা হয়েছে।

---

## ✅ ১. বিদ্যমান টেস্টসমূহ (Tests Already Added)

### 🔷 A. Backend Core Module Tests (`backend/tests/core/`)

| # | ফাইল | কভার করে | স্ট্যাটাস |
|---|------|----------|-----------|
| 1 | `test_agent_factory.py` | `core/agent_factory.py` | ✅ পাস |
| 2 | `test_cache_optimization.py` | `core/cache/` | ✅ পাস |
| 3 | `test_config_proxy.py` | `core/config_proxy.py` | ⚠️ ফেইল |
| 4 | `test_container_auditor.py` | `core/container_auditor.py` | ✅ পাস |
| 5 | `test_core_missing_coverage.py` | core বিভিন্ন মডিউল | ⚠️ ফেইল |
| 6 | `test_cost_guard.py` | `core/cost_guard.py` | ✅ পাস |
| 7 | `test_cost_guard_coverage.py` | `core/cost_guard.py` বিস্তারিত | ✅ পাস |
| 8 | `test_database_async_proxy.py` | DB async proxy | ✅ পাস |
| 9 | `test_enum_guard.py` | `core/enum_guard.py` | ✅ পাস |
| 10 | `test_event_bus_coverage.py` | Event bus | ✅ পাস |
| 11 | `test_integration_phase3.py` | Phase 3 integration | ✅ পাস |
| 12 | `test_knowledge_base.py` | `core/knowledge_base.py` | ✅ পাস |
| 13 | `test_log_batcher.py` | `core/observability/log_batcher.py` | ✅ পাস |
| 14 | `test_nats_messaging.py` | `core/messaging/` NATS | ⚠️ ফেইল |
| 15 | `test_orchestrators_crew.py` | `core/orchestration/crew_departments.py` | ✅ পাস |
| 16 | `test_playwright_manager.py` | `core/playwright_manager.py` | ✅ পাস |
| 17 | `test_pubsub.py` | `core/swarm_pubsub.py` | ⚠️ ফেইল |
| 18 | `test_security_vault.py` | `core/security/security_vault.py` | ✅ পাস |
| 19 | `test_self_healer.py` | Self-healing engine | ✅ পাস |
| 20 | `test_swarm_orchestrator.py` | `core/orchestration/swarm_orchestrator.py` | ✅ পাস |
| 21 | `test_swarm_orchestrator_coverage.py` | Swarm orchestrator বিস্তারিত | ⚠️ ফেইল |
| 22 | `test_swarm_pubsub.py` | `core/swarm_pubsub.py` | ✅ পাস |

### 🔷 B. Backend Main Tests (`backend/tests/`)

| # | ফাইল | কভার করে | স্ট্যাটাস |
|---|------|----------|-----------|
| 23 | `test_lifespan.py` | `core/lifespan.py` | ✅ পাস |
| 24 | `test_adaptive_engine.py` | `adaptive_engine/` | ✅ পাস |
| 24 | `test_admin_god.py` | `core/admin_god.py` admin routes | ✅ পাস |
| 25 | `test_admin_models.py` | Admin models | ✅ পাস |
| 26 | `test_admin_routes.py` | `core/admin_routes.py` | ✅ পাস |
| 27 | `test_advanced.py` | Advanced features | ✅ পাস |
| 28 | `test_agent_department.py` | Agent departments | ✅ পাস |
| 29 | `test_agent_departments.py` | Agent departments বিস্তারিত | ✅ পাস |
| 30 | `test_agent_orchestrator.py` | `core/orchestration/agent_orchestrator.py` | ✅ পাস |
| 31 | `test_api.py` | API endpoints | ⚠️ ফেইল |
| 32 | `test_api_chat.py` | Chat API | ✅ পাস |
| 33 | `test_api_keys.py` | API key management | ✅ পাস |
| 34 | `test_api_new_endpoints.py` | নতুন endpoints | ✅ পাস |
| 35 | `test_api_router.py` | API router | ✅ পাস |
| 36 | `test_approval_manager.py` | Approval workflow | ✅ পাস |
| 37 | `test_audit_logger.py` | `core/observability/audit_logger.py` | ✅ পাস |
| 38 | `test_auth_middleware.py` | `core/security/auth_middleware.py` | ⚠️ ফেইল |
| 39 | `test_auth_routes.py` | Auth routes | ✅ পাস |
| 40 | `test_auto_fix_trigger.py` | Auto fix trigger | ✅ পাস |
| 41 | `test_autonomous_agent.py` | Autonomous agent | ✅ পাস |
| 42 | `test_bangla_nlp.py` | Bangla NLP | ✅ পাস |
| 43 | `test_bangla_voice.py` | Bangla voice | ✅ পাস |
| 44 | `test_billing_api_integration.py` | Billing API integration | ⚠️ ফেইল |
| 45 | `test_billing_system.py` | Billing system | ✅ পাস |
| 46 | `test_brain.py` | Brain module | ✅ পাস |
| 47 | `test_browser_credentials.py` | Browser credentials | ✅ পাস |
| 48 | `test_byoc_endpoints.py` | BYOC endpoints | ✅ পাস |
| 49 | `test_chaos_worker.py` | `workers/chaos_worker.py` | ✅ পাস |
| 50 | `test_checkpoint_resume.py` | Checkpoint/resume | ✅ পাস |
| 51 | `test_circuit_breaker.py` | `core/resilience/circuit_breaker.py` | ✅ পাস |
| 52 | `test_cloud_sandbox.py` | Cloud sandbox | ✅ পাস |
| 53 | `test_cloud_storage.py` | `core/cloud_storage.py` | ✅ পাস |
| 54 | `test_code_validator.py` | `core/code_validator.py` | ✅ পাস |
| 55 | `test_collaborative_editor.py` | Collaborative editor | ✅ পাস |
| 56 | `test_config.py` | `core/config.py` | ⚠️ ফেইল |
| 57 | `test_config_additional.py` | Config অতিরিক্ত | ✅ পাস |
| 58 | `test_config_cache.py` | `core/config_cache.py` | ⚠️ ফেইল |
| 59 | `test_config_coverage.py` | Config বিস্তারিত কভারেজ | ✅ পাস |
| 60 | `test_constants.py` | `core/constants.py` | ✅ পাস |
| 61 | `test_context_and_actions.py` | Context & actions | ✅ পাস |
| 62 | `test_core.py` | Core মডিউল | ✅ পাস |
| 63 | `test_core_knowledge_qa.py` | Knowledge QA | ✅ পাস |
| 64 | `test_core_smoke.py` | Core smoke tests | ✅ পাস |
| 65 | `test_coverage_gaps.py` | Coverage gaps | ⚠️ ফেইল |
| 66 | `test_crew_mcp.py` | Crew MCP integration | ✅ পাস |
| 67 | `test_database_storage_client.py` | DB storage client | ✅ পাস |
| 68 | `test_db_repository.py` | `core/db_repository.py` | ✅ পাস |
| 69 | `test_docker_sandbox.py` | Docker sandbox | ✅ পাস |
| 70 | `test_e2e.py` | End-to-end | ⚠️ ফেইল |
| 71 | `test_e2e_media.py` | E2E media | ✅ পাস |
| 72 | `test_email_agent.py` | Email agent | ✅ পাস |
| 73 | `test_email_service.py` | `core/email_service.py` | ✅ পাস |
| 74 | `test_episodic_memory.py` | Episodic memory | ✅ পাস |
| 75 | `test_error_remediation.py` | `core/error_remediation.py` | ⚠️ ফেইল |
| 76 | `test_evolution_engine.py` | Evolution engine | ⚠️ ফেইল |
| 77 | `test_evolution_pipeline.py` | Evolution pipeline | ⚠️ ফেইল |
| 78 | `test_factual_verifier.py` | `core/factual_verifier.py` | ✅ পাস |
| 79 | `test_feedback_loop.py` | `core/feedback_loop.py` | ✅ পাস |
| 80 | `test_firebase_integration.py` | Firebase integration | ✅ পাস |
| 81 | `test_fitness_engine.py` | Fitness engine | ⚠️ ফেইল |
| 82 | `test_free_tier_tracker.py` | `core/llm/free_tier_tracker.py` | ✅ পাস |
| 83 | `test_gcp_integration.py` | GCP integration | ✅ পাস |
| 84 | `test_generation_monitor.py` | `core/generation_monitor.py` | ✅ পাস |
| 85 | `test_github_agent.py` | GitHub agent | ⚠️ ফেইল |
| 86 | `test_graph_routes.py` | Graph routes | ✅ পাস |
| 87 | `test_graph_service.py` | Graph service | ⚠️ ফেইল |
| 88 | `test_hallucination_guard.py` | Hallucination guard | ✅ পাস |
| 89 | `test_health.py` | Health endpoints | ✅ পাস |
| 90 | `test_health_monitor.py` | Health monitor | ✅ পাস |
| 91 | `test_health_monitor_routes.py` | Health monitor routes | ✅ পাস |
| 92 | `test_honeypot_middleware.py` | `core/security/honeypot_middleware.py` | ✅ পাস |
| 93 | `test_idempotency_middleware.py` | `core/idempotency_middleware.py` | ✅ পাস |
| 94 | `test_immune_system.py` | `core/immune_system.py` | ⚠️ ফেইল |
| 95 | `test_immune_system_scanner.py` | Immune system scanner | ✅ পাস |
| 96 | `test_input_sanitizer.py` | `core/security/input_sanitizer.py` | ✅ পাস |
| 97 | `test_knowledge_qa.py` | `services/knowledge_qa.py` | ⚠️ ফেইল |
| 98 | `test_language_router.py` | `core/language_router.py` | ✅ পাস |
| 99 | `test_llm_gateway.py` | `core/llm/llm_gateway.py` | ✅ পাস |
| 100 | `test_llm_gateway_coverage.py` | LLM gateway বিস্তারিত | ✅ পাস |
| 101 | `test_long_term_memory.py` | Long-term memory | ✅ পাস |
| 102 | `test_markdown_export.py` | Markdown export | ✅ পাস |
| 103 | `test_marketplace_agent.py` | Marketplace agent | ✅ পাস |
| 104 | `test_mcp_allowlist.py` | `core/mcp_allowlist.py` | ✅ পাস |
| 105 | `test_mcp_server.py` | MCP server | ✅ পাস |
| 106 | `test_mcp_servers_integration.py` | MCP servers integration (84KB!) | ✅ পাস |
| 107 | `test_media_r2.py` | Media R2 storage | ✅ পাস |
| 108 | `test_meta_ai.py` | Meta AI | ✅ পাস |
| 109 | `test_middleware_chaos_injector.py` | `middleware/chaos_injector.py` | ✅ পাস |
| 110 | `test_migrations.py` | DB migrations | ✅ পাস |
| 111 | `test_migrations_and_onboarding.py` | Migrations & onboarding | ✅ পাস |
| 112 | `test_mobile_e2e.py` | Mobile E2E | ✅ পাস |
| 113 | `test_model_registry.py` | Model registry | ✅ পাস |
| 114 | `test_model_router_unit.py` | Model router | ✅ পাস |
| 115 | `test_model_trainer.py` | Model trainer | ✅ পাস |
| 116 | `test_models_ci_report.py` | Models CI report | ✅ পাস |
| 117 | `test_models_evolution.py` | Models evolution | ✅ পাস |
| 118 | `test_monitoring.py` | Monitoring | ✅ পাস |
| 119 | `test_multi_account_rotator.py` | Multi-account rotator | ✅ পাস |
| 120 | `test_multicloud.py` | Multi-cloud | ✅ পাস |
| 121 | `test_new_endpoints_sprint5.py` | Sprint 5 endpoints | ⚠️ ফেইল |
| 122 | `test_new_interfaces.py` | New interfaces | ✅ পাস |
| 123 | `test_new_localization_analytics.py` | Localization analytics | ✅ পাস |
| 124 | `test_new_tools_sprint5.py` | Sprint 5 tools | ✅ পাস |
| 125 | `test_optimization_engine.py` | Optimization engine | ✅ পাস |
| 126 | `test_output_validator.py` | `core/output_validator.py` | ✅ পাস |
| 127 | `test_parallel_agent_executor.py` | Parallel agent executor | ✅ পাস |
| 128 | `test_payments.py` | Payments | ✅ পাস |
| 129 | `test_performance_aware_router.py` | Performance-aware router | ✅ পাস |
| 130 | `test_pgbouncer_pool.py` | `core/pgbouncer_pool.py` | ⚠️ ফেইল |
| 131 | `test_posthog.py` | `core/observability/posthog_client.py` | ✅ পাস |
| 132 | `test_pr_dry_run.py` | PR dry run | ✅ পাস |
| 133 | `test_pr_reviewer.py` | PR reviewer | ✅ পাস |
| 134 | `test_prod_docs_security.py` | Prod docs security | ⚠️ ফেইল |
| 135 | `test_production_readiness_integration.py` | Production readiness | ✅ পাস |
| 136 | `test_prompt_firewall.py` | `core/security/prompt_firewall.py` | ✅ পাস |
| 137 | `test_prompt_handler.py` | `core/prompt_handler.py` | ✅ পাস |
| 138 | `test_rag.py` | RAG pipeline | ✅ পাস |
| 139 | `test_rbac.py` | `core/security/rbac.py` | ⚠️ ফেইল |
| 140 | `test_reasoning_orchestrator.py` | Reasoning orchestrator | ✅ পাস |
| 141 | `test_reliability_plane.py` | Reliability plane | ✅ পাস |
| 142 | `test_repo_discovery.py` | Repo discovery | ✅ পাস |
| 143 | `test_resource_catalog.py` | Resource catalog | ✅ পাস |
| 144 | `test_rlhf.py` | RLHF (Reinforcement Learning) | ✅ পাস |
| 145 | `test_saga.py` | SAGA pattern | ✅ পাস |
| 146 | `test_sandbox_orchestration_run.py` | Sandbox orchestration | ✅ পাস |
| 147 | `test_schema_validator.py` | `core/schema_validator.py` | ✅ পাস |
| 148 | `test_secret_vault.py` | `core/security/secret_vault.py` | ✅ পাস |
| 149 | `test_secure_credential_store.py` | `core/security/secure_credential_store.py` | ✅ পাস |
| 150 | `test_security_middleware.py` | Security middleware | ✅ পাস |
| 151 | `test_security_regression.py` | Security regression | ✅ পাস |
| 152 | `test_self_evolution_agent.py` | Self-evolution agent | ✅ পাস |
| 153 | `test_session_takeover.py` | Session takeover | ✅ পাস |
| 154 | `test_simulator_browser_api.py` | Browser simulator API | ✅ পাস |
| 155 | `test_skill_graph.py` | Skill graph | ✅ পাস |
| 156 | `test_skill_recommender.py` | Skill recommender | ✅ পাস |
| 157 | `test_sliding_window_memory.py` | Sliding window memory | ✅ পাস |
| 158 | `test_sprint_c_tools.py` | Sprint C tools | ⚠️ ফেইল |
| 159 | `test_sprint_g.py` | Sprint G | ✅ পাস |
| 160 | `test_stealth_networking.py` | Stealth networking | ✅ পাস |
| 161 | `test_stream.py` | Stream | ⚠️ ফেইল |
| 162 | `test_style_learner.py` | Style learner | ✅ পাস |
| 163 | `test_supabase_schema_bootstrap.py` | Supabase schema bootstrap | ⚠️ ফেইল |
| 164 | `test_supabase_store.py` | Supabase store | ✅ পাস |
| 165 | `test_task_endpoints.py` | Task endpoints | ✅ পাস |
| 166 | `test_task_queue.py` | `core/queue/task_queue_enhanced.py` | ✅ পাস |
| 167 | `test_task_router.py` | `core/queue/task_router.py` | ✅ পাস |
| 168 | `test_telegram_bot.py` | Telegram bot | ✅ পাস |
| 169 | `test_telemetry.py` | `core/observability/telemetry.py` | ✅ পাস |
| 170 | `test_tenant_rate_limiter.py` | `middleware/tenant_rate_limiter.py` | ⚠️ ফেইল |
| 171 | `test_tier8.py` | Tier8 | ✅ পাস |
| 172 | `test_universal_rules.py` | `core/universal_rules.py` | ✅ পাস |
| 173 | `test_upstash_redis.py` | Upstash Redis | ⚠️ ফেইল |
| 174 | `test_uss.py` | USS | ✅ পাস |
| 175 | `test_video_generator.py` | Video generator | ⚠️ ফেইল |
| 176 | `test_vision_agent.py` | Vision agent | ✅ পাস |
| 177 | `test_voice_stream.py` | Voice stream | ✅ পাস |
| 178 | `test_vpn_switcher.py` | VPN switcher | ✅ পাস |
| 179 | `test_vscode_e2e.py` | VS Code E2E | ✅ পাস |
| 180 | `test_web_fallback.py` | Web fallback | ⚠️ ফেইল |
| 181 | `test_worker_discovery.py` | Worker discovery | ✅ পাস |

### 🔷 C. Sub-domain Tests (`backend/tests/` উপডিরেক্টরি)

| # | ফাইল | কভার করে | স্ট্যাটাস |
|---|------|----------|-----------|
| 182 | `adaptive_engine/test_learning_loop.py` | Learning loop | ✅ পাস |
| 183 | `adaptive_engine/test_platform_learner.py` | Platform learner | ✅ পাস |
| 184 | `agents/test_ephemeral_executor.py` | `agents/ephemeral_executor.py` | ✅ পাস |
| 185 | `api/test_admin.py` | Admin API | ✅ পাস |
| 186 | `api/test_swarm_routes.py` | Swarm routes | ⚠️ ফেইল |
| 187 | `byoc/test_cloud_connector.py` | Cloud connector | ✅ পাস |
| 188 | `byoc/test_container_orchestrator.py` | Container orchestrator | ✅ পাস |
| 189 | `byoc/test_resource_manager.py` | Resource manager | ✅ পাস |
| 190 | `engine/test_cost_optimizer.py` | Cost optimizer | ✅ পাস |
| 191 | `middleware/test_anti_hacking.py` | `middleware/anti_hacking.py` | ✅ পাস |
| 192 | `monitoring/test_cost_auditor.py` | Cost auditor | ✅ পাস |
| 193 | `p2p/test_credit_system.py` | P2P credit system | ✅ পাস |
| 194 | `p2p/test_secure_tunnel.py` | P2P secure tunnel | ✅ পাস |
| 195 | `scout/test_knowledge_extractor.py` | Knowledge extractor | ✅ পাস |
| 196 | `scout/test_web_crawler_agent.py` | Web crawler agent | ✅ পাস |

### 🔷 D. Root-level Tests (`tests/` ডিরেক্টরি)

| # | ফাইল | কভার করে |
|---|------|----------|
| 197 | `test_adversarial_security.py` | Adversarial security |
| 198 | `test_agents_churn_prophet.py` | `agents/churn_prophet.py` |
| 199 | `test_agents_insight_mage.py` | `agents/insight_mage.py` |
| 200 | `test_agents_skill_ingestor.py` | `agents/skill_ingestor.py` |
| 201 | `test_agents_skill_librarian.py` | `agents/skill_librarian.py` |
| 202 | `test_core_config.py` | Core config |
| 203 | `test_core_error_handling.py` | Core error handling |
| 204 | `test_core_feedback.py` | Core feedback |
| 205 | `test_core_immune_system.py` | Core immune system |
| 206 | `test_core_language_router.py` | Core language router |
| 207 | `test_core_output_validator.py` | Core output validator |
| 208 | `test_core_rate_limiter.py` | Core rate limiter |
| 209 | `test_core_sandbox.py` | Core sandbox |
| 210 | `test_doc_summarizer_run.py` | Doc summarizer |
| 211 | `test_e2e_chat.py` | E2E chat |
| 212 | `test_ephemeral_executor.py` | Ephemeral executor |
| 213 | `test_ephemeral_lifecycle.py` | Ephemeral lifecycle |
| 214 | `test_file_gate_run.py` | File gate |
| 215 | `test_live_morphic_run.py` | Live morphic |
| 216 | `test_skill_pipeline.py` | Skill pipeline |
| 217 | `test_tenant_di.py` | Tenant DI |

### 🔷 E. Admin Tests

| # | ফাইল | কভার করে | স্ট্যাটাস |
|---|------|----------|-----------|
| 218 | `admin/test_god.py` | Admin god mode (৩১টি test) | ✅ পাস |

---

## ❌ ২. যে টেস্টগুলো এখনো যুক্ত করা হয়নি (Tests Needed)

> [!WARNING]
> নিচের মডিউলগুলো কোডবেসে বিদ্যমান কিন্তু এদের জন্য কোনো ডেডিকেটেড টেস্ট নেই বা কভারেজ অপ্রতুল।

### 🔴 Priority 1 — Critical (অবশ্যই যুক্ত করতে হবে)

| # | মডিউল পাথ | প্রস্তাবিত টেস্ট ফাইল | কারণ |
|---|-----------|----------------------|------|
| 1 | `core/security/compliance_bot.py` | `test_compliance_bot.py` | 21KB — কোনো টেস্ট নেই |
| 2 | `core/security/guardian_ai.py` | `test_guardian_ai.py` | 18KB security critical |
| 3 | `core/security/secret_hunter.py` | `test_secret_hunter.py` | 16KB — secret leak detection |
| 4 | `core/security/api_key_middleware.py` | `test_api_key_middleware.py` | API key validation টেস্ট নেই |
| 5 | `core/security/autonoguard_middleware.py` | `test_autonoguard_middleware.py` | Security middleware টেস্ট নেই |
| 6 | `core/security/origin_validator.py` | `test_origin_validator.py` | CORS/origin validation টেস্ট নেই |
| 7 | `core/security/resource_guard.py` | `test_resource_guard.py` | Resource access টেস্ট নেই |
| 8 | `core/lifespan.py` | `test_lifespan.py` | 27KB — app startup/shutdown |
| 9 | `core/llm_router.py` | `test_llm_router.py` | 32KB — LLM routing logic |
| 10 | `core/error_pattern_db.py` | `test_error_pattern_db.py` | Error pattern matching |
| 11 | `core/maintenance_pipeline.py` | `test_maintenance_pipeline.py` | 11KB — maintenance workflow |
| 12 | `core/microvm_sandbox.py` | `test_microvm_sandbox.py` | 19KB — VM sandbox |
| 13 | `core/autonoguard_engine.py` | `test_autonoguard_engine.py` | 13KB — guard engine |
| 14 | `core/sentinel_agent.py` | `test_sentinel_agent.py` | 12KB — sentinel agent |
| 15 | `core/otp_router.py` | `test_otp_router.py` | JIT OTP — security critical |
| 16 | `core/universal_rules.py` (extended) | `test_universal_rules_extended.py` | 24KB — business rules deeper test |

### 🟠 Priority 2 — High (দ্রুত যুক্ত করতে হবে)

| # | মডিউল পাথ | প্রস্তাবিত টেস্ট ফাইল | কারণ |
|---|-----------|----------------------|------|
| 17 | `core/resilience/auto_remediation.py` | `test_auto_remediation.py` | Auto-healing logic |
| 18 | `core/resilience/rollback_monitor.py` | `test_rollback_monitor.py` | Rollback logic |
| 19 | `core/resilience/chaos_engine.py` | `test_chaos_engine.py` | Chaos engineering |
| 20 | `core/orchestration/orchestrator.py` | `test_orchestrator.py` | Main orchestrator |
| 21 | `core/orchestration/cloud_sandbox_orchestrator.py` | `test_cloud_sandbox_orchestrator.py` | Cloud sandbox orch. |
| 22 | `core/observability/observability_middleware.py` | `test_observability_middleware.py` | Observability middleware |
| 23 | `core/llm/token_budget.py` | `test_token_budget.py` | Token budget management |
| 24 | `core/llm/token_deductor.py` | `test_token_deductor.py` | Token deduction logic |
| 25 | `core/intent_router.py` | `test_intent_router.py` | Intent routing |
| 26 | `core/human_behavior.py` | `test_human_behavior.py` | Human behavior simulation |
| 27 | `core/mcp_client.py` | `test_mcp_client.py` | MCP client |
| 28 | `core/skill_manager.py` | `test_skill_manager.py` | 12KB — skill management |
| 29 | `core/rules_mutator.py` | `test_rules_mutator.py` | Rules mutation |
| 30 | `core/startup_validator.py` | `test_startup_validator.py` | Startup validation |
| 31 | `agents/headless_terminal_agent.py` | `test_headless_terminal_agent.py` | 10KB terminal agent |
| 32 | `agents/performance_guardian.py` | `test_performance_guardian.py` | Performance guard |
| 33 | `agents/vulnerability_prophet.py` | `test_vulnerability_prophet.py` | 16KB vulnerability detection |
| 34 | `agents/morphic_adapter.py` | `test_morphic_adapter.py` | Morphic adapter |
| 35 | `agents/skill_gc.py` | `test_skill_gc.py` | Skill garbage collector |

### 🟡 Priority 3 — Medium (পরবর্তী স্প্রিন্টে যুক্ত করতে হবে)

| # | মডিউল পাথ | প্রস্তাবিত টেস্ট ফাইল | কারণ |
|---|-----------|----------------------|------|
| 36 | `services/diagram_parser_service.py` | `test_diagram_parser_service.py` | 17KB — no test |
| 37 | `services/escrow_service.py` | `test_escrow_service.py` | Financial logic — no test |
| 38 | `services/memory_service.py` | `test_memory_service.py` | Memory management |
| 39 | `services/minio_client.py` | `test_minio_client.py` | Object storage |
| 40 | `services/project_context_service.py` | `test_project_context_service.py` | Project context |
| 41 | `services/rider_tracker.py` | `test_rider_tracker.py` | Rider tracking |
| 42 | `services/sandbox_service.py` | `test_sandbox_service.py` | Sandbox service |
| 43 | `services/video_to_code_pipeline.py` | `test_video_to_code_pipeline.py` | 13KB pipeline |
| 44 | `middleware/anti_hacking.py` | `test_anti_hacking_extended.py` | বিস্তারিত টেস্ট দরকার |
| 45 | `core/gcp_firestore.py` | `test_gcp_firestore.py` | 13KB — Firestore CRUD |
| 46 | `core/intent.py` | `test_intent.py` | Intent parsing |
| 47 | `core/upload_validator.py` | `test_upload_validator.py` | File upload validation |
| 48 | `api/v1/` routes | `test_api_v1_routes.py` | V1 API routes coverage কম |
| 49 | `core/swarm_pubsub.py` (extended) | `test_swarm_pubsub_extended.py` | Edge case টেস্ট দরকার |
| 50 | `workers/celery_app.py` | `test_celery_app.py` | Celery worker টেস্ট নেই |

### 🔵 Priority 4 — Integration & E2E

| # | প্রস্তাবিত টেস্ট | বর্ণনা |
|---|-----------------|--------|
| 51 | `test_full_chat_flow_e2e.py` | সম্পূর্ণ চ্যাট flow: user → LLM → response |
| 52 | `test_auth_jit_otp_flow.py` | JIT OTP সহ auth flow |
| 53 | `test_multi_tenant_isolation.py` | Multi-tenant data isolation |
| 54 | `test_provider_failover_chain.py` | AI provider failover chain |
| 55 | `test_rate_limit_enforcement.py` | Rate limiting under load |
| 56 | `test_skill_execution_pipeline.py` | Skill discovery → execution → result |
| 57 | `test_evolution_self_improvement.py` | Self-improvement loop |
| 58 | `test_billing_zero_cost.py` | Zero-cost constraint enforcement |
| 59 | `test_admin_god_security.py` | Admin god mode security boundary |
| 60 | `test_cross_provider_consistency.py` | Cross-provider response consistency |

---

## 🚨 ৩. ব্যর্থ টেস্টসমূহ যেগুলো ঠিক করা প্রয়োজন (Failing Tests)

> [!TIP]
> **সর্বশেষ আপডেট (2026-07-20):** নিচের 3টি collection error সম্পূর্ণ ঠিক করা হয়েছে।

### ✅ সম্প্রতি ঠিক করা Collection Errors

| # | ফাইল | সমস্যা | সমাধান |
|---|------|--------|---------|
| ✅ | `test_headless_terminal_agent.py` | `NameError: res not defined` (indentation bug) | Function body-তে সঠিক indent দেওয়া হয়েছে |
| ✅ | `test_skill_gc.py` | `IndentationError` + `agents/skill_gc.py`-তে `datetime` import নেই | Indentation ঠিক + `datetime` class import যোগ |
| ✅ | `test_lifespan.py` | `SyntaxError: too many statically nested blocks` | `contextlib.ExitStack` + `@pytest.mark.anyio` দিয়ে রিফ্যাক্টর |

> [!IMPORTANT]
> **Security fix (2026-07-20):** `agents/headless_terminal_agent.py`-এ `_looks_like_command()` থেকে `rm`, `sudo`, `wget`, `curl` ইত্যাদি missing ছিল — dangerous commands NL interpreter-এ গিয়ে empty string হয়ে `SAFE` status পাচ্ছিল। এটি একটি critical bypass bug যা ঠিক করা হয়েছে।

### 🔴 বাকি Failing Tests (ঠিক করা প্রয়োজন)

| # | ফাইল | ব্যর্থ সংখ্যা | সম্ভাব্য কারণ |
|---|------|--------------|--------------|
| 1 | `test_billing_api_integration.py` | 3 fail | Billing API mock/endpoint mismatch |
| 2 | `test_fitness_engine.py` | 3 error | Import error / missing dependency |
| 3 | `test_github_agent.py` | 3 fail | GitHub token / API mock missing |
| 4 | `test_evolution_pipeline.py` | 2 fail | Pipeline state management bug |
| 5 | `test_error_remediation.py` | 3 fail | Remediation logic regression |
| 6 | `test_auth_middleware.py` | 2 fail | JWT validation edge case |
| 7 | `test_knowledge_qa.py` | 3 fail | QA retrieval logic mismatch |
| 8 | `test_config.py` | 3 fail | Config field validation mismatch |
| 9 | `api/test_swarm_routes.py` | 3 fail | Swarm route 404/auth issue |
| 10 | `test_pubsub.py` | 2 fail | Async pubsub timing issue |
| 11 | `test_swarm_orchestrator_coverage.py` | 3 fail | Orchestrator state regression |
| 12 | `test_immune_system.py` | 1 fail | Immune system rule mismatch |
| 13 | `test_graph_service.py` | 1 fail | Graph query edge case |
| 14 | `test_e2e.py` | 1 fail | E2E endpoint availability |
| 15 | `test_coverage_gaps.py` | 1 fail | Coverage expectation mismatch |

---

## 📈 ৪. কভারেজ বাড়ানোর রোডম্যাপ

```
বর্তমান: ~38-45%  (2569 collected, 3 collection errors fixed ✅)
          │
          ▼ Phase 1 (এখনই) — 15 failing tests fix + 16 critical tests add
          52%
          │
          ▼ Phase 2 (১ সপ্তাহ) — High priority 19 tests (resilience, LLM, agents)
          63%
          │
          ▼ Phase 3 (২-৩ সপ্তাহ) — Medium priority 15 tests (services, workers)
          72%
          │
          ▼ Phase 4 (১ মাস) — E2E Integration 10 tests
          80%+
```

### 🗓️ Phase 1 — এখনই করণীয়

| # | কাজ | অগ্রাধিকার |
|---|-----|------------|
| 1 | ~~3 collection errors fix~~ | ✅ Done |
| 2 | `test_billing_api_integration.py` ঠিক করো | 🔴 Critical |
| 3 | `test_github_agent.py` mock যোগ করো | 🔴 Critical |
| 4 | `test_fitness_engine.py` import fix করো | 🔴 Critical |
| 5 | `core/security/compliance_bot.py` টেস্ট লিখো | 🔴 Critical |
| 6 | `core/otp_router.py` JIT OTP টেস্ট লিখো | 🔴 Critical |

---

## 🔧 ৫. দ্রুত টেস্ট চালানোর কমান্ড

```bash
# সম্পূর্ণ টেস্ট সুইট + কভারেজ রিপোর্ট
poetry run pytest --cov --cov-report=html -v

# শুধু fail হওয়া টেস্ট পুনরায় চালাও
poetry run pytest --last-failed -v

# নির্দিষ্ট মডিউলের টেস্ট
poetry run pytest tests/test_auth_middleware.py -v

# কভারেজ নির্দিষ্ট ফাইলের
poetry run pytest --cov=core/security --cov-report=term-missing

# দ্রুত parallel রান
poetry run pytest -n auto --cov
```

---

_শেষ আপডেট: 2026-07-20 10:58 BDT | টেস্ট সুইট: ✅ 2569 collected, 0 collection errors | fixes: 3 errors resolved, 1 critical security bug fixed_
