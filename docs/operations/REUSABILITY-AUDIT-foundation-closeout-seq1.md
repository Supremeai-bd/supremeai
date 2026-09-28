# Reusability Audit — group:foundation-closeout (seq:1)

> **তারিখ:** 2026-09-28 20:31 UTC · **স্ক্যানার:** `scripts/supremeai_toolkit` v0.1.0 · **roots:** scripts, backend/pyerrorfix
> **Golden Rule:** Clean up-এর আগে Reusability Check — beneficial কিছু কোনো অবস্থাতেই ডিলিট করা যাবে না (#2403)।
> এই রিপোর্ট প্রমাণ-বেস মাত্র — এখান থেকে কোনো ফাইল স্বয়ংক্রিয়ভাবে ডিলিট হয় না।

## সারসংক্ষেপ

**মোট স্ক্যান করা .py/.sh ফাইল: 434**

| Verdict | সংখ্যা | অর্থ |
| :--- | ---: | :--- |
| keep-canonical | 198 | workflow/live-code রেফ আছে — স্পর্শ নিষিদ্ধ |
| review-standalone | 151 | entry-point, শূন্য রেফ — ম্যানুয়াল যাচাই |
| prune-candidate | 85 | শূন্য রেফ + non-entry — harvest-check-পরবর্তী ছাঁটাই |

## বিশেষ রায় (Deep-Dive)

- **`backend/pyerrorfix` = KEEP (canonical capability, 36 ফাইল, 13টি লাইভ-রেফারেন্সড):** `backend/action.yml` একটি প্রকাশিত SARIF GitHub Action (python -m pyerrorfix analyze), ৪টি লাইভ স্ক্রিপ্ট রেফারেন্স করে (test_coverage_gap_mapper, check_hardcoded_deployment_config, check_no_requests_in_backend.sh, audit_isolated_components), master-docs (ARCH-01/BACKEND-01) সহ ১৭টি ডক-রেফ। **বাগ-নোট:** action.yml `./pyerrorfix` subdirectory আশা করে, বাস্তবে প্যাকেজ `backend/pyerrorfix`-এ — path-mismatch; পরবর্তী seq-এ harvest/ফিক্স প্রার্থী, ডিলিট প্রার্থী নয়।

## prune-candidate তালিকা (পরবর্তী seq-এর evidence-base)

Harvest-check (দরকারি লজিক → ক্যানোনিকাল মডিউলে সংরক্ষণ) শেষ না হওয়া পর্যন্ত কোনোটিই ডিলিট হবে না।

| ফাইল | লাইন | docs-রেফ | কারণ |
| :--- | ---: | ---: | :--- |
| `scripts/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ai/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ai/test_baseline_commands.py` | 6 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ai/test_change_impact_detector.py` | 46 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ai/test_drift_checks.py` | 19 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ai/test_evidence_bundle.py` | 25 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ai/test_repository_metadata_index.py` | 16 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/apply_plan_renames.py` | 81 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/audit/__init__.py` | 2 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/backup/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/benchmark/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/billing/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/bots/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ci/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ci/test_render_deploy_preflight.py` | 109 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/ci/update_ci_comments.py` | 39 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/consolidate_identical_plans.py` | 55 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/core_engine/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/db/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/check_render_auto_deploy.py` | 23 | 2 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/create_render_service.py` | 27 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/list_render_services.py` | 22 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/update_infisical_render.py` | 54 | 9 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/update_render_env2.py` | 37 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/deploy/update_render_image.py` | 35 | 2 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/devops/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/devops/apply_patch.py` | 168 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/devops/apply_tier_patch.py` | 272 | 2 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/devops/config/validators.py` | 827 | 4 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/diagnostics/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/docs/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/generate_isolation_markdown.py` | 176 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/generate_module_docs.py` | 131 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/git/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/health/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/i18n/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/inspect_rename_candidates.py` | 35 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/k6/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/kaggle/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/lib/__init__.py` | 7 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/maintenance/__init__.py` | 0 | 1 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/monitoring/__init__.py` | 11 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/move_nonascii_root_plans.py` | 24 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/orchestrator/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/organize_external_plans.py` | 147 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/patches/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/quality/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/refactor/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/resource_collection/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/resource_collection/api_clients.py` | 182 | 3 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/resource_collection/ossinsight/__init__.py` | 4 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/resource_collection/run_all_collectors.py` | 2 | 3 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/resource_scraping/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/runner/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/scan_duplicate_plans.py` | 63 | 2 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/security/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/security/generate_secrets.py` | 124 | 5 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/supremeai_toolkit/__init__.py` | 16 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/tenant/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/test_mcp_servers.py` | 32 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/testenv/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/testing/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |
| `scripts/worktrees/__init__.py` | 0 | 0 | শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য |

## review-standalone তালিকা (ম্যানুয়াল রান-ভ্যালু যাচাই প্রয়োজন)

| ফাইল | লাইন | docs-রেফ |
| :--- | ---: | ---: |
| `scripts/advanced_analysis/agent_capability_registry_sync.py` | 996 | 2 |
| `scripts/advanced_analysis/dead_code_verified_finder.py` | 1017 | 5 |
| `scripts/advanced_analysis/endpoint_timeout_auditor.py` | 1040 | 2 |
| `scripts/advanced_analysis/error_handling_consistency_checker.py` | 1252 | 1 |
| `scripts/advanced_analysis/importer_graph.py` | 1040 | 1 |
| `scripts/advanced_analysis/migration_safety_diff.py` | 1237 | 5 |
| `scripts/advanced_analysis/pydantic_schema_consistency_checker.py` | 1170 | 1 |
| `scripts/agents/heartbeat_ping.py` | 230 | 4 |
| `scripts/agents/heartbeat_ping.sh` | 114 | 2 |
| `scripts/agents/next_claimable.sh` | 111 | 13 |
| `scripts/agents/zai_browser_worker.py` | 196 | 0 |
| `scripts/ai/change_impact_detector.py` | 123 | 4 |
| `scripts/ai/cited_change_planner.py` | 51 | 1 |
| `scripts/ai/drift_checks.py` | 68 | 2 |
| `scripts/ai/evidence_bundle.py` | 61 | 2 |
| `scripts/ai/feature_store_sync.py` | 420 | 1 |
| `scripts/ai/memory_write.py` | 167 | 7 |
| `scripts/ai/repository_metadata_index.py` | 62 | 2 |
| `scripts/ai/sandboxed_repair.py` | 52 | 2 |
| `scripts/audit/find_dead_modules.py` | 482 | 4 |
| `scripts/audit/find_duplicates.py` | 281 | 4 |
| `scripts/audit/system_deep_scan_2026_09_15.py` | 312 | 3 |
| `scripts/audit/system_defect_scan_2026_09_16.py` | 278 | 4 |
| `scripts/audit_isolated_components.py` | 233 | 1 |
| `scripts/audit_isolated_modules_and_capabilities.py` | 450 | 2 |
| `scripts/audit_module_wiring.py` | 141 | 17 |
| `scripts/audit_run_backend_suites.sh` | 32 | 0 |
| `scripts/audit_underutilized_capabilities.py` | 215 | 1 |
| `scripts/auto_marketing_skill_forge.py` | 261 | 1 |
| `scripts/backup/auto_cross_cloud_replicate.py` | 328 | 7 |
| `scripts/backup/auto_firestore_backup.py` | 262 | 6 |
| `scripts/backup/create_desktop_backup.py` | 444 | 4 |
| `scripts/backup/drill_preflight.py` | 260 | 4 |
| `scripts/benchmark/perf_benchmark.py` | 71 | 2 |
| `scripts/benchmark/superai_load_tester.py` | 943 | 7 |
| `scripts/bots/auto_alert_bot.py` | 232 | 4 |
| `scripts/bots/auto_daily_standup_bot.py` | 257 | 2 |
| `scripts/check_app_boots.sh` | 106 | 6 |
| `scripts/ci/architecture_query.py` | 51 | 0 |
| `scripts/ci/check_config_control_plane.py` | 68 | 5 |
| `scripts/ci/check_i18n_keys.py` | 129 | 0 |
| `scripts/ci/check_migration_safety.py` | 71 | 2 |
| `scripts/ci/cleanup_stale_branches.py` | 93 | 0 |
| `scripts/ci/config_registry_evidence.py` | 99 | 2 |
| `scripts/ci/deploy.sh` | 10 | 7 |
| `scripts/ci/enforce_circle_boundaries.py` | 52 | 5 |
| `scripts/ci/generate_changelog.py` | 120 | 0 |
| `scripts/ci/generate_changelog.sh` | 10 | 2 |
| `scripts/ci/group_closeout_janitor.py` | 315 | 11 |
| `scripts/ci/issue_queue_manager.py` | 480 | 3 |
| `scripts/ci/knip_summarize.py` | 77 | 0 |
| `scripts/ci/render_recheck_scheduler.py` | 57 | 9 |
| `scripts/ci/run_tests.sh` | 15 | 1 |
| `scripts/ci/schedule_render_rechecks.py` | 34 | 1 |
| `scripts/codegraph_integration.py` | 281 | 1 |
| `scripts/core_engine/multicatalog_search.py` | 405 | 1 |
| `scripts/core_engine/tool_ranker.py` | 453 | 2 |
| `scripts/db/auto_seed.py` | 115 | 5 |
| `scripts/db/load_coldstart_knowledge.py` | 255 | 2 |
| `scripts/db/run_migration.py` | 34 | 2 |
| `scripts/db/seed_knowledge_fts.py` | 162 | 1 |
| `scripts/db/validate_retrieval.py` | 198 | 6 |
| `scripts/deploy/add_secrets_to_infisical.py` | 80 | 9 |
| `scripts/deploy/blue_green_deploy.py` | 360 | 5 |
| `scripts/deploy/canary_deploy.py` | 365 | 3 |
| `scripts/deploy/check_render.py` | 38 | 4 |
| `scripts/deploy/check_render_svc.py` | 31 | 1 |
| `scripts/deploy/disaster_recovery_test.py` | 393 | 8 |
| `scripts/deploy/infrastructure_as_code_validator.py` | 318 | 2 |
| `scripts/deploy/rollback_rehearsal_preflight.py` | 307 | 4 |
| `scripts/deploy/superai_quick_deploy.sh` | 832 | 3 |
| `scripts/deploy_all_services.py` | 189 | 2 |
| `scripts/devops/cloud_watchman.py` | 455 | 10 |
| `scripts/devops/config/cli.py` | 60 | 13 |
| `scripts/devops/devops_ai_scribe.py` | 609 | 77 |
| `scripts/devops/generate_modular_audits.py` | 946 | 6 |
| `scripts/devops/run_local_audit.py` | 116 | 8 |
| `scripts/devops/todo_manager.py` | 238 | 3 |
| `scripts/docs/auto_adr_generator.py` | 258 | 1 |
| `scripts/docs/auto_api_doc_sync.py` | 345 | 3 |
| `scripts/docs/auto_readme_update.py` | 220 | 1 |
| `scripts/free-tier-health-check.sh` | 299 | 6 |
| `scripts/generate_api_health_report.py` | 74 | 3 |
| `scripts/generate_doc_inventory.py` | 136 | 0 |
| `scripts/generate_openapi.py` | 54 | 4 |
| `scripts/generate_script_index.py` | 390 | 6 |
| `scripts/git/push_as_agent.py` | 165 | 2 |
| `scripts/health/check_system_health.py` | 283 | 4 |
| `scripts/health/cleanup_duplicate_health_scripts.sh` | 42 | 2 |
| `scripts/i18n/bangla_translator.py` | 256 | 4 |
| `scripts/i18n/banglish_converter.py` | 258 | 5 |
| `scripts/i18n/rtl_support_checker.py` | 330 | 2 |
| `scripts/maintenance/check_infisical_vault_synth.py` | 124 | 3 |
| `scripts/maintenance/create_issue.py` | 84 | 2 |
| `scripts/maintenance/notify.py` | 47 | 2 |
| `scripts/maintenance/reindex_ai_memory_embeddings.py` | 211 | 4 |
| `scripts/merge_and_consolidate_docs.py` | 109 | 0 |
| `scripts/monitoring/sla_tracker.py` | 796 | 4 |
| `scripts/monitoring/superai_cpu_monitor.py` | 776 | 2 |
| `scripts/monitoring/superai_log_analyzer.py` | 965 | 3 |
| `scripts/multi_model_validator.py` | 267 | 2 |
| `scripts/operations/ingest_plans_to_rag.py` | 249 | 2 |
| `scripts/operations/operational_truth_db.py` | 389 | 1 |
| `scripts/operations/sync_operational_truth.py` | 469 | 3 |
| `scripts/pre_commit_hook.py` | 282 | 1 |
| `scripts/pre_deploy_check.sh` | 88 | 8 |
| `scripts/pre_push_hook.py` | 255 | 0 |
| `scripts/prune_cache.sh` | 28 | 3 |
| `scripts/quality/auto_dead_code_remover.py` | 423 | 4 |
| `scripts/quality/auto_improve_coverage.py` | 255 | 2 |
| `scripts/quality/check_ollama_test_coverage.py` | 277 | 2 |
| `scripts/refactor/superai_transform.py` | 798 | 3 |
| `scripts/render_build_backend.sh` | 62 | 3 |
| `scripts/render_build_frontend.sh` | 95 | 9 |
| `scripts/resource_collection/run_all.py` | 70 | 2 |
| `scripts/resource_collection/scrapers.py` | 532 | 4 |
| `scripts/resource_scraping/awesome_go/scrape.py` | 79 | 3 |
| `scripts/resource_scraping/awesome_python/scrape.py` | 71 | 3 |
| `scripts/resource_scraping/awesome_selfhosted/scrape.py` | 71 | 3 |
| `scripts/rotate_lessons.py` | 83 | 4 |
| `scripts/runner/setup_runner.sh` | 74 | 2 |
| `scripts/runner/zero_cost_optimizer.sh` | 36 | 3 |
| `scripts/security/audit_log_analyzer.py` | 852 | 3 |
| `scripts/security/auto_secret_rotate.py` | 102 | 5 |
| `scripts/security/delete_vault_duplicate_render_keys.py` | 110 | 0 |
| `scripts/security/delete_vault_stale_keys.py` | 110 | 1 |
| `scripts/security/idor_runtime_matrix.py` | 229 | 0 |
| `scripts/security/purge_history_secrets.sh` | 81 | 5 |
| `scripts/security/secrets_rotation_manager.py` | 590 | 10 |
| `scripts/security/verify_token_rotation.py` | 199 | 1 |
| `scripts/setup-git-hooks.sh` | 60 | 3 |
| `scripts/setup_kms.sh` | 23 | 5 |
| `scripts/supreme_ops.py` | 120 | 2 |
| `scripts/supremeai_performance_benchmark.py` | 186 | 1 |
| `scripts/supremeai_toolkit/__main__.py` | 16 | 0 |
| `scripts/supremeai_toolkit/cli.py` | 56 | 13 |
| `scripts/supremeai_toolkit/reusability_audit.py` | 229 | 0 |
| `scripts/sync_modules_list.py` | 52 | 11 |
| `scripts/tenant/auto_tenant_health_report.py` | 670 | 1 |
| `scripts/tenant/auto_tenant_setup.py` | 435 | 1 |
| `scripts/testenv/setup_test_env.sh` | 71 | 2 |
| `scripts/testing/_gen_services.py` | 898 | 3 |
| `scripts/testing/api_contract_validator.py` | 1073 | 7 |
| `scripts/testing/log_anomaly_detector.py` | 713 | 4 |
| `scripts/testing/test_runners.py` | 1334 | 7 |
| `scripts/verify_capabilities.py` | 178 | 4 |
| `scripts/verify_render_env.py` | 187 | 2 |
| `scripts/worktrees/run_task.sh` | 33 | 1 |
| `scripts/worktrees/setup_worktree.sh` | 69 | 1 |

---

# seq:2 — Harvest-Check ও প্রমাণ-ভিত্তিক ছাঁটাই (Execution Record)

> **তারিখ:** 2026-09-28 · **ইঞ্জিন:** `scripts/supremeai_toolkit` v0.2.0 (`audit` + `harvest` + `plan-guard`) · **পূর্ণ রায়-ম্যানিফেস্ট:** [HARVEST-MANIFEST-foundation-closeout-seq2.md](HARVEST-MANIFEST-foundation-closeout-seq2.md)

## ১. seq:1 স্ক্যানারের ব্লাইন্ড-স্পট ফিক্স (Golden-Rule সেফটি-ফিক্স)

seq:1 ইঞ্জিনের দুটি গভীর ত্রুটি ছিল — দুটোই **false-PRUNE** দিকে ঝুঁকিযুক্ত (Golden Rule-এর বিপরীত):

| ত্রুটি | প্রমাণ | ফিক্স |
| :--- | :--- | :--- |
| basename-ম্যাচ কেবল extension-সহ (`validators.py`) — import-stem (`from validators import X`) অদৃশ্য | `scripts/devops/config/cli.py` সত্যিই `validators.py` import করত, তবুও ৮২৭-লাইনের মডিউল prune-candidate | live-code রেফ = ফাইলনাম **অথবা** import-stem টোকেন (line-anchored parser) |
| scan-root-এর ফাইল রেফ-সোর্স হিসেবে বাদ — scripts/-অভ্যন্তরীণ import-chain অদৃশ্য | `cli.py → validators.py` রেফ দেখাই নি | target-ফাইলরাও রেফ-সোর্স (সেলফ-রেফ বাদ); toolkit-এর নিজের ফাইল কেবল import-stem-এ গণ্য (মেটাডাটা-স্তর নিজেকে প্রমাণ করে না) |

পাশাপাশি: module-level `sys.argv` = entry-point মার্কার যোগ (`generate_secrets.py`-এর মতো CLI ধরা পেত না) + `__init__.py`/`test_*` harvest-exemption verdict (`keep-structural` / `keep-tested` — test_guard gate-এর সাংবিধানিক রক্ষার সাথে সামঞ্জস্য)।

**Verdict-শিফট (seq:1 → seq:2, একই রুট `scripts`):**

| Verdict | seq:1 | seq:2 | ব্যাখ্যা |
| :--- | ---: | ---: | :--- |
| keep-structural | — | 36 | নতুন exemption: `__init__.py` প্যাকেজ-মার্কার |
| keep-tested | — | 13 | নতুন exemption: `test_*` (test_guard-রক্ষিত) |
| keep-canonical | 198 | 229 | import-stem + root-অভ্যন্তরীণ chain এখন দৃশ্যমান |
| review-standalone | 151 | 104 | অনেক entry-point-এর প্রকৃত রেফ ধরা পড়েছে |
| prune-candidate | 85 | 18 | **৪৭টি ভুল-প্রার্থী প্রমাণসহ রক্ষা পেল** — false-PRUNE প্রতিরোধ |

## ২. Harvest Manifest — ১৮ প্রার্থীর চূড়ান্ত রায়

| রায় | সংখ্যা | তালিকা |
| :--- | ---: | :--- |
| 🛡️ keep-operational | 7 | `generate_secrets.py` (ENV_HYGIENE_POLICY + ARCH-02), `update_infisical_render.py` (৩ runbook), `apply_tier_patch.py` (ARCH-02), `update_render_image.py` (BACKUP_RESTORE runbook), render 2-C3 পরিবার: `update_render_env2` / `create_render_service` / `list_render_services` / `check_render_auto_deploy` |
| ⚙️ engine-keep-canonical | 2 | `validators.py` (cli.py import), `api_clients.py` (scrapers.py import — রিপেয়ার-পরবর্তী) |
| 🧺 absorb-then-prune | 1 | `scan_duplicate_plans.py` → পোর্টেবল `supremeai_toolkit/plan_guard.py` হিসেবে পুনঃসৃষ্ট (MODULE_21 doc-রেফারেন্সড ক্যাপাবিলিটি — হারানো যাবে না) |
| ✂️ prune-after-harvest | 10 | নিচের টেবিল |

**রক্ষিত-বিশেষ (স্পর্শই করা হয়নি):** ৩৬× `__init__.py` + ১৩× `test_*` (test_guard gate `deleted_test_files: block` — সাংবিধানিক রক্ষা; ভাঙা `test_mcp_servers.py`-এর `f:\supremeai` পাথ follow-up-নোট হিসেবে নথিভুক্ত)।

## ৩. সম্পাদিত ছাঁটাই (১১ ফাইল, প্রত্যেকটির প্রমাণ)

| ফাইল | লাইন | প্রমাণ |
| :--- | ---: | :--- |
| `scripts/scan_duplicate_plans.py` | 63 | **absorbed** — `plan_guard.py`-তে পোর্টেবল পুনঃসৃষ্ট; `f:\`-হার্ডকোডে অচল |
| `scripts/resource_collection/run_all_collectors.py` | 2 | ড্যাঙ্গলিং রিডাইরেক্ট-স্টাব — লক্ষ্য `scripts/run_all_collectors.py` নেই; আগের hygiene-roadmap-ও "Unnecessary — delete" বলেছে |
| `scripts/generate_isolation_markdown.py` | 176 | ইনপুট JSON (`deep_codebase_isolation_raw.json`) রিপোতেই নেই — মৃত-ইনপুট রেন্ডারার |
| `scripts/devops/apply_patch.py` | 168 | ওয়ান-টাইম প্যাচার — হার্ডকোড প্যাচ ইতোমধ্যে প্রয়োগৃত; শূন্য রেফ |
| `scripts/organize_external_plans.py` | 147 | ওয়ান-টাইম অর্গানাইজার — external plans ইতোমধ্যে সংগঠিত; শূন্য রেফ/ডক |
| `scripts/generate_module_docs.py` | 131 | `f:\supremeai`-হার্ডকোড — যেকোনো মেশিনে অচল |
| `scripts/apply_plan_renames.py` | 81 | `f:\`-হার্ডকোড + রিনেম-ম্যাপ ইতোমধ্যে প্রয়োগৃত |
| `scripts/consolidate_identical_plans.py` | 55 | `f:\`-হার্ডকোড + consolidation ইতোমধ্যে সম্পন্ন |
| `scripts/ci/update_ci_comments.py` | 39 | ওয়ান-টাইম ci.yml-এডিটর — এডিট প্রয়োগৃত; শূন্য রেফ |
| `scripts/inspect_rename_candidates.py` | 35 | `f:\`-হার্ডকোড, ওয়ান-টাইম প্রিভিউ-জেনারেটর |
| `scripts/move_nonascii_root_plans.py` | 24 | `f:\`-হার্ডকোড, ওয়ান-টাইム মুভ — nonascii প্ল্যান ইতোমধ্যে সরানো |

সব ডিলিট `git history`-তে সংরক্ষিত — পুনরুজ্জীবন-প্রয়োজনে রিস্টোরযোগ্য।

## ৪. ক্যাপাবিলিটি-রিপেয়ার ও পুনঃসৃষ্টি (Zero-Loss Ledger)

| কাজ | প্রমাণ |
| :--- | :--- |
| `scrapers.py` ভাঙা import রিপেয়ার | `from base_api_client import ...` → `from api_clients import ...` — অডিট-ইঞ্জিন নিজেই যাচাই করেছে: api_clients.py এখন keep-canonical (live-ref: scrapers.py) |
| `plan_guard.py` পুনঃসৃষ্টি | MD5-dup + name/header-similarity (0.70/0.80 থ্রেশহোল্ড অক্ষুণ্ণ), রিপো-আপেক্ষিক রুট, `--out-json/--out-txt`, exit-code CI-বান্ধব |
| Harvest Engine (`harvest.py`) | ১৮ প্রার্থীর প্রত্যেকটির প্রমাণ-বান্ডিলসহ রায় — ভবিষ্যৎ ছাঁটাই-প্রস্তাবের বাধ্যতামূলক প্রথম-পদক্ষেপ |
| `_INDEX.md` regen | অটো-জেনারেটেড ইনডেক্স 2026-09-10 থেকে স্টেল — ২৬৯→৩৬৩ স্ক্রিপ্ট, staleness-gate পরিষ্কার |
| MODULE_21 succession-নোট | crown-jewel ডকের "সক্রিয়-টুল" রেফ এখন পোর্টেবল উত্তরাধিকারে নির্দেশ করে |

**চূড়ান্ত অবস্থা (post-prune audit, 389 ফাইল):** 36 keep-structural · 13 keep-tested · **229** keep-canonical · 104 review-standalone · **7** prune-candidate — যার প্রত্যেকটি harvest-manifest-এ keep-operational রায়প্রাপ্ত (স্পর্শ নিষিদ্ধ)। **শূন্য ক্যাপাবিলিটি-লস।**
