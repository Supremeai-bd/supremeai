# SupremeAI Modules Audit Directory

Total Documented Functional Modules: **224**

<!--
ARCHITECTURE DIRECTIVE / GOVERNANCE GUARDRAIL:
DO NOT expand this catalog to file-level granularity (1000+ individual files).
In SupremeAI architecture, a 'Module' is a high-level cohesive subsystem, service, monorepo package,
MCP server, tool, or state store.
Individual UI components (e.g. Button.tsx, Skeleton.tsx), utility helpers (e.g. cn.ts), hooks,
and type interfaces belong to their parent module and are documented within that module's scope.
Keeping this index strictly at the 224 functional module boundary is mandatory for system wiring, clarity, and dependency governance.
-->

| ID | Category | Module Name / Relative Path | Documentation Link |
|---|---|---|---|
| 1 | Monorepo Package | `packages/core-infrastructure` | [001_packages_core-infrastructure.md](./001_packages_core-infrastructure.md) |
| 2 | Monorepo Package | `packages/design-tokens` | [002_packages_design-tokens.md](./002_packages_design-tokens.md) |
| 3 | Monorepo Package | `packages/scripts` | [003_packages_scripts.md](./003_packages_scripts.md) |
| 4 | Monorepo Package | `packages/shared-services` | [004_packages_shared-services.md](./004_packages_shared-services.md) |
| 5 | Monorepo Package | `packages/shared-types` | [005_packages_shared-types.md](./005_packages_shared-types.md) |
| 6 | Monorepo Package | `packages/ui-components` | [006_packages_ui-components.md](./006_packages_ui-components.md) |
| 7 | Backend Core Service | `backend/services/billing` | [007_backend_services_billing.md](./007_backend_services_billing.md) |
| 8 | Backend Core Service | `backend/services/browser` | [008_backend_services_browser.md](./008_backend_services_browser.md) |
| 9 | Backend Core Service | `backend/services/data` | [009_backend_services_data.md](./009_backend_services_data.md) |
| 10 | Backend Core Service | `backend/services/dynamic_ai` | [010_backend_services_dynamic_ai.md](./010_backend_services_dynamic_ai.md) |
| 11 | Backend Core Service | `backend/services/email` | [011_backend_services_email.md](./011_backend_services_email.md) |
| 12 | Backend Core Service | `backend/services/hitl` | [012_backend_services_hitl.md](./012_backend_services_hitl.md) |
| 13 | Backend Core Service | `backend/services/ide_trio` | [013_backend_services_ide_trio.md](./013_backend_services_ide_trio.md) |
| 14 | Backend Core Service | `backend/services/ingestion` | [014_backend_services_ingestion.md](./014_backend_services_ingestion.md) |
| 15 | Backend Core Service | `backend/services/llm` | [015_backend_services_llm.md](./015_backend_services_llm.md) |
| 16 | Backend Core Service | `backend/services/scraper` | [016_backend_services_scraper.md](./016_backend_services_scraper.md) |
| 17 | Backend Core Service | `backend/services/storage` | [017_backend_services_storage.md](./017_backend_services_storage.md) |
| 18 | Backend Core Service | `backend/services/worker` | [018_backend_services_worker.md](./018_backend_services_worker.md) |
| 19 | Infrastructure Module | `infrastructure/cloudflare` | [019_infrastructure_cloudflare.md](./019_infrastructure_cloudflare.md) |
| 20 | Infrastructure Module | `infrastructure/kubernetes` | [020_infrastructure_kubernetes.md](./020_infrastructure_kubernetes.md) |
| 21 | Infrastructure Module | `infrastructure/mcp-control-plane` | [021_infrastructure_mcp-control-plane.md](./021_infrastructure_mcp-control-plane.md) |
| 22 | Infrastructure Module | `infrastructure/monitoring` | [022_infrastructure_monitoring.md](./022_infrastructure_monitoring.md) |
| 23 | Infrastructure Module | `infrastructure/zero_cost` | [023_infrastructure_zero_cost.md](./023_infrastructure_zero_cost.md) |
| 24 | Specialized Tool Subsystem | `tools/autonomy` | [024_tools_autonomy.md](./024_tools_autonomy.md) |
| 25 | Specialized Tool Subsystem | `tools/discovery_fabric` | [025_tools_discovery_fabric.md](./025_tools_discovery_fabric.md) |
| 26 | Specialized Tool Subsystem | `tools/firebase_functions_v1` | [026_tools_firebase_functions_v1.md](./026_tools_firebase_functions_v1.md) |
| 27 | Specialized Tool Subsystem | `tools/gap_finder` | [027_tools_gap_finder.md](./027_tools_gap_finder.md) |
| 28 | Specialized Tool Subsystem | `tools/gap_miner` | [028_tools_gap_miner.md](./028_tools_gap_miner.md) |
| 29 | Specialized Tool Subsystem | `tools/intelligence_extensions` | [029_tools_intelligence_extensions.md](./029_tools_intelligence_extensions.md) |
| 30 | Specialized Tool Subsystem | `tools/knowledge` | [030_tools_knowledge.md](./030_tools_knowledge.md) |
| 31 | Specialized Tool Subsystem | `tools/knowledge_squeezer` | [031_tools_knowledge_squeezer.md](./031_tools_knowledge_squeezer.md) |
| 32 | Specialized Tool Subsystem | `tools/solution_synthesizer` | [032_tools_solution_synthesizer.md](./032_tools_solution_synthesizer.md) |
| 33 | Specialized Tool Subsystem | `tools/vscode-extension` | [033_tools_vscode-extension.md](./033_tools_vscode-extension.md) |
| 34 | MCP Server / Tool | `backend/tools/mcp/mcp_cloud_deploy.py` | [034_backend_tools_mcp_mcp_cloud_deploy_py.md](./034_backend_tools_mcp_mcp_cloud_deploy_py.md) |
| 35 | MCP Server / Tool | `backend/tools/mcp/mcp_github_cicd.py` | [035_backend_tools_mcp_mcp_github_cicd_py.md](./035_backend_tools_mcp_mcp_github_cicd_py.md) |
| 36 | MCP Server / Tool | `backend/tools/mcp/mcp_ide_trio.py` | [036_backend_tools_mcp_mcp_ide_trio_py.md](./036_backend_tools_mcp_mcp_ide_trio_py.md) |
| 37 | MCP Server / Tool | `backend/tools/mcp/mcp_neon.py` | [037_backend_tools_mcp_mcp_neon_py.md](./037_backend_tools_mcp_mcp_neon_py.md) |
| 38 | MCP Server / Tool | `backend/tools/mcp/mcp_observability.py` | [038_backend_tools_mcp_mcp_observability_py.md](./038_backend_tools_mcp_mcp_observability_py.md) |
| 39 | MCP Server / Tool | `backend/tools/mcp/mcp_server.py` | [039_backend_tools_mcp_mcp_server_py.md](./039_backend_tools_mcp_mcp_server_py.md) |
| 40 | MCP Server / Tool | `backend/tools/mcp/mcp_supabase.py` | [040_backend_tools_mcp_mcp_supabase_py.md](./040_backend_tools_mcp_mcp_supabase_py.md) |
| 41 | MCP Server / Tool | `backend/tools/mcp/mcp_telegram.py` | [041_backend_tools_mcp_mcp_telegram_py.md](./041_backend_tools_mcp_mcp_telegram_py.md) |
| 42 | MCP Server / Tool | `backend/tools/mcp/mcp_workspace.py` | [042_backend_tools_mcp_mcp_workspace_py.md](./042_backend_tools_mcp_mcp_workspace_py.md) |
| 43 | Backend Tool / Utility | `backend/tools/_bootstrap.py` | [043_backend_tools__bootstrap_py.md](./043_backend_tools__bootstrap_py.md) |
| 44 | Backend Tool / Utility | `backend/tools/agent_tools.py` | [044_backend_tools_agent_tools_py.md](./044_backend_tools_agent_tools_py.md) |
| 45 | Backend Tool / Utility | `backend/tools/ai_federation_protocol.py` | [045_backend_tools_ai_federation_protocol_py.md](./045_backend_tools_ai_federation_protocol_py.md) |
| 46 | Backend Tool / Utility | `backend/tools/api_gateway.py` | [046_backend_tools_api_gateway_py.md](./046_backend_tools_api_gateway_py.md) |
| 47 | Backend Tool / Utility | `backend/tools/bandwidth_optimizer.py` | [047_backend_tools_bandwidth_optimizer_py.md](./047_backend_tools_bandwidth_optimizer_py.md) |
| 48 | Backend Tool / Utility | `backend/tools/checkpoint_manager.py` | [048_backend_tools_checkpoint_manager_py.md](./048_backend_tools_checkpoint_manager_py.md) |
| 49 | Backend Tool / Utility | `backend/tools/cli.py` | [049_backend_tools_cli_py.md](./049_backend_tools_cli_py.md) |
| 50 | Backend Tool / Utility | `backend/tools/cli_process_delegator.py` | [050_backend_tools_cli_process_delegator_py.md](./050_backend_tools_cli_process_delegator_py.md) |
| 51 | Backend Tool / Utility | `backend/tools/collaborative_editor.py` | [051_backend_tools_collaborative_editor_py.md](./051_backend_tools_collaborative_editor_py.md) |
| 52 | Backend Tool / Utility | `backend/tools/comment_thread_ai.py` | [052_backend_tools_comment_thread_ai_py.md](./052_backend_tools_comment_thread_ai_py.md) |
| 53 | Backend Tool / Utility | `backend/tools/conversation_manager.py` | [053_backend_tools_conversation_manager_py.md](./053_backend_tools_conversation_manager_py.md) |
| 54 | Backend Tool / Utility | `backend/tools/ensemble_router.py` | [054_backend_tools_ensemble_router_py.md](./054_backend_tools_ensemble_router_py.md) |
| 55 | Backend Tool / Utility | `backend/tools/freebuff_client.py` | [055_backend_tools_freebuff_client_py.md](./055_backend_tools_freebuff_client_py.md) |
| 56 | Backend Tool / Utility | `backend/tools/graph_service.py` | [056_backend_tools_graph_service_py.md](./056_backend_tools_graph_service_py.md) |
| 57 | Backend Tool / Utility | `backend/tools/headless_agent_registry.py` | [057_backend_tools_headless_agent_registry_py.md](./057_backend_tools_headless_agent_registry_py.md) |
| 58 | Backend Tool / Utility | `backend/tools/health_checker.py` | [058_backend_tools_health_checker_py.md](./058_backend_tools_health_checker_py.md) |
| 59 | Backend Tool / Utility | `backend/tools/langchain_agent_example.py` | [059_backend_tools_langchain_agent_example_py.md](./059_backend_tools_langchain_agent_example_py.md) |
| 60 | Backend Tool / Utility | `backend/tools/launchdarkly_agent_adapter.py` | [060_backend_tools_launchdarkly_agent_adapter_py.md](./060_backend_tools_launchdarkly_agent_adapter_py.md) |
| 61 | Backend Tool / Utility | `backend/tools/meta_architect.py` | [061_backend_tools_meta_architect_py.md](./061_backend_tools_meta_architect_py.md) |
| 62 | Backend Tool / Utility | `backend/tools/offline_mode.py` | [062_backend_tools_offline_mode_py.md](./062_backend_tools_offline_mode_py.md) |
| 63 | Backend Tool / Utility | `backend/tools/parallel_agent_executor.py` | [063_backend_tools_parallel_agent_executor_py.md](./063_backend_tools_parallel_agent_executor_py.md) |
| 64 | Backend Tool / Utility | `backend/tools/plan_sorter.py` | [064_backend_tools_plan_sorter_py.md](./064_backend_tools_plan_sorter_py.md) |
| 65 | Backend Tool / Utility | `backend/tools/preference_memory.py` | [065_backend_tools_preference_memory_py.md](./065_backend_tools_preference_memory_py.md) |
| 66 | Backend Tool / Utility | `backend/tools/repo_discovery_agent.py` | [066_backend_tools_repo_discovery_agent_py.md](./066_backend_tools_repo_discovery_agent_py.md) |
| 67 | Backend Tool / Utility | `backend/tools/resource_catalog.py` | [067_backend_tools_resource_catalog_py.md](./067_backend_tools_resource_catalog_py.md) |
| 68 | Backend Tool / Utility | `backend/tools/seed_database.py` | [068_backend_tools_seed_database_py.md](./068_backend_tools_seed_database_py.md) |
| 69 | Backend Tool / Utility | `backend/tools/self_planner.py` | [069_backend_tools_self_planner_py.md](./069_backend_tools_self_planner_py.md) |
| 70 | Backend Tool / Utility | `backend/tools/sso_integrator.py` | [070_backend_tools_sso_integrator_py.md](./070_backend_tools_sso_integrator_py.md) |
| 71 | Backend Tool / Utility | `backend/tools/tenant_rate_limiter.py` | [071_backend_tools_tenant_rate_limiter_py.md](./071_backend_tools_tenant_rate_limiter_py.md) |
| 72 | Backend Tool / Utility | `backend/tools/ai_agents/browser_agent.py` | [072_backend_tools_ai_agents_browser_agent_py.md](./072_backend_tools_ai_agents_browser_agent_py.md) |
| 73 | Backend Tool / Utility | `backend/tools/ai_agents/vision_agent.py` | [073_backend_tools_ai_agents_vision_agent_py.md](./073_backend_tools_ai_agents_vision_agent_py.md) |
| 74 | Backend Tool / Utility | `backend/tools/analytics/churn_prophet.py` | [074_backend_tools_analytics_churn_prophet_py.md](./074_backend_tools_analytics_churn_prophet_py.md) |
| 75 | Backend Tool / Utility | `backend/tools/analytics/insight_mage.py` | [075_backend_tools_analytics_insight_mage_py.md](./075_backend_tools_analytics_insight_mage_py.md) |
| 76 | Backend Tool / Utility | `backend/tools/billing/cost_auditor.py` | [076_backend_tools_billing_cost_auditor_py.md](./076_backend_tools_billing_cost_auditor_py.md) |
| 77 | Backend Tool / Utility | `backend/tools/billing/monthly_cost_reporter.py` | [077_backend_tools_billing_monthly_cost_reporter_py.md](./077_backend_tools_billing_monthly_cost_reporter_py.md) |
| 78 | Backend Tool / Utility | `backend/tools/browser/ai_web_extractor.py` | [078_backend_tools_browser_ai_web_extractor_py.md](./078_backend_tools_browser_ai_web_extractor_py.md) |
| 79 | Backend Tool / Utility | `backend/tools/browser/browser_stealth.py` | [079_backend_tools_browser_browser_stealth_py.md](./079_backend_tools_browser_browser_stealth_py.md) |
| 80 | Backend Tool / Utility | `backend/tools/browser/mcp_tools.py` | [080_backend_tools_browser_mcp_tools_py.md](./080_backend_tools_browser_mcp_tools_py.md) |
| 81 | Backend Tool / Utility | `backend/tools/browser/playwright_browser_agent.py` | [081_backend_tools_browser_playwright_browser_agent_py.md](./081_backend_tools_browser_playwright_browser_agent_py.md) |
| 82 | Backend Tool / Utility | `backend/tools/browser/stealth_http_client.py` | [082_backend_tools_browser_stealth_http_client_py.md](./082_backend_tools_browser_stealth_http_client_py.md) |
| 83 | Backend Tool / Utility | `backend/tools/browser/web_fallback_agent.py` | [083_backend_tools_browser_web_fallback_agent_py.md](./083_backend_tools_browser_web_fallback_agent_py.md) |
| 84 | Backend Tool / Utility | `backend/tools/browser/web_scraper.py` | [084_backend_tools_browser_web_scraper_py.md](./084_backend_tools_browser_web_scraper_py.md) |
| 85 | Backend Tool / Utility | `backend/tools/code/ai_pair_programmer.py` | [085_backend_tools_code_ai_pair_programmer_py.md](./085_backend_tools_code_ai_pair_programmer_py.md) |
| 86 | Backend Tool / Utility | `backend/tools/code/auto_pr_pipeline.py` | [086_backend_tools_code_auto_pr_pipeline_py.md](./086_backend_tools_code_auto_pr_pipeline_py.md) |
| 87 | Backend Tool / Utility | `backend/tools/code/auto_test_generator.py` | [087_backend_tools_code_auto_test_generator_py.md](./087_backend_tools_code_auto_test_generator_py.md) |
| 88 | Backend Tool / Utility | `backend/tools/code/code_smell_detector.py` | [088_backend_tools_code_code_smell_detector_py.md](./088_backend_tools_code_code_smell_detector_py.md) |
| 89 | Backend Tool / Utility | `backend/tools/code/cot_reasoner.py` | [089_backend_tools_code_cot_reasoner_py.md](./089_backend_tools_code_cot_reasoner_py.md) |
| 90 | Backend Tool / Utility | `backend/tools/code/dependency_manager_agent.py` | [090_backend_tools_code_dependency_manager_agent_py.md](./090_backend_tools_code_dependency_manager_agent_py.md) |
| 91 | Backend Tool / Utility | `backend/tools/code/diagram_to_architecture.py` | [091_backend_tools_code_diagram_to_architecture_py.md](./091_backend_tools_code_diagram_to_architecture_py.md) |
| 92 | Backend Tool / Utility | `backend/tools/code/fuzz_sandbox.py` | [092_backend_tools_code_fuzz_sandbox_py.md](./092_backend_tools_code_fuzz_sandbox_py.md) |
| 93 | Backend Tool / Utility | `backend/tools/code/image_to_code.py` | [093_backend_tools_code_image_to_code_py.md](./093_backend_tools_code_image_to_code_py.md) |
| 94 | Backend Tool / Utility | `backend/tools/code/local_code_executor.py` | [094_backend_tools_code_local_code_executor_py.md](./094_backend_tools_code_local_code_executor_py.md) |
| 95 | Backend Tool / Utility | `backend/tools/code/lsp_bridge.py` | [095_backend_tools_code_lsp_bridge_py.md](./095_backend_tools_code_lsp_bridge_py.md) |
| 96 | Backend Tool / Utility | `backend/tools/code/pr_reviewer.py` | [096_backend_tools_code_pr_reviewer_py.md](./096_backend_tools_code_pr_reviewer_py.md) |
| 97 | Backend Tool / Utility | `backend/tools/code/pre_commit_ai.py` | [097_backend_tools_code_pre_commit_ai_py.md](./097_backend_tools_code_pre_commit_ai_py.md) |
| 98 | Backend Tool / Utility | `backend/tools/code/safe_executor.py` | [098_backend_tools_code_safe_executor_py.md](./098_backend_tools_code_safe_executor_py.md) |
| 99 | Backend Tool / Utility | `backend/tools/code/voice_coder.py` | [099_backend_tools_code_voice_coder_py.md](./099_backend_tools_code_voice_coder_py.md) |
| 100 | Backend Tool / Utility | `backend/tools/creative/audio_engineering_agent.py` | [100_backend_tools_creative_audio_engineering_agent_py.md](./100_backend_tools_creative_audio_engineering_agent_py.md) |
| 101 | Backend Tool / Utility | `backend/tools/creative/brand_identity_agent.py` | [101_backend_tools_creative_brand_identity_agent_py.md](./101_backend_tools_creative_brand_identity_agent_py.md) |
| 102 | Backend Tool / Utility | `backend/tools/creative/creative_agents_registry.py` | [102_backend_tools_creative_creative_agents_registry_py.md](./102_backend_tools_creative_creative_agents_registry_py.md) |
| 103 | Backend Tool / Utility | `backend/tools/creative/game_design_agent.py` | [103_backend_tools_creative_game_design_agent_py.md](./103_backend_tools_creative_game_design_agent_py.md) |
| 104 | Backend Tool / Utility | `backend/tools/creative/video_production_agent.py` | [104_backend_tools_creative_video_production_agent_py.md](./104_backend_tools_creative_video_production_agent_py.md) |
| 105 | Backend Tool / Utility | `backend/tools/devops/auto_coverage_improver.py` | [105_backend_tools_devops_auto_coverage_improver_py.md](./105_backend_tools_devops_auto_coverage_improver_py.md) |
| 106 | Backend Tool / Utility | `backend/tools/devops/coverage_auditor.py` | [106_backend_tools_devops_coverage_auditor_py.md](./106_backend_tools_devops_coverage_auditor_py.md) |
| 107 | Backend Tool / Utility | `backend/tools/devops/docker_sandbox.py` | [107_backend_tools_devops_docker_sandbox_py.md](./107_backend_tools_devops_docker_sandbox_py.md) |
| 108 | Backend Tool / Utility | `backend/tools/devops/gcp_cloud_functions.py` | [108_backend_tools_devops_gcp_cloud_functions_py.md](./108_backend_tools_devops_gcp_cloud_functions_py.md) |
| 109 | Backend Tool / Utility | `backend/tools/devops/github_agent.py` | [109_backend_tools_devops_github_agent_py.md](./109_backend_tools_devops_github_agent_py.md) |
| 110 | Backend Tool / Utility | `backend/tools/devops/on_premise_deployer.py` | [110_backend_tools_devops_on_premise_deployer_py.md](./110_backend_tools_devops_on_premise_deployer_py.md) |
| 111 | Backend Tool / Utility | `backend/tools/knowledge/codebase_exporter.py` | [111_backend_tools_knowledge_codebase_exporter_py.md](./111_backend_tools_knowledge_codebase_exporter_py.md) |
| 112 | Backend Tool / Utility | `backend/tools/knowledge/git_knowledge_extractor.py` | [112_backend_tools_knowledge_git_knowledge_extractor_py.md](./112_backend_tools_knowledge_git_knowledge_extractor_py.md) |
| 113 | Backend Tool / Utility | `backend/tools/knowledge/knowledge_base_indexer.py` | [113_backend_tools_knowledge_knowledge_base_indexer_py.md](./113_backend_tools_knowledge_knowledge_base_indexer_py.md) |
| 114 | Backend Tool / Utility | `backend/tools/knowledge/local_search_rag.py` | [114_backend_tools_knowledge_local_search_rag_py.md](./114_backend_tools_knowledge_local_search_rag_py.md) |
| 115 | Backend Tool / Utility | `backend/tools/knowledge/pdf_to_sdk.py` | [115_backend_tools_knowledge_pdf_to_sdk_py.md](./115_backend_tools_knowledge_pdf_to_sdk_py.md) |
| 116 | Backend Tool / Utility | `backend/tools/knowledge/repo_deep_indexer.py` | [116_backend_tools_knowledge_repo_deep_indexer_py.md](./116_backend_tools_knowledge_repo_deep_indexer_py.md) |
| 117 | Backend Tool / Utility | `backend/tools/learning/agent_knowledge_store.py` | [117_backend_tools_learning_agent_knowledge_store_py.md](./117_backend_tools_learning_agent_knowledge_store_py.md) |
| 118 | Backend Tool / Utility | `backend/tools/learning/domain_adapter.py` | [118_backend_tools_learning_domain_adapter_py.md](./118_backend_tools_learning_domain_adapter_py.md) |
| 119 | Backend Tool / Utility | `backend/tools/learning/model_trainer.py` | [119_backend_tools_learning_model_trainer_py.md](./119_backend_tools_learning_model_trainer_py.md) |
| 120 | Backend Tool / Utility | `backend/tools/learning/rlhf_pipeline.py` | [120_backend_tools_learning_rlhf_pipeline_py.md](./120_backend_tools_learning_rlhf_pipeline_py.md) |
| 121 | Backend Tool / Utility | `backend/tools/learning/skill_recommender.py` | [121_backend_tools_learning_skill_recommender_py.md](./121_backend_tools_learning_skill_recommender_py.md) |
| 122 | Backend Tool / Utility | `backend/tools/learning/style_learner.py` | [122_backend_tools_learning_style_learner_py.md](./122_backend_tools_learning_style_learner_py.md) |
| 123 | Backend Tool / Utility | `backend/tools/localization/bangla_ai_connector.py` | [123_backend_tools_localization_bangla_ai_connector_py.md](./123_backend_tools_localization_bangla_ai_connector_py.md) |
| 124 | Backend Tool / Utility | `backend/tools/localization/bangla_nlp.py` | [124_backend_tools_localization_bangla_nlp_py.md](./124_backend_tools_localization_bangla_nlp_py.md) |
| 125 | Backend Tool / Utility | `backend/tools/localization/bangla_voice.py` | [125_backend_tools_localization_bangla_voice_py.md](./125_backend_tools_localization_bangla_voice_py.md) |
| 126 | Backend Tool / Utility | `backend/tools/localization/bengali_ocr_converter.py` | [126_backend_tools_localization_bengali_ocr_converter_py.md](./126_backend_tools_localization_bengali_ocr_converter_py.md) |
| 127 | Backend Tool / Utility | `backend/tools/localization/local_ocr_extractor.py` | [127_backend_tools_localization_local_ocr_extractor_py.md](./127_backend_tools_localization_local_ocr_extractor_py.md) |
| 128 | Backend Tool / Utility | `backend/tools/media/image_generator.py` | [128_backend_tools_media_image_generator_py.md](./128_backend_tools_media_image_generator_py.md) |
| 129 | Backend Tool / Utility | `backend/tools/media/multilingual_tts.py` | [129_backend_tools_media_multilingual_tts_py.md](./129_backend_tools_media_multilingual_tts_py.md) |
| 130 | Backend Tool / Utility | `backend/tools/media/music_generator.py` | [130_backend_tools_media_music_generator_py.md](./130_backend_tools_media_music_generator_py.md) |
| 131 | Backend Tool / Utility | `backend/tools/media/presentation_generator.py` | [131_backend_tools_media_presentation_generator_py.md](./131_backend_tools_media_presentation_generator_py.md) |
| 132 | Backend Tool / Utility | `backend/tools/media/threed_model_generator.py` | [132_backend_tools_media_threed_model_generator_py.md](./132_backend_tools_media_threed_model_generator_py.md) |
| 133 | Backend Tool / Utility | `backend/tools/media/video_generator.py` | [133_backend_tools_media_video_generator_py.md](./133_backend_tools_media_video_generator_py.md) |
| 134 | Backend Tool / Utility | `backend/tools/media/voice.py` | [134_backend_tools_media_voice_py.md](./134_backend_tools_media_voice_py.md) |
| 135 | Backend Tool / Utility | `backend/tools/security_tools/multi_account_rotator.py` | [135_backend_tools_security_tools_multi_account_rotator_py.md](./135_backend_tools_security_tools_multi_account_rotator_py.md) |
| 136 | Backend Tool / Utility | `backend/tools/security_tools/proxy_manager.py` | [136_backend_tools_security_tools_proxy_manager_py.md](./136_backend_tools_security_tools_proxy_manager_py.md) |
| 137 | Backend Tool / Utility | `backend/tools/security_tools/vpn_switcher.py` | [137_backend_tools_security_tools_vpn_switcher_py.md](./137_backend_tools_security_tools_vpn_switcher_py.md) |
| 138 | Backend Tool / Utility | `backend/tools/security_tools/vulnerability_predictor.py` | [138_backend_tools_security_tools_vulnerability_predictor_py.md](./138_backend_tools_security_tools_vulnerability_predictor_py.md) |
| 139 | Backend Tool / Utility | `backend/tools/social/email_agent.py` | [139_backend_tools_social_email_agent_py.md](./139_backend_tools_social_email_agent_py.md) |
| 140 | Backend Tool / Utility | `backend/tools/social/marketplace_agent.py` | [140_backend_tools_social_marketplace_agent_py.md](./140_backend_tools_social_marketplace_agent_py.md) |
| 141 | Backend Tool / Utility | `backend/tools/social/teldrive_storage.py` | [141_backend_tools_social_teldrive_storage_py.md](./141_backend_tools_social_teldrive_storage_py.md) |
| 142 | Backend Tool / Utility | `backend/tools/social/telegram_bot.py` | [142_backend_tools_social_telegram_bot_py.md](./142_backend_tools_social_telegram_bot_py.md) |
| 143 | Backend Tool / Utility | `backend/tools/social/telegram_security.py` | [143_backend_tools_social_telegram_security_py.md](./143_backend_tools_social_telegram_security_py.md) |
| 144 | Backend Tool / Utility | `backend/tools/social/viral_referral_engine.py` | [144_backend_tools_social_viral_referral_engine_py.md](./144_backend_tools_social_viral_referral_engine_py.md) |
| 145 | Frontend Page / View | `frontend/src/pages/BillingPage.tsx` | [145_frontend_src_pages_BillingPage_tsx.md](./145_frontend_src_pages_BillingPage_tsx.md) |
| 146 | Frontend Page / View | `frontend/src/pages/ErrorPage.tsx` | [146_frontend_src_pages_ErrorPage_tsx.md](./146_frontend_src_pages_ErrorPage_tsx.md) |
| 147 | Frontend Page / View | `frontend/src/pages/ProfilePage.tsx` | [147_frontend_src_pages_ProfilePage_tsx.md](./147_frontend_src_pages_ProfilePage_tsx.md) |
| 148 | Frontend Page / View | `frontend/src/pages/PromptTemplatePage.tsx` | [148_frontend_src_pages_PromptTemplatePage_tsx.md](./148_frontend_src_pages_PromptTemplatePage_tsx.md) |
| 149 | Frontend Page / View | `frontend/src/pages/PublicPages.tsx` | [149_frontend_src_pages_PublicPages_tsx.md](./149_frontend_src_pages_PublicPages_tsx.md) |
| 150 | Frontend Page / View | `frontend/src/pages/SharedConversationPage.tsx` | [150_frontend_src_pages_SharedConversationPage_tsx.md](./150_frontend_src_pages_SharedConversationPage_tsx.md) |
| 151 | Frontend Page / View | `frontend/src/pages/WorkspaceModulePage.tsx` | [151_frontend_src_pages_WorkspaceModulePage_tsx.md](./151_frontend_src_pages_WorkspaceModulePage_tsx.md) |
| 152 | Frontend Page / View | `frontend/src/pages/admin` | [152_frontend_src_pages_admin.md](./152_frontend_src_pages_admin.md) |
| 153 | Frontend Page / View | `frontend/src/pages/auth` | [153_frontend_src_pages_auth.md](./153_frontend_src_pages_auth.md) |
| 154 | Frontend Page / View | `frontend/src/pages/user` | [154_frontend_src_pages_user.md](./154_frontend_src_pages_user.md) |
| 155 | Frontend Service Module | `frontend/src/services/adminService.test.ts` | [155_frontend_src_services_adminService_test_ts.md](./155_frontend_src_services_adminService_test_ts.md) |
| 156 | Frontend Service Module | `frontend/src/services/adminService.ts` | [156_frontend_src_services_adminService_ts.md](./156_frontend_src_services_adminService_ts.md) |
| 157 | Frontend Service Module | `frontend/src/services/adminTokenStore.test.ts` | [157_frontend_src_services_adminTokenStore_test_ts.md](./157_frontend_src_services_adminTokenStore_test_ts.md) |
| 158 | Frontend Service Module | `frontend/src/services/adminTokenStore.ts` | [158_frontend_src_services_adminTokenStore_ts.md](./158_frontend_src_services_adminTokenStore_ts.md) |
| 159 | Frontend Service Module | `frontend/src/services/agentService.test.ts` | [159_frontend_src_services_agentService_test_ts.md](./159_frontend_src_services_agentService_test_ts.md) |
| 160 | Frontend Service Module | `frontend/src/services/agentService.ts` | [160_frontend_src_services_agentService_ts.md](./160_frontend_src_services_agentService_ts.md) |
| 161 | Frontend Service Module | `frontend/src/services/aiActions.test.ts` | [161_frontend_src_services_aiActions_test_ts.md](./161_frontend_src_services_aiActions_test_ts.md) |
| 162 | Frontend Service Module | `frontend/src/services/aiActions.ts` | [162_frontend_src_services_aiActions_ts.md](./162_frontend_src_services_aiActions_ts.md) |
| 163 | Frontend Service Module | `frontend/src/services/api` | [163_frontend_src_services_api.md](./163_frontend_src_services_api.md) |
| 164 | Frontend Service Module | `frontend/src/services/apiClient.test.ts` | [164_frontend_src_services_apiClient_test_ts.md](./164_frontend_src_services_apiClient_test_ts.md) |
| 165 | Frontend Service Module | `frontend/src/services/apiClient.ts` | [165_frontend_src_services_apiClient_ts.md](./165_frontend_src_services_apiClient_ts.md) |
| 166 | Frontend Service Module | `frontend/src/services/audio` | [166_frontend_src_services_audio.md](./166_frontend_src_services_audio.md) |
| 167 | Frontend Service Module | `frontend/src/services/authService.test.ts` | [167_frontend_src_services_authService_test_ts.md](./167_frontend_src_services_authService_test_ts.md) |
| 168 | Frontend Service Module | `frontend/src/services/authService.ts` | [168_frontend_src_services_authService_ts.md](./168_frontend_src_services_authService_ts.md) |
| 169 | Frontend Service Module | `frontend/src/services/browserService.test.ts` | [169_frontend_src_services_browserService_test_ts.md](./169_frontend_src_services_browserService_test_ts.md) |
| 170 | Frontend Service Module | `frontend/src/services/browserService.ts` | [170_frontend_src_services_browserService_ts.md](./170_frontend_src_services_browserService_ts.md) |
| 171 | Frontend Service Module | `frontend/src/services/chatService.test.ts` | [171_frontend_src_services_chatService_test_ts.md](./171_frontend_src_services_chatService_test_ts.md) |
| 172 | Frontend Service Module | `frontend/src/services/chatService.ts` | [172_frontend_src_services_chatService_ts.md](./172_frontend_src_services_chatService_ts.md) |
| 173 | Frontend Service Module | `frontend/src/services/ciReportService.test.ts` | [173_frontend_src_services_ciReportService_test_ts.md](./173_frontend_src_services_ciReportService_test_ts.md) |
| 174 | Frontend Service Module | `frontend/src/services/ciReportService.ts` | [174_frontend_src_services_ciReportService_ts.md](./174_frontend_src_services_ciReportService_ts.md) |
| 175 | Frontend Service Module | `frontend/src/services/controlPlane.test.ts` | [175_frontend_src_services_controlPlane_test_ts.md](./175_frontend_src_services_controlPlane_test_ts.md) |
| 176 | Frontend Service Module | `frontend/src/services/controlPlane.ts` | [176_frontend_src_services_controlPlane_ts.md](./176_frontend_src_services_controlPlane_ts.md) |
| 177 | Frontend Service Module | `frontend/src/services/costOptimizer.service.test.ts` | [177_frontend_src_services_costOptimizer_service_test_ts.md](./177_frontend_src_services_costOptimizer_service_test_ts.md) |
| 178 | Frontend Service Module | `frontend/src/services/costOptimizer.service.ts` | [178_frontend_src_services_costOptimizer_service_ts.md](./178_frontend_src_services_costOptimizer_service_ts.md) |
| 179 | Frontend Service Module | `frontend/src/services/heartbeat.test.ts` | [179_frontend_src_services_heartbeat_test_ts.md](./179_frontend_src_services_heartbeat_test_ts.md) |
| 180 | Frontend Service Module | `frontend/src/services/heartbeat.ts` | [180_frontend_src_services_heartbeat_ts.md](./180_frontend_src_services_heartbeat_ts.md) |
| 181 | Frontend Service Module | `frontend/src/services/policyService.ts` | [181_frontend_src_services_policyService_ts.md](./181_frontend_src_services_policyService_ts.md) |
| 182 | Frontend Service Module | `frontend/src/services/queryClient.test.ts` | [182_frontend_src_services_queryClient_test_ts.md](./182_frontend_src_services_queryClient_test_ts.md) |
| 183 | Frontend Service Module | `frontend/src/services/queryClient.ts` | [183_frontend_src_services_queryClient_ts.md](./183_frontend_src_services_queryClient_ts.md) |
| 184 | Frontend Service Module | `frontend/src/services/realtime` | [184_frontend_src_services_realtime.md](./184_frontend_src_services_realtime.md) |
| 185 | Frontend Service Module | `frontend/src/services/sandbox.ts` | [185_frontend_src_services_sandbox_ts.md](./185_frontend_src_services_sandbox_ts.md) |
| 186 | Frontend Service Module | `frontend/src/services/skillsService.test.ts` | [186_frontend_src_services_skillsService_test_ts.md](./186_frontend_src_services_skillsService_test_ts.md) |
| 187 | Frontend Service Module | `frontend/src/services/skillsService.ts` | [187_frontend_src_services_skillsService_ts.md](./187_frontend_src_services_skillsService_ts.md) |
| 188 | Frontend Service Module | `frontend/src/services/socialGrowthService.ts` | [188_frontend_src_services_socialGrowthService_ts.md](./188_frontend_src_services_socialGrowthService_ts.md) |
| 189 | Frontend Service Module | `frontend/src/services/storageApi.test.ts` | [189_frontend_src_services_storageApi_test_ts.md](./189_frontend_src_services_storageApi_test_ts.md) |
| 190 | Frontend Service Module | `frontend/src/services/storageApi.ts` | [190_frontend_src_services_storageApi_ts.md](./190_frontend_src_services_storageApi_ts.md) |
| 191 | Frontend Service Module | `frontend/src/services/supremeShared.test.ts` | [191_frontend_src_services_supremeShared_test_ts.md](./191_frontend_src_services_supremeShared_test_ts.md) |
| 192 | Frontend Service Module | `frontend/src/services/supremeShared.ts` | [192_frontend_src_services_supremeShared_ts.md](./192_frontend_src_services_supremeShared_ts.md) |
| 193 | Frontend Service Module | `frontend/src/services/test_budget_check.test.ts` | [193_frontend_src_services_test_budget_check_test_ts.md](./193_frontend_src_services_test_budget_check_test_ts.md) |
| 194 | Frontend State Store | `frontend/src/store/adminStore.test.ts` | [194_frontend_src_store_adminStore_test_ts.md](./194_frontend_src_store_adminStore_test_ts.md) |
| 195 | Frontend State Store | `frontend/src/store/adminStore.ts` | [195_frontend_src_store_adminStore_ts.md](./195_frontend_src_store_adminStore_ts.md) |
| 196 | Frontend State Store | `frontend/src/store/authStore.test.ts` | [196_frontend_src_store_authStore_test_ts.md](./196_frontend_src_store_authStore_test_ts.md) |
| 197 | Frontend State Store | `frontend/src/store/authStore.ts` | [197_frontend_src_store_authStore_ts.md](./197_frontend_src_store_authStore_ts.md) |
| 198 | Frontend State Store | `frontend/src/store/chatStore.test.ts` | [198_frontend_src_store_chatStore_test_ts.md](./198_frontend_src_store_chatStore_test_ts.md) |
| 199 | Frontend State Store | `frontend/src/store/chatStore.ts` | [199_frontend_src_store_chatStore_ts.md](./199_frontend_src_store_chatStore_ts.md) |
| 200 | Frontend State Store | `frontend/src/store/customerStore.test.ts` | [200_frontend_src_store_customerStore_test_ts.md](./200_frontend_src_store_customerStore_test_ts.md) |
| 201 | Frontend State Store | `frontend/src/store/customerStore.ts` | [201_frontend_src_store_customerStore_ts.md](./201_frontend_src_store_customerStore_ts.md) |
| 202 | Frontend State Store | `frontend/src/store/dashboardStore.test.ts` | [202_frontend_src_store_dashboardStore_test_ts.md](./202_frontend_src_store_dashboardStore_test_ts.md) |
| 203 | Frontend State Store | `frontend/src/store/dashboardStore.ts` | [203_frontend_src_store_dashboardStore_ts.md](./203_frontend_src_store_dashboardStore_ts.md) |
| 204 | Frontend State Store | `frontend/src/store/index.test.ts` | [204_frontend_src_store_index_test_ts.md](./204_frontend_src_store_index_test_ts.md) |
| 205 | Frontend State Store | `frontend/src/store/index.ts` | [205_frontend_src_store_index_ts.md](./205_frontend_src_store_index_ts.md) |
| 206 | Frontend State Store | `frontend/src/store/localFirstDb.ts` | [206_frontend_src_store_localFirstDb_ts.md](./206_frontend_src_store_localFirstDb_ts.md) |
| 207 | Frontend State Store | `frontend/src/store/sessionCockpitStore.ts` | [207_frontend_src_store_sessionCockpitStore_ts.md](./207_frontend_src_store_sessionCockpitStore_ts.md) |
| 208 | Frontend State Store | `frontend/src/store/slices` | [208_frontend_src_store_slices.md](./208_frontend_src_store_slices.md) |
| 209 | Frontend State Store | `frontend/src/store/stateOwnership.ts` | [209_frontend_src_store_stateOwnership_ts.md](./209_frontend_src_store_stateOwnership_ts.md) |
| 210 | Frontend State Store | `frontend/src/store/themeStore.test.ts` | [210_frontend_src_store_themeStore_test_ts.md](./210_frontend_src_store_themeStore_test_ts.md) |
| 211 | Frontend State Store | `frontend/src/store/themeStore.ts` | [211_frontend_src_store_themeStore_ts.md](./211_frontend_src_store_themeStore_ts.md) |
| 212 | Frontend State Store | `frontend/src/store/unifiedStore.ts` | [212_frontend_src_store_unifiedStore_ts.md](./212_frontend_src_store_unifiedStore_ts.md) |
| 213 | Frontend State Store | `frontend/src/store/useIdeStore.test.ts` | [213_frontend_src_store_useIdeStore_test_ts.md](./213_frontend_src_store_useIdeStore_test_ts.md) |
| 214 | Frontend State Store | `frontend/src/store/useIdeStore.ts` | [214_frontend_src_store_useIdeStore_ts.md](./214_frontend_src_store_useIdeStore_ts.md) |
| 215 | Frontend State Store | `frontend/src/store/useStore.test.ts` | [215_frontend_src_store_useStore_test_ts.md](./215_frontend_src_store_useStore_test_ts.md) |
| 216 | Frontend State Store | `frontend/src/store/useStore.ts` | [216_frontend_src_store_useStore_ts.md](./216_frontend_src_store_useStore_ts.md) |
| 217 | Frontend State Store | `frontend/src/store/useSupremeStore.test.ts` | [217_frontend_src_store_useSupremeStore_test_ts.md](./217_frontend_src_store_useSupremeStore_test_ts.md) |
| 218 | Frontend State Store | `frontend/src/store/useSupremeStore.ts` | [218_frontend_src_store_useSupremeStore_ts.md](./218_frontend_src_store_useSupremeStore_ts.md) |
| 219 | Frontend State Store | `frontend/src/store/useWorkspaceSettingsStore.test.ts` | [219_frontend_src_store_useWorkspaceSettingsStore_test_ts.md](./219_frontend_src_store_useWorkspaceSettingsStore_test_ts.md) |
| 220 | Frontend State Store | `frontend/src/store/useWorkspaceSettingsStore.ts` | [220_frontend_src_store_useWorkspaceSettingsStore_ts.md](./220_frontend_src_store_useWorkspaceSettingsStore_ts.md) |
| 221 | Frontend State Store | `frontend/src/store/useWorkspaceStore.test.ts` | [221_frontend_src_store_useWorkspaceStore_test_ts.md](./221_frontend_src_store_useWorkspaceStore_test_ts.md) |
| 222 | Frontend State Store | `frontend/src/store/useWorkspaceStore.ts` | [222_frontend_src_store_useWorkspaceStore_ts.md](./222_frontend_src_store_useWorkspaceStore_ts.md) |
| 223 | Frontend State Store | `frontend/src/store/workspaceUiStateStore.test.ts` | [223_frontend_src_store_workspaceUiStateStore_test_ts.md](./223_frontend_src_store_workspaceUiStateStore_test_ts.md) |
| 224 | Frontend State Store | `frontend/src/store/workspaceUiStateStore.ts` | [224_frontend_src_store_workspaceUiStateStore_ts.md](./224_frontend_src_store_workspaceUiStateStore_ts.md) |
