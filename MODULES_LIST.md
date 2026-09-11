# SupremeAI - Comprehensive List of Modules

Total Modules: **224**  
**Truthful Operational Wiring Audit Summary (2026-09-11):**
- 🟢 **Operational:** 119 modules (Importable + Active Inbound Production Callers > 0 + Test backing)
- 🟡 **Environment-Dependent:** 3 modules (Requires host Docker daemon, Telegram bot token, etc.)
- 🟠 **Partially Wired (Dormant):** 102 modules (Cleanly importable/standalone; 0 active inbound production callers)
- 🔴 **Broken:** 0 modules (Crash on import or missing core dependency)
- ⚪ **Planned:** 0 modules (Architectural placeholder)

<!--
ARCHITECTURE DIRECTIVE / GOVERNANCE GUARDRAIL:
Do NOT expand this catalog to file-level granularity (1000+ files).
In SupremeAI architecture, a 'Module' represents a high-level cohesive subsystem, service, monorepo package,
MCP server, tool, or state store. Individual UI components, utility helpers, and type interfaces belong
to their respective parent modules. Preserving the 224 functional module boundary is mandatory for system wiring.
-->

| # | Category | Module Name / Relative Path | Operational Status | Caller Evidence | Test Evidence |
|---|---|---|---|---|---|
| 1 | Monorepo Package | packages/core-infrastructure | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 2 | Monorepo Package | packages/design-tokens | 🟢 Operational | infrastructure/mcp-control-plane/src/tools/source.tools.ts | None |
| 3 | Monorepo Package | packages/scripts | 🟢 Operational | 44 callers (backend/core/config_classification.py, ...) | 14 test files (backend/tests/test_rls_policy_coverage.py, ...) |
| 4 | Monorepo Package | packages/shared-services | 🟢 Operational | 6 callers (frontend/src/commandcenter/realtime/websocketManager.ts, ...) | 7 test files (frontend/src/services/aiActions.test.ts, ...) |
| 5 | Monorepo Package | packages/shared-types | 🟢 Operational | backend/core/schema_exporter.py, backend/core/type_sync_bus.py | None |
| 6 | Monorepo Package | packages/ui-components | 🟢 Operational | frontend/src/main.tsx, frontend/src/components/swarm/SwarmHealthDashboard.tsx | frontend/src/main.tsx, frontend/src/components/swarm/SwarmHealthDashboard.tsx |
| 7 | Backend Core Service | backend/services/billing | 🟢 Operational | 28 callers (backend/core/autonoguard_engine.py, ...) | 27 test files (frontend/src/auth/routePolicies.test.ts, ...) |
| 8 | Backend Core Service | backend/services/browser | 🟢 Operational | 68 callers (backend/core/admin_routes.py, ...) | 46 test files (backend/services/scraper/tests/test_scraper_service.py, ...) |
| 9 | Backend Core Service | backend/services/data | 🟢 Operational | 502 callers (backend/core/admin_god.py, ...) | 301 test files (backend/services/scraper/.venv/Lib/site-packages/pip/_internal/commands/inspect.py, ...) |
| 10 | Backend Core Service | backend/services/dynamic_ai | 🟢 Operational | 7 callers (backend/core/unified_learning.py, ...) | backend/tests/services/dynamic_ai/test_learning_engine_shim.py |
| 11 | Backend Core Service | backend/services/email | 🟢 Operational | 71 callers (backend/core/admin_routes.py, ...) | 46 test files (frontend/src/components/customer/QuickPresets.test.tsx, ...) |
| 12 | Backend Core Service | backend/services/hitl | 🟢 Operational | 12 callers (backend/core/automation/registry.py, ...) | 6 test files (backend/tests/conftest.py, ...) |
| 13 | Backend Core Service | backend/services/ide_trio | 🟢 Operational | backend/api/routers.py | backend/tests/test_ide_trio_smoke.py |
| 14 | Backend Core Service | backend/services/ingestion | 🟢 Operational | 4 callers (backend/core/self_evolution/performance_oracle.py, ...) | 3 test files (backend/services/ingestion/test_context_collector.py, ...) |
| 15 | Backend Core Service | backend/services/llm | 🟢 Operational | 49 callers (backend/core/admin_routes.py, ...) | 28 test files (backend/tests/conftest.py, ...) |
| 16 | Backend Core Service | backend/services/scraper | 🟢 Operational | 19 callers (backend/core/app_builder.py, ...) | 12 test files (backend/services/scraper/.venv/Lib/site-packages/pip/_internal/commands/inspect.py, ...) |
| 17 | Backend Core Service | backend/services/storage | 🟢 Operational | 53 callers (backend/core/advanced_reasoning.py, ...) | 22 test files (frontend/src/services/storageApi.test.ts, ...) |
| 18 | Backend Core Service | backend/services/worker | 🟢 Operational | 36 callers (backend/core/app_builder.py, ...) | 19 test files (frontend/src/services/api/microserviceMonitor.test.ts, ...) |
| 19 | Infrastructure Module | infrastructure/cloudflare | 🟢 Operational | 22 callers (backend/core/llm/free_tier_tracker.py, ...) | 3 test files (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) |
| 20 | Infrastructure Module | infrastructure/kubernetes | 🟢 Operational | frontend/src/components/admin/SciFiFlowNode.tsx | frontend/src/components/admin/SciFiFlowNode.tsx |
| 21 | Infrastructure Module | infrastructure/mcp-control-plane | 🟢 Operational | 7 callers (backend/core/mcp_client.py, ...) | 3 test files (backend/tests/api/test_capability_contracts.py, ...) |
| 22 | Infrastructure Module | infrastructure/monitoring | 🟢 Operational | 54 callers (backend/core/adaptive_optimizer.py, ...) | 14 test files (backend/tests/agents/test_sentinel_agent.py, ...) |
| 23 | Infrastructure Module | infrastructure/zero_cost | 🟢 Operational | 3 callers (backend/core/universal_rules.py, ...) | backend/tests/core/test_billing_zero_cost.py |
| 24 | Specialized Tool Subsystem | tools/autonomy | 🟢 Operational | 4 callers (backend/core/self_evolution/daily_learner.py, ...) | None |
| 25 | Specialized Tool Subsystem | tools/discovery_fabric | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 26 | Specialized Tool Subsystem | tools/firebase_functions_v1 | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 27 | Specialized Tool Subsystem | tools/gap_finder | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 28 | Specialized Tool Subsystem | tools/gap_miner | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 29 | Specialized Tool Subsystem | tools/intelligence_extensions | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 30 | Specialized Tool Subsystem | tools/knowledge | 🟢 Operational | 33 callers (backend/core/competitive_kit.py, ...) | 18 test files (backend/tests/api/routes/commandcenter/test_build.py, ...) |
| 31 | Specialized Tool Subsystem | tools/knowledge_squeezer | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 32 | Specialized Tool Subsystem | tools/solution_synthesizer | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 33 | Specialized Tool Subsystem | tools/vscode-extension | 🟢 Operational | backend/core/app.py | None |
| 34 | MCP Server / Tool | backend/tools/mcp/mcp_cloud_deploy.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_mcp_servers_integration.py |
| 35 | MCP Server / Tool | backend/tools/mcp/mcp_github_cicd.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_mcp_servers_integration.py |
| 36 | MCP Server / Tool | backend/tools/mcp/mcp_ide_trio.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 37 | MCP Server / Tool | backend/tools/mcp/mcp_neon.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_mcp_servers_integration.py |
| 38 | MCP Server / Tool | backend/tools/mcp/mcp_observability.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 39 | MCP Server / Tool | backend/tools/mcp/mcp_server.py | 🟢 Operational | infrastructure/mcp-control-plane/src/adapters/memory/index.ts, infrastructure/mcp-control-plane/src/tools/memory.tools.ts | backend/tests/core/test_mcp_servers_integration.py |
| 40 | MCP Server / Tool | backend/tools/mcp/mcp_supabase.py | 🟢 Operational | backend/core/skill_manager.py, backend/core/universal_rules.py | 3 test files (backend/tests/core/test_mcp_servers_integration.py, ...) |
| 41 | MCP Server / Tool | backend/tools/mcp/mcp_telegram.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 42 | MCP Server / Tool | backend/tools/mcp/mcp_workspace.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_mcp_servers_integration.py |
| 43 | Backend Tool / Utility | backend/tools/_bootstrap.py | 🟠 Partially Wired | 0 active callers (dormant) | 3 test files (backend/tests/api/test_api_bootstrap.py, ...) |
| 44 | Backend Tool / Utility | backend/tools/agent_tools.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_agent_tools.py |
| 45 | Backend Tool / Utility | backend/tools/ai_federation_protocol.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 46 | Backend Tool / Utility | backend/tools/api_gateway.py | 🟢 Operational | 3 callers (backend/core/self_evolution/digital_twin/remediation_engine.py, ...) | None |
| 47 | Backend Tool / Utility | backend/tools/bandwidth_optimizer.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 48 | Backend Tool / Utility | backend/tools/checkpoint_manager.py | 🟢 Operational | 4 callers (backend/core/shutdown.py, ...) | 4 test files (backend/tests/conftest.py, ...) |
| 49 | Backend Tool / Utility | backend/tools/cli.py | 🟢 Operational | 43 callers (backend/core/intent_router_v2.py, ...) | 8 test files (backend/services/scraper/.venv/Lib/site-packages/pip/_internal/commands/inspect.py, ...) |
| 50 | Backend Tool / Utility | backend/tools/cli_process_delegator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 51 | Backend Tool / Utility | backend/tools/collaborative_editor.py | 🟢 Operational | backend/api/routers.py | None |
| 52 | Backend Tool / Utility | backend/tools/comment_thread_ai.py | 🟢 Operational | backend/api/routers.py | None |
| 53 | Backend Tool / Utility | backend/tools/conversation_manager.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 54 | Backend Tool / Utility | backend/tools/ensemble_router.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 55 | Backend Tool / Utility | backend/tools/freebuff_client.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_freebuff_client.py |
| 56 | Backend Tool / Utility | backend/tools/graph_service.py | 🟢 Operational | backend/api/routes/graph.py | backend/tests/services/test_graph_service.py |
| 57 | Backend Tool / Utility | backend/tools/headless_agent_registry.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_headless_agent_registry.py |
| 58 | Backend Tool / Utility | backend/tools/health_checker.py | 🟢 Operational | 5 callers (backend/core/app.py, ...) | backend/tests/core/test_advanced_wiring.py, backend/tests/services/test_monitoring.py |
| 59 | Backend Tool / Utility | backend/tools/langchain_agent_example.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 60 | Backend Tool / Utility | backend/tools/launchdarkly_agent_adapter.py | 🟡 Environment-Dependent | 0 active callers (dormant) | None |
| 61 | Backend Tool / Utility | backend/tools/meta_architect.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_meta_architect_coverage_full.py |
| 62 | Backend Tool / Utility | backend/tools/offline_mode.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 63 | Backend Tool / Utility | backend/tools/parallel_agent_executor.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/conftest.py, backend/tests/agents/test_parallel_agent_executor.py |
| 64 | Backend Tool / Utility | backend/tools/plan_sorter.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/services/test_monitoring.py, backend/tests/tools/test_plan_sorter.py |
| 65 | Backend Tool / Utility | backend/tools/preference_memory.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_preference_memory.py |
| 66 | Backend Tool / Utility | backend/tools/repo_discovery_agent.py | 🟢 Operational | backend/api/routes/github.py | None |
| 67 | Backend Tool / Utility | backend/tools/resource_catalog.py | 🟢 Operational | backend/api/routes/marketplace_endpoints.py | backend/tests/api/test_resource_catalog.py, backend/tests/tools/test_resource_catalog.py |
| 68 | Backend Tool / Utility | backend/tools/seed_database.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 69 | Backend Tool / Utility | backend/tools/self_planner.py | 🟢 Operational | backend/api/routers.py | backend/tests/security/test_dead_route_wiring.py |
| 70 | Backend Tool / Utility | backend/tools/sso_integrator.py | 🟢 Operational | backend/api/routes/sso.py | backend/tests/tools/test_new_tools_sprint5.py, backend/tests/tools/test_sso_integrator_comprehensive.py |
| 71 | Backend Tool / Utility | backend/tools/tenant_rate_limiter.py | 🟢 Operational | backend/api/routes/tenant_admin.py, backend/middleware/tenant_rate_limiter.py | backend/tests/core/test_billing_zero_cost.py, backend/tests/tools/test_new_tools_sprint5.py |
| 72 | Backend Tool / Utility | backend/tools/ai_agents/browser_agent.py | 🟢 Operational | 7 callers (backend/core/lifespan.py, ...) | 3 test files (backend/services/scraper/tests/test_scraper_service.py, ...) |
| 73 | Backend Tool / Utility | backend/tools/ai_agents/vision_agent.py | 🟢 Operational | backend/core/agents/live/vision_agent.py | backend/tests/agents/test_vision_agent.py |
| 74 | Backend Tool / Utility | backend/tools/analytics/churn_prophet.py | 🟢 Operational | backend/api/routes/analytics.py | backend/tests/agents/test_agents_churn_prophet.py |
| 75 | Backend Tool / Utility | backend/tools/analytics/insight_mage.py | 🟢 Operational | backend/api/routes/analytics.py | backend/tests/agents/test_agents_insight_mage.py |
| 76 | Backend Tool / Utility | backend/tools/billing/cost_auditor.py | 🟢 Operational | backend/api/routes/admin_dashboard.py, backend/api/routes/billing_api.py | backend/tests/monitoring/test_cost_auditor.py, backend/tests/services/test_monitoring.py |
| 77 | Backend Tool / Utility | backend/tools/billing/monthly_cost_reporter.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 78 | Backend Tool / Utility | backend/tools/browser/ai_web_extractor.py | 🟢 Operational | backend/api/routes/browser.py | None |
| 79 | Backend Tool / Utility | backend/tools/browser/browser_stealth.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 80 | Backend Tool / Utility | backend/tools/browser/mcp_tools.py | 🟢 Operational | backend/core/mcp_policy.py, backend/core/skill_manager.py | None |
| 81 | Backend Tool / Utility | backend/tools/browser/playwright_browser_agent.py | 🟢 Operational | backend/api/routes/session_takeover.py, backend/services/scraper/browser_agent.py | None |
| 82 | Backend Tool / Utility | backend/tools/browser/stealth_http_client.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_stealth_networking.py |
| 83 | Backend Tool / Utility | backend/tools/browser/web_fallback_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 84 | Backend Tool / Utility | backend/tools/browser/web_scraper.py | 🟢 Operational | 9 callers (backend/core/admin_routes.py, ...) | 4 test files (backend/services/scraper/tests/test_scraper_service.py, ...) |
| 85 | Backend Tool / Utility | backend/tools/code/ai_pair_programmer.py | 🟢 Operational | backend/api/routers.py | backend/tests/security/test_dead_route_wiring.py, backend/tests/tools/test_sprint_c_tools.py |
| 86 | Backend Tool / Utility | backend/tools/code/auto_pr_pipeline.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 87 | Backend Tool / Utility | backend/tools/code/auto_test_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_auto_test_generator.py |
| 88 | Backend Tool / Utility | backend/tools/code/code_smell_detector.py | 🟢 Operational | backend/api/routes/tools_ops.py | backend/tests/tools/test_code_smell_detector.py |
| 89 | Backend Tool / Utility | backend/tools/code/cot_reasoner.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_brain.py, backend/tests/tools/test_cot_reasoner.py |
| 90 | Backend Tool / Utility | backend/tools/code/dependency_manager_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 91 | Backend Tool / Utility | backend/tools/code/diagram_to_architecture.py | 🟢 Operational | backend/api/routers.py, backend/services/diagram_parser_service.py | 3 test files (backend/tests/security/test_dead_route_wiring.py, ...) |
| 92 | Backend Tool / Utility | backend/tools/code/fuzz_sandbox.py | 🟢 Operational | backend/core/skill_manager.py, backend/core/self_evolution/auto_skill_creator.py | backend/tests/security/test_p0_safety_regression.py, backend/tests/workers/test_nightly_auditor_audit.py |
| 93 | Backend Tool / Utility | backend/tools/code/image_to_code.py | 🟢 Operational | backend/api/routers.py | backend/tests/tools/test_image_to_code_react.py |
| 94 | Backend Tool / Utility | backend/tools/code/local_code_executor.py | 🟢 Operational | 4 callers (backend/core/config_fields.py, ...) | backend/tests/core/test_stealth_networking.py, backend/tests/tools/test_local_code_executor.py |
| 95 | Backend Tool / Utility | backend/tools/code/lsp_bridge.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 96 | Backend Tool / Utility | backend/tools/code/pr_reviewer.py | 🟢 Operational | backend/api/routes/pr_review_api.py | backend/tests/tools/test_pr_reviewer_webhook.py |
| 97 | Backend Tool / Utility | backend/tools/code/pre_commit_ai.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 98 | Backend Tool / Utility | backend/tools/code/safe_executor.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_cot_reasoner.py |
| 99 | Backend Tool / Utility | backend/tools/code/voice_coder.py | 🟢 Operational | backend/api/routers.py | backend/tests/security/test_dead_route_wiring.py, backend/tests/tools/test_sprint_c_tools.py |
| 100 | Backend Tool / Utility | backend/tools/creative/audio_engineering_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 101 | Backend Tool / Utility | backend/tools/creative/brand_identity_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 102 | Backend Tool / Utility | backend/tools/creative/creative_agents_registry.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 103 | Backend Tool / Utility | backend/tools/creative/game_design_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 104 | Backend Tool / Utility | backend/tools/creative/video_production_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 105 | Backend Tool / Utility | backend/tools/devops/auto_coverage_improver.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_auto_coverage_improver.py |
| 106 | Backend Tool / Utility | backend/tools/devops/coverage_auditor.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/tools/test_auto_coverage_improver.py, backend/tests/tools/test_coverage_auditor.py |
| 107 | Backend Tool / Utility | backend/tools/devops/docker_sandbox.py | 🟡 Environment-Dependent | backend/core/config_fields.py, backend/api/routes/agent_workspace.py | backend/tests/core/test_docker_sandbox.py, backend/tests/services/test_monitoring.py |
| 108 | Backend Tool / Utility | backend/tools/devops/gcp_cloud_functions.py | 🟢 Operational | backend/core/services.py | backend/tests/core/test_gcp_integration.py |
| 109 | Backend Tool / Utility | backend/tools/devops/github_agent.py | 🟢 Operational | 3 callers (backend/api/routes/agent_workspace.py, ...) | backend/tests/agents/test_github_agent.py |
| 110 | Backend Tool / Utility | backend/tools/devops/on_premise_deployer.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 111 | Backend Tool / Utility | backend/tools/knowledge/codebase_exporter.py | 🟢 Operational | backend/api/routes/admin_dashboard.py, backend/api/routes/markdown.py | None |
| 112 | Backend Tool / Utility | backend/tools/knowledge/git_knowledge_extractor.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 113 | Backend Tool / Utility | backend/tools/knowledge/knowledge_base_indexer.py | 🟢 Operational | backend/api/routes/deep_research.py, backend/api/routes/slash_commands.py | backend/tests/tools/test_knowledge_base_indexer.py |
| 114 | Backend Tool / Utility | backend/tools/knowledge/local_search_rag.py | 🟢 Operational | backend/core/factual_verifier.py | None |
| 115 | Backend Tool / Utility | backend/tools/knowledge/pdf_to_sdk.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 116 | Backend Tool / Utility | backend/tools/knowledge/repo_deep_indexer.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 117 | Backend Tool / Utility | backend/tools/learning/agent_knowledge_store.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 118 | Backend Tool / Utility | backend/tools/learning/domain_adapter.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 119 | Backend Tool / Utility | backend/tools/learning/model_trainer.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_tier8_evolution.py |
| 120 | Backend Tool / Utility | backend/tools/learning/rlhf_pipeline.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 121 | Backend Tool / Utility | backend/tools/learning/skill_recommender.py | 🟢 Operational | backend/api/routes/tools_ops.py | backend/tests/test_rls_policy_coverage.py |
| 122 | Backend Tool / Utility | backend/tools/learning/style_learner.py | 🟢 Operational | backend/api/routers.py | backend/tests/tools/test_sprint_c_tools.py, backend/tests/tools/test_style_learner_ast.py |
| 123 | Backend Tool / Utility | backend/tools/localization/bangla_ai_connector.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 124 | Backend Tool / Utility | backend/tools/localization/bangla_nlp.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 125 | Backend Tool / Utility | backend/tools/localization/bangla_voice.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 126 | Backend Tool / Utility | backend/tools/localization/bengali_ocr_converter.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 127 | Backend Tool / Utility | backend/tools/localization/local_ocr_extractor.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 128 | Backend Tool / Utility | backend/tools/media/image_generator.py | 🟢 Operational | backend/api/routes/slash_commands.py | backend/tests/core/test_e2e_media.py |
| 129 | Backend Tool / Utility | backend/tools/media/multilingual_tts.py | 🟢 Operational | backend/api/routers.py, backend/api/routes/voice.py | backend/tests/tools/test_multilingual_tts.py |
| 130 | Backend Tool / Utility | backend/tools/media/music_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 131 | Backend Tool / Utility | backend/tools/media/presentation_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 132 | Backend Tool / Utility | backend/tools/media/threed_model_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 133 | Backend Tool / Utility | backend/tools/media/video_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/core/test_e2e_media.py |
| 134 | Backend Tool / Utility | backend/tools/media/voice.py | 🟢 Operational | 18 callers (backend/core/config_fields.py, ...) | 11 test files (frontend/src/services/chatService.test.ts, ...) |
| 135 | Backend Tool / Utility | backend/tools/security_tools/multi_account_rotator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 136 | Backend Tool / Utility | backend/tools/security_tools/proxy_manager.py | 🟢 Operational | backend/services/scraper/.venv/Lib/site-packages/pip/_vendor/requests/adapters.py | backend/tests/core/test_stealth_networking.py |
| 137 | Backend Tool / Utility | backend/tools/security_tools/vpn_switcher.py | 🟢 Operational | backend/core/agents/framework/autonomous_task_orchestrator.py | backend/tests/tools/test_vpn_switcher_rotator.py |
| 138 | Backend Tool / Utility | backend/tools/security_tools/vulnerability_predictor.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 139 | Backend Tool / Utility | backend/tools/social/email_agent.py | 🟢 Operational | backend/api/routes/email.py | backend/tests/agents/test_email_agent.py, backend/tests/api/test_api_new_endpoints.py |
| 140 | Backend Tool / Utility | backend/tools/social/marketplace_agent.py | 🟢 Operational | backend/api/routes/marketplace_endpoints.py | backend/tests/agents/test_marketplace_agent.py |
| 141 | Backend Tool / Utility | backend/tools/social/teldrive_storage.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 142 | Backend Tool / Utility | backend/tools/social/telegram_bot.py | 🟡 Environment-Dependent | backend/core/messaging/adapters.py, backend/api/routers.py | backend/tests/agents/test_telegram_bot.py, backend/tests/agents/test_telegram_bot_v2.py |
| 143 | Backend Tool / Utility | backend/tools/social/telegram_security.py | 🟢 Operational | backend/api/routes/workspaces_route.py | backend/tests/agents/test_telegram_bot_v2.py |
| 144 | Backend Tool / Utility | backend/tools/social/viral_referral_engine.py | 🟠 Partially Wired | 0 active callers (dormant) | 3 test files (backend/tests/test_rls_policy_coverage.py, ...) |
| 145 | Frontend Page / View | frontend/src/pages/BillingPage.tsx | 🟢 Operational | frontend/src/App.tsx | frontend/src/App.tsx |
| 146 | Frontend Page / View | frontend/src/pages/ErrorPage.tsx | 🟢 Operational | frontend/src/App.tsx, frontend/src/routes/workspaceFeatureRoutes.tsx | 3 test files (frontend/src/App.routes.test.tsx, ...) |
| 147 | Frontend Page / View | frontend/src/pages/ProfilePage.tsx | 🟢 Operational | frontend/src/App.tsx, frontend/src/store/index.ts | frontend/src/App.tsx, frontend/src/store/index.ts |
| 148 | Frontend Page / View | frontend/src/pages/PromptTemplatePage.tsx | 🟢 Operational | frontend/src/routes/workspaceFeatureRoutes.tsx | frontend/src/routes/workspaceFeatureRoutes.tsx |
| 149 | Frontend Page / View | frontend/src/pages/PublicPages.tsx | 🟢 Operational | frontend/src/App.tsx | frontend/src/App.routes.test.tsx, frontend/src/App.tsx |
| 150 | Frontend Page / View | frontend/src/pages/SharedConversationPage.tsx | 🟢 Operational | frontend/src/routes/workspaceFeatureRoutes.tsx | frontend/src/routes/workspaceFeatureRoutes.tsx |
| 151 | Frontend Page / View | frontend/src/pages/WorkspaceModulePage.tsx | 🟢 Operational | frontend/src/App.tsx | frontend/src/App.tsx |
| 152 | Frontend Page / View | frontend/src/pages/admin | 🟢 Operational | 189 callers (backend/core/admin_god.py, ...) | 202 test files (backend/services/scraper/tests/test_scraper_service.py, ...) |
| 153 | Frontend Page / View | frontend/src/pages/auth | 🟢 Operational | 123 callers (backend/core/admin_god.py, ...) | 87 test files (frontend/src/App.routes.test.tsx, ...) |
| 154 | Frontend Page / View | frontend/src/pages/user | 🟢 Operational | 317 callers (backend/core/admin_god.py, ...) | 178 test files (backend/services/scraper/.venv/Lib/site-packages/pip/_internal/commands/inspect.py, ...) |
| 155 | Frontend Service Module | frontend/src/services/adminService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 156 | Frontend Service Module | frontend/src/services/adminService.ts | 🟠 Partially Wired | 0 active callers (dormant) | frontend/src/services/adminService.test.ts |
| 157 | Frontend Service Module | frontend/src/services/adminTokenStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 158 | Frontend Service Module | frontend/src/services/adminTokenStore.ts | 🟢 Operational | 18 callers (frontend/src/commandcenter/data/hooks.ts, ...) | 20 test files (frontend/src/App.test.tsx, ...) |
| 159 | Frontend Service Module | frontend/src/services/agentService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 160 | Frontend Service Module | frontend/src/services/agentService.ts | 🟢 Operational | backend/api/routes/agents.py | frontend/src/services/agentService.test.ts |
| 161 | Frontend Service Module | frontend/src/services/aiActions.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 162 | Frontend Service Module | frontend/src/services/aiActions.ts | 🟢 Operational | frontend/src/components/editor/AiAssistantBar.tsx | frontend/src/services/aiActions.test.ts, frontend/src/components/editor/AiAssistantBar.tsx |
| 163 | Frontend Service Module | frontend/src/services/api | 🟢 Operational | 356 callers (backend/core/adaptive_optimizer.py, ...) | 260 test files (frontend/src/App.routes.test.tsx, ...) |
| 164 | Frontend Service Module | frontend/src/services/apiClient.test.ts | 🟢 Operational | frontend/src/test/setup.ts | frontend/src/test/setup.ts |
| 165 | Frontend Service Module | frontend/src/services/apiClient.ts | 🟢 Operational | 94 callers (backend/core/app_builder.py, ...) | 112 test files (frontend/src/App.routes.test.tsx, ...) |
| 166 | Frontend Service Module | frontend/src/services/audio | 🟢 Operational | 11 callers (backend/core/intent_router_v2.py, ...) | 7 test files (backend/tests/core/test_voice_stream.py, ...) |
| 167 | Frontend Service Module | frontend/src/services/authService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 168 | Frontend Service Module | frontend/src/services/authService.ts | 🟢 Operational | frontend/src/store/adminStore.ts | 3 test files (frontend/src/services/authService.test.ts, ...) |
| 169 | Frontend Service Module | frontend/src/services/browserService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 170 | Frontend Service Module | frontend/src/services/browserService.ts | 🟢 Operational | frontend/src/components/customer/BrowserPreview.tsx | frontend/src/services/browserService.test.ts, frontend/src/components/customer/BrowserPreview.tsx |
| 171 | Frontend Service Module | frontend/src/services/chatService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 172 | Frontend Service Module | frontend/src/services/chatService.ts | 🟢 Operational | 5 callers (backend/api/routes/task.py, ...) | 6 test files (frontend/src/App.routes.test.tsx, ...) |
| 173 | Frontend Service Module | frontend/src/services/ciReportService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 174 | Frontend Service Module | frontend/src/services/ciReportService.ts | 🟠 Partially Wired | 0 active callers (dormant) | frontend/src/services/ciReportService.test.ts |
| 175 | Frontend Service Module | frontend/src/services/controlPlane.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 176 | Frontend Service Module | frontend/src/services/controlPlane.ts | 🟢 Operational | frontend/src/components/admin/infra/ServiceHealthMonitor.tsx, frontend/src/components/chat/ChatInterface.tsx | 4 test files (frontend/src/services/controlPlane.test.ts, ...) |
| 177 | Frontend Service Module | frontend/src/services/costOptimizer.service.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 178 | Frontend Service Module | frontend/src/services/costOptimizer.service.ts | 🟠 Partially Wired | 0 active callers (dormant) | frontend/src/services/costOptimizer.service.test.ts |
| 179 | Frontend Service Module | frontend/src/services/heartbeat.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 180 | Frontend Service Module | frontend/src/services/heartbeat.ts | 🟢 Operational | 15 callers (backend/core/agent_supervisor.py, ...) | 5 test files (frontend/src/services/heartbeat.test.ts, ...) |
| 181 | Frontend Service Module | frontend/src/services/policyService.ts | 🟢 Operational | frontend/src/components/customer/TaskAutomationCard.tsx | frontend/src/components/customer/TaskAutomationCard.tsx |
| 182 | Frontend Service Module | frontend/src/services/queryClient.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 183 | Frontend Service Module | frontend/src/services/queryClient.ts | 🟢 Operational | 5 callers (frontend/src/App.tsx, ...) | 8 test files (frontend/src/components/auth/ServiceHealthBar.test.tsx, ...) |
| 184 | Frontend Service Module | frontend/src/services/realtime | 🟢 Operational | 16 callers (backend/core/agents/framework/autonomous_task_orchestrator.py, ...) | 10 test files (backend/tests/core/orchestration/test_spoke_contracts.py, ...) |
| 185 | Frontend Service Module | frontend/src/services/sandbox.ts | 🟢 Operational | 35 callers (backend/core/ast_security_scanner.py, ...) | 35 test files (frontend/src/store/useStore.test.ts, ...) |
| 186 | Frontend Service Module | frontend/src/services/skillsService.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 187 | Frontend Service Module | frontend/src/services/skillsService.ts | 🟢 Operational | frontend/src/pages/user/SkillCatalog.tsx | frontend/src/services/skillsService.test.ts, frontend/src/pages/user/SkillCatalog.tsx |
| 188 | Frontend Service Module | frontend/src/services/socialGrowthService.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 189 | Frontend Service Module | frontend/src/services/storageApi.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 190 | Frontend Service Module | frontend/src/services/storageApi.ts | 🟠 Partially Wired | 0 active callers (dormant) | frontend/src/services/storageApi.test.ts |
| 191 | Frontend Service Module | frontend/src/services/supremeShared.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 192 | Frontend Service Module | frontend/src/services/supremeShared.ts | 🟢 Operational | frontend/src/components/editor/monacoAi.ts, frontend/src/services/aiActions.ts | 5 test files (frontend/src/services/aiActions.test.ts, ...) |
| 193 | Frontend Service Module | frontend/src/services/test_budget_check.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 194 | Frontend State Store | frontend/src/store/adminStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 195 | Frontend State Store | frontend/src/store/adminStore.ts | 🟢 Operational | 8 callers (backend/core/admin_routes.py, ...) | 9 test files (frontend/src/services/apiClient.test.ts, ...) |
| 196 | Frontend State Store | frontend/src/store/authStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 197 | Frontend State Store | frontend/src/store/authStore.ts | 🟢 Operational | 21 callers (frontend/src/auth/identity.ts, ...) | 26 test files (frontend/src/App.test.tsx, ...) |
| 198 | Frontend State Store | frontend/src/store/chatStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 199 | Frontend State Store | frontend/src/store/chatStore.ts | 🟢 Operational | 4 callers (frontend/src/store/index.ts, ...) | 6 test files (frontend/src/store/chatStore.test.ts, ...) |
| 200 | Frontend State Store | frontend/src/store/customerStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 201 | Frontend State Store | frontend/src/store/customerStore.ts | 🟢 Operational | 6 callers (frontend/src/components/customer/HomeFeed.tsx, ...) | 7 test files (frontend/src/store/customerStore.test.ts, ...) |
| 202 | Frontend State Store | frontend/src/store/dashboardStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 203 | Frontend State Store | frontend/src/store/dashboardStore.ts | 🟢 Operational | 7 callers (frontend/src/components/admin/AuditLogsPanel.tsx, ...) | 9 test files (frontend/src/App.test.tsx, ...) |
| 204 | Frontend State Store | frontend/src/store/index.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | frontend/src/components/ui/index.test.tsx |
| 205 | Frontend State Store | frontend/src/store/index.ts | 🟢 Operational | 129 callers (backend/core/intent_router.py, ...) | 41 test files (backend/services/scraper/tests/test_scraper_service.py, ...) |
| 206 | Frontend State Store | frontend/src/store/localFirstDb.ts | 🟢 Operational | frontend/src/store/authStore.ts, frontend/src/store/themeStore.ts | frontend/src/store/authStore.ts, frontend/src/store/themeStore.ts |
| 207 | Frontend State Store | frontend/src/store/sessionCockpitStore.ts | 🟢 Operational | 10 callers (backend/api/routers.py, ...) | 9 test files (frontend/src/components/AgentStateShaderBackground.tsx, ...) |
| 208 | Frontend State Store | frontend/src/store/slices | 🟢 Operational | 4 callers (backend/services/scraper/.venv/Lib/site-packages/pip/_vendor/requests/utils.py, ...) | 11 test files (frontend/src/store/index.test.ts, ...) |
| 209 | Frontend State Store | frontend/src/store/stateOwnership.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 210 | Frontend State Store | frontend/src/store/themeStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 211 | Frontend State Store | frontend/src/store/themeStore.ts | 🟢 Operational | frontend/src/store/slices/migration_map.ts | frontend/src/store/themeStore.test.ts, frontend/src/store/slices/migration_map.ts |
| 212 | Frontend State Store | frontend/src/store/unifiedStore.ts | 🟢 Operational | 6 callers (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) | 7 test files (frontend/src/store/index.test.ts, ...) |
| 213 | Frontend State Store | frontend/src/store/useIdeStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 214 | Frontend State Store | frontend/src/store/useIdeStore.ts | 🟢 Operational | 6 callers (frontend/src/components/editor/AiAssistantBar.tsx, ...) | 7 test files (frontend/src/store/useIdeStore.test.ts, ...) |
| 215 | Frontend State Store | frontend/src/store/useStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 216 | Frontend State Store | frontend/src/store/useStore.ts | 🟢 Operational | 10 callers (frontend/src/components/admin/CICDVisualizer.tsx, ...) | 13 test files (frontend/src/App.test.tsx, ...) |
| 217 | Frontend State Store | frontend/src/store/useSupremeStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 218 | Frontend State Store | frontend/src/store/useSupremeStore.ts | 🟢 Operational | 4 callers (backend/api/routes/files.py, ...) | 4 test files (frontend/src/store/useSupremeStore.test.ts, ...) |
| 219 | Frontend State Store | frontend/src/store/useWorkspaceSettingsStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 220 | Frontend State Store | frontend/src/store/useWorkspaceSettingsStore.ts | 🟢 Operational | frontend/src/components/dashboard/ActionDock.tsx, frontend/src/store/slices/migration_map.ts | 3 test files (frontend/src/store/useWorkspaceSettingsStore.test.ts, ...) |
| 221 | Frontend State Store | frontend/src/store/useWorkspaceStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 222 | Frontend State Store | frontend/src/store/useWorkspaceStore.ts | 🟢 Operational | frontend/src/components/dock/DynamicActionDock.tsx, frontend/src/store/slices/migration_map.ts | 3 test files (frontend/src/store/useWorkspaceStore.test.ts, ...) |
| 223 | Frontend State Store | frontend/src/store/workspaceUiStateStore.test.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 224 | Frontend State Store | frontend/src/store/workspaceUiStateStore.ts | 🟢 Operational | frontend/src/components/chat/ChatInterface.tsx | frontend/src/store/workspaceUiStateStore.test.ts, frontend/src/components/chat/ChatInterface.tsx |
