# Route → Frontend-Consumer Inventory (generated)

> Generator: `scripts/audit/generate_route_consumer_inventory.py` — issue #480 required-fix steps 1-2+5. Do not edit by hand; regenerate with `python scripts/audit/generate_route_consumer_inventory.py`. CI gate: `tests/test_route_consumer_contract.py` (drift + new-orphan).

| metric | value |
|---|---|
| backend routes | 871 |
| routes with frontend consumer | 311 |
| unique frontend `/api/...` refs | 158 |
| unmounted routes (not in ALL_ROUTERS) | 7 |
| orphan routes (unclassified) | 0 |
| orphan families | 0 |
| api-only routes (allowlisted) | 285 |
| api-only families | 156 |

## Classification legend

| classification | count | meaning |
|---|---|---|
| `user-facing` | 183 | frontend consumer matched |
| `admin-only` | 358 | /admin path, admin router file or ALL_ROUTERS is_admin |
| `internal` | 41 | internal namespace (internal/ops/health/metrics/webhook/cdc/kernel/system) |
| `deprecated` | 4 | marked deprecated (docstring/decorator/name/path) |
| `api-only` | 285 | family allowlisted in `scripts/audit/api_only_routes.txt` — owner to prune as wiring lands (#480 steps 3-4) |
| `orphaned` | 0 | no consumer and no classification — CI fails on NEW orphans |

## Orphan families

None — every route is classified or allowlisted. New orphans fail `tests/test_route_consumer_contract.py`.

## Intentionally API-only families (allowlisted — owner to prune as wiring lands)

| family | routes |
|---|---|
| `/agent/plan` | 1 |
| `/api/artifacts` | 1 |
| `/api/artifacts/:param` | 4 |
| `/api/artifacts/conversation` | 1 |
| `/api/billing/add-funds` | 1 |
| `/api/billing/budget-check` | 1 |
| `/api/billing/history` | 1 |
| `/api/browser/activity` | 1 |
| `/api/browser/automation` | 2 |
| `/api/browser/autonomous` | 1 |
| `/api/browser/browse` | 1 |
| `/api/browser/extract` | 1 |
| `/api/browser/findings` | 1 |
| `/api/browser/render` | 1 |
| `/api/browser/scrape` | 1 |
| `/api/browser/semantic-click` | 1 |
| `/api/browser/simulate-activity` | 1 |
| `/api/browser/smart-click` | 1 |
| `/api/browser/surf` | 12 |
| `/api/browser/system-learning` | 2 |
| `/api/browser/urls` | 8 |
| `/api/byoc/credentials` | 1 |
| `/api/byoc/deploy` | 1 |
| `/api/byoc/status` | 1 |
| `/api/chat/capabilities` | 1 |
| `/api/chat/completion` | 1 |
| `/api/chat/get_completion` | 1 |
| `/api/chat/learning` | 1 |
| `/api/chat/search` | 1 |
| `/api/chat/stream_chat` | 1 |
| `/api/chat/tasks` | 1 |
| `/api/ci/cache` | 1 |
| `/api/ci/history` | 1 |
| `/api/ci/stats` | 1 |
| `/api/ci/summary` | 1 |
| `/api/ci/trends` | 1 |
| `/api/codeflow/analyze` | 1 |
| `/api/comment-ai/handle-comment` | 1 |
| `/api/comment-ai/stale-prs` | 1 |
| `/api/comment-ai/summarize` | 1 |
| `/api/conversations/:param` | 3 |
| `/api/conversations/tree` | 1 |
| `/api/dashboard/stream` | 1 |
| `/api/feedback/ingest` | 1 |
| `/api/files/:param` | 2 |
| `/api/knowledge/ask` | 1 |
| `/api/knowledge/ask-scribe` | 1 |
| `/api/knowledge/failure` | 1 |
| `/api/knowledge/feedback` | 1 |
| `/api/knowledge/learn` | 1 |
| `/api/knowledge/search` | 1 |
| `/api/knowledge/stats` | 1 |
| `/api/memory/checkpoint` | 1 |
| `/api/memory/chunk` | 1 |
| `/api/memory/context` | 1 |
| `/api/memory/recall` | 3 |
| `/api/memory/save` | 1 |
| `/api/memory/session` | 1 |
| `/api/merge-learning/reports` | 1 |
| `/api/mobile/bff` | 1 |
| `/api/reasoning/think` | 2 |
| `/api/research/:param` | 1 |
| `/api/research/deep` | 1 |
| `/api/session/:param` | 2 |
| `/api/simulator/devices` | 1 |
| `/api/simulator/install` | 2 |
| `/api/simulator/installed` | 1 |
| `/api/simulator/profile` | 2 |
| `/api/simulator/session` | 3 |
| `/api/skills/install` | 1 |
| `/api/skills/uninstall` | 1 |
| `/api/style/generate` | 1 |
| `/api/style/learn` | 1 |
| `/api/style/prompt` | 1 |
| `/api/telemetry/frontend-error` | 1 |
| `/api/telemetry/performance` | 1 |
| `/api/telemetry/status` | 1 |
| `/api/tts/audio` | 1 |
| `/api/tts/cache` | 1 |
| `/api/tts/generate` | 1 |
| `/api/tts/languages` | 1 |
| `/api/tts/synthesize` | 1 |
| `/api/tts/voices` | 1 |
| `/api/v1/agent_review_workflow` | 2 |
| `/api/v1/analytics` | 3 |
| `/api/v1/auth` | 4 |
| `/api/v1/browse` | 1 |
| `/api/v1/cache` | 1 |
| `/api/v1/circles` | 3 |
| `/api/v1/cognitive` | 1 |
| `/api/v1/deep` | 1 |
| `/api/v1/ecosystem` | 14 |
| `/api/v1/engine` | 1 |
| `/api/v1/graph` | 1 |
| `/api/v1/healing` | 1 |
| `/api/v1/kaggle` | 4 |
| `/api/v1/keys` | 2 |
| `/api/v1/localization` | 3 |
| `/api/v1/maintenance` | 1 |
| `/api/v1/markdown` | 7 |
| `/api/v1/mcp` | 13 |
| `/api/v1/mesh` | 10 |
| `/api/v1/missions` | 11 |
| `/api/v1/onboarding` | 5 |
| `/api/v1/plugins` | 1 |
| `/api/v1/pr-review` | 1 |
| `/api/v1/rag` | 2 |
| `/api/v1/recipe` | 1 |
| `/api/v1/router` | 1 |
| `/api/v1/runs` | 9 |
| `/api/v1/sandbox` | 4 |
| `/api/v1/scrape` | 1 |
| `/api/v1/stream` | 1 |
| `/api/v1/syncguard` | 1 |
| `/api/v1/tools-registry` | 4 |
| `/api/v1/zero-cost` | 1 |
| `/api/voice/stream_audio` | 1 |
| `/auth/sso` | 6 |
| `/config/:param` | 2 |
| `/config/public` | 1 |
| `/config/validation-report` | 1 |
| `/diagram/api-spec` | 1 |
| `/diagram/generate` | 1 |
| `/diagram/to-kubernetes` | 1 |
| `/diagram/to-schema` | 1 |
| `/diagram/to-terraform` | 1 |
| `/github/connect` | 1 |
| `/github/discover` | 1 |
| `/github/implement` | 1 |
| `/github/improve` | 1 |
| `/github/push` | 1 |
| `/github/repos` | 2 |
| `/integrations/email` | 2 |
| `/marketplace/install` | 1 |
| `/marketplace/search` | 1 |
| `/pair/review` | 1 |
| `/pair/solve` | 1 |
| `/payments/checkout` | 1 |
| `/payments/plans` | 1 |
| `/render-ticket` | 1 |
| `/repos` | 2 |
| `/repos/:param` | 2 |
| `/task/execute` | 1 |
| `/tools/image-to-code` | 1 |
| `/tools/image-to-component` | 1 |
| `/tools/image-to-palette` | 1 |
| `/tools/image-to-tree` | 1 |
| `/unified-memory/long-term` | 2 |
| `/v1/chat` | 1 |
| `/v1/models` | 1 |
| `/v1/orchestrator` | 1 |
| `/v1/pool` | 2 |
| `/v1/prompt` | 1 |
| `/v1/tasks` | 1 |
| `/video-to-code/process` | 1 |
| `/voice/process-audio` | 1 |

## Full route table

| Method | Path | Router file | Classification | Frontend consumers |
|---|---|---|---|---|
| GET | `/admin-api/agents` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/alerts/acknowledge` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/approvals` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/approvals` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/approvals/mcp` | `backend/api/routes/admin_dashboard/endpoints_approvals_mcp.py` | admin-only | NONE |
| POST | `/admin-api/approvals/mcp` | `backend/api/routes/admin_dashboard/endpoints_approvals_mcp.py` | admin-only | NONE |
| GET | `/admin-api/audit` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/backup` | `backend/api/routes/admin_dashboard/endpoints_backups.py` | admin-only | NONE |
| GET | `/admin-api/backups` | `backend/api/routes/admin_dashboard/endpoints_backups.py` | admin-only | NONE |
| POST | `/admin-api/backups` | `backend/api/routes/admin_dashboard/endpoints_backups.py` | admin-only | NONE |
| POST | `/admin-api/backups/:param/restore` | `backend/api/routes/admin_dashboard/endpoints_backups.py` | admin-only | NONE |
| GET | `/admin-api/budget-caps` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| POST | `/admin-api/budget-caps` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/ci-logs` | `backend/api/routes/admin_dashboard/endpoints_ci.py` | admin-only | NONE |
| POST | `/admin-api/ci-report` | `backend/api/routes/admin_dashboard/endpoints_ci.py` | admin-only | NONE |
| GET | `/admin-api/codebase/export` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/commandcenter/events` | `backend/api/routes/commandcenter/__init__.py` | admin-only | NONE |
| GET | `/admin-api/commandcenter/health` | `backend/api/routes/commandcenter/__init__.py` | admin-only | NONE |
| GET | `/admin-api/commandcenter/metrics` | `backend/api/routes/commandcenter/__init__.py` | admin-only | NONE |
| GET | `/admin-api/config` | `backend/api/routes/admin_dashboard/endpoints_config.py` | admin-only | NONE |
| POST | `/admin-api/config` | `backend/api/routes/admin_dashboard/endpoints_config.py` | admin-only | NONE |
| GET | `/admin-api/cost-caps` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| POST | `/admin-api/cost-caps` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/costs` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/costs/breakdown` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/customers` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| GET | `/admin-api/data-export` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/dependencies` | `backend/api/routes/health_aggregation.py` | admin-only | NONE |
| POST | `/admin-api/deploy` | `backend/api/routes/admin_dashboard/endpoints_deploy.py` | admin-only | NONE |
| GET | `/admin-api/deploy-gate` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/deploy-gate` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/emergency-deploy` | `backend/api/routes/admin_dashboard/endpoints_backups.py` | admin-only | NONE |
| GET | `/admin-api/evaluation/dimensions` | `backend/api/routes/admin_evaluation.py` | admin-only | NONE |
| POST | `/admin-api/evaluation/scores` | `backend/api/routes/admin_evaluation.py` | admin-only | NONE |
| GET | `/admin-api/evaluation/weights/:param` | `backend/api/routes/admin_evaluation.py` | admin-only | NONE |
| GET | `/admin-api/events` | `backend/api/routes/admin_dashboard/endpoints_events.py` | admin-only | NONE |
| GET | `/admin-api/feature-flags` | `backend/api/routes/admin_dashboard/endpoints_flags.py` | admin-only | NONE |
| POST | `/admin-api/feature-flags` | `backend/api/routes/admin_dashboard/endpoints_flags.py` | admin-only | NONE |
| PUT | `/admin-api/feature-flags/:param` | `backend/api/routes/admin_dashboard/endpoints_flags.py` | admin-only | NONE |
| POST | `/admin-api/gate/override` | `backend/api/routes/admin_dashboard/endpoints_gate.py` | admin-only | NONE |
| GET | `/admin-api/health-aggregation` | `backend/api/routes/health_aggregation.py` | admin-only | NONE |
| GET | `/admin-api/health-map` | `backend/api/routes/admin_dashboard/endpoints_health.py` | admin-only | NONE |
| POST | `/admin-api/impersonate` | `backend/api/routes/admin_dashboard/endpoints_impersonate.py` | admin-only | NONE |
| GET | `/admin-api/intelligence/insights` | `backend/api/routes/intelligence_insights.py` | admin-only | NONE |
| GET | `/admin-api/intelligence/manual-tasks` | `backend/api/routes/intelligence_insights.py` | admin-only | NONE |
| POST | `/admin-api/intelligence/manual-tasks/:param/complete` | `backend/api/routes/intelligence_insights.py` | admin-only | NONE |
| POST | `/admin-api/intelligence/memory/consolidate` | `backend/api/routes/intelligence_insights.py` | admin-only | NONE |
| POST | `/admin-api/intelligence/risk-proposals` | `backend/api/routes/intelligence_insights.py` | admin-only | NONE |
| GET | `/admin-api/knowledge` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/learning/run` | `backend/api/routes/admin_learning.py` | admin-only | NONE |
| GET | `/admin-api/learning/status` | `backend/api/routes/admin_learning.py` | admin-only | NONE |
| GET | `/admin-api/logs/stream` | `backend/api/routes/admin_dashboard/__init__.py` | admin-only | NONE |
| GET | `/admin-api/memory` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/metrics` | `backend/api/routes/admin_dashboard/endpoints_metrics.py` | admin-only | NONE |
| GET | `/admin-api/metrics/dashboard` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/model-router` | `backend/api/routes/admin_dashboard/endpoints_router_cfg.py` | admin-only | NONE |
| POST | `/admin-api/model-router/override` | `backend/api/routes/admin_dashboard/endpoints_router_cfg.py` | admin-only | NONE |
| GET | `/admin-api/permissions` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| GET | `/admin-api/ping-all` | `backend/api/routes/service_topology.py` | admin-only | NONE |
| GET | `/admin-api/ping-service` | `backend/api/routes/service_topology.py` | admin-only | NONE |
| POST | `/admin-api/policies/enforce` | `backend/api/routes/admin_policies.py` | admin-only | NONE |
| POST | `/admin-api/policies/evaluate` | `backend/api/routes/admin_policies.py` | admin-only | NONE |
| GET | `/admin-api/policies/rules` | `backend/api/routes/admin_policies.py` | admin-only | NONE |
| GET | `/admin-api/policies/rules/active` | `backend/api/routes/admin_policies.py` | admin-only | NONE |
| GET | `/admin-api/provider-readiness` | `backend/api/routes/health_aggregation.py` | admin-only | NONE |
| GET | `/admin-api/providers` | `backend/api/routes/admin_dashboard/endpoints_metrics.py` | admin-only | NONE |
| GET | `/admin-api/rate-limits` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/reports` | `backend/api/routes/admin_dashboard/endpoints_events.py` | admin-only | NONE |
| GET | `/admin-api/roles` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| GET | `/admin-api/routing/classify/:param` | `backend/api/routes/admin_routing.py` | admin-only | NONE |
| POST | `/admin-api/routing/enforce` | `backend/api/routes/admin_routing.py` | admin-only | NONE |
| POST | `/admin-api/routing/evaluate` | `backend/api/routes/admin_routing.py` | admin-only | NONE |
| GET | `/admin-api/routing/tiers` | `backend/api/routes/admin_routing.py` | admin-only | NONE |
| GET | `/admin-api/rules` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| POST | `/admin-api/rules` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/secrets-health` | `backend/api/routes/admin_dashboard/endpoints_secrets_health.py` | admin-only | NONE |
| GET | `/admin-api/security-scan` | `backend/api/routes/admin_dashboard/endpoints_security.py` | admin-only | NONE |
| POST | `/admin-api/security-scan` | `backend/api/routes/admin_dashboard/endpoints_security.py` | admin-only | NONE |
| GET | `/admin-api/security-scan/findings` | `backend/api/routes/admin_dashboard/endpoints_security.py` | admin-only | NONE |
| GET | `/admin-api/security/memory` | `backend/api/routes/admin_dashboard/endpoints_security_memory.py` | admin-only | NONE |
| GET | `/admin-api/security/tasks` | `backend/api/routes/admin_dashboard/endpoints_security_memory.py` | admin-only | NONE |
| GET | `/admin-api/service-categories` | `backend/api/routes/service_topology.py` | admin-only | NONE |
| GET | `/admin-api/service-health-map` | `backend/api/routes/health_aggregation.py` | admin-only | NONE |
| GET | `/admin-api/service-topology` | `backend/api/routes/service_topology.py` | admin-only | NONE |
| GET | `/admin-api/service-uptime` | `backend/api/routes/health_aggregation.py` | admin-only | NONE |
| GET | `/admin-api/sessions` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| GET | `/admin-api/settings` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| POST | `/admin-api/settings` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| GET | `/admin-api/skills` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/swarm` | `backend/api/routes/admin_dashboard/endpoints_command.py` | admin-only | NONE |
| GET | `/admin-api/tenant-limits` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| POST | `/admin-api/tenant-limits` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| DELETE | `/admin-api/tenant-limits/:param` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| GET | `/admin-api/tenant-limits/:param` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| PUT | `/admin-api/tenant-limits/:param` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| POST | `/admin-api/tenant-limits/:param/reset` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| POST | `/admin-api/tenant-limits/:param/reset-usage` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| GET | `/admin-api/tenant-limits/:param/usage` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| GET | `/admin-api/tenant-limits/tiers/defaults` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| POST | `/admin-api/tenants/:param/reset` | `backend/api/routes/admin_dashboard/endpoints_users.py` | admin-only | NONE |
| POST | `/admin-api/tenants/:param/reset` | `backend/api/routes/tenant_admin.py` | admin-only | NONE |
| POST | `/admin-api/test-service` | `backend/api/routes/health_aggregation.py` | admin-only | NONE |
| GET | `/admin-api/users` | `backend/api/routes/admin_dashboard/endpoints_users.py` | admin-only | NONE |
| POST | `/admin-api/users` | `backend/api/routes/admin_dashboard/endpoints_users.py` | admin-only | NONE |
| DELETE | `/admin-api/users/:param` | `backend/api/routes/admin_dashboard/endpoints_users.py` | admin-only | NONE |
| POST | `/admin-api/users/impersonate/:param` | `backend/api/routes/admin_dashboard/endpoints_impersonate.py` | admin-only | NONE |
| GET | `/admin-api/workspaces` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| POST | `/admin-api/workspaces` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| DELETE | `/admin-api/workspaces/:param` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| PUT | `/admin-api/workspaces/:param` | `backend/api/routes/admin_dashboard/endpoints_crud.py` | admin-only | NONE |
| POST | `/admin-api/workspaces/bind-target` | `backend/api/routes/workspaces_route.py` | admin-only | NONE |
| GET | `/admin-api/workspaces/targets` | `backend/api/routes/workspaces_route.py` | admin-only | NONE |
| GET | `/admin/cloud-distribution` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| POST | `/admin/free-tier-override/:param` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| POST | `/admin/free-tier-pause/:param` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/admin/free-tier-status` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/admin/free-tier-status/:param` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/admin/rules` | `backend/api/routes/admin_routes.py` | deprecated | NONE |
| POST | `/admin/rules` | `backend/api/routes/admin_routes.py` | deprecated | NONE |
| GET | `/admin/token-budget-stats` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| DELETE | `/admin/trusted-browsers` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/admin/trusted-browsers` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| DELETE | `/admin/trusted-browsers/:param` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| POST | `/agent/plan` | `backend/tools/self_planner.py` | api-only | NONE |
| POST | `/api/admin/actions/:param` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/ai/assign` | `backend/api/routes/ai_assignment.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/ai/assignment` | `backend/api/routes/ai_assignment.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/ai/overview` | `backend/api/routes/ai_assignment.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/ai/providers` | `backend/api/routes/ai_assignment.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/ai/surfaces` | `backend/api/routes/ai_assignment.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/ai/test/:param` | `backend/api/routes/ai_assignment.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/alerts` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/alerts` | `backend/api/routes/admin.py` | deprecated | `frontend/src/utils/api.ts` |
| POST | `/api/admin/alerts/:param/resolve` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/automation/executions` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/automation/executions/:param` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/automation/workflows` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/cloud-mesh/defcon` | `backend/api/routes/cloud_mesh.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/cloud-mesh/kill-switch` | `backend/api/routes/cloud_mesh.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/cloud-mesh/purge-cache` | `backend/api/routes/cloud_mesh.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/cloud-mesh/rotate-keys` | `backend/api/routes/cloud_mesh.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/cloud-mesh/smell-check` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/configs/refresh` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/decisions` | `backend/api/routes/admin_decisions.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/decisions/:param` | `backend/api/routes/admin_decisions.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/execution-policies` | `backend/api/routes/execution_policies.py` | admin-only | `frontend/src/components/dashboard/GuardrailsPage.tsx` |
| PUT | `/api/admin/execution-policies/:param` | `backend/api/routes/execution_policies.py` | admin-only | `frontend/src/components/dashboard/GuardrailsPage.tsx` |
| POST | `/api/admin/firebase-login` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/services/authService.test.ts`, `frontend/src/services/authService.ts`, `frontend/src/utils/api.test.ts` |
| POST | `/api/admin/firebase-totp-recover` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/services/authService.ts` |
| POST | `/api/admin/firebase-totp-setup` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/services/authService.test.ts`, `frontend/src/services/authService.ts` |
| POST | `/api/admin/firebase-totp-verify` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/services/authService.test.ts`, `frontend/src/services/authService.ts` |
| GET | `/api/admin/fixes` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/fixes` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/fixes/:param/approve` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/fixes/:param/reject` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/fixes/apply` | `backend/api/routes/admin.py` | admin-only | `frontend/src/components/admin/OneClickPatch.tsx` |
| GET | `/api/admin/infrastructure/auto-scaling/status` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/infrastructure/cost/forecast` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/infrastructure/cost/report` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/infrastructure/disaster-recovery/backup` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/infrastructure/disaster-recovery/backups` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/infrastructure/disaster-recovery/schedule` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/infrastructure/performance/summary` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/infrastructure/status` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/integrations` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/integrations/:param/health` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/librarian/process` | `backend/api/routes/admin_librarian.py` | admin-only | `frontend/src/components/admin/EnhancedSkillMarketplace.tsx`, `frontend/src/components/admin/LibrarianQueue.tsx` |
| GET | `/api/admin/librarian/queue` | `backend/api/routes/admin_librarian.py` | admin-only | `frontend/src/components/admin/LibrarianQueue.tsx` |
| GET | `/api/admin/llm/providers` | `backend/api/routes/admin_llm.py` | admin-only | `frontend/src/components/dashboard/LlmGatewayPage.tsx` |
| GET | `/api/admin/llm/router` | `backend/api/routes/admin_llm.py` | admin-only | `frontend/src/components/dashboard/LlmGatewayPage.tsx` |
| POST | `/api/admin/llm/router/override` | `backend/api/routes/admin_llm.py` | admin-only | `frontend/src/components/dashboard/LlmGatewayPage.tsx` |
| GET | `/api/admin/llm/rules` | `backend/api/routes/admin_llm.py` | admin-only | `frontend/src/components/dashboard/LlmGatewayPage.tsx` |
| POST | `/api/admin/llm/rules` | `backend/api/routes/admin_llm.py` | admin-only | `frontend/src/components/dashboard/LlmGatewayPage.tsx` |
| GET | `/api/admin/metrics` | `backend/api/routes/metrics.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/metrics/dashboard` | `backend/api/routes/metrics.py` | admin-only | `frontend/src/store/useStore.ts` |
| GET | `/api/admin/metrics/realtime` | `backend/api/routes/metrics.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/metrics/trigger-nightly-chaos` | `backend/api/routes/metrics.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/model-branding` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/render/accounts/:param/override` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/render/accounts/:param/recheck` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/render/preflight` | `backend/api/routes/admin.py` | admin-only | `frontend/src/components/admin/RenderPreflightWidget.tsx` |
| GET | `/api/admin/rules` | `backend/api/routes/admin.py` | admin-only | `frontend/src/hooks/useAdminApi.ts`, `frontend/src/pages/admin/AdminShell.tsx` |
| POST | `/api/admin/rules` | `backend/api/routes/admin.py` | admin-only | `frontend/src/hooks/useAdminApi.ts`, `frontend/src/pages/admin/AdminShell.tsx` |
| GET | `/api/admin/selector-healing` | `backend/api/routes/selector_healing.py` | admin-only | `frontend/src/components/dashboard/HealingLogPanel.tsx` |
| POST | `/api/admin/selector-healing/:param/decision` | `backend/api/routes/selector_healing.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/selector-healing/selectors/audit` | `backend/api/routes/selector_healing.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/site-actions` | `backend/api/routes/browser_action_registry.py` | admin-only | `frontend/src/components/dashboard/SiteActionsPage.tsx` |
| POST | `/api/admin/site-actions` | `backend/api/routes/browser_action_registry.py` | admin-only | `frontend/src/components/dashboard/SiteActionsPage.tsx` |
| DELETE | `/api/admin/site-actions/:param` | `backend/api/routes/browser_action_registry.py` | admin-only | `frontend/src/components/dashboard/SiteActionsPage.tsx` |
| PUT | `/api/admin/site-actions/:param` | `backend/api/routes/browser_action_registry.py` | admin-only | `frontend/src/components/dashboard/SiteActionsPage.tsx` |
| POST | `/api/admin/site-actions/test` | `backend/api/routes/browser_action_registry.py` | admin-only | `frontend/src/components/dashboard/SiteActionsPage.tsx` |
| GET | `/api/admin/tenant-limits` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/utils/api.ts` |
| PUT | `/api/admin/tenant-limits/:param` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/admin/traffic/kill-switch` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/admin/traffic/live` | `backend/api/routes/traffic_monitor.py` | admin-only | `frontend/src/commandcenter/data/hooks.ts` |
| POST | `/api/admin/verify-otp` | `backend/api/routes/admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/agents` | `backend/api/routes/agents.py` | user-facing | `frontend/src/services/agentService.test.ts`, `frontend/src/services/agentService.ts`, `frontend/src/services/apiClient.test.ts` |
| GET | `/api/agents/:param/status` | `backend/api/routes/agents.py` | user-facing | `frontend/src/services/agentService.test.ts`, `frontend/src/services/agentService.ts`, `frontend/src/services/apiClient.test.ts` |
| POST | `/api/agents/research/cite` | `backend/api/routes/agents.py` | user-facing | `frontend/src/services/agentService.test.ts`, `frontend/src/services/agentService.ts`, `frontend/src/services/apiClient.test.ts` |
| POST | `/api/agents/research/search` | `backend/api/routes/agents.py` | user-facing | `frontend/src/services/agentService.test.ts`, `frontend/src/services/agentService.ts`, `frontend/src/services/apiClient.test.ts` |
| POST | `/api/agents/research/summarize` | `backend/api/routes/agents.py` | user-facing | `frontend/src/services/agentService.test.ts`, `frontend/src/services/agentService.ts`, `frontend/src/services/apiClient.test.ts` |
| GET | `/api/api-keys` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| DELETE | `/api/api-keys/:param` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| GET | `/api/api-keys/:param` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| GET | `/api/api-keys/:param/admin/quota-alert` | `backend/api/routes/api_keys.py` | admin-only | `frontend/src/components/dashboard/SecretsPage.tsx` |
| POST | `/api/api-keys/:param/revoke` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| POST | `/api/api-keys/:param/rotate` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| GET | `/api/api-keys/:param/stats` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| GET | `/api/api-keys/:param/usage` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| POST | `/api/api-keys/:param/usage` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| POST | `/api/api-keys/admin/bulk-delete` | `backend/api/routes/api_keys.py` | admin-only | `frontend/src/components/dashboard/SecretsPage.tsx` |
| GET | `/api/api-keys/all` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| POST | `/api/api-keys/create` | `backend/api/routes/api_keys.py` | user-facing | `frontend/src/components/dashboard/SecretsPage.tsx` |
| POST | `/api/artifacts` | `backend/api/routes/artifacts.py` | api-only | NONE |
| DELETE | `/api/artifacts/:param` | `backend/api/routes/artifacts.py` | api-only | NONE |
| GET | `/api/artifacts/:param` | `backend/api/routes/artifacts.py` | api-only | NONE |
| PATCH | `/api/artifacts/:param` | `backend/api/routes/artifacts.py` | api-only | NONE |
| GET | `/api/artifacts/:param/preview` | `backend/api/routes/artifacts.py` | api-only | NONE |
| GET | `/api/artifacts/conversation/:param` | `backend/api/routes/artifacts.py` | api-only | NONE |
| POST | `/api/billing/add-funds` | `backend/api/routes/billing_api.py` | api-only | NONE |
| GET | `/api/billing/analytics` | `backend/api/routes/billing_api.py` | user-facing | `frontend/src/pages/user/CostDashboard.tsx` |
| GET | `/api/billing/budget-check` | `backend/api/routes/billing_api.py` | api-only | NONE |
| POST | `/api/billing/checkout` | `backend/api/routes/billing_api.py` | user-facing | `frontend/src/pages/BillingPage.test.tsx`, `frontend/src/pages/BillingPage.tsx` |
| GET | `/api/billing/history` | `backend/api/routes/billing_api.py` | api-only | NONE |
| GET | `/api/billing/plans` | `backend/api/routes/billing_api.py` | user-facing | `frontend/src/pages/BillingPage.test.tsx`, `frontend/src/pages/BillingPage.tsx` |
| GET | `/api/billing/wallet` | `backend/api/routes/billing_api.py` | user-facing | `frontend/src/pages/BillingPage.test.tsx`, `frontend/src/pages/BillingPage.tsx` |
| POST | `/api/billing/webhook/sslcommerz` | `backend/api/routes/billing_api.py` | internal | NONE |
| POST | `/api/billing/webhook/stripe` | `backend/api/routes/billing_api.py` | internal | NONE |
| GET | `/api/browser/activity/recent` | `backend/api/routes/browser/_legacy_status.py` | api-only | NONE |
| PUT | `/api/browser/admin/policy` | `backend/api/routes/browser/_policy.py` | admin-only | NONE |
| POST | `/api/browser/ai-action` | `backend/api/routes/browser/_crown_jewel.py` | user-facing | `frontend/src/components/admin/admin-browser/useBrowserActions.ts` |
| POST | `/api/browser/automation/actions` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.test.ts`, `frontend/src/services/browserService.ts` |
| POST | `/api/browser/automation/pause` | `backend/api/routes/browser/_automation.py` | api-only | NONE |
| POST | `/api/browser/automation/resume` | `backend/api/routes/browser/_automation.py` | api-only | NONE |
| GET | `/api/browser/automation/saved-sessions` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.ts` |
| POST | `/api/browser/automation/saved-sessions` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.ts` |
| DELETE | `/api/browser/automation/saved-sessions/:param` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.ts` |
| GET | `/api/browser/automation/sessions` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.test.ts`, `frontend/src/services/browserService.ts` |
| POST | `/api/browser/automation/sessions` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.test.ts`, `frontend/src/services/browserService.ts` |
| DELETE | `/api/browser/automation/sessions/:param` | `backend/api/routes/browser/_automation.py` | user-facing | `frontend/src/services/browserService.ts` |
| POST | `/api/browser/autonomous/run` | `backend/api/routes/browser/_cognitive.py` | api-only | NONE |
| POST | `/api/browser/browse` | `backend/api/routes/browser/_scraping.py` | api-only | NONE |
| POST | `/api/browser/browse-session` | `backend/api/routes/browser/_crown_jewel.py` | user-facing | `frontend/src/components/admin/admin-browser/CrownJewelBrowser.tsx` |
| GET | `/api/browser/credentials` | `backend/api/routes/browser/_credentials.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| POST | `/api/browser/credentials` | `backend/api/routes/browser/_credentials.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| DELETE | `/api/browser/credentials/:param` | `backend/api/routes/browser/_credentials.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| DELETE | `/api/browser/credentials/:param` | `backend/api/routes/browser/_credentials.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| POST | `/api/browser/credentials/:param/revoke` | `backend/api/routes/browser/_credentials.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| POST | `/api/browser/credentials/:param/use` | `backend/api/routes/browser/_credentials.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| POST | `/api/browser/extract` | `backend/api/routes/browser/_scraping.py` | api-only | NONE |
| POST | `/api/browser/findings` | `backend/api/routes/browser/_tasks.py` | api-only | NONE |
| GET | `/api/browser/health` | `backend/api/routes/browser/_health.py` | internal | NONE |
| GET | `/api/browser/policy` | `backend/api/routes/browser/_policy.py` | user-facing | `frontend/src/services/policyService.ts` |
| PUT | `/api/browser/policy` | `backend/api/routes/browser/_policy.py` | user-facing | `frontend/src/services/policyService.ts` |
| GET | `/api/browser/render` | `backend/api/routes/browser/_render_proxy.py` | api-only | NONE |
| POST | `/api/browser/scrape` | `backend/api/routes/browser/_scraping.py` | api-only | NONE |
| POST | `/api/browser/screenshot` | `backend/api/routes/browser/_crown_jewel.py` | user-facing | `frontend/src/components/admin/admin-browser/useBrowserActions.ts` |
| POST | `/api/browser/screenshots` | `backend/api/routes/browser/_crown_jewel.py` | user-facing | `frontend/src/components/admin/admin-browser/useBrowserActions.ts` |
| POST | `/api/browser/security-scan` | `backend/api/routes/browser/_crown_jewel.py` | user-facing | `frontend/src/components/admin/admin-browser/useBrowserActions.ts` |
| POST | `/api/browser/semantic-click` | `backend/api/routes/browser/_cognitive.py` | api-only | NONE |
| GET | `/api/browser/sessions` | `backend/api/routes/browser/_session_store.py` | user-facing | `frontend/src/App.test.tsx`, `frontend/src/components/dashboard/sessionStore.ts` |
| POST | `/api/browser/sessions` | `backend/api/routes/browser/_session_store.py` | user-facing | `frontend/src/App.test.tsx`, `frontend/src/components/dashboard/sessionStore.ts` |
| DELETE | `/api/browser/sessions/:param` | `backend/api/routes/browser/_session_store.py` | user-facing | `frontend/src/components/dashboard/sessionStore.ts` |
| GET | `/api/browser/sessions/:param` | `backend/api/routes/browser/_session_store.py` | user-facing | `frontend/src/components/dashboard/sessionStore.ts` |
| PUT | `/api/browser/sessions/:param` | `backend/api/routes/browser/_session_store.py` | user-facing | `frontend/src/components/dashboard/sessionStore.ts` |
| POST | `/api/browser/simulate-activity` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/smart-click` | `backend/api/routes/browser/_cognitive.py` | api-only | NONE |
| GET | `/api/browser/surf/accessibility` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/surf/click` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/surf/click-at` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/surf/fill` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/surf/navigate` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/surf/pause-manual` | `backend/api/routes/browser/_surf_controls.py` | api-only | NONE |
| GET | `/api/browser/surf/paused-state` | `backend/api/routes/browser/_surf_controls.py` | api-only | NONE |
| POST | `/api/browser/surf/resume` | `backend/api/routes/browser/_surf_controls.py` | api-only | NONE |
| GET | `/api/browser/surf/screenshot` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| POST | `/api/browser/surf/skip-auth` | `backend/api/routes/browser/_surf_controls.py` | api-only | NONE |
| POST | `/api/browser/surf/start` | `backend/api/routes/browser/_legacy_status.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| GET | `/api/browser/surf/status` | `backend/api/routes/browser/_legacy_status.py` | user-facing | `frontend/src/components/dashboard/VaultPage.tsx` |
| POST | `/api/browser/surf/stop` | `backend/api/routes/browser/_legacy_status.py` | api-only | NONE |
| POST | `/api/browser/surf/type-key` | `backend/api/routes/browser/_surf_actions.py` | api-only | NONE |
| GET | `/api/browser/system-learning` | `backend/api/routes/browser/_learning.py` | api-only | NONE |
| POST | `/api/browser/system-learning/toggle` | `backend/api/routes/browser/_learning.py` | api-only | NONE |
| GET | `/api/browser/tasks` | `backend/api/routes/browser/_policy.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| POST | `/api/browser/tasks` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| DELETE | `/api/browser/tasks/:param` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| POST | `/api/browser/tasks/:param/circuit-open` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| POST | `/api/browser/tasks/:param/complete` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| POST | `/api/browser/tasks/:param/fail` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| GET | `/api/browser/tasks/:param/findings` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| POST | `/api/browser/tasks/:param/step` | `backend/api/routes/browser/_crown_jewel.py` | user-facing | `frontend/src/components/dashboard/AutomationQueuePage.tsx` |
| POST | `/api/browser/tasks/preview` | `backend/api/routes/browser/_tasks.py` | user-facing | `frontend/src/components/customer/TaskAutomationCard.tsx` |
| DELETE | `/api/browser/urls/:param` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| POST | `/api/browser/urls/allowAll` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| GET | `/api/browser/urls/allowed` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| POST | `/api/browser/urls/allowed` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| GET | `/api/browser/urls/denied` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| POST | `/api/browser/urls/denied` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| GET | `/api/browser/urls/requests` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| POST | `/api/browser/urls/requests/:param/decision` | `backend/api/routes/browser/_url_permissions.py` | api-only | NONE |
| POST | `/api/byoc/credentials` | `backend/api/routes/byoc_api.py` | api-only | NONE |
| POST | `/api/byoc/deploy` | `backend/api/routes/byoc_api.py` | api-only | NONE |
| GET | `/api/byoc/status/:param` | `backend/api/routes/byoc_api.py` | api-only | NONE |
| GET | `/api/chat/capabilities` | `backend/api/routes/chat.py` | api-only | NONE |
| POST | `/api/chat/completion` | `backend/api/routes/task.py` | api-only | NONE |
| POST | `/api/chat/export` | `backend/api/routes/chat_export.py` | user-facing | `frontend/src/components/export/ExportMenu.tsx` |
| GET | `/api/chat/export/formats` | `backend/api/routes/chat_export.py` | user-facing | `frontend/src/components/export/ExportMenu.tsx` |
| POST | `/api/chat/get_completion` | `backend/api/routes/chat.py` | api-only | NONE |
| GET | `/api/chat/learning/stats` | `backend/api/routes/chat.py` | api-only | NONE |
| POST | `/api/chat/orchestrate` | `backend/api/routes/chat.py` | user-facing | `frontend/src/pages/PublicPages.tsx` |
| POST | `/api/chat/prompt-action` | `backend/api/routes/task.py` | user-facing | `frontend/src/components/admin/InteractiveChatTab.tsx`, `frontend/src/services/chatService.ts` |
| GET | `/api/chat/search` | `backend/api/routes/chat_search.py` | api-only | NONE |
| POST | `/api/chat/stream` | `backend/api/routes/stream_chat_sse.py` | user-facing | `frontend/src/components/admin/InteractiveChatTab.tsx`, `frontend/src/pages/admin/AdminShell.tsx` |
| POST | `/api/chat/stream` | `backend/api/routes/task.py` | user-facing | `frontend/src/components/admin/InteractiveChatTab.tsx`, `frontend/src/pages/admin/AdminShell.tsx` |
| POST | `/api/chat/stream_chat` | `backend/api/routes/chat.py` | api-only | NONE |
| GET | `/api/chat/tasks/:param` | `backend/api/routes/chat.py` | api-only | NONE |
| GET | `/api/chat/upload` | `backend/api/routes/chat_upload.py` | user-facing | `frontend/src/pages/FilesPage.tsx`, `frontend/src/services/fileService.test.ts`, `frontend/src/services/fileService.ts` |
| POST | `/api/chat/upload` | `backend/api/routes/chat_upload.py` | user-facing | `frontend/src/pages/FilesPage.tsx`, `frontend/src/services/fileService.test.ts`, `frontend/src/services/fileService.ts` |
| DELETE | `/api/chat/upload/:param` | `backend/api/routes/chat_upload.py` | user-facing | `frontend/src/services/fileService.ts` |
| GET | `/api/chat/upload/:param` | `backend/api/routes/chat_upload.py` | user-facing | `frontend/src/services/fileService.ts` |
| DELETE | `/api/ci/cache` | `backend/api/routes/ci_dashboard_api.py` | api-only | NONE |
| GET | `/api/ci/health` | `backend/api/routes/ci_dashboard_api.py` | internal | NONE |
| GET | `/api/ci/history` | `backend/api/routes/ci_dashboard_api.py` | api-only | NONE |
| GET | `/api/ci/latest-summary` | `backend/api/routes/ci_dashboard_api.py` | user-facing | `frontend/src/components/admin/ci/CIDashboard.tsx` |
| GET | `/api/ci/stats/overview` | `backend/api/routes/ci_dashboard_api.py` | api-only | NONE |
| GET | `/api/ci/summary/:param` | `backend/api/routes/ci_dashboard_api.py` | api-only | NONE |
| GET | `/api/ci/trends` | `backend/api/routes/ci_dashboard_api.py` | api-only | NONE |
| POST | `/api/ci/webhook` | `backend/api/routes/ci_dashboard_api.py` | internal | NONE |
| POST | `/api/ci/webhook` | `backend/api/routes/ci_webhooks.py` | internal | NONE |
| POST | `/api/codeflow/analyze` | `backend/api/routes/code_dependency_graph.py` | api-only | NONE |
| GET | `/api/commands` | `backend/api/routes/slash_commands.py` | user-facing | `frontend/src/components/commands/SlashCommandMenu.tsx` |
| POST | `/api/commands/execute` | `backend/api/routes/slash_commands.py` | user-facing | `frontend/src/components/commands/SlashCommandMenu.tsx` |
| POST | `/api/comment-ai/handle-comment` | `backend/tools/comment_thread_ai.py` | api-only | NONE |
| GET | `/api/comment-ai/stale-prs/:param/:param` | `backend/tools/comment_thread_ai.py` | api-only | NONE |
| POST | `/api/comment-ai/summarize` | `backend/tools/comment_thread_ai.py` | api-only | NONE |
| POST | `/api/comment-ai/webhook` | `backend/tools/comment_thread_ai.py` | internal | NONE |
| GET | `/api/config/public` | `backend/api/routes/public_config.py` | user-facing | `frontend/src/components/core/GlobalConfigInitializer.tsx` |
| GET | `/api/config/public/branding` | `backend/api/routes/public_config.py` | user-facing | `frontend/src/lib/modelBranding.ts` |
| POST | `/api/conversations/:param/branch` | `backend/api/routes/branch_conversations.py` | api-only | NONE |
| GET | `/api/conversations/:param/branches` | `backend/api/routes/branch_conversations.py` | api-only | NONE |
| PATCH | `/api/conversations/:param/merge` | `backend/api/routes/branch_conversations.py` | api-only | NONE |
| GET | `/api/conversations/tree` | `backend/api/routes/branch_conversations.py` | api-only | NONE |
| GET | `/api/dashboard/stream` | `backend/api/routes/events.py` | api-only | NONE |
| POST | `/api/feedback/ingest` | `backend/api/routes/feedback.py` | api-only | NONE |
| GET | `/api/files/:param` | `backend/api/routes/files.py` | api-only | NONE |
| PUT | `/api/files/:param` | `backend/api/routes/files.py` | api-only | NONE |
| GET | `/api/health-aggregation` | `backend/api/routes/admin_routes.py` | admin-only | `frontend/src/components/auth/ServiceHealthBar.tsx`, `frontend/src/utils/apiInterceptor.ts` |
| POST | `/api/knowledge/ask` | `backend/api/routes/knowledge.py` | api-only | NONE |
| POST | `/api/knowledge/ask-scribe` | `backend/api/routes/knowledge.py` | api-only | NONE |
| POST | `/api/knowledge/failure` | `backend/api/routes/knowledge.py` | api-only | NONE |
| POST | `/api/knowledge/feedback` | `backend/api/routes/knowledge.py` | api-only | NONE |
| POST | `/api/knowledge/learn` | `backend/api/routes/knowledge.py` | api-only | NONE |
| POST | `/api/knowledge/search` | `backend/api/routes/knowledge.py` | api-only | NONE |
| POST | `/api/knowledge/seed` | `backend/api/routes/knowledge.py` | user-facing | `frontend/src/components/dashboard/KnowledgePage.test.tsx`, `frontend/src/components/dashboard/KnowledgePage.tsx` |
| GET | `/api/knowledge/stats` | `backend/api/routes/knowledge.py` | api-only | NONE |
| GET | `/api/living-brain/metrics` | `backend/api/routes/living_brain.py` | admin-only | NONE |
| POST | `/api/living-brain/query` | `backend/api/routes/living_brain.py` | admin-only | NONE |
| GET | `/api/living-brain/status` | `backend/api/routes/living_brain.py` | admin-only | NONE |
| GET | `/api/living-brain/timeline` | `backend/api/routes/living_brain.py` | admin-only | NONE |
| POST | `/api/memory/checkpoint` | `backend/api/routes/memory.py` | api-only | NONE |
| DELETE | `/api/memory/checkpoint/:param` | `backend/api/routes/memory.py` | user-facing | `frontend/src/hooks/useAdminApi.ts` |
| GET | `/api/memory/checkpoint/:param` | `backend/api/routes/memory.py` | user-facing | `frontend/src/hooks/useAdminApi.ts` |
| GET | `/api/memory/checkpoints` | `backend/api/routes/memory.py` | user-facing | `frontend/src/hooks/useAdminApi.ts` |
| POST | `/api/memory/chunk` | `backend/api/routes/memory.py` | api-only | NONE |
| POST | `/api/memory/context` | `backend/api/routes/memory.py` | api-only | NONE |
| DELETE | `/api/memory/recall` | `backend/api/routes/memory.py` | api-only | NONE |
| GET | `/api/memory/recall` | `backend/api/routes/memory.py` | api-only | NONE |
| POST | `/api/memory/recall` | `backend/api/routes/memory.py` | api-only | NONE |
| POST | `/api/memory/save` | `backend/api/routes/memory.py` | api-only | NONE |
| POST | `/api/memory/session` | `backend/api/routes/memory.py` | api-only | NONE |
| GET | `/api/merge-learning/reports` | `backend/api/routes/merge_learning.py` | api-only | NONE |
| POST | `/api/merge-learning/webhook` | `backend/api/routes/merge_learning.py` | internal | NONE |
| POST | `/api/mobile/bff/orchestrate` | `backend/api/routes/mobile_bff.py` | api-only | NONE |
| GET | `/api/preferences` | `backend/api/routes/preferences.py` | user-facing | `frontend/src/contexts/ThemeProvider.tsx`, `frontend/src/i18n/I18nProvider.tsx`, `frontend/src/pages/ProfilePage.tsx` (+1 more) |
| POST | `/api/preferences` | `backend/api/routes/preferences.py` | user-facing | `frontend/src/contexts/ThemeProvider.tsx`, `frontend/src/i18n/I18nProvider.tsx`, `frontend/src/pages/ProfilePage.tsx` (+1 more) |
| GET | `/api/preferences/:param/stream` | `backend/api/routes/preferences.py` | user-facing | `frontend/src/contexts/ThemeProvider.tsx`, `frontend/src/i18n/I18nProvider.tsx`, `frontend/src/pages/ProfilePage.tsx` (+1 more) |
| GET | `/api/preferences/memory` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| POST | `/api/preferences/memory` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| DELETE | `/api/preferences/memory/:param` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| PUT | `/api/preferences/memory/:param` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| POST | `/api/preferences/memory/search` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| GET | `/api/preferences/memory/stats` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| POST | `/api/preferences/memory/sync` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| DELETE | `/api/preferences/memory/user-data` | `backend/api/routes/global_memory.py` | user-facing | `frontend/src/components/memory/MemoryPanel.tsx` |
| GET | `/api/prompt-templates` | `backend/api/routes/prompt_templates.py` | user-facing | `frontend/src/components/templates/PromptTemplateLibrary.tsx` |
| POST | `/api/prompt-templates` | `backend/api/routes/prompt_templates.py` | user-facing | `frontend/src/components/templates/PromptTemplateLibrary.tsx` |
| DELETE | `/api/prompt-templates/:param` | `backend/api/routes/prompt_templates.py` | user-facing | `frontend/src/components/templates/PromptTemplateLibrary.tsx` |
| GET | `/api/prompt-templates/:param` | `backend/api/routes/prompt_templates.py` | user-facing | `frontend/src/components/templates/PromptTemplateLibrary.tsx` |
| PUT | `/api/prompt-templates/:param` | `backend/api/routes/prompt_templates.py` | user-facing | `frontend/src/components/templates/PromptTemplateLibrary.tsx` |
| POST | `/api/prompt-templates/:param/use` | `backend/api/routes/prompt_templates.py` | user-facing | `frontend/src/components/templates/PromptTemplateLibrary.tsx` |
| POST | `/api/reasoning/think` | `backend/api/routes/reasoning.py` | api-only | NONE |
| POST | `/api/reasoning/think/stream` | `backend/api/routes/reasoning.py` | api-only | NONE |
| GET | `/api/research/:param` | `backend/api/routes/deep_research.py` | api-only | NONE |
| POST | `/api/research/deep` | `backend/api/routes/deep_research.py` | api-only | NONE |
| POST | `/api/research/deep/stream` | `backend/api/routes/deep_research.py` | user-facing | `frontend/src/components/research/DeepResearchPanel.tsx` |
| GET | `/api/research/history` | `backend/api/routes/deep_research.py` | user-facing | `frontend/src/components/research/DeepResearchPanel.tsx` |
| GET | `/api/schedule` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| POST | `/api/schedule` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| DELETE | `/api/schedule/:param` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| GET | `/api/schedule/:param` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| PUT | `/api/schedule/:param` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| POST | `/api/schedule/:param/run` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| POST | `/api/schedule/:param/toggle` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| GET | `/api/schedule/history` | `backend/api/routes/scheduled_tasks.py` | user-facing | `frontend/src/components/schedule/ScheduledTasksPanel.tsx` |
| POST | `/api/session/:param/integrations/:param` | `backend/api/routes/dock_integrations.py` | api-only | NONE |
| GET | `/api/session/:param/stream` | `backend/api/routes/session_stream.py` | api-only | NONE |
| DELETE | `/api/share/:param` | `backend/api/routes/share.py` | user-facing | `frontend/src/pages/SharedConversationPage.tsx` |
| GET | `/api/share/:param` | `backend/api/routes/share.py` | user-facing | `frontend/src/pages/SharedConversationPage.tsx` |
| POST | `/api/share/generate` | `backend/api/routes/share.py` | user-facing | `frontend/src/components/share/ShareDialog.tsx` |
| GET | `/api/share/list` | `backend/api/routes/share.py` | user-facing | `frontend/src/pages/SharedConversationPage.tsx` |
| POST | `/api/simulator/admin/set-quota/:param` | `backend/api/routes/simulator_admin.py` | admin-only | NONE |
| GET | `/api/simulator/admin/usage` | `backend/api/routes/simulator_admin.py` | admin-only | NONE |
| GET | `/api/simulator/devices` | `backend/api/routes/simulator.py` | api-only | NONE |
| POST | `/api/simulator/install` | `backend/api/routes/simulator.py` | api-only | NONE |
| DELETE | `/api/simulator/install/:param` | `backend/api/routes/simulator.py` | api-only | NONE |
| GET | `/api/simulator/installed` | `backend/api/routes/simulator.py` | api-only | NONE |
| GET | `/api/simulator/profile` | `backend/api/routes/simulator.py` | api-only | NONE |
| POST | `/api/simulator/profile` | `backend/api/routes/simulator.py` | api-only | NONE |
| POST | `/api/simulator/session/start` | `backend/api/routes/simulator.py` | api-only | NONE |
| GET | `/api/simulator/session/status` | `backend/api/routes/simulator.py` | api-only | NONE |
| POST | `/api/simulator/session/stop` | `backend/api/routes/simulator.py` | api-only | NONE |
| GET | `/api/skills/catalog` | `backend/api/routes/skills.py` | user-facing | `frontend/src/services/skillsService.test.ts`, `frontend/src/services/skillsService.ts` |
| POST | `/api/skills/deploy-blueprint` | `backend/api/routes/skills.py` | user-facing | `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` |
| POST | `/api/skills/install` | `backend/api/routes/skills.py` | api-only | NONE |
| GET | `/api/skills/search` | `backend/api/routes/skills.py` | user-facing | `frontend/src/components/admin/EnhancedSkillMarketplace.tsx`, `frontend/src/hooks/useAdminApi.ts` |
| POST | `/api/skills/search` | `backend/api/routes/skills.py` | user-facing | `frontend/src/components/admin/EnhancedSkillMarketplace.tsx`, `frontend/src/hooks/useAdminApi.ts` |
| DELETE | `/api/skills/uninstall` | `backend/api/routes/skills.py` | api-only | NONE |
| POST | `/api/stream/chat` | `backend/api/routes/stream.py` | user-facing | `frontend/src/pages/PublicPages.tsx`, `frontend/src/services/chatService.ts` |
| POST | `/api/style/generate` | `backend/tools/learning/style_learner.py` | api-only | NONE |
| POST | `/api/style/learn` | `backend/tools/learning/style_learner.py` | api-only | NONE |
| GET | `/api/style/prompt` | `backend/tools/learning/style_learner.py` | api-only | NONE |
| GET | `/api/task/:param` | `backend/api/routes/async_task_router.py` | user-facing | `frontend/src/services/apiClient.ts` |
| GET | `/api/task/_stats` | `backend/api/routes/async_task_router.py` | user-facing | `frontend/src/services/apiClient.ts` |
| POST | `/api/task/execute` | `backend/api/routes/task.py` | user-facing | `frontend/src/services/chatService.test.ts`, `frontend/src/services/chatService.ts` |
| GET | `/api/task/stream` | `backend/api/routes/task.py` | user-facing | `frontend/src/services/apiClient.ts` |
| POST | `/api/telemetry/frontend-error` | `backend/api/v1/telemetry.py` | api-only | NONE |
| GET | `/api/telemetry/health` | `backend/api/v1/telemetry.py` | internal | NONE |
| GET | `/api/telemetry/metrics/ai` | `backend/api/v1/telemetry.py` | internal | NONE |
| GET | `/api/telemetry/metrics/cache` | `backend/api/v1/telemetry.py` | internal | NONE |
| GET | `/api/telemetry/metrics/db` | `backend/api/v1/telemetry.py` | internal | NONE |
| GET | `/api/telemetry/metrics/security` | `backend/api/v1/telemetry.py` | internal | NONE |
| GET | `/api/telemetry/performance/overview` | `backend/api/v1/telemetry.py` | api-only | NONE |
| GET | `/api/telemetry/status` | `backend/api/v1/telemetry.py` | api-only | NONE |
| GET | `/api/tts/audio/:param` | `backend/tools/media/multilingual_tts.py` | api-only | NONE |
| DELETE | `/api/tts/cache` | `backend/tools/media/multilingual_tts.py` | api-only | NONE |
| POST | `/api/tts/generate` | `backend/tools/media/multilingual_tts.py` | api-only | NONE |
| GET | `/api/tts/languages` | `backend/tools/media/multilingual_tts.py` | api-only | NONE |
| POST | `/api/tts/synthesize` | `backend/tools/media/multilingual_tts.py` | api-only | NONE |
| GET | `/api/tts/voices` | `backend/tools/media/multilingual_tts.py` | api-only | NONE |
| POST | `/api/v1/access/set-mode` | `backend/api/routes/access.py` | user-facing | `frontend/src/services/connectionsApi.ts` |
| GET | `/api/v1/admin/agents` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/admin/alerts` | `backend/api/routes/internal.py` | deprecated | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/analytics` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/api-keys` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/audit` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/audit-logs` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/billing` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/config` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/crawler/events` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/crawler/history` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/crawler/policies` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/admin/crawler/policies` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| DELETE | `/api/v1/admin/crawler/policies/:param` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| PATCH | `/api/v1/admin/crawler/policies/:param` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/admin/crawler/policies/:param/disable` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/admin/crawler/policies/:param/enable` | `backend/api/routes/crawler_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/dashboard` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/deployments` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/health` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/metrics` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/notifications` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/admin/render/accounts/:param/override` | `backend/api/routes/render_preflight_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/admin/render/accounts/:param/recheck` | `backend/api/routes/render_preflight_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/render/accounts/health` | `backend/api/routes/render_preflight_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/render/events` | `backend/api/routes/render_preflight_admin.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/render/preflight` | `backend/api/routes/render_preflight_admin.py` | admin-only | `frontend/src/components/admin/RenderPreflightWidget.tsx` |
| GET | `/api/v1/admin/security` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/skills` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/stats` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/system-status` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/tiers` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/users` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| GET | `/api/v1/admin/webhooks` | `backend/api/routes/admin_v1.py` | admin-only | `frontend/src/utils/api.ts` |
| POST | `/api/v1/agent/execute` | `backend/api/routes/agent_workspace.py` | user-facing | `frontend/src/services/apiClient.test.ts` |
| POST | `/api/v1/agent/github/pr` | `backend/api/routes/agent_workspace.py` | user-facing | `frontend/src/services/apiClient.ts` |
| POST | `/api/v1/agent/learn` | `backend/api/routes/agent_workspace.py` | user-facing | `frontend/src/services/apiClient.ts` |
| POST | `/api/v1/agent_review_workflow/execute` | `backend/api/routes/ide_trio.py` | api-only | NONE |
| GET | `/api/v1/agent_review_workflow/status` | `backend/api/routes/ide_trio.py` | api-only | NONE |
| GET | `/api/v1/agents` | `backend/api/routes/agent_registry.py` | user-facing | `frontend/src/services/agentService.ts` |
| POST | `/api/v1/agents` | `backend/api/routes/agent_registry.py` | user-facing | `frontend/src/services/agentService.ts` |
| DELETE | `/api/v1/agents/:param` | `backend/api/routes/agent_registry.py` | user-facing | `frontend/src/services/agentService.ts` |
| GET | `/api/v1/agents/:param` | `backend/api/routes/agent_registry.py` | user-facing | `frontend/src/services/agentService.ts` |
| POST | `/api/v1/agents/:param/ownership` | `backend/api/routes/agent_registry.py` | user-facing | `frontend/src/services/agentService.ts` |
| POST | `/api/v1/agents/execute` | `backend/api/routes/agent.py` | user-facing | `frontend/src/pages/user/AgentWorkspace.tsx`, `frontend/src/services/agentService.test.ts`, `frontend/src/services/agentService.ts` |
| GET | `/api/v1/agents/monitor/latency` | `backend/api/routes/agent_tasks.py` | user-facing | `frontend/src/services/agentService.ts` |
| GET | `/api/v1/agents/roles` | `backend/api/routes/agent_tasks.py` | user-facing | `frontend/src/services/agentService.ts` |
| GET | `/api/v1/analytics/business` | `backend/api/routes/analytics.py` | api-only | NONE |
| POST | `/api/v1/analytics/predict-churn` | `backend/api/routes/analytics.py` | api-only | NONE |
| POST | `/api/v1/analytics/report` | `backend/api/routes/analytics.py` | api-only | NONE |
| POST | `/api/v1/auth/login` | `backend/api/routes/auth.py` | user-facing | `frontend/src/pages/PublicPages.tsx`, `frontend/src/services/apiClient.test.ts`, `frontend/src/services/apiClient.ts` (+1 more) |
| POST | `/api/v1/auth/logout` | `backend/api/routes/auth.py` | user-facing | `frontend/src/services/apiClient.ts` |
| GET | `/api/v1/auth/me` | `backend/api/routes/auth.py` | user-facing | `frontend/src/config/permissions.ts`, `frontend/src/services/apiClient.test.ts`, `frontend/src/services/apiClient.ts` (+2 more) |
| POST | `/api/v1/auth/refresh` | `backend/api/routes/auth.py` | user-facing | `frontend/src/services/apiClient.ts` |
| POST | `/api/v1/auth/register` | `backend/api/routes/auth.py` | user-facing | `frontend/src/pages/PublicPages.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/store/authStore.ts` |
| POST | `/api/v1/auth/totp/verify` | `backend/api/routes/auth.py` | api-only | NONE |
| GET | `/api/v1/auth/users` | `backend/api/routes/auth.py` | api-only | NONE |
| PATCH | `/api/v1/auth/users/:param/role` | `backend/api/routes/auth.py` | api-only | NONE |
| GET | `/api/v1/auth/verify` | `backend/api/routes/auth.py` | api-only | NONE |
| POST | `/api/v1/browse` | `backend/api/routes/scraper.py` | api-only | NONE |
| GET | `/api/v1/cache/predictions/:param` | `backend/api/routes/cache_predictions.py` | api-only | NONE |
| GET | `/api/v1/capabilities` | `backend/api/routes/capabilities.py` | user-facing | `frontend/src/services/controlPlane.ts` |
| POST | `/api/v1/capabilities/execute` | `backend/api/routes/capabilities.py` | user-facing | `frontend/src/services/controlPlane.ts` |
| GET | `/api/v1/capabilities/runtime` | `backend/api/routes/capabilities.py` | user-facing | `frontend/src/services/controlPlane.ts` |
| GET | `/api/v1/circles` | `backend/api/routes/circles.py` | api-only | NONE |
| POST | `/api/v1/circles/dispatch` | `backend/api/routes/circles.py` | api-only | NONE |
| GET | `/api/v1/circles/events` | `backend/api/routes/circles.py` | api-only | NONE |
| GET | `/api/v1/circles/health` | `backend/api/routes/circles.py` | internal | NONE |
| POST | `/api/v1/cognitive/route` | `backend/api/routes/cognitive.py` | api-only | NONE |
| POST | `/api/v1/connections/detect` | `backend/api/routes/connections.py` | user-facing | `frontend/src/services/connectionsApi.ts` |
| GET | `/api/v1/connections/my-workspace` | `backend/api/routes/connections.py` | user-facing | `frontend/src/services/connectionsApi.ts` |
| POST | `/api/v1/connections/register` | `backend/api/routes/connections.py` | user-facing | `frontend/src/services/connectionsApi.ts` |
| GET | `/api/v1/control-plane/health` | `backend/api/routes/control_plane.py` | internal | `frontend/src/services/controlPlane.ts` |
| GET | `/api/v1/control-plane/registry` | `backend/api/routes/control_plane.py` | user-facing | `frontend/src/services/controlPlane.test.ts`, `frontend/src/services/controlPlane.ts` |
| GET | `/api/v1/conversations` | `backend/api/routes/conversations.py` | user-facing | `frontend/src/components/admin/MemoryBrowser.tsx`, `frontend/src/components/customer/UserDashboard.tsx`, `frontend/src/pages/PublicPages.tsx` |
| POST | `/api/v1/conversations` | `backend/api/routes/conversations.py` | user-facing | `frontend/src/components/admin/MemoryBrowser.tsx`, `frontend/src/components/customer/UserDashboard.tsx`, `frontend/src/pages/PublicPages.tsx` |
| GET | `/api/v1/conversations/:param/messages` | `backend/api/routes/conversations.py` | user-facing | `frontend/src/components/admin/MemoryBrowser.tsx`, `frontend/src/components/customer/UserDashboard.tsx`, `frontend/src/pages/PublicPages.tsx` |
| POST | `/api/v1/conversations/:param/messages` | `backend/api/routes/conversations.py` | user-facing | `frontend/src/components/admin/MemoryBrowser.tsx`, `frontend/src/components/customer/UserDashboard.tsx`, `frontend/src/pages/PublicPages.tsx` |
| GET | `/api/v1/deep` | `backend/api/routes/health.py` | api-only | NONE |
| POST | `/api/v1/ecosystem/admin/capabilities` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| DELETE | `/api/v1/ecosystem/admin/capabilities/:param` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/capabilities/:param/archive` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/capabilities/:param/lifecycle` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/capabilities/:param/promote` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/decisions` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/governance/budgets` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/governance/decisions` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/learned` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| DELETE | `/api/v1/ecosystem/admin/learned/:param` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/learned/prune` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/opportunities` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/opportunities` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/opportunities/:param/advance` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/overview` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/policies` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/policies` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| DELETE | `/api/v1/ecosystem/admin/policies/:param` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/policies/match` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/proposals` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/proposals` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/proposals/:param/decide` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/proposals/:param/decisions` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/sources` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/admin/sources/:param` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/sources/:param/transition` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| POST | `/api/v1/ecosystem/admin/sources/discover` | `backend/api/routes/ecosystem_admin.py` | admin-only | NONE |
| GET | `/api/v1/ecosystem/capabilities` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/capabilities/:param` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| POST | `/api/v1/ecosystem/capabilities/search` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/deployments` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/deployments/trace/:param` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/health` | `backend/api/routes/ecosystem.py` | internal | NONE |
| POST | `/api/v1/ecosystem/mcp/call` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/mcp/manifest` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/resources` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| POST | `/api/v1/ecosystem/resources` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/tasks` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| POST | `/api/v1/ecosystem/tasks` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| GET | `/api/v1/ecosystem/tasks/:param` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| POST | `/api/v1/ecosystem/tasks/:param/deliver` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| POST | `/api/v1/ecosystem/tasks/:param/transition` | `backend/api/routes/ecosystem.py` | api-only | NONE |
| POST | `/api/v1/engine/solve` | `backend/api/routes/living_engine.py` | api-only | NONE |
| POST | `/api/v1/evolution/breed` | `backend/api/routes/evolution.py` | admin-only | NONE |
| POST | `/api/v1/evolution/canary/:param/observation` | `backend/api/routes/evolution.py` | admin-only | NONE |
| GET | `/api/v1/evolution/canary/:param/route` | `backend/api/routes/evolution.py` | admin-only | NONE |
| POST | `/api/v1/evolution/evaluate-performance` | `backend/api/routes/evolution.py` | admin-only | NONE |
| POST | `/api/v1/evolution/forge` | `backend/api/routes/evolution.py` | admin-only | `frontend/src/store/useStore.ts` |
| GET | `/api/v1/evolution/logs` | `backend/api/routes/evolution.py` | admin-only | NONE |
| GET | `/api/v1/evolution/metrics` | `backend/api/routes/evolution.py` | admin-only | `frontend/src/commandcenter/data/hooks.ts` |
| GET | `/api/v1/evolution/proposals` | `backend/api/routes/evolution.py` | admin-only | NONE |
| POST | `/api/v1/evolution/proposals/:param/approve` | `backend/api/routes/evolution.py` | admin-only | NONE |
| POST | `/api/v1/evolution/quarantine` | `backend/api/routes/evolution.py` | admin-only | NONE |
| GET | `/api/v1/evolution/swarm-graph` | `backend/api/routes/evolution.py` | admin-only | `frontend/src/hooks/useSwarmGraph.ts` |
| POST | `/api/v1/evolution/swarm/forge` | `backend/api/routes/evolution.py` | admin-only | `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` |
| POST | `/api/v1/evolution/swarm/forge/:param/execute` | `backend/api/routes/evolution.py` | admin-only | `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` |
| POST | `/api/v1/external-agents/jobs` | `backend/api/routes/external_agents_admin.py` | admin-only | NONE |
| DELETE | `/api/v1/external-agents/jobs/:param` | `backend/api/routes/external_agents_admin.py` | admin-only | NONE |
| GET | `/api/v1/external-agents/jobs/:param` | `backend/api/routes/external_agents_admin.py` | admin-only | NONE |
| POST | `/api/v1/gateway/automation` | `backend/tools/api_gateway.py` | admin-only | NONE |
| POST | `/api/v1/gateway/dispatch/:param` | `backend/tools/api_gateway.py` | admin-only | NONE |
| POST | `/api/v1/gateway/forward` | `backend/tools/api_gateway.py` | admin-only | NONE |
| POST | `/api/v1/gateway/make` | `backend/tools/api_gateway.py` | admin-only | NONE |
| GET | `/api/v1/graph/path` | `backend/api/routes/graph.py` | api-only | NONE |
| GET | `/api/v1/graph/skills` | `backend/api/routes/graph.py` | user-facing | `frontend/src/components/graph/SkillGraph.tsx` |
| GET | `/api/v1/healing/stats` | `backend/api/routes/healing_stats.py` | api-only | NONE |
| GET | `/api/v1/health` | `backend/api/routes/health.py` | internal | `frontend/src/components/auth/ServiceHealthBar.tsx`, `frontend/src/hooks/useServerStream.ts`, `frontend/src/pages/PublicPages.tsx` (+1 more) |
| GET | `/api/v1/health` | `backend/api/routes/scraper.py` | internal | `frontend/src/components/auth/ServiceHealthBar.tsx`, `frontend/src/hooks/useServerStream.ts`, `frontend/src/pages/PublicPages.tsx` (+1 more) |
| GET | `/api/v1/health/agents` | `backend/api/routes/health.py` | internal | `frontend/src/hooks/useSwarmGraph.ts` |
| POST | `/api/v1/health/agents` | `backend/api/routes/health.py` | internal | `frontend/src/hooks/useSwarmGraph.ts` |
| GET | `/api/v1/health/predictions` | `backend/api/routes/healing_stats.py` | internal | `frontend/src/components/auth/ServiceHealthBar.tsx`, `frontend/src/hooks/useServerStream.ts`, `frontend/src/pages/PublicPages.tsx` (+1 more) |
| POST | `/api/v1/hitl/approve/:param` | `backend/api/routes/approval_manager.py` | admin-only | `frontend/src/data/hooks.ts` |
| POST | `/api/v1/hitl/approve/:param` | `backend/api/routes/hitl_admin.py` | admin-only | `frontend/src/data/hooks.ts` |
| POST | `/api/v1/hitl/cancel/:param` | `backend/api/routes/approval_manager.py` | admin-only | `frontend/src/data/hooks.ts` |
| GET | `/api/v1/hitl/pending` | `backend/api/routes/approval_manager.py` | admin-only | `frontend/src/data/hooks.ts` |
| GET | `/api/v1/hitl/pending` | `backend/api/routes/hitl_admin.py` | admin-only | `frontend/src/data/hooks.ts` |
| POST | `/api/v1/hitl/reject/:param` | `backend/api/routes/approval_manager.py` | admin-only | `frontend/src/data/hooks.ts` |
| POST | `/api/v1/hitl/reject/:param` | `backend/api/routes/hitl_admin.py` | admin-only | `frontend/src/data/hooks.ts` |
| GET | `/api/v1/hitl/resume/:param` | `backend/api/routes/hitl_admin.py` | admin-only | NONE |
| GET | `/api/v1/integrations` | `backend/api/routes/integrations.py` | user-facing | `frontend/src/components/dashboard/ConnectedPlatformsVault.tsx` |
| POST | `/api/v1/integrations/discover` | `backend/api/routes/integrations.py` | user-facing | `frontend/src/components/dashboard/OneLinerMCPConnect.test.tsx`, `frontend/src/components/dashboard/OneLinerMCPConnect.tsx` |
| GET | `/api/v1/integrations/github/callback` | `backend/api/routes/integrations.py` | user-facing | `frontend/src/components/dashboard/ConnectedPlatformsVault.tsx` |
| GET | `/api/v1/integrations/github/link` | `backend/api/routes/integrations.py` | user-facing | `frontend/src/components/dashboard/ConnectedPlatformsVault.tsx` |
| POST | `/api/v1/integrations/github/webhook` | `backend/integrations/github_webhook.py` | internal | `frontend/src/components/dashboard/ConnectedPlatformsVault.tsx` |
| POST | `/api/v1/kaggle/callback` | `backend/api/routes/kaggle.py` | api-only | NONE |
| GET | `/api/v1/kaggle/jobs/:param` | `backend/api/routes/kaggle.py` | api-only | NONE |
| GET | `/api/v1/kaggle/stats` | `backend/api/routes/kaggle.py` | api-only | NONE |
| POST | `/api/v1/kaggle/submit` | `backend/api/routes/kaggle.py` | api-only | NONE |
| POST | `/api/v1/kernel/dispatch` | `backend/api/routes/kernel_dispatch.py` | internal | NONE |
| GET | `/api/v1/keys` | `backend/api/routes/keys.py` | api-only | NONE |
| POST | `/api/v1/keys` | `backend/api/routes/keys.py` | api-only | NONE |
| GET | `/api/v1/live` | `backend/api/routes/health.py` | user-facing | `frontend/src/services/heartbeat.test.ts`, `frontend/src/services/heartbeat.ts`, `frontend/src/services/skillsService.ts` |
| POST | `/api/v1/localization/ai-translate` | `backend/api/routes/localization.py` | api-only | NONE |
| POST | `/api/v1/localization/translate` | `backend/api/routes/localization.py` | api-only | NONE |
| POST | `/api/v1/localization/voice-command` | `backend/api/routes/localization.py` | api-only | NONE |
| GET | `/api/v1/maintenance/status` | `backend/api/routes/maintenance.py` | api-only | NONE |
| POST | `/api/v1/markdown/compare` | `backend/api/routes/markdown.py` | api-only | NONE |
| POST | `/api/v1/markdown/export` | `backend/api/routes/markdown.py` | api-only | NONE |
| GET | `/api/v1/markdown/export/:param/download` | `backend/api/routes/markdown.py` | api-only | NONE |
| GET | `/api/v1/markdown/export/:param/status` | `backend/api/routes/markdown.py` | api-only | NONE |
| GET | `/api/v1/markdown/export/history` | `backend/api/routes/markdown.py` | api-only | NONE |
| GET | `/api/v1/markdown/search` | `backend/api/routes/markdown.py` | api-only | NONE |
| POST | `/api/v1/markdown/share` | `backend/api/routes/markdown.py` | api-only | NONE |
| GET | `/api/v1/mcp/clients` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| POST | `/api/v1/mcp/clients` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| DELETE | `/api/v1/mcp/clients/:param` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| PATCH | `/api/v1/mcp/clients/:param` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| POST | `/api/v1/mcp/clients/:param/rotate` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| GET | `/api/v1/mcp/connections` | `backend/api/routes/mcp_marketplace.py` | api-only | NONE |
| DELETE | `/api/v1/mcp/connections/:param` | `backend/api/routes/mcp_marketplace.py` | api-only | NONE |
| GET | `/api/v1/mcp/connections/:param/health` | `backend/api/routes/mcp_marketplace.py` | internal | NONE |
| PATCH | `/api/v1/mcp/connections/:param/permission` | `backend/api/routes/mcp_marketplace.py` | api-only | NONE |
| POST | `/api/v1/mcp/connections/:param/reactivate` | `backend/api/routes/mcp_marketplace.py` | api-only | NONE |
| PATCH | `/api/v1/mcp/connections/:param/tools` | `backend/api/routes/mcp_marketplace.py` | api-only | NONE |
| POST | `/api/v1/mcp/discover` | `backend/api/routes/mcp_marketplace.py` | api-only | NONE |
| GET | `/api/v1/mcp/gateway` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| POST | `/api/v1/mcp/slug/claim` | `backend/api/routes/mcp_hub.py` | api-only | NONE |
| POST | `/api/v1/media/generate-upload-url` | `backend/api/routes/media.py` | user-facing | `frontend/src/services/storageApi.test.ts`, `frontend/src/services/storageApi.ts` |
| GET | `/api/v1/mesh/tasks` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| GET | `/api/v1/mesh/tasks/:param` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks/:param/cancel` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks/:param/claim` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks/:param/complete` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks/:param/fail` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks/:param/lease` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| GET | `/api/v1/mesh/tasks/queue/stats` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/mesh/tasks/reap` | `backend/api/routes/mesh_tasks.py` | api-only | NONE |
| POST | `/api/v1/meta-ai/breed` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| POST | `/api/v1/meta-ai/metrics` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| GET | `/api/v1/meta-ai/metrics/:param` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| GET | `/api/v1/meta-ai/pool` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| POST | `/api/v1/meta-ai/pool` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| GET | `/api/v1/meta-ai/top-performers` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| GET | `/api/v1/meta-ai/weakest-links` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| POST | `/api/v1/meta-ai/weakest-links/:param/ack` | `backend/api/routes/agent_breeding.py` | admin-only | NONE |
| GET | `/api/v1/missions` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions` | `backend/api/routes/missions.py` | api-only | NONE |
| GET | `/api/v1/missions/:param` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions/:param/advance` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions/:param/approve` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions/:param/cancel` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions/:param/fail` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions/:param/repair` | `backend/api/routes/missions.py` | api-only | NONE |
| POST | `/api/v1/missions/:param/start` | `backend/api/routes/missions.py` | api-only | NONE |
| GET | `/api/v1/missions/:param/trace` | `backend/api/routes/missions.py` | api-only | NONE |
| GET | `/api/v1/missions/:param/trace/stream` | `backend/api/routes/missions.py` | api-only | NONE |
| GET | `/api/v1/nodes` | `backend/api/routes/mesh.py` | user-facing | `frontend/src/components/admin/MeshAgentsPanel.test.tsx`, `frontend/src/components/admin/MeshAgentsPanel.tsx` |
| GET | `/api/v1/nodes/:param` | `backend/api/routes/mesh.py` | user-facing | `frontend/src/components/admin/MeshAgentsPanel.tsx` |
| PATCH | `/api/v1/nodes/:param` | `backend/api/routes/mesh.py` | user-facing | `frontend/src/components/admin/MeshAgentsPanel.tsx` |
| POST | `/api/v1/nodes/heartbeat` | `backend/api/routes/mesh.py` | user-facing | `frontend/src/components/admin/MeshAgentsPanel.tsx` |
| POST | `/api/v1/onboarding/complete` | `backend/api/routes/onboarding.py` | api-only | NONE |
| POST | `/api/v1/onboarding/plan` | `backend/api/routes/onboarding.py` | api-only | NONE |
| DELETE | `/api/v1/onboarding/reset/:param` | `backend/api/routes/onboarding.py` | api-only | NONE |
| POST | `/api/v1/onboarding/signal` | `backend/api/routes/onboarding.py` | api-only | NONE |
| GET | `/api/v1/onboarding/status/:param` | `backend/api/routes/onboarding.py` | api-only | NONE |
| POST | `/api/v1/plugins/community/submit` | `backend/api/routes/plugin_submissions.py` | api-only | NONE |
| POST | `/api/v1/plugins/install` | `backend/api/routes/plugins.py` | user-facing | `frontend/src/hooks/usePlugins.test.ts`, `frontend/src/hooks/usePlugins.ts` |
| GET | `/api/v1/plugins/installed` | `backend/api/routes/plugins.py` | user-facing | `frontend/src/hooks/usePlugins.ts` |
| GET | `/api/v1/plugins/marketplace` | `backend/api/routes/plugins.py` | user-facing | `frontend/src/hooks/usePlugins.ts` |
| DELETE | `/api/v1/plugins/uninstall/:param` | `backend/api/routes/plugins.py` | user-facing | `frontend/src/hooks/usePlugins.ts` |
| GET | `/api/v1/pr-review/:param/status` | `backend/api/routes/pr_review_api.py` | api-only | NONE |
| POST | `/api/v1/pr-review/webhook` | `backend/api/routes/pr_review_api.py` | internal | NONE |
| GET | `/api/v1/projects` | `backend/api/routes/projects.py` | user-facing | `frontend/src/services/projectService.test.ts`, `frontend/src/services/projectService.ts` |
| POST | `/api/v1/projects` | `backend/api/routes/projects.py` | user-facing | `frontend/src/services/projectService.test.ts`, `frontend/src/services/projectService.ts` |
| DELETE | `/api/v1/projects/:param` | `backend/api/routes/projects.py` | user-facing | `frontend/src/services/projectService.ts` |
| PATCH | `/api/v1/projects/:param` | `backend/api/routes/projects.py` | user-facing | `frontend/src/services/projectService.ts` |
| POST | `/api/v1/rag/hybrid-search` | `backend/api/routes/hybrid_search.py` | api-only | NONE |
| POST | `/api/v1/rag/index` | `backend/api/routes/hybrid_search.py` | api-only | NONE |
| GET | `/api/v1/ready` | `backend/api/routes/health.py` | user-facing | `frontend/src/services/skillsService.ts` |
| POST | `/api/v1/recipe` | `backend/api/routes/scraper.py` | api-only | NONE |
| POST | `/api/v1/router/route` | `backend/api/routes/advanced_router.py` | api-only | NONE |
| GET | `/api/v1/runs` | `backend/runs/api.py` | api-only | NONE |
| POST | `/api/v1/runs` | `backend/runs/api.py` | api-only | NONE |
| GET | `/api/v1/runs/:param` | `backend/runs/api.py` | api-only | NONE |
| POST | `/api/v1/runs/:param/cancel` | `backend/runs/api.py` | api-only | NONE |
| POST | `/api/v1/runs/:param/classify` | `backend/runs/api.py` | api-only | NONE |
| GET | `/api/v1/runs/:param/events` | `backend/runs/api.py` | api-only | NONE |
| POST | `/api/v1/runs/:param/retry` | `backend/runs/api.py` | api-only | NONE |
| POST | `/api/v1/runs/:param/transition` | `backend/runs/api.py` | api-only | NONE |
| POST | `/api/v1/runs/:param/usage` | `backend/runs/api.py` | api-only | NONE |
| DELETE | `/api/v1/sandbox/:param` | `backend/api/routes/sandbox_api.py` | api-only | NONE |
| POST | `/api/v1/sandbox/:param/execute` | `backend/api/routes/sandbox_api.py` | api-only | NONE |
| GET | `/api/v1/sandbox/:param/logs` | `backend/api/routes/sandbox_api.py` | api-only | NONE |
| POST | `/api/v1/sandbox/create` | `backend/api/routes/sandbox_api.py` | user-facing | `frontend/src/components/chat/UnifiedChatBubble.tsx` |
| GET | `/api/v1/sandbox/list` | `backend/api/routes/sandbox_api.py` | api-only | NONE |
| POST | `/api/v1/scrape` | `backend/api/routes/scraper.py` | api-only | NONE |
| GET | `/api/v1/social/drafts` | `backend/api/routes/social_growth.py` | user-facing | `frontend/src/services/socialGrowthService.ts` |
| POST | `/api/v1/social/drafts` | `backend/api/routes/social_growth.py` | user-facing | `frontend/src/services/socialGrowthService.ts` |
| POST | `/api/v1/social/drafts/:param/approve` | `backend/api/routes/social_growth.py` | user-facing | `frontend/src/services/socialGrowthService.ts` |
| POST | `/api/v1/social/pause` | `backend/api/routes/social_growth.py` | user-facing | `frontend/src/services/socialGrowthService.ts` |
| POST | `/api/v1/social/resume` | `backend/api/routes/social_growth.py` | user-facing | `frontend/src/services/socialGrowthService.ts` |
| GET | `/api/v1/stream/chat` | `backend/api/routes/stream_chat_sse.py` | user-facing | `frontend/src/pages/PublicPages.tsx`, `frontend/src/services/chatService.ts` |
| POST | `/api/v1/stream/chat` | `backend/api/routes/stream_chat_sse.py` | user-facing | `frontend/src/pages/PublicPages.tsx`, `frontend/src/services/chatService.ts` |
| GET | `/api/v1/stream/hitl` | `backend/api/routes/stream_hitl_sse.py` | api-only | NONE |
| GET | `/api/v1/swarm/stream` | `backend/api/routes/swarm_stream.py` | user-facing | `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` |
| POST | `/api/v1/syncguard/audit` | `backend/api/routes/syncguard.py` | api-only | NONE |
| POST | `/api/v1/tasks` | `backend/api/routes/task_gateway.py` | user-facing | `frontend/src/services/controlPlane.ts` |
| GET | `/api/v1/tasks/:param` | `backend/api/routes/task_gateway.py` | user-facing | `frontend/src/services/controlPlane.ts` |
| POST | `/api/v1/tasks/:param/cancel` | `backend/api/routes/task_gateway.py` | user-facing | `frontend/src/services/controlPlane.ts` |
| GET | `/api/v1/telegram/health` | `backend/tools/social/telegram_bot/router.py` | internal | NONE |
| POST | `/api/v1/telegram/webhook` | `backend/tools/social/telegram_bot/router.py` | internal | NONE |
| GET | `/api/v1/tools-registry` | `backend/api/routes/tools_registry.py` | api-only | NONE |
| POST | `/api/v1/tools-registry` | `backend/api/routes/tools_registry.py` | api-only | NONE |
| DELETE | `/api/v1/tools-registry/:param` | `backend/api/routes/tools_registry.py` | api-only | NONE |
| PATCH | `/api/v1/tools-registry/:param` | `backend/api/routes/tools_registry.py` | api-only | NONE |
| POST | `/api/v1/webhooks/n8n/callback` | `backend/api/routes/n8n_webhooks.py` | internal | NONE |
| POST | `/api/v1/webhooks/telegram/callback` | `backend/api/routes/webhooks_ai.py` | internal | NONE |
| POST | `/api/v1/webhooks/telegram/send-alert` | `backend/api/routes/webhooks_ai.py` | internal | NONE |
| GET | `/api/v1/workspace/capabilities` | `backend/api/routes/workspace_capabilities.py` | user-facing | `frontend/src/utils/api.ts` |
| POST | `/api/v1/workspace/capabilities` | `backend/api/routes/workspace_capabilities.py` | user-facing | `frontend/src/utils/api.ts` |
| POST | `/api/v1/workspace/capabilities/:param/health` | `backend/api/routes/workspace_capabilities.py` | internal | `frontend/src/utils/api.ts` |
| PATCH | `/api/v1/workspace/capabilities/:param/permission` | `backend/api/routes/workspace_capabilities.py` | user-facing | `frontend/src/utils/api.ts` |
| POST | `/api/v1/workspace/capabilities/:param/reactivate` | `backend/api/routes/workspace_capabilities.py` | user-facing | `frontend/src/utils/api.ts` |
| POST | `/api/v1/workspace/capabilities/:param/revoke` | `backend/api/routes/workspace_capabilities.py` | user-facing | `frontend/src/utils/api.ts` |
| PATCH | `/api/v1/workspace/capabilities/:param/tools` | `backend/api/routes/workspace_capabilities.py` | user-facing | `frontend/src/utils/api.ts` |
| POST | `/api/v1/workspace/task/execute` | `backend/api/routes/task_workspace.py` | user-facing | `frontend/src/utils/api.ts` |
| GET | `/api/v1/workspace/task/quota` | `backend/api/routes/task_workspace.py` | user-facing | `frontend/src/utils/api.ts` |
| GET | `/api/v1/zero-cost/health` | `backend/api/routes/zero_cost.py` | internal | NONE |
| GET | `/api/v1/zero-cost/metrics` | `backend/api/routes/zero_cost.py` | internal | NONE |
| GET | `/api/v1/zero-cost/recommendations` | `backend/api/routes/zero_cost.py` | api-only | NONE |
| GET | `/api/voice/stream_audio` | `backend/api/routes/voice.py` | api-only | NONE |
| GET | `/api/voice/voices` | `backend/api/routes/voice.py` | user-facing | `frontend/src/services/chatService.test.ts`, `frontend/src/services/chatService.ts` |
| POST | `/api/webhooks/github` | `backend/api/routes/webhooks_github.py` | internal | NONE |
| GET | `/auth/sso/metadata` | `backend/api/routes/sso.py` | api-only | NONE |
| POST | `/auth/sso/oidc/:param/authorize` | `backend/api/routes/sso.py` | api-only | NONE |
| POST | `/auth/sso/oidc/:param/callback` | `backend/api/routes/sso.py` | api-only | NONE |
| GET | `/auth/sso/oidc/:param/logout` | `backend/api/routes/sso.py` | api-only | NONE |
| POST | `/auth/sso/oidc/discovery` | `backend/api/routes/sso.py` | api-only | NONE |
| POST | `/auth/sso/saml` | `backend/api/routes/sso.py` | api-only | NONE |
| GET | `/build/knowledge` | `backend/api/routes/commandcenter/build.py` | admin-only | NONE |
| GET | `/build/memory` | `backend/api/routes/commandcenter/build.py` | admin-only | NONE |
| GET | `/build/providers` | `backend/api/routes/commandcenter/build.py` | admin-only | NONE |
| GET | `/build/router` | `backend/api/routes/commandcenter/build.py` | admin-only | NONE |
| GET | `/build/skills` | `backend/api/routes/commandcenter/build.py` | admin-only | NONE |
| GET | `/cdc/health` | `backend/api/routes/cdc_webhooks.py` | internal | NONE |
| POST | `/cdc/webhook` | `backend/api/routes/cdc_webhooks.py` | internal | NONE |
| GET | `/config/:param` | `backend/api/routes/config_routes.py` | api-only | NONE |
| PUT | `/config/:param` | `backend/api/routes/config_routes.py` | api-only | NONE |
| GET | `/config/public` | `backend/api/routes/config_routes.py` | api-only | NONE |
| GET | `/config/validation-report` | `backend/api/routes/config_routes.py` | api-only | NONE |
| POST | `/diagram/api-spec` | `backend/tools/code/diagram_to_architecture.py` | api-only | NONE |
| POST | `/diagram/generate` | `backend/tools/code/diagram_to_architecture.py` | api-only | NONE |
| POST | `/diagram/to-kubernetes` | `backend/tools/code/diagram_to_architecture.py` | api-only | NONE |
| POST | `/diagram/to-schema` | `backend/tools/code/diagram_to_architecture.py` | api-only | NONE |
| POST | `/diagram/to-terraform` | `backend/tools/code/diagram_to_architecture.py` | api-only | NONE |
| GET | `/gcp/health` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/gcp/pubsub/stats` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/gcp/verification-queue/stats` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| POST | `/github/connect` | `backend/api/routes/github.py` | api-only | NONE |
| POST | `/github/discover` | `backend/api/routes/github.py` | api-only | NONE |
| POST | `/github/implement` | `backend/api/routes/github.py` | api-only | NONE |
| POST | `/github/improve` | `backend/api/routes/github.py` | api-only | NONE |
| POST | `/github/push` | `backend/api/routes/github.py` | api-only | NONE |
| GET | `/github/repos` | `backend/api/routes/github.py` | api-only | NONE |
| GET | `/github/repos/:param/commits` | `backend/api/routes/github.py` | api-only | NONE |
| POST | `/integrations/email/gmail` | `backend/api/routes/email.py` | api-only | NONE |
| POST | `/integrations/email/imap` | `backend/api/routes/email.py` | api-only | NONE |
| POST | `/internal/run-daily-evolution` | `backend/api/routes/internal.py` | admin-only | NONE |
| GET | `/internet-monitor/capabilities` | `backend/api/routes/internet_monitor.py` | admin-only | NONE |
| GET | `/internet-monitor/history` | `backend/api/routes/internet_monitor.py` | admin-only | NONE |
| POST | `/internet-monitor/start-monitoring` | `backend/api/routes/internet_monitor.py` | admin-only | NONE |
| GET | `/internet-monitor/status` | `backend/api/routes/internet_monitor.py` | admin-only | NONE |
| GET | `/internet-monitor/summary` | `backend/api/routes/internet_monitor.py` | admin-only | NONE |
| GET | `/internet-monitor/updates` | `backend/api/routes/internet_monitor.py` | admin-only | NONE |
| POST | `/llm-gateway/admin/circuit-breaker/reset/:param` | `backend/api/routes/llm_gateway_routes.py` | admin-only | NONE |
| GET | `/llm-gateway/admin/gateway/state` | `backend/api/routes/llm_gateway_routes.py` | admin-only | NONE |
| GET | `/llm-gateway/admin/providers/fallback-chain` | `backend/api/routes/llm_gateway_routes.py` | admin-only | NONE |
| GET | `/llm-gateway/health` | `backend/api/routes/llm_gateway_routes.py` | internal | NONE |
| POST | `/marketplace/install` | `backend/api/routes/marketplace_endpoints.py` | api-only | NONE |
| POST | `/marketplace/search` | `backend/api/routes/marketplace_endpoints.py` | api-only | NONE |
| GET | `/metrics/usage` | `backend/api/routes/usage_metrics.py` | internal | NONE |
| POST | `/metrics/usage` | `backend/api/routes/usage_metrics.py` | internal | NONE |
| GET | `/money/budget` | `backend/api/routes/commandcenter/money.py` | admin-only | NONE |
| POST | `/money/budget` | `backend/api/routes/commandcenter/money.py` | admin-only | NONE |
| GET | `/money/cost` | `backend/api/routes/commandcenter/money.py` | admin-only | NONE |
| GET | `/money/roi` | `backend/api/routes/commandcenter/money.py` | admin-only | NONE |
| GET | `/money/usage` | `backend/api/routes/commandcenter/money.py` | admin-only | NONE |
| GET | `/observe/ci` | `backend/api/routes/commandcenter/observe.py` | admin-only | NONE |
| GET | `/observe/events` | `backend/api/routes/commandcenter/observe.py` | admin-only | NONE |
| GET | `/observe/health` | `backend/api/routes/commandcenter/observe.py` | admin-only | NONE |
| GET | `/observe/logs` | `backend/api/routes/commandcenter/observe.py` | admin-only | NONE |
| GET | `/observe/metrics` | `backend/api/routes/commandcenter/observe.py` | admin-only | NONE |
| GET | `/observe/traffic` | `backend/api/routes/commandcenter/observe.py` | admin-only | NONE |
| GET | `/operate/agents` | `backend/api/routes/commandcenter/operate.py` | admin-only | NONE |
| GET | `/operate/sessions` | `backend/api/routes/commandcenter/operate.py` | admin-only | NONE |
| GET | `/operate/swarm` | `backend/api/routes/commandcenter/operate.py` | admin-only | NONE |
| GET | `/operate/tasks` | `backend/api/routes/commandcenter/operate.py` | admin-only | NONE |
| GET | `/operate/tenants` | `backend/api/routes/commandcenter/operate.py` | admin-only | NONE |
| GET | `/overview` | `backend/api/routes/commandcenter/overview.py` | admin-only | NONE |
| POST | `/pair/review` | `backend/tools/code/ai_pair_programmer.py` | api-only | NONE |
| POST | `/pair/solve` | `backend/tools/code/ai_pair_programmer.py` | api-only | NONE |
| POST | `/payments/checkout` | `backend/api/routes/payments.py` | api-only | NONE |
| GET | `/payments/plans` | `backend/api/routes/payments.py` | api-only | NONE |
| POST | `/payments/webhook` | `backend/api/routes/payments.py` | internal | NONE |
| POST | `/render-ticket` | `backend/api/routes/browser/_render_proxy.py` | api-only | NONE |
| GET | `/repos` | `backend/api/routes/repos.py` | api-only | NONE |
| POST | `/repos` | `backend/api/routes/repos.py` | api-only | NONE |
| DELETE | `/repos/:param` | `backend/api/routes/repos.py` | api-only | NONE |
| PATCH | `/repos/:param` | `backend/api/routes/repos.py` | api-only | NONE |
| GET | `/secure/approvals` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| GET | `/secure/audit` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| GET | `/secure/ratelimits` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| GET | `/secure/rules` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| POST | `/secure/rules` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| GET | `/secure/secrets` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| GET | `/secure/threats` | `backend/api/routes/commandcenter/secure.py` | admin-only | NONE |
| POST | `/security/vulnerabilities/scan` | `backend/agents/code_vulnerability_scanner_agent.py` | admin-only | NONE |
| POST | `/security/vulnerabilities/scan-project` | `backend/agents/code_vulnerability_scanner_agent.py` | admin-only | NONE |
| GET | `/skills` | `backend/api/routes/admin_routes.py` | admin-only | NONE |
| GET | `/system/backups` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| POST | `/system/backups` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| POST | `/system/backups/:param/restore` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| GET | `/system/config` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| POST | `/system/config` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| GET | `/system/deploy-gate` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| POST | `/system/deploy-gate` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| GET | `/system/flags` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| POST | `/system/flags` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| GET | `/system/workspaces` | `backend/api/routes/commandcenter/system.py` | admin-only | NONE |
| POST | `/task/execute` | `backend/api/routes/task.py` | api-only | NONE |
| POST | `/tools/deploy/compose` | `backend/api/routes/tools_ops.py` | admin-only | NONE |
| POST | `/tools/deploy/helm` | `backend/api/routes/tools_ops.py` | admin-only | NONE |
| POST | `/tools/domain/adapt` | `backend/api/routes/tools_ops.py` | admin-only | NONE |
| POST | `/tools/image-to-code` | `backend/tools/code/image_to_code.py` | api-only | NONE |
| POST | `/tools/image-to-component` | `backend/tools/code/image_to_code.py` | api-only | NONE |
| POST | `/tools/image-to-palette` | `backend/tools/code/image_to_code.py` | api-only | NONE |
| POST | `/tools/image-to-tree` | `backend/tools/code/image_to_code.py` | api-only | NONE |
| POST | `/tools/skills/recommend` | `backend/api/routes/tools_ops.py` | admin-only | NONE |
| POST | `/tools/smell-check` | `backend/api/routes/tools_ops.py` | admin-only | NONE |
| POST | `/tools/vulnerability-check` | `backend/api/routes/tools_ops.py` | admin-only | NONE |
| GET | `/unified-memory/long-term/query` | `backend/api/routes/unified_memory_api.py` | api-only | NONE |
| POST | `/unified-memory/long-term/store` | `backend/api/routes/unified_memory_api.py` | api-only | NONE |
| POST | `/v1/chat/completions` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| GET | `/v1/models` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| POST | `/v1/orchestrator/parse-and-plan` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| POST | `/v1/pool/accounts` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| GET | `/v1/pool/status` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| POST | `/v1/prompt/enhance` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| POST | `/v1/tasks/parallel` | `backend/api/routes/web_ai_proxy.py` | api-only *(unmounted)* | NONE |
| POST | `/video-to-code/process` | `backend/services/video_to_code_pipeline.py` | api-only | NONE |
| POST | `/voice/process-audio` | `backend/tools/code/voice_coder.py` | api-only | NONE |
| GET | `/ws/command-center/health` | `backend/ws/command_center.py` | internal | NONE |
