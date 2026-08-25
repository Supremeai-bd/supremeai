# Refactoring Suggestions Report

Generated on: 2026-08-25 21:19:36

## Summary
- **Total Suggestions**: 787
- **High Priority**: 48
- **Medium Priority**: 739
- **Low Priority**: 0

## Configuration
- Function line threshold: 50
- Parameter threshold: 5
- Nesting depth threshold: 4
- Target directories: backend, apps

## Long Function (413 items - 48 High, 365 Medium)

| File | Line | Function | Priority | Issue | Suggestion |
|---|---|---|---|---|---|
| backend/main.py | 90 | run_server | 🟡 Medium | Function has 53 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/skill_librarian.py | 33 | SkillLibrarian.process_approval | 🟡 Medium | Function has 61 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/skill_librarian.py | 33 | process_approval | 🟡 Medium | Function has 61 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/skill_gc.py | 32 | SkillGarbageCollector.run_daily_cleanup | 🟡 Medium | Function has 69 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/skill_gc.py | 32 | run_daily_cleanup | 🟡 Medium | Function has 69 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/skill_ingestor.py | 71 | SkillIngestor.ingest_mcp_skill | 🔴 High | Function has 109 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/skill_ingestor.py | 71 | ingest_mcp_skill | 🔴 High | Function has 109 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/morphic_adapter.py | 46 | MorphicAdapter.adapt_code_to_contract | 🟡 Medium | Function has 65 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/morphic_adapter.py | 46 | adapt_code_to_contract | 🟡 Medium | Function has 65 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/insight_mage.py | 93 | TrendDetector.analyze | 🟡 Medium | Function has 76 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/insight_mage.py | 179 | AnomalyDetector.detect | 🟡 Medium | Function has 63 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/insight_mage.py | 93 | analyze | 🟡 Medium | Function has 76 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/insight_mage.py | 179 | detect | 🟡 Medium | Function has 63 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/churn_prophet.py | 129 | BehavioralScorer.calculate | 🟡 Medium | Function has 54 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/churn_prophet.py | 129 | calculate | 🟡 Medium | Function has 54 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ephemeral_executor.py | 283 | EphemeralExecutor.execute_use_and_throw | 🔴 High | Function has 112 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ephemeral_executor.py | 429 | EphemeralExecutor._wrap_code | 🟡 Medium | Function has 52 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ephemeral_executor.py | 283 | execute_use_and_throw | 🔴 High | Function has 112 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ephemeral_executor.py | 429 | _wrap_code | 🟡 Medium | Function has 52 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/infrastructure/cost_optimization_agent.py | 66 | CostOptimizationAgent.__init__ | 🟡 Medium | Function has 99 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/infrastructure/cost_optimization_agent.py | 66 | __init__ | 🟡 Medium | Function has 99 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/infrastructure/performance_tuning_agent.py | 67 | PerformanceTuningAgent.__init__ | 🟡 Medium | Function has 83 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/infrastructure/performance_tuning_agent.py | 67 | __init__ | 🟡 Medium | Function has 83 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/infrastructure/disaster_recovery_agent.py | 54 | DisasterRecoveryAgent.__init__ | 🟡 Medium | Function has 82 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/infrastructure/disaster_recovery_agent.py | 54 | __init__ | 🟡 Medium | Function has 82 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/evolution/federated_learning_agent.py | 122 | FederatedLearningAgent.aggregate_updates | 🟡 Medium | Function has 53 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/evolution/federated_learning_agent.py | 122 | aggregate_updates | 🟡 Medium | Function has 53 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ide/trio_adapters.py | 324 | KiloReviewer._basic_review | 🟡 Medium | Function has 90 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ide/trio_adapters.py | 324 | _basic_review | 🟡 Medium | Function has 90 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ux/accessibility_agent.py | 64 | HTMLAccessibilityParser._check_tag_accessibility | 🟡 Medium | Function has 62 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ux/accessibility_agent.py | 131 | AccessibilityAgent.__init__ | 🟡 Medium | Function has 80 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ux/accessibility_agent.py | 64 | _check_tag_accessibility | 🟡 Medium | Function has 62 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/ux/accessibility_agent.py | 131 | __init__ | 🟡 Medium | Function has 80 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/governance/bias_detection_agent.py | 35 | BiasDetectionAgent.__init__ | 🟡 Medium | Function has 67 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/agents/governance/bias_detection_agent.py | 35 | __init__ | 🟡 Medium | Function has 67 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/benchmark_runner.py | 47 | BenchmarkRunner.compare_and_decide | 🟡 Medium | Function has 67 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/benchmark_runner.py | 47 | compare_and_decide | 🟡 Medium | Function has 67 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/federated_learning/fed_learning.py | 319 | FederatedServer.aggregate_model_updates | 🟡 Medium | Function has 72 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/federated_learning/fed_learning.py | 433 | FederatedServer.run_federated_training | 🟡 Medium | Function has 90 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/federated_learning/fed_learning.py | 627 | demo_federated_learning | 🟡 Medium | Function has 65 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/federated_learning/fed_learning.py | 319 | aggregate_model_updates | 🟡 Medium | Function has 72 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/federated_learning/fed_learning.py | 433 | run_federated_training | 🟡 Medium | Function has 90 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 453 | ToMReasoner.predict_behavior | 🟡 Medium | Function has 55 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 557 | ToMReasoner.recursive_reasoning | 🟡 Medium | Function has 54 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 664 | TheoryOfMindSystem.process_interaction | 🟡 Medium | Function has 58 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 723 | TheoryOfMindSystem.analyze_social_dynamics | 🟡 Medium | Function has 57 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 833 | demo_theory_of_mind | 🟡 Medium | Function has 52 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 453 | predict_behavior | 🟡 Medium | Function has 55 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 557 | recursive_reasoning | 🟡 Medium | Function has 54 lines (threshold: 50) | Break down into smaller, focused functions |
| backend/evolution/theory_of_mind/tom_system.py | 664 | process_interaction | 🟡 Medium | Function has 58 lines (threshold: 50) | Break down into smaller, focused functions |

*... and 363 more items*

### Recommendations:
1. Apply the Extract Method refactoring technique
2. Look for logical groupings of statements that can become separate functions
3. Consider using early returns to reduce nesting

## Deep Nesting (166 items - 166 Medium)

| File | Line | Function | Priority | Issue | Suggestion |
|---|---|---|---|---|---|
| backend/main.py | 90 | run_server | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/skill_librarian.py | 33 | SkillLibrarian.process_approval | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/skill_librarian.py | 33 | process_approval | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/skill_gc.py | 32 | SkillGarbageCollector.run_daily_cleanup | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/skill_gc.py | 32 | run_daily_cleanup | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/skill_ingestor.py | 36 | SkillIngestor.static_ast_safety_check | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/skill_ingestor.py | 36 | static_ast_safety_check | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/ephemeral_executor.py | 141 | SecurityScanner._ast_scan | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/agents/ephemeral_executor.py | 141 | _ast_scan | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/federated_learning/fed_learning.py | 319 | FederatedServer.aggregate_model_updates | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/federated_learning/fed_learning.py | 319 | aggregate_model_updates | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/theory_of_mind/tom_system.py | 781 | TheoryOfMindSystem.generate_insight | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/theory_of_mind/tom_system.py | 781 | generate_insight | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/neural_symbolic/integration.py | 184 | SymbolicReasoner.perform_mathematical_reasoning | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/neural_symbolic/integration.py | 425 | NeuralSymbolicIntegrator.solve_mathematical_problem | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/neural_symbolic/integration.py | 184 | perform_mathematical_reasoning | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/neural_symbolic/integration.py | 425 | solve_mathematical_problem | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/temporal_abstraction/temporal_system.py | 616 | TemporalAbstractionLayer._get_time_key | 🟡 Medium | Function has nesting depth of 7 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/evolution/temporal_abstraction/temporal_system.py | 616 | _get_time_key | 🟡 Medium | Function has nesting depth of 7 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/mcp_server.py | 169 | KnowledgeGraph.delete_entities | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/mcp_server.py | 267 | KnowledgeGraph.search_nodes | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/mcp_server.py | 169 | delete_entities | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/mcp_server.py | 267 | search_nodes | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/supabase_store.py | 99 | SupabaseStore._get_supabase_client | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/supabase_store.py | 254 | SupabaseStore.save_learned_fact | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/supabase_store.py | 302 | SupabaseStore.search_facts | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/supabase_store.py | 99 | _get_supabase_client | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/supabase_store.py | 254 | save_learned_fact | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/memory/supabase_store.py | 302 | search_facts | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/memory_service.py | 120 | CascadeMemoryService._parse_code_structure | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/memory_service.py | 242 | CascadeMemoryService.retrieve_memories | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/memory_service.py | 349 | CascadeMemoryService.query_context | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/memory_service.py | 120 | _parse_code_structure | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/memory_service.py | 242 | retrieve_memories | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/memory_service.py | 349 | query_context | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/security_auditor.py | 258 | SecurityAuditor.scan_code_patterns | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/security_auditor.py | 413 | SecurityAuditor._version_in_range | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/security_auditor.py | 440 | SecurityAuditor._detect_unused_dependencies | 🟡 Medium | Function has nesting depth of 8 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/security_auditor.py | 258 | scan_code_patterns | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/security_auditor.py | 413 | _version_in_range | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/security_auditor.py | 440 | _detect_unused_dependencies | 🟡 Medium | Function has nesting depth of 8 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/intent_deciphering.py | 102 | IntentDecipheringService._separate_goal_from_method | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/intent_deciphering.py | 102 | _separate_goal_from_method | 🟡 Medium | Function has nesting depth of 5 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/smart_model_router.py | 677 | SmartRouter._score_candidates | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/smart_model_router.py | 677 | _score_candidates | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/dynamic_ai/learning_engine.py | 124 | LearningEngine.detect_task_type | 🟡 Medium | Function has nesting depth of 8 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/services/dynamic_ai/learning_engine.py | 124 | detect_task_type | 🟡 Medium | Function has nesting depth of 8 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/tools/health_checker.py | 75 | HealthChecker.detect_anomalies | 🟡 Medium | Function has nesting depth of 7 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/tools/health_checker.py | 75 | detect_anomalies | 🟡 Medium | Function has nesting depth of 7 (threshold: 4) | Extract nested blocks into separate functions or use early returns |
| backend/tools/repo_discovery_agent.py | 86 | RepoDiscoveryAgent.analyze_compatibility | 🟡 Medium | Function has nesting depth of 6 (threshold: 4) | Extract nested blocks into separate functions or use early returns |

*... and 116 more items*

### Recommendations:
1. Use guard clauses for early returns
2. Extract nested logic into separate functions
3. Consider using the Strategy Pattern for complex conditional logic

## Too Many Parameters (128 items - 128 Medium)

| File | Line | Function | Priority | Issue | Suggestion |
|---|---|---|---|---|---|
| backend/agents/churn_prophet.py | 129 | BehavioralScorer.calculate | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/churn_prophet.py | 283 | RetentionStrategist._build_personalization_prompt | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/churn_prophet.py | 129 | calculate | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/churn_prophet.py | 283 | _build_personalization_prompt | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/ephemeral_executor.py | 211 | ResourceQuota.__init__ | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/ephemeral_executor.py | 283 | EphemeralExecutor.execute_use_and_throw | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/ephemeral_executor.py | 211 | __init__ | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/ephemeral_executor.py | 283 | execute_use_and_throw | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/devops/cost_sage.py | 163 | UsageTracker.record_usage | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/devops/cost_sage.py | 427 | CostSage.record_api_call | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/devops/cost_sage.py | 163 | record_usage | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/devops/cost_sage.py | 427 | record_api_call | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/devops/cloud_watchman.py | 163 | AnomalyDetector._generate_suggestion | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/devops/cloud_watchman.py | 163 | _generate_suggestion | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/monitoring/technology_radar_agent.py | 92 | TechnologyRadarAgent.register_technology | 🟡 Medium | Function has 9 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/monitoring/technology_radar_agent.py | 92 | register_technology | 🟡 Medium | Function has 9 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/monitoring/competitor_analysis_agent.py | 112 | CompetitorAnalysisAgent.record_feature | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/agents/monitoring/competitor_analysis_agent.py | 112 | record_feature | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/change_proposal.py | 136 | ChangeProposalManager.create_proposal | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/change_proposal.py | 136 | create_proposal | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/fitness_evaluator.py | 46 | FitnessEvaluator.evaluate_skill_execution | 🟡 Medium | Function has 8 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/fitness_evaluator.py | 46 | evaluate_skill_execution | 🟡 Medium | Function has 8 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/auto_tuner.py | 30 | TuningParameter.__init__ | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/auto_tuner.py | 76 | AutoTuner.register_parameter | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/auto_tuner.py | 30 | __init__ | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/evolution/auto_tuner.py | 76 | register_parameter | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/hierarchical_tree.py | 70 | HierarchicalMemoryTree.add_leaf | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/hierarchical_tree.py | 70 | add_leaf | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/episodic_memory.py | 35 | EpisodicMemory.store_episode | 🟡 Medium | Function has 12 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/episodic_memory.py | 73 | EpisodicMemory.recall_episodes | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/episodic_memory.py | 35 | store_episode | 🟡 Medium | Function has 12 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/episodic_memory.py | 73 | recall_episodes | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/sqlite_store.py | 69 | SQLiteMemoryStore.log_task | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/memory/sqlite_store.py | 69 | log_task | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/brain/supreme_learning_engine.py | 193 | SupremeLearningEngine.learn_from_interaction | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/brain/supreme_learning_engine.py | 416 | SupremeLearningEngine._store_pattern | 🟡 Medium | Function has 9 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/brain/supreme_learning_engine.py | 193 | learn_from_interaction | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/brain/supreme_learning_engine.py | 416 | _store_pattern | 🟡 Medium | Function has 9 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/auto_healer.py | 343 | RetryPolicy.__init__ | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/auto_healer.py | 343 | __init__ | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/knowledge_qa.py | 178 | KnowledgeQAService._audit | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/knowledge_qa.py | 178 | _audit | 🟡 Medium | Function has 6 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/escrow_service.py | 115 | EscrowService.create_escrow_sync | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/escrow_service.py | 115 | create_escrow_sync | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/memory_service.py | 180 | CascadeMemoryService.store_memory | 🟡 Medium | Function has 10 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/memory_service.py | 180 | store_memory | 🟡 Medium | Function has 10 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/living_engine.py | 231 | LivingEngineOrchestrator.__init__ | 🟡 Medium | Function has 10 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/living_engine.py | 231 | __init__ | 🟡 Medium | Function has 10 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/smart_model_router.py | 543 | SmartRouter.route | 🟡 Medium | Function has 9 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |
| backend/services/smart_model_router.py | 617 | SmartRouter._filter_models | 🟡 Medium | Function has 7 parameters (threshold: 5) | Consider using a data class or dictionary to group related parameters |

*... and 78 more items*

### Recommendations:
1. Introduce Parameter Object: group related parameters into a class
2. Preserve Whole Object: if parameters come from same object, pass the object
3. Remove Setting Method: if some parameters are used to set state, use setter methods

## Large Class (72 items - 72 Medium)

| File | Line | Class | Priority | Issue | Suggestion |
|---|---|---|---|---|---|
| backend/agents/insight_mage.py | 334 | InsightMage | 🟡 Medium | Class has 375 lines and 3 methods | Consider splitting into smaller, more focused classes |
| backend/agents/internet_monitor_agent.py | 41 | InternetMonitorAgent | 🟡 Medium | Class has 425 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/agents/churn_prophet.py | 310 | ChurnProphet | 🟡 Medium | Class has 368 lines and 2 methods | Consider splitting into smaller, more focused classes |
| backend/agents/infrastructure/auto_scaling_agent.py | 49 | AutoScalingAgent | 🟡 Medium | Class has 485 lines and 5 methods | Consider splitting into smaller, more focused classes |
| backend/agents/infrastructure/cost_optimization_agent.py | 63 | CostOptimizationAgent | 🟡 Medium | Class has 719 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/agents/infrastructure/performance_tuning_agent.py | 64 | PerformanceTuningAgent | 🟡 Medium | Class has 663 lines and 2 methods | Consider splitting into smaller, more focused classes |
| backend/agents/infrastructure/disaster_recovery_agent.py | 51 | DisasterRecoveryAgent | 🟡 Medium | Class has 597 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/agents/ux/accessibility_agent.py | 128 | AccessibilityAgent | 🟡 Medium | Class has 565 lines and 3 methods | Consider splitting into smaller, more focused classes |
| backend/agents/governance/bias_detection_agent.py | 32 | BiasDetectionAgent | 🟡 Medium | Class has 306 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/agents/governance/governance_agent.py | 49 | GovernanceAgent | 🟡 Medium | Class has 522 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/evolution/digital_twin/topology.py | 72 | SystemTopologyMapper | 🟡 Medium | Class has 416 lines and 3 methods | Consider splitting into smaller, more focused classes |
| backend/evolution/digital_twin/simulator.py | 64 | ImpactSimulator | 🟡 Medium | Class has 487 lines and 7 methods | Consider splitting into smaller, more focused classes |
| backend/evolution/digital_twin/remediation_engine.py | 98 | RemediationEngine | 🟡 Medium | Class has 492 lines and 7 methods | Consider splitting into smaller, more focused classes |
| backend/engine/compression/token_juice.py | 31 | TokenJuice | 🟡 Medium | Class has 351 lines and 9 methods | Consider splitting into smaller, more focused classes |
| backend/memory/supabase_store.py | 13 | SupabaseStore | 🟡 Medium | Class has 405 lines and 16 methods | Consider splitting into smaller, more focused classes |
| backend/memory/sliding_window.py | 31 | SlidingWindowMemory | 🟡 Medium | Class has 316 lines and 15 methods | Consider splitting into smaller, more focused classes |
| backend/brain/model_router.py | 49 | ModelRouter | 🟡 Medium | Class has 309 lines and 9 methods | Consider splitting into smaller, more focused classes |
| backend/brain/supreme_learning_engine.py | 61 | SupremeLearningEngine | 🟡 Medium | Class has 547 lines and 22 methods | Consider splitting into smaller, more focused classes |
| backend/services/intelligent_cache.py | 98 | IntelligentCache | 🟡 Medium | Class has 365 lines and 12 methods | Consider splitting into smaller, more focused classes |
| backend/services/auto_healer.py | 371 | AutoHealer | 🟡 Medium | Class has 431 lines and 11 methods | Consider splitting into smaller, more focused classes |
| backend/services/memory_service.py | 57 | CascadeMemoryService | 🟡 Medium | Class has 434 lines and 19 methods | Consider splitting into smaller, more focused classes |
| backend/services/security_auditor.py | 194 | SecurityAuditor | 🟡 Medium | Class has 461 lines and 14 methods | Consider splitting into smaller, more focused classes |
| backend/services/smart_model_router.py | 504 | SmartRouter | 🟡 Medium | Class has 585 lines and 8 methods | Consider splitting into smaller, more focused classes |
| backend/services/llm/llm_router.py | 225 | LLMRouter | 🟡 Medium | Class has 482 lines and 5 methods | Consider splitting into smaller, more focused classes |
| backend/services/dynamic_ai/orchestrator.py | 36 | DynamicAIOrchestrator | 🟡 Medium | Class has 467 lines and 2 methods | Consider splitting into smaller, more focused classes |
| backend/services/dynamic_ai/learning_engine.py | 108 | LearningEngine | 🟡 Medium | Class has 334 lines and 4 methods | Consider splitting into smaller, more focused classes |
| backend/services/dynamic_ai/provider_registry.py | 101 | ProviderRegistry | 🟡 Medium | Class has 442 lines and 9 methods | Consider splitting into smaller, more focused classes |
| backend/tools/sso_integrator.py | 10 | SSOIntegrator | 🟡 Medium | Class has 419 lines and 12 methods | Consider splitting into smaller, more focused classes |
| backend/tools/comment_thread_ai.py | 46 | CommentThreadAI | 🟡 Medium | Class has 309 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/tools/tenant_rate_limiter.py | 9 | TenantRateLimiter | 🟡 Medium | Class has 309 lines and 4 methods | Consider splitting into smaller, more focused classes |
| backend/tools/security_tools/multi_account_rotator.py | 150 | MultiAccountRotator | 🟡 Medium | Class has 753 lines and 13 methods | Consider splitting into smaller, more focused classes |
| backend/tools/devops/docker_sandbox.py | 13 | DockerSandbox | 🟡 Medium | Class has 301 lines and 4 methods | Consider splitting into smaller, more focused classes |
| backend/tools/code/code_smell_detector.py | 14 | CodeSmellDetector | 🟡 Medium | Class has 681 lines and 17 methods | Consider splitting into smaller, more focused classes |
| backend/tools/browser/playwright_browser_agent.py | 27 | PlaywrightBrowserAgent | 🟡 Medium | Class has 614 lines and 20 methods | Consider splitting into smaller, more focused classes |
| backend/tools/knowledge/knowledge_base_indexer.py | 22 | KnowledgeBaseIndexer | 🟡 Medium | Class has 407 lines and 13 methods | Consider splitting into smaller, more focused classes |
| backend/tools/knowledge/local_search_rag.py | 40 | LocalSearchRAG | 🟡 Medium | Class has 316 lines and 10 methods | Consider splitting into smaller, more focused classes |
| backend/tools/media/multilingual_tts.py | 89 | MultilingualTTS | 🟡 Medium | Class has 326 lines and 5 methods | Consider splitting into smaller, more focused classes |
| backend/tools/social/telegram_bot.py | 33 | TelegramBotHandler | 🟡 Medium | Class has 1349 lines and 8 methods | Consider splitting into smaller, more focused classes |
| backend/tools/social/viral_referral_engine.py | 22 | ViralReferralEngine | 🟡 Medium | Class has 401 lines and 16 methods | Consider splitting into smaller, more focused classes |
| backend/core/performance_enhancer.py | 53 | PerformanceOptimizer | 🟡 Medium | Class has 495 lines and 7 methods | Consider splitting into smaller, more focused classes |
| backend/core/intelligent_cache.py | 100 | IntelligentCache | 🟡 Medium | Class has 378 lines and 12 methods | Consider splitting into smaller, more focused classes |
| backend/core/universal_rules.py | 14 | UniversalRulesEngine | 🟡 Medium | Class has 535 lines and 15 methods | Consider splitting into smaller, more focused classes |
| backend/core/self_benchmark.py | 113 | SelfBenchmarkEngine | 🟡 Medium | Class has 366 lines and 7 methods | Consider splitting into smaller, more focused classes |
| backend/core/health_check.py | 63 | ComprehensiveHealthChecker | 🟡 Medium | Class has 403 lines and 1 methods | Consider splitting into smaller, more focused classes |
| backend/core/agent_supervisor.py | 44 | AgentSupervisor | 🟡 Medium | Class has 316 lines and 3 methods | Consider splitting into smaller, more focused classes |
| backend/core/config_validation.py | 13 | SettingsValidationMixin | 🟡 Medium | Class has 371 lines and 19 methods | Consider splitting into smaller, more focused classes |
| backend/core/autonoguard_engine.py | 84 | AutonoGuardEngine | 🟡 Medium | Class has 389 lines and 2 methods | Consider splitting into smaller, more focused classes |
| backend/core/config_secrets.py | 15 | SettingsSecretsMixin | 🟡 Medium | Class has 601 lines and 50 methods | Consider splitting into smaller, more focused classes |
| backend/core/advanced_reasoning.py | 107 | AdvancedReasoningEngine | 🟡 Medium | Class has 392 lines and 10 methods | Consider splitting into smaller, more focused classes |
| backend/core/evolution_module.py | 65 | EvolutionModule | 🟡 Medium | Class has 301 lines and 8 methods | Consider splitting into smaller, more focused classes |

*... and 22 more items*

### Recommendations:
1. Apply Extract Class: group related fields and methods into a new class
2. Use Superclass Extraction if there's common behavior
3. Consider if the class is trying to do too much (Single Responsibility Principle)

## Too Many Methods (8 items - 8 Medium)

| File | Line | Class | Priority | Issue | Suggestion |
|---|---|---|---|---|---|
| backend/brain/supreme_learning_engine.py | 61 | SupremeLearningEngine | 🟡 Medium | Class has 22 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/core/config_secrets.py | 15 | SettingsSecretsMixin | 🟡 Medium | Class has 50 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/database/supabase_client.py | 78 | SupabaseDB | 🟡 Medium | Class has 30 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/adapters/business_adapter.py | 60 | BusinessAdapter | 🟡 Medium | Class has 24 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/adapters/ux_adapter.py | 96 | UXAdapter | 🟡 Medium | Class has 29 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/adapters/dev_adapter.py | 38 | DevAdapter | 🟡 Medium | Class has 22 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/learning/pattern_recognizer.py | 58 | PatternRecognizer | 🟡 Medium | Class has 23 methods | Consider applying Single Responsibility Principle - split into multiple classes |
| backend/pyerrorfix/detectors/core_python.py | 306 | CorePythonDetector | 🟡 Medium | Class has 21 methods | Consider applying Single Responsibility Principle - split into multiple classes |

### Recommendations:
1. Look for clusters of methods that work on similar data
2. Apply Extract Class to group related functionality
3. Consider using Facade or Mediator patterns if this is a complex interface
