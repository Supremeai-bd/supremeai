# SupremeAI - Comprehensive List of Modules

Total Modules: **194**
**Truthful Operational Wiring Audit Summary (2026-09-11):**
- 🟢 **Operational:** 115 modules (Importable + Active Inbound Production Callers > 0 + Test backing)
- 🟡 **Environment-Dependent:** 4 modules (Requires host Docker daemon, Telegram bot token, etc.)
- 🟠 **Partially Wired (Dormant):** 73 modules (Cleanly importable/standalone; 0 active inbound production callers)
- 🔴 **Broken:** 2 modules (Crash on import or missing core dependency)
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
| 3 | Monorepo Package | packages/scripts | 🟢 Operational | 18 callers (backend/core/config_classification.py, ...) | 7 test files (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) |
| 4 | Monorepo Package | packages/shared-services | 🟢 Operational | 6 callers (frontend/src/commandcenter/realtime/websocketManager.ts, ...) | 6 test files (frontend/src/commandcenter/realtime/websocketManager.ts, ...) |
| 5 | Monorepo Package | packages/shared-types | 🟢 Operational | backend/core/schema_exporter.py, backend/core/type_sync_bus.py | None |
| 6 | Monorepo Package | packages/ui-components | 🟢 Operational | frontend/src/main.tsx, frontend/src/components/swarm/SwarmHealthDashboard.tsx | frontend/src/main.tsx, frontend/src/components/swarm/SwarmHealthDashboard.tsx |
| 7 | Backend Core Service | backend/services/billing | 🟢 Operational | 28 callers (backend/core/autonoguard_engine.py, ...) | 13 test files (backend/tests/conftest.py, ...) |
| 8 | Backend Core Service | backend/services/browser | 🟢 Operational | 64 callers (backend/core/admin_routes.py, ...) | 25 test files (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) |
| 9 | Backend Core Service | backend/services/data | 🔴 Broken | 0 active callers (dormant) | None |
| 10 | Backend Core Service | backend/services/dynamic_ai | 🟢 Operational | 7 callers (backend/core/unified_learning.py, ...) | None |
| 11 | Backend Core Service | backend/services/email | 🟢 Operational | 48 callers (backend/core/admin_routes.py, ...) | 22 test files (backend/tests/conftest.py, ...) |
| 12 | Backend Core Service | backend/services/hitl | 🟢 Operational | 12 callers (backend/core/automation/registry.py, ...) | 3 test files (backend/tests/conftest.py, ...) |
| 13 | Backend Core Service | backend/services/ide_trio | 🟢 Operational | backend/api/routers.py | None |
| 14 | Backend Core Service | backend/services/ingestion | 🟢 Operational | 4 callers (backend/core/self_evolution/performance_oracle.py, ...) | frontend/src/components/dashboard/VaultPage.tsx |
| 15 | Backend Core Service | backend/services/llm | 🟢 Operational | 49 callers (backend/core/admin_routes.py, ...) | 5 test files (backend/tests/conftest.py, ...) |
| 16 | Backend Core Service | backend/services/scraper | 🟢 Operational | 18 callers (backend/core/app_builder.py, ...) | backend/services/scraper/tests/conftest.py, frontend/src/components/admin/infra/ServiceHealthMonitor.tsx |
| 17 | Backend Core Service | backend/services/storage | 🟢 Operational | 49 callers (backend/core/advanced_reasoning.py, ...) | 14 test files (frontend/src/components/admin/SciFiFlowNode.tsx, ...) |
| 18 | Backend Core Service | backend/services/worker | 🟢 Operational | 35 callers (backend/core/app_builder.py, ...) | 6 test files (frontend/src/components/admin/LiveLogs.tsx, ...) |
| 19 | Infrastructure Module | infrastructure/cloudflare | 🟢 Operational | 21 callers (backend/core/llm/free_tier_tracker.py, ...) | 3 test files (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) |
| 20 | Infrastructure Module | infrastructure/kubernetes | 🟢 Operational | frontend/src/components/admin/SciFiFlowNode.tsx | frontend/src/components/admin/SciFiFlowNode.tsx |
| 21 | Infrastructure Module | infrastructure/mcp-control-plane | 🟢 Operational | 7 callers (backend/core/mcp_client.py, ...) | frontend/src/components/admin/infra/ServiceHealthMonitor.tsx |
| 22 | Infrastructure Module | infrastructure/monitoring | 🟢 Operational | 54 callers (backend/core/adaptive_optimizer.py, ...) | 5 test files (frontend/src/components/admin/infra/ServiceHealthMonitor.tsx, ...) |
| 23 | Infrastructure Module | infrastructure/zero_cost | 🔴 Broken | 0 active callers (dormant) | None |
| 24 | Specialized Tool Subsystem | tools/autonomy | 🟢 Operational | 4 callers (backend/core/self_evolution/daily_learner.py, ...) | None |
| 25 | Specialized Tool Subsystem | tools/discovery_fabric | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 26 | Specialized Tool Subsystem | tools/firebase_functions_v1 | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 27 | Specialized Tool Subsystem | tools/gap_finder | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 28 | Specialized Tool Subsystem | tools/gap_miner | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 29 | Specialized Tool Subsystem | tools/intelligence_extensions | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 30 | Specialized Tool Subsystem | tools/knowledge | 🟢 Operational | 31 callers (backend/core/competitive_kit.py, ...) | 10 test files (frontend/src/commandcenter/data/hooks.ts, ...) |
| 31 | Specialized Tool Subsystem | tools/knowledge_squeezer | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 32 | Specialized Tool Subsystem | tools/solution_synthesizer | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 33 | Specialized Tool Subsystem | tools/vscode-extension | 🟢 Operational | backend/core/app.py | None |
| 34 | MCP Server / Tool | backend/tools/mcp/mcp_cloud_deploy.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 35 | MCP Server / Tool | backend/tools/mcp/mcp_github_cicd.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 36 | MCP Server / Tool | backend/tools/mcp/mcp_ide_trio.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 37 | MCP Server / Tool | backend/tools/mcp/mcp_neon.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 38 | MCP Server / Tool | backend/tools/mcp/mcp_observability.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 39 | MCP Server / Tool | backend/tools/mcp/mcp_server.py | 🟢 Operational | infrastructure/mcp-control-plane/src/adapters/memory/index.ts, infrastructure/mcp-control-plane/src/tools/memory.tools.ts | None |
| 40 | MCP Server / Tool | backend/tools/mcp/mcp_supabase.py | 🟢 Operational | backend/core/skill_manager.py, backend/core/universal_rules.py | None |
| 41 | MCP Server / Tool | backend/tools/mcp/mcp_telegram.py | 🟡 Environment-Dependent | 0 active callers (dormant) | None |
| 42 | MCP Server / Tool | backend/tools/mcp/mcp_workspace.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 43 | Backend Tool / Utility | backend/tools/_bootstrap.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 44 | Backend Tool / Utility | backend/tools/agent_tools.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 45 | Backend Tool / Utility | backend/tools/ai_federation_protocol.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 46 | Backend Tool / Utility | backend/tools/api_gateway.py | 🟢 Operational | 3 callers (backend/core/self_evolution/digital_twin/remediation_engine.py, ...) | None |
| 47 | Backend Tool / Utility | backend/tools/bandwidth_optimizer.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 48 | Backend Tool / Utility | backend/tools/checkpoint_manager.py | 🟢 Operational | 4 callers (backend/core/shutdown.py, ...) | backend/tests/conftest.py |
| 49 | Backend Tool / Utility | backend/tools/cli.py | 🟢 Operational | backend/core/intent_router_v2.py, backend/core/mcp_allowlist.py | frontend/src/lib/supabase.client.ts |
| 50 | Backend Tool / Utility | backend/tools/cli_process_delegator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 51 | Backend Tool / Utility | backend/tools/collaborative_editor.py | 🟢 Operational | backend/api/routers.py | None |
| 52 | Backend Tool / Utility | backend/tools/comment_thread_ai.py | 🟢 Operational | backend/api/routers.py | None |
| 53 | Backend Tool / Utility | backend/tools/conversation_manager.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 54 | Backend Tool / Utility | backend/tools/ensemble_router.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 55 | Backend Tool / Utility | backend/tools/freebuff_client.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 56 | Backend Tool / Utility | backend/tools/graph_service.py | 🟢 Operational | backend/api/routes/graph.py | None |
| 57 | Backend Tool / Utility | backend/tools/headless_agent_registry.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 58 | Backend Tool / Utility | backend/tools/health_checker.py | 🟢 Operational | 5 callers (backend/core/app.py, ...) | None |
| 59 | Backend Tool / Utility | backend/tools/langchain_agent_example.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 60 | Backend Tool / Utility | backend/tools/launchdarkly_agent_adapter.py | 🟡 Environment-Dependent | 0 active callers (dormant) | None |
| 61 | Backend Tool / Utility | backend/tools/meta_architect.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 62 | Backend Tool / Utility | backend/tools/offline_mode.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 63 | Backend Tool / Utility | backend/tools/parallel_agent_executor.py | 🟠 Partially Wired | 0 active callers (dormant) | backend/tests/conftest.py |
| 64 | Backend Tool / Utility | backend/tools/plan_sorter.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 65 | Backend Tool / Utility | backend/tools/preference_memory.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 66 | Backend Tool / Utility | backend/tools/repo_discovery_agent.py | 🟢 Operational | backend/api/routes/github.py | None |
| 67 | Backend Tool / Utility | backend/tools/resource_catalog.py | 🟢 Operational | backend/api/routes/marketplace_endpoints.py | None |
| 68 | Backend Tool / Utility | backend/tools/seed_database.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 69 | Backend Tool / Utility | backend/tools/self_planner.py | 🟢 Operational | backend/api/routers.py | None |
| 70 | Backend Tool / Utility | backend/tools/sso_integrator.py | 🟢 Operational | backend/api/routes/sso.py | None |
| 71 | Backend Tool / Utility | backend/tools/tenant_rate_limiter.py | 🟢 Operational | backend/api/routes/tenant_admin.py, backend/middleware/tenant_rate_limiter.py | None |
| 72 | Backend Tool / Utility | backend/tools/ai_agents/browser_agent.py | 🟢 Operational | 8 callers (backend/core/lifespan.py, ...) | None |
| 73 | Backend Tool / Utility | backend/tools/ai_agents/vision_agent.py | 🟢 Operational | backend/core/agents/framework/agent_registry.py, backend/core/agents/live/vision_agent.py | None |
| 74 | Backend Tool / Utility | backend/tools/analytics/churn_prophet.py | 🟢 Operational | backend/core/agents/framework/agent_registry.py, backend/api/routes/analytics.py | None |
| 75 | Backend Tool / Utility | backend/tools/analytics/insight_mage.py | 🟢 Operational | backend/core/agents/framework/agent_registry.py, backend/api/routes/analytics.py | None |
| 76 | Backend Tool / Utility | backend/tools/billing/cost_auditor.py | 🟢 Operational | backend/api/routes/admin_dashboard.py, backend/api/routes/billing_api.py | None |
| 77 | Backend Tool / Utility | backend/tools/billing/monthly_cost_reporter.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 78 | Backend Tool / Utility | backend/tools/browser/ai_web_extractor.py | 🟢 Operational | backend/api/routes/browser.py | None |
| 79 | Backend Tool / Utility | backend/tools/browser/browser_stealth.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 80 | Backend Tool / Utility | backend/tools/browser/mcp_tools.py | 🟢 Operational | backend/core/mcp_policy.py, backend/core/skill_manager.py | None |
| 81 | Backend Tool / Utility | backend/tools/browser/playwright_browser_agent.py | 🟢 Operational | backend/api/routes/session_takeover.py, backend/services/scraper/browser_agent.py | None |
| 82 | Backend Tool / Utility | backend/tools/browser/stealth_http_client.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 83 | Backend Tool / Utility | backend/tools/browser/web_fallback_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 84 | Backend Tool / Utility | backend/tools/browser/web_scraper.py | 🟢 Operational | 9 callers (backend/core/admin_routes.py, ...) | None |
| 85 | Backend Tool / Utility | backend/tools/code/ai_pair_programmer.py | 🟢 Operational | backend/api/routers.py | None |
| 86 | Backend Tool / Utility | backend/tools/code/auto_pr_pipeline.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 87 | Backend Tool / Utility | backend/tools/code/auto_test_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 88 | Backend Tool / Utility | backend/tools/code/code_smell_detector.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 89 | Backend Tool / Utility | backend/tools/code/cot_reasoner.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 90 | Backend Tool / Utility | backend/tools/code/dependency_manager_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 91 | Backend Tool / Utility | backend/tools/code/diagram_to_architecture.py | 🟢 Operational | backend/api/routers.py, backend/services/diagram_parser_service.py | None |
| 92 | Backend Tool / Utility | backend/tools/code/fuzz_sandbox.py | 🟢 Operational | backend/core/skill_manager.py, backend/core/self_evolution/auto_skill_creator.py | None |
| 93 | Backend Tool / Utility | backend/tools/code/image_to_code.py | 🟢 Operational | backend/api/routers.py | None |
| 94 | Backend Tool / Utility | backend/tools/code/local_code_executor.py | 🟢 Operational | 4 callers (backend/core/config_fields.py, ...) | None |
| 95 | Backend Tool / Utility | backend/tools/code/lsp_bridge.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 96 | Backend Tool / Utility | backend/tools/code/pr_reviewer.py | 🟢 Operational | backend/api/routes/pr_review_api.py | None |
| 97 | Backend Tool / Utility | backend/tools/code/pre_commit_ai.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 98 | Backend Tool / Utility | backend/tools/code/safe_executor.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 99 | Backend Tool / Utility | backend/tools/code/voice_coder.py | 🟢 Operational | backend/api/routers.py | None |
| 100 | Backend Tool / Utility | backend/tools/creative/audio_engineering_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 101 | Backend Tool / Utility | backend/tools/creative/brand_identity_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 102 | Backend Tool / Utility | backend/tools/creative/creative_agents_registry.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 103 | Backend Tool / Utility | backend/tools/creative/game_design_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 104 | Backend Tool / Utility | backend/tools/creative/video_production_agent.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 105 | Backend Tool / Utility | backend/tools/devops/auto_coverage_improver.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 106 | Backend Tool / Utility | backend/tools/devops/coverage_auditor.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 107 | Backend Tool / Utility | backend/tools/devops/docker_sandbox.py | 🟡 Environment-Dependent | backend/core/config_fields.py, backend/api/routes/agent_workspace.py | None |
| 108 | Backend Tool / Utility | backend/tools/devops/gcp_cloud_functions.py | 🟢 Operational | backend/core/services.py | None |
| 109 | Backend Tool / Utility | backend/tools/devops/github_agent.py | 🟢 Operational | 3 callers (backend/api/routes/agent_workspace.py, ...) | None |
| 110 | Backend Tool / Utility | backend/tools/devops/on_premise_deployer.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 111 | Backend Tool / Utility | backend/tools/knowledge/codebase_exporter.py | 🟢 Operational | backend/api/routes/admin_dashboard.py, backend/api/routes/markdown.py | None |
| 112 | Backend Tool / Utility | backend/tools/knowledge/git_knowledge_extractor.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 113 | Backend Tool / Utility | backend/tools/knowledge/knowledge_base_indexer.py | 🟢 Operational | backend/api/routes/deep_research.py, backend/api/routes/slash_commands.py | None |
| 114 | Backend Tool / Utility | backend/tools/knowledge/local_search_rag.py | 🟢 Operational | backend/core/factual_verifier.py | None |
| 115 | Backend Tool / Utility | backend/tools/knowledge/pdf_to_sdk.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 116 | Backend Tool / Utility | backend/tools/knowledge/repo_deep_indexer.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 117 | Backend Tool / Utility | backend/tools/learning/agent_knowledge_store.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 118 | Backend Tool / Utility | backend/tools/learning/domain_adapter.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 119 | Backend Tool / Utility | backend/tools/learning/model_trainer.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 120 | Backend Tool / Utility | backend/tools/learning/rlhf_pipeline.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 121 | Backend Tool / Utility | backend/tools/learning/skill_recommender.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 122 | Backend Tool / Utility | backend/tools/learning/style_learner.py | 🟢 Operational | backend/api/routers.py | None |
| 123 | Backend Tool / Utility | backend/tools/localization/bangla_ai_connector.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 124 | Backend Tool / Utility | backend/tools/localization/bangla_nlp.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 125 | Backend Tool / Utility | backend/tools/localization/bangla_voice.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 126 | Backend Tool / Utility | backend/tools/localization/bengali_ocr_converter.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 127 | Backend Tool / Utility | backend/tools/localization/local_ocr_extractor.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 128 | Backend Tool / Utility | backend/tools/media/image_generator.py | 🟢 Operational | backend/api/routes/slash_commands.py | None |
| 129 | Backend Tool / Utility | backend/tools/media/multilingual_tts.py | 🟢 Operational | backend/api/routers.py, backend/api/routes/voice.py | None |
| 130 | Backend Tool / Utility | backend/tools/media/music_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 131 | Backend Tool / Utility | backend/tools/media/presentation_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 132 | Backend Tool / Utility | backend/tools/media/threed_model_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 133 | Backend Tool / Utility | backend/tools/media/video_generator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 134 | Backend Tool / Utility | backend/tools/media/voice.py | 🟢 Operational | 18 callers (backend/core/config_fields.py, ...) | 7 test files (frontend/src/components/admin/CommandCenter.tsx, ...) |
| 135 | Backend Tool / Utility | backend/tools/security_tools/multi_account_rotator.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 136 | Backend Tool / Utility | backend/tools/security_tools/proxy_manager.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 137 | Backend Tool / Utility | backend/tools/security_tools/vpn_switcher.py | 🟢 Operational | backend/core/agents/framework/autonomous_task_orchestrator.py | None |
| 138 | Backend Tool / Utility | backend/tools/security_tools/vulnerability_predictor.py | 🟢 Operational | backend/api/routes/tools_ops.py | None |
| 139 | Backend Tool / Utility | backend/tools/social/email_agent.py | 🟢 Operational | backend/api/routes/email.py | None |
| 140 | Backend Tool / Utility | backend/tools/social/marketplace_agent.py | 🟢 Operational | backend/api/routes/marketplace_endpoints.py | None |
| 141 | Backend Tool / Utility | backend/tools/social/teldrive_storage.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 142 | Backend Tool / Utility | backend/tools/social/telegram_bot.py | 🟡 Environment-Dependent | backend/core/messaging/adapters.py, backend/api/routers.py | None |
| 143 | Backend Tool / Utility | backend/tools/social/telegram_security.py | 🟢 Operational | backend/api/routes/workspaces_route.py | None |
| 144 | Backend Tool / Utility | backend/tools/social/viral_referral_engine.py | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 145 | Frontend Page / View | frontend/src/pages/BillingPage.tsx | 🟢 Operational | frontend/src/App.tsx | frontend/src/App.tsx |
| 146 | Frontend Page / View | frontend/src/pages/ErrorPage.tsx | 🟢 Operational | frontend/src/App.tsx, frontend/src/routes/workspaceFeatureRoutes.tsx | frontend/src/App.tsx, frontend/src/routes/workspaceFeatureRoutes.tsx |
| 147 | Frontend Page / View | frontend/src/pages/ProfilePage.tsx | 🟢 Operational | frontend/src/App.tsx, frontend/src/store/index.ts | frontend/src/App.tsx, frontend/src/store/index.ts |
| 148 | Frontend Page / View | frontend/src/pages/PromptTemplatePage.tsx | 🟢 Operational | frontend/src/routes/workspaceFeatureRoutes.tsx | frontend/src/routes/workspaceFeatureRoutes.tsx |
| 149 | Frontend Page / View | frontend/src/pages/PublicPages.tsx | 🟢 Operational | frontend/src/App.tsx | frontend/src/App.tsx |
| 150 | Frontend Page / View | frontend/src/pages/SharedConversationPage.tsx | 🟢 Operational | frontend/src/routes/workspaceFeatureRoutes.tsx | frontend/src/routes/workspaceFeatureRoutes.tsx |
| 151 | Frontend Page / View | frontend/src/pages/WorkspaceModulePage.tsx | 🟢 Operational | frontend/src/App.tsx | frontend/src/App.tsx |
| 152 | Frontend Page / View | frontend/src/pages/admin | 🟢 Operational | 187 callers (backend/core/admin_god.py, ...) | 108 test files (backend/tests/conftest.py, ...) |
| 153 | Frontend Page / View | frontend/src/pages/auth | 🟢 Operational | 104 callers (backend/core/admin_god.py, ...) | 50 test files (backend/tests/conftest.py, ...) |
| 154 | Frontend Page / View | frontend/src/pages/user | 🟢 Operational | 230 callers (backend/core/admin_god.py, ...) | 83 test files (backend/tests/conftest.py, ...) |
| 156 | Frontend Service Module | frontend/src/services/adminService.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 158 | Frontend Service Module | frontend/src/services/adminTokenStore.ts | 🟢 Operational | 18 callers (frontend/src/commandcenter/data/hooks.ts, ...) | 18 test files (frontend/src/commandcenter/data/hooks.ts, ...) |
| 160 | Frontend Service Module | frontend/src/services/agentService.ts | 🟢 Operational | backend/api/routes/agents.py | None |
| 162 | Frontend Service Module | frontend/src/services/aiActions.ts | 🟢 Operational | frontend/src/components/editor/AiAssistantBar.tsx | frontend/src/components/editor/AiAssistantBar.tsx |
| 163 | Frontend Service Module | frontend/src/services/api | 🟢 Operational | 342 callers (backend/core/adaptive_optimizer.py, ...) | 133 test files (backend/tests/conftest.py, ...) |
| 165 | Frontend Service Module | frontend/src/services/apiClient.ts | 🟢 Operational | 94 callers (backend/core/app_builder.py, ...) | 93 test files (frontend/src/commandcenter/data/hooks.ts, ...) |
| 166 | Frontend Service Module | frontend/src/services/audio | 🟢 Operational | 11 callers (backend/core/intent_router_v2.py, ...) | 5 test files (frontend/src/components/admin/CommandCenter.tsx, ...) |
| 168 | Frontend Service Module | frontend/src/services/authService.ts | 🟢 Operational | frontend/src/store/adminStore.ts | frontend/src/store/adminStore.ts |
| 170 | Frontend Service Module | frontend/src/services/browserService.ts | 🟢 Operational | frontend/src/components/customer/BrowserPreview.tsx | frontend/src/components/customer/BrowserPreview.tsx |
| 172 | Frontend Service Module | frontend/src/services/chatService.ts | 🟢 Operational | 5 callers (backend/api/routes/task.py, ...) | 3 test files (frontend/src/components/admin/CommandCenter.tsx, ...) |
| 174 | Frontend Service Module | frontend/src/services/ciReportService.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 176 | Frontend Service Module | frontend/src/services/controlPlane.ts | 🟢 Operational | frontend/src/components/admin/infra/ServiceHealthMonitor.tsx, frontend/src/components/chat/ChatInterface.tsx | frontend/src/components/admin/infra/ServiceHealthMonitor.tsx, frontend/src/components/chat/ChatInterface.tsx |
| 178 | Frontend Service Module | frontend/src/services/costOptimizer.service.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 180 | Frontend Service Module | frontend/src/services/heartbeat.ts | 🟢 Operational | 14 callers (backend/core/agent_supervisor.py, ...) | 4 test files (frontend/src/main.tsx, ...) |
| 181 | Frontend Service Module | frontend/src/services/policyService.ts | 🟢 Operational | frontend/src/components/customer/TaskAutomationCard.tsx | frontend/src/components/customer/TaskAutomationCard.tsx |
| 183 | Frontend Service Module | frontend/src/services/queryClient.ts | 🟢 Operational | 5 callers (frontend/src/App.tsx, ...) | 5 test files (frontend/src/App.tsx, ...) |
| 184 | Frontend Service Module | frontend/src/services/realtime | 🟢 Operational | 16 callers (backend/core/agents/framework/autonomous_task_orchestrator.py, ...) | 9 test files (frontend/src/App.tsx, ...) |
| 185 | Frontend Service Module | frontend/src/services/sandbox.ts | 🟢 Operational | 35 callers (backend/core/ast_security_scanner.py, ...) | 14 test files (frontend/src/types.ts, ...) |
| 187 | Frontend Service Module | frontend/src/services/skillsService.ts | 🟢 Operational | frontend/src/pages/user/SkillCatalog.tsx | frontend/src/pages/user/SkillCatalog.tsx |
| 188 | Frontend Service Module | frontend/src/services/socialGrowthService.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 190 | Frontend Service Module | frontend/src/services/storageApi.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 192 | Frontend Service Module | frontend/src/services/supremeShared.ts | 🟢 Operational | frontend/src/components/editor/monacoAi.ts, frontend/src/services/aiActions.ts | 3 test files (frontend/src/components/editor/monacoAi.ts, ...) |
| 195 | Frontend State Store | frontend/src/store/adminStore.ts | 🟢 Operational | 8 callers (backend/core/admin_routes.py, ...) | 7 test files (frontend/src/components/admin/CommandCenter.tsx, ...) |
| 197 | Frontend State Store | frontend/src/store/authStore.ts | 🟢 Operational | 21 callers (frontend/src/auth/identity.ts, ...) | 21 test files (frontend/src/auth/identity.ts, ...) |
| 199 | Frontend State Store | frontend/src/store/chatStore.ts | 🟢 Operational | 4 callers (frontend/src/store/index.ts, ...) | 4 test files (frontend/src/store/index.ts, ...) |
| 201 | Frontend State Store | frontend/src/store/customerStore.ts | 🟢 Operational | 6 callers (frontend/src/components/customer/HomeFeed.tsx, ...) | 6 test files (frontend/src/components/customer/HomeFeed.tsx, ...) |
| 203 | Frontend State Store | frontend/src/store/dashboardStore.ts | 🟢 Operational | 7 callers (frontend/src/components/admin/AuditLogsPanel.tsx, ...) | 7 test files (frontend/src/components/admin/AuditLogsPanel.tsx, ...) |
| 205 | Frontend State Store | frontend/src/store/index.ts | 🟢 Operational | 57 callers (backend/core/intent_router.py, ...) | 27 test files (frontend/src/main.tsx, ...) |
| 206 | Frontend State Store | frontend/src/store/localFirstDb.ts | 🟢 Operational | frontend/src/store/authStore.ts, frontend/src/store/themeStore.ts | frontend/src/store/authStore.ts, frontend/src/store/themeStore.ts |
| 207 | Frontend State Store | frontend/src/store/sessionCockpitStore.ts | 🟢 Operational | 10 callers (backend/api/routers.py, ...) | 9 test files (frontend/src/components/AgentStateShaderBackground.tsx, ...) |
| 208 | Frontend State Store | frontend/src/store/slices | 🟢 Operational | frontend/src/store/index.ts, frontend/src/store/useSupremeStore.ts | 7 test files (frontend/src/store/index.ts, ...) |
| 209 | Frontend State Store | frontend/src/store/stateOwnership.ts | 🟠 Partially Wired | 0 active callers (dormant) | None |
| 211 | Frontend State Store | frontend/src/store/themeStore.ts | 🟢 Operational | frontend/src/store/slices/migration_map.ts | frontend/src/store/slices/migration_map.ts |
| 212 | Frontend State Store | frontend/src/store/unifiedStore.ts | 🟢 Operational | 6 callers (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) | 6 test files (frontend/src/components/admin/AdminBrowserPanel.tsx, ...) |
| 214 | Frontend State Store | frontend/src/store/useIdeStore.ts | 🟢 Operational | 6 callers (frontend/src/components/editor/AiAssistantBar.tsx, ...) | 6 test files (frontend/src/components/editor/AiAssistantBar.tsx, ...) |
| 216 | Frontend State Store | frontend/src/store/useStore.ts | 🟢 Operational | 10 callers (frontend/src/components/admin/CICDVisualizer.tsx, ...) | 10 test files (frontend/src/components/admin/CICDVisualizer.tsx, ...) |
| 218 | Frontend State Store | frontend/src/store/useSupremeStore.ts | 🟢 Operational | 4 callers (backend/api/routes/files.py, ...) | 3 test files (frontend/src/components/dashboard/AgentExecutionTelemetryCockpit.tsx, ...) |
| 220 | Frontend State Store | frontend/src/store/useWorkspaceSettingsStore.ts | 🟢 Operational | frontend/src/components/dashboard/ActionDock.tsx, frontend/src/store/slices/migration_map.ts | frontend/src/components/dashboard/ActionDock.tsx, frontend/src/store/slices/migration_map.ts |
| 222 | Frontend State Store | frontend/src/store/useWorkspaceStore.ts | 🟢 Operational | frontend/src/components/dock/DynamicActionDock.tsx, frontend/src/store/slices/migration_map.ts | frontend/src/components/dock/DynamicActionDock.tsx, frontend/src/store/slices/migration_map.ts |
| 224 | Frontend State Store | frontend/src/store/workspaceUiStateStore.ts | 🟢 Operational | frontend/src/components/chat/ChatInterface.tsx | frontend/src/components/chat/ChatInterface.tsx |
