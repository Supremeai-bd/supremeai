# 15 — Operations

SupremeAI ships an unusually large operational toolbelt: a unified ops CLI, 25+ categories of scripts under `scripts/`, and standalone `tools/` packages for autonomy, mining and knowledge work. This page is the field guide.

## Unified Ops CLI

`python scripts/supreme_ops.py <command>` — commands: `audit | knowledge | health | sync-env | clean | recipe`.

Other root-level operational entry points:

| Script | Purpose |
|--------|---------|
| `scripts/verify_capabilities.py` | Capability-matrix smoke test; exit 0 = pass (the "VERIFY before trust" gate) |
| `scripts/pre_deploy_check.sh` | 9-step deploy gate (compile, router imports, boot test, no-`requests` check, frontend secret scan, migration safety, required secrets, free-tier limits, optional pytest); `--quick` skips tests |
| `scripts/ci-full-audit.sh` | Full audit → `ci-reports/{summary,errors,warnings}.txt` (used by CI advanced-checks) |
| `scripts/free-tier-health-check.sh` | Free-tier usage guard: exit 0 <70 %, 1 = 70–89 %, 2 ≥90 %; `--json/--quiet` |
| `scripts/keepalive.js` | Standalone 5-min pinger (`BACKEND_URL/api/v1/health`) |
| `scripts/deploy_all_services.py` | Orchestrate multi-service deploys |
| `scripts/audit_env_usage.py` | Reconcile env vars the code reads vs the registry |
| `scripts/audit_observability.py` | Detect silent excepts / stray prints (pre-commit) |
| `scripts/generate_api_health_report.py` | API health report |
| `scripts/check_app_boots.sh`, `check_no_requests_in_backend.sh`, `prune_cache.sh`, `organize_tests.sh` | Sanity + hygiene |

## Scripts Catalog (`scripts/`)

| Category | Highlights |
|----------|-----------|
| `advanced_analysis/` | 21 static analyzers wired into CI: api_contract_diff, db_model_drift_checker, migration_safety_diff, duplicate_detector, env_var_reconciler, hardcode_config_scanner, circular_import_mapper, endpoint_timeout_auditor, pydantic_schema_consistency_checker, orphan_route_finder, dead_code_verified_finder, dependency_freshness_radar, error_handling_consistency_checker, secret_rotation_reminder, test_coverage_gap_mapper, llm_cost_projector, config_single_source_enforcer, bengali_i18n_completeness_checker, importer_graph, duplicate_logic_detector, agent_capability_registry_sync |
| `ci/` | Deploy & gate scripts: render_trigger_deploy, check_required_secrets, check_frontend_secrets, check_migration_safety, check_database_schema, check_single_frontend, validate_config_registry, check_config_control_plane, check_hardcoded_deployment_config, check_service_topology, check_free_tier_limits, coverage_quality_gate (+ coverage_policy.yaml), verify_api_contract, validate_router_imports, validate_frontend_build, project_health_check, generate_audit_summary, generate_changelog.sh |
| `deploy/` | Render/Firebase/Infisical ops: trigger_render_deploy, check_render*, list/create/update services, generate_firebase_config, add_secrets_to_infisical, blue_green_deploy, canary_deploy, disaster_recovery_test, infrastructure_as_code_validator, superai_quick_deploy.sh |
| `security/` | generate_secrets, secrets_rotation_manager, auto_vulnerability_scanner (SARIF+SBOM), auto_secret_rotate, check_dependencies, audit_log_analyzer, find_dead_code, auto_find_blindspots |
| `monitoring/` | capacity_planner (zero-cost HA), cost_analyzer, sla_tracker, fetch_logs, superai_cpu_monitor, superai_log_analyzer, console detective (HTML + JS + Python) |
| `health/` | superai_health_check, check_system_health |
| `db/` | auto_migrate, run_migration, auto_seed, ingest_knowledge, load_coldstart_knowledge, validate_retrieval |
| `backup/` | superai_backup_manager, auto_firestore_backup, auto_cross_cloud_replicate, backup_telegram (encrypted offsite), create_desktop_backup |
| `billing/` | usage_reporter, quota_enforcer, fraud_detector |
| `bots/` | auto_alert_bot, auto_daily_standup_bot |
| `devops/` | bug_prophet, cloud_watchman, devops_ai_scribe, devops_security_scan, run_local_audit, generate_modular_audits, fix_mypy, fix_eslint_any, todo_manager, update_vault, upload_infisical, config/ (rules·cli·models·validators) |
| `quality/` | self_audit_scan, regression_scanner, auto_improve_coverage, auto_dead_code_remover, auto_refactor_suggester, docs_drift_check, check_ollama_test_coverage |
| `testing/` | mutation_testing, api_contract_validator, auto_test_generator, test_runners, log_anomaly_detector, alert_manager, check_timing, performance_benchmark |
| `ai/` | bias_detector, model_drift_detector, model_version_manager, prompt_injection_tester, feature_store_sync, memory_read/write |
| `i18n/` | bangla_translator, banglish_converter, rtl_support_checker |
| `tenant/` | auto_tenant_setup, auto_tenant_health_report |
| `runner/` | setup_runner.sh, zero_cost_optimizer.sh (health-gated prune) |
| `worktrees/`, `testenv/`, `refactor/`, `resource_collection/`, `resource_scraping/`, `orchestrator/` (auto_budget_guardian), `maintenance/`, `diagnostics/`, `docs/` (auto ADR/API-doc/README generators), `git/`, `k6/`, `evolution/`, `core_engine/`, `benchmark/` | Support tooling |

## `tools/` — Autonomy & Intelligence Packages

| Tool | Essence |
|------|---------|
| `tools/autonomy/` | "Autonomy Pack": observe→diagnose→plan→patch→verify→deploy→monitor→learn loop. **Read-only/plan-first by default.** `autonomy_cycle.py` runs watchdog + deploy_guard + capability_builder into one JSON report |
| `tools/gap_miner/` | Read-only project intelligence: security hazards, CI weaknesses, dependency drift, provider routing opportunities, free-tier capacity, docs gaps — scored & prioritized; `--fail-on critical` CI mode; never reads `.env` contents |
| `tools/gap_finder/` | Universal gap discovery CLI (`--profile universal|supremeai|backend|frontend|mobile|security`, `--strict`, baselines) |
| `tools/knowledge/` | Tool Knowledge Cards → `ai_memory` (`--inject`, `--verify`, `--export`) |
| `tools/knowledge_squeezer/` | Multi-model brainstorm → adversarial audit → Socratic gap mining → confidence-gated synthesis → memory promotion (needs DEEPSEEK/ANTHROPIC/GEMINI key) |
| `tools/solution_synthesizer/` | "The Hand": diagnosis→evidence→hypothesis→patch→sandbox→tests→verified patch; **dry-run default, `--apply` required**; `.supremeai_backups/` timestamps |
| `tools/discovery_fabric/` | `supremeai_discovery` package: source_scout (GitHub/npm/HF/PyPI), trust_engine, marketplace_scout, solution synthesizer |
| `tools/master_orchestrator.py` | CLI dispatch of Crown Jewel cognitive tools: `--intent repair|synthesis|audit|evolution` |
| `tools/intelligence_extensions/` | failure_pattern_miner, autonomous_red_team, execution_verifier, knowledge_graph_builder, model_router_economist, skill_distiller, evidence_verifier, memory_curator, contradiction_hunter, pipeline |

## Monitoring & Observability Stack

- **Runtime**: Sentry (errors + boot failures), OpenTelemetry (FastAPI auto-instrumentation + OTLP), Langfuse (LLM traces), PostHog (product), Prometheus `/metrics` (when `MONITORING_DETAILED`).
- **Self-hosted stack** (production compose): Prometheus v2.48 + Alertmanager v0.26 (`infrastructure/monitoring/prometheus/` with alert rules) + Grafana 10.2.3 (dashboard `infrastructure/monitoring/grafana/dashboards/supremeai-overview.json`) + OTel Collector 0.88.
- **Uptime**: keep-alive workflows + Cloudflare cron + `heartbeat` service pinging `/api/v1/live`; AETHEL Command Center surfaces live metrics over `/ws/dashboard`.
- **Cost**: CostGuard in the LLM gateway; `scripts/monitoring/cost_analyzer.py`; `llm_cost_projector.py`; billing quota enforcer + fraud detector; cost-guard DEFCON job in maintenance workflow.
- **Alerts**: Telegram (`TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_CHAT_ID`), Discord, Slack webhooks; `scripts/bots/auto_alert_bot.py`.

## Troubleshooting Playbook

| Symptom | First checks |
|---------|--------------|
| Service asleep / 502 on Render | keep-alive workflows ran? `curl /api/v1/health/live`; check `keepalive.yml` + Cloudflare cron; cold start up to 60 s |
| High memory / OOM kills | `LOW_MEMORY_MODE=true`? Only 1 worker? `MemoryAwareMiddleware` logs; check ChromaDB volume size; `memory` health check (<90 %) |
| LLM failures cascade | `/llm-gateway/admin/gateway/state` — circuit breakers open? reset via `/llm-gateway/admin/circuit-breaker/reset/{name}`; RPM limits hit (Gemini 9/min)? |
| Budget guardian halted orchestrator | inspect `auto_budget_guardian.py` output; cost limits (`MAX_COST_PER_TASK`) exceeded is fail-closed by design |
| DB degraded mode active | `SUPABASE_ALLOW_DB_DEGRADATION` triggered — Supabase unreachable; check pooler URL/SSL CA; SQLite fallback is temporary |
| Silent errors creeping in | run `python scripts/detect_silent_errors.py`; baseline `scripts/silent_errors_baseline.json`; `audit_observability.py` |
| Docs drifted from code | `python scripts/quality/docs_drift_check.py`; `tools/gap_miner/tools/drift_detector.py` |
| Frontend can't reach backend | `VITE_API_URL` chain + fail-fast rule; circuit breaker state (`VITE_CIRCUIT_*`); relative-path mode for same-origin hosting |
| WS dashboard disconnected | `VITE_WS_BASE_URL`/https→wss swap; auth window/attempt caps; two WS managers share reconnect logic |

## Operational Wisdom Baked Into the Repo

- **`LESSONS_LEARNED.md`, `CHECKPOINT.md`, `FEATURE_TRACKING_LOG.md`** at repo root record operational history (excluded from this clean doc set by design, but useful context).
- The **silent-catcher** (`core/intelligent_silent_catcher.py`, installed first in `main.py`) exists because silent failures were historically the top incident class — hence also `detect_silent_errors.py`, `auto_fix_silent_excepts.py`, the baseline JSON, and the observability audit pre-commit hook.
- The **budget guardian halts everything** on failure — cost safety outranks availability, per the Zero-Waste principle.
- Worker degradation is **reported honestly** (degraded status, not fake health) — the keep-alive pinger targets `/health` which reports real state.
