# Standalone Run-Value Verification — group:foundation-closeout (seq:3)

> **তারিখ:** 2026-09-28 22:38 UTC · **ইঞ্জিন:** `scripts/supremeai_toolkit/standalone_check.py` v0.1.0 · **roots:** scripts
> **Golden Rule:** Clean up-এর আগে Reusability Check — beneficial কিছু কোনো অবস্থাতেই ডিলিট করা যাবে না (#2403)।
> এই রিপোর্ট review-standalone বাকেটের প্রমাণ-বেস — এখান থেকে কোনো ফাইল স্বয়ংক্রিয়ভাবে ডিলিট বা সরানো হয় না।

## সারসংক্ষেপ

**যাচাই করা review-standalone ফাইল: 104**

| Verdict | সংখ্যা | অর্থ |
| :--- | ---: | :--- |
| keep-operational | 86 | চলুচিত অপারেশনাল টুল — মানুষ চালায়, শূন্য স্বয়ংক্রিয় রেফ স্বাভাবিক |
| absorb-candidate | 18 | পোর্টেবল unique লজিক — পরবর্তী slice-এ toolkit-এ পুনঃসৃষ্টির ম্যানিফেস্ট |
| stale-review | 0 | ভাঙা/পুরনো প্রমাণ — পরবর্তী slice-এ prune-after-harvest প্রার্থী (এই স্লাইসে ডিলিট নেই) |

## stale-review তালিকা (পরবর্তী slice-এর harvest-check evidence-base)

| ফাইল | লাইন | রানেবিল | unique-সিম্বল | docs-রেফ | কারণ |
| :--- | ---: | :---: | ---: | ---: | :--- |

## absorb-candidate তালিকা (হারভেস্ট-ম্যানিফেস্ট — toolkit-এ পুনঃসৃষ্টির প্রার্থী)

| ফাইল | লাইন | রানেবিল | unique-সিম্বল | docs-রেফ | কারণ |
| :--- | ---: | :---: | ---: | ---: | :--- |
| `scripts/advanced_analysis/agent_capability_registry_sync.py` | 996 | ✅ | 18/23 | 3 | 18/23 unique সিম্বল + 996L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/advanced_analysis/dead_code_verified_finder.py` | 1017 | ✅ | 22/36 | 6 | 22/36 unique সিম্বল + 1017L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/advanced_analysis/migration_safety_diff.py` | 1237 | ✅ | 18/26 | 6 | 18/26 unique সিম্বল + 1237L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/advanced_analysis/pydantic_schema_consistency_checker.py` | 1170 | ✅ | 23/28 | 2 | 23/28 unique সিম্বল + 1170L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/audit/find_duplicates.py` | 281 | ✅ | 6/10 | 6 | 6/10 unique সিম্বল + 281L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/audit_isolated_modules_and_capabilities.py` | 450 | ✅ | 14/25 | 3 | 14/25 unique সিম্বল + 450L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/backup/drill_preflight.py` | 260 | ✅ | 5/9 | 6 | 5/9 unique সিম্বল + 260L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/bots/auto_daily_standup_bot.py` | 257 | ✅ | 9/9 | 3 | 9/9 unique সিম্বল + 257L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/codegraph_integration.py` | 281 | ✅ | 9/10 | 2 | 9/10 unique সিম্বল + 281L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/db/load_coldstart_knowledge.py` | 255 | ✅ | 9/12 | 3 | 9/12 unique সিম্বল + 255L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/deploy/infrastructure_as_code_validator.py` | 318 | ✅ | 11/15 | 3 | 11/15 unique সিম্বল + 318L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/deploy/rollback_rehearsal_preflight.py` | 307 | ✅ | 6/10 | 6 | 6/10 unique সিম্বল + 307L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/i18n/bangla_translator.py` | 256 | ✅ | 8/12 | 5 | 8/12 unique সিম্বল + 256L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/i18n/banglish_converter.py` | 258 | ✅ | 8/10 | 6 | 8/10 unique সিম্বল + 258L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/operations/sync_operational_truth.py` | 469 | ✅ | 7/10 | 6 | 7/10 unique সিম্বল + 469L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/testing/_gen_services.py` | 898 | ✅ | 12/21 | 4 | 12/21 unique সিম্বল + 898L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/testing/log_anomaly_detector.py` | 713 | ✅ | 16/30 | 5 | 16/30 unique সিম্বল + 713L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |
| `scripts/verify_capabilities.py` | 178 | ✅ | 8/9 | 5 | 8/9 unique সিম্বল + 178L পোর্টেবল লজিক — toolkit-এ পুনঃসৃষ্টির প্রার্থী |

## keep-operational তালিকা (স্পর্শ নিষিদ্ধ — চলুচিত অপারেশনাল টুল)

| ফাইল | লাইন | রানেবিল | unique-সিম্বল | docs-রেফ | কারণ |
| :--- | ---: | :---: | ---: | ---: | :--- |
| `scripts/advanced_analysis/endpoint_timeout_auditor.py` | 1040 | ✅ | 34/41 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/agents/heartbeat_ping.sh` | 114 | ✅ | 0/0 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/agents/zai_browser_worker.py` | 196 | ✅ | 0/1 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ai/cited_change_planner.py` | 51 | ✅ | 1/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ai/feature_store_sync.py` | 420 | ✅ | 6/9 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ai/memory_write.py` | 167 | ✅ | 1/4 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ai/sandboxed_repair.py` | 52 | ✅ | 2/2 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/audit/find_dead_modules.py` | 482 | ✅ | 9/14 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/audit/system_defect_scan_2026_09_16.py` | 278 | ✅ | 4/7 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/audit_module_wiring.py` | 141 | ✅ | 6/8 | 19 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 19, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/audit_run_backend_suites.sh` | 32 | ✅ | 0/0 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/audit_underutilized_capabilities.py` | 215 | ✅ | 1/1 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/auto_marketing_skill_forge.py` | 261 | ✅ | 4/4 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/backup/auto_cross_cloud_replicate.py` | 328 | ✅ | 5/6 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/backup/create_desktop_backup.py` | 444 | ✅ | 1/11 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/benchmark/perf_benchmark.py` | 71 | ✅ | 1/1 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/benchmark/superai_load_tester.py` | 943 | ✅ | 17/33 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/bots/auto_alert_bot.py` | 232 | ✅ | 5/7 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/architecture_query.py` | 51 | ✅ | 0/0 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/check_config_control_plane.py` | 68 | ✅ | 0/1 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/check_i18n_keys.py` | 129 | ✅ | 2/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/cleanup_stale_branches.py` | 93 | ✅ | 2/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/config_registry_evidence.py` | 99 | ✅ | 0/3 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/enforce_circle_boundaries.py` | 52 | ✅ | 1/1 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/generate_changelog.py` | 120 | ✅ | 2/3 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/generate_changelog.sh` | 10 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/group_closeout_janitor.py` | 315 | ✅ | 8/9 | 13 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 13, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/knip_summarize.py` | 77 | ✅ | 0/1 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/render_recheck_scheduler.py` | 57 | ✅ | 0/0 | 10 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 10, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/ci/schedule_render_rechecks.py` | 34 | ✅ | 0/0 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/core_engine/tool_ranker.py` | 453 | ✅ | 13/19 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/db/auto_seed.py` | 115 | ✅ | 0/1 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/db/run_migration.py` | 34 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/db/validate_retrieval.py` | 198 | ✅ | 2/3 | 7 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 7, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/deploy/add_secrets_to_infisical.py` | 80 | ✅ | 2/2 | 10 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 10, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/deploy/canary_deploy.py` | 365 | ✅ | 7/10 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/deploy_all_services.py` | 189 | ✅ | 2/2 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/devops/cloud_watchman.py` | 455 | ✅ | 14/23 | 11 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 11, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/devops/generate_modular_audits.py` | 946 | ✅ | 8/12 | 7 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 7, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/devops/run_local_audit.py` | 116 | ✅ | 3/3 | 9 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 9, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/devops/todo_manager.py` | 238 | ✅ | 3/8 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/docs/auto_adr_generator.py` | 258 | ✅ | 5/5 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/docs/auto_api_doc_sync.py` | 345 | ✅ | 7/7 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/docs/auto_readme_update.py` | 220 | ✅ | 2/3 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/free-tier-health-check.sh` | 299 | ✅ | 0/0 | 7 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 7, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/generate_doc_inventory.py` | 136 | ✅ | 1/1 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/generate_openapi.py` | 54 | ✅ | 0/1 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/health/cleanup_duplicate_health_scripts.sh` | 42 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/maintenance/check_infisical_vault_synth.py` | 124 | ✅ | 0/2 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/maintenance/create_issue.py` | 84 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/maintenance/notify.py` | 47 | ✅ | 0/1 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/maintenance/reindex_ai_memory_embeddings.py` | 211 | ✅ | 3/4 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/merge_and_consolidate_docs.py` | 109 | ✅ | 2/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/monitoring/superai_log_analyzer.py` | 965 | ✅ | 16/25 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/multi_model_validator.py` | 267 | ✅ | 3/4 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/operations/ingest_plans_to_rag.py` | 249 | ✅ | 3/8 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/pre_commit_hook.py` | 282 | ✅ | 1/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/prune_cache.sh` | 28 | ✅ | 0/0 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/quality/auto_improve_coverage.py` | 255 | ✅ | 3/3 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/quality/check_ollama_test_coverage.py` | 277 | ✅ | 5/5 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/render_build_backend.sh` | 62 | ✅ | 0/0 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/resource_collection/run_all.py` | 70 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/resource_collection/scrapers.py` | 535 | ✅ | 7/13 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/resource_scraping/awesome_go/scrape.py` | 79 | ✅ | 0/2 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/resource_scraping/awesome_python/scrape.py` | 71 | ✅ | 0/2 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/resource_scraping/awesome_selfhosted/scrape.py` | 71 | ✅ | 0/2 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/runner/setup_runner.sh` | 74 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/runner/zero_cost_optimizer.sh` | 36 | ✅ | 0/0 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/audit_log_analyzer.py` | 852 | ✅ | 5/15 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/auto_secret_rotate.py` | 102 | ✅ | 1/2 | 6 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 6, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/delete_vault_duplicate_render_keys.py` | 110 | ✅ | 0/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/delete_vault_stale_keys.py` | 110 | ✅ | 0/2 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/generate_secrets.py` | 124 | ✅ | 1/1 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/idor_runtime_matrix.py` | 229 | ✅ | 0/4 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/purge_history_secrets.sh` | 81 | ✅ | 0/0 | 7 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 7, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/security/verify_token_rotation.py` | 199 | ✅ | 3/7 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/setup-git-hooks.sh` | 60 | ✅ | 0/0 | 4 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 4, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/setup_kms.sh` | 23 | ✅ | 0/0 | 5 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 5, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/supreme_ops.py` | 120 | ✅ | 2/4 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/supremeai_performance_benchmark.py` | 186 | ✅ | 2/2 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/tenant/auto_tenant_health_report.py` | 670 | ✅ | 5/9 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/tenant/auto_tenant_setup.py` | 435 | ✅ | 4/7 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/testenv/setup_test_env.sh` | 71 | ✅ | 0/0 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/testing/api_contract_validator.py` | 1073 | ✅ | 34/47 | 8 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 8, service-bound অপারেশনাল, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/verify_render_env.py` | 187 | ✅ | 1/2 | 3 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 3, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
| `scripts/worktrees/run_task.sh` | 33 | ✅ | 0/0 | 2 | রানেবিল অপারেশনাল টুল (runnable=True, docs-রেফ 2, শেষ কমিট 0 দিন আগে) — স্পর্শ নিষিদ্ধ |
