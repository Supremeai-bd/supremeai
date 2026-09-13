# SupremeAI Full Non-Working Components Audit

**Audit date:** 2026-09-14  
**Repository:** `SaifulHaqueNiloy/supremeai`  
**Branch checked:** `v0/fix-high-blockers`  
**Purpose:** Record every component that is confirmed non-working, mismatched, simulated, stubbed, orphaned, or not reliably auditable. Items that could not be fully verified are intentionally included in the final section.

## Evidence and limitations

The audit used:

- `scripts/feature_parity_sentinel.py` against the current source tree.
- Python bytecode compilation with `python -m compileall -q backend`.
- Static source inspection and the previous audit attachment.
- Frontend/backend route and component inventories.

The current sentinel scan reported **158 backend route modules, 653 mounted routes, 142 frontend API calls, 49 navigation links, 42 frontend route paths, and 643 total findings**. It reported **185 NEW findings** relative to its baseline. The report is not considered a runtime health check: route parity cannot prove that a handler performs real work.

`compileall` passed, but runtime imports could not be validated in this environment because `fastapi`, `loguru`, `pydantic`, `sqlalchemy`, and `httpx` are unavailable. Therefore, the unverified list below is part of the audit and must not be treated as working.

## Priority legend

- **P0 — broken at runtime or a frontend request has no backend route**
- **P1 — mounted but simulated, stubbed, or always reports success**
- **P2 — orphaned or disconnected; no known active frontend consumer**
- **UNVERIFIED — could not execute because dependencies, credentials, external services, or runtime fixtures were unavailable**

## 1. P0: confirmed route and wiring failures

### Frontend calls with no mounted backend route

The sentinel currently reports these route families as missing or mismatched:

- Admin events: `/admin-api/events`
- Admin backups: `/admin-api/backups`, `/admin-api/backup`
- Feature flags: `/admin-api/feature-flags`, `/admin-api/feature-flags/{id}`
- Admin configuration: `/admin-api/config`
- Health and metrics: `/admin-api/health-map`, `/admin-api/metrics`
- Model routing: `/admin-api/model-router`, `/admin-api/providers`, `/admin-api/model-router/override`
- User management: `/admin-api/users`, `/admin-api/users/{username}`
- Security: `/admin-api/rules`, `/admin-api/security-scan`
- Costs: `/admin-api/costs`, `/admin-api/costs/breakdown`
- Deployment: `/admin-api/deploy`
- CI logs: `/admin-api/ci-logs`
- Agent execution test contract: `/api/agent/execute`
- Profile settings test contract: `/api/v1/settings/profile`

Primary callers are under `frontend/src/components/admin`, `frontend/src/hooks/useAdminApi.ts`, `frontend/src/hooks/useDashboardData.ts`, `frontend/src/pages/admin/AdminShell.tsx`, and `frontend/src/services/apiClient.test.ts`.

### Known contract mismatches requiring verification

- `frontend/src/services/skillService.ts` calls `/api/skills/verify-skll-config`, while the backend skill router uses `/api/v1/skills`.
- `frontend/src/services/skillsService.ts` calls `/api/v1/skills/` and `/api/v1/skills/deploy-blueprint`; the router must remain mounted in `ALL_ROUTERS`.
- `frontend` calls `GET /api/v1/connections/my-workspace`, but `backend/api/routes/connections.py` previously had no matching handler.
- `frontend` calls `POST /api/v1/access/set-mode`, but `backend/api/routes/access.py` previously had no matching handler.
- Agent, task, capability, workspace binding, and control-plane calls still appear in the sentinel missing-route set and require direct runtime verification.

### Sandbox runtime

- `backend/api/routes/sandbox_api.py` depends on `CloudSandboxOrchestrator`.
- Any provider configuration, environment variable, or constructor path not covered by the local provider implementation can still fail before the endpoint handler executes.
- Create, execute, logs, delete, and list sandbox flows require an integration/runtime smoke test; static route parity is insufficient.

## 2. P1: mounted components that do not perform the advertised work

### Learning, training, and self-evolution

- `backend/core/kaggle_orchestrator.py` — generated kernel is a template and returns dummy completion output; no real training or checkpoint is produced.
- `backend/tools/learning/model_trainer.py` — local mode is explicitly simulated and produces no checkpoint.
- `backend/tools/learning/rlhf_pipeline.py` — local TRL/DPO path returns `status: "not_implemented"`.
- `.github/workflows/weekly-fine-tuning.yml` — referenced by architecture documentation but absent from the workflow directory.
- `backend/tools/learning/style_learner.py` — skips AST analysis when `build/my-languages.so` is unavailable and falls back to hardcoded data.
- `backend/services/dynamic_ai/orchestrator.py` — missing learning engine falls back to a class that raises `NotImplementedError`.

### Simulated providers and fabricated results

- `backend/core/competitive_kit.py` — `MultiLLMRouter._call_llm()` returns a fabricated response instead of calling a provider SDK.
- `backend/core/messaging/service.py` — `MockMessagingAdapter` reports successful delivery without sending a message; dispatcher can fall back to it.
- `backend/core/agents/framework/task_runner_agent.py` — pipeline stages return hardcoded investigation, fix, scaffold, implementation, and test placeholders.
- `backend/core/agents/legacy/system_health_agent.py` — database health uses an unconditional truthy fallback and can report healthy without a database.
- `backend/core/optimization/performance_optimizer.py` — default `MockConnection` fabricates query results and optimization gains.
- `backend/services/voice_service.py` — speech-to-text returns a fixed transcript; text-to-speech does not return real audio bytes.
- `backend/api/routes/stream_voice_sse.py` — emits placeholder WAV bytes when the voice service has no audio payload.
- `backend/core/queue/task_queue_enhanced.py` — deprecated status wrapper returns `"unknown"` for every task.

### Command Center and observability stubs

- `backend/api/routes/commandcenter/overview.py` — returns zeroed metrics and 100% health without collecting live values.
- `backend/api/routes/commandcenter/build.py` — provider, skill, memory, and router data are empty or hardcoded.
- `backend/api/routes/commandcenter/money.py` — financial data is empty/zeroed.
- `backend/api/routes/commandcenter/observe.py` — observability data is empty.
- `backend/api/routes/commandcenter/operate.py` — system state is hardcoded.
- `backend/api/routes/commandcenter/secure.py` — security status is stubbed and does not scan.
- `backend/api/routes/commandcenter/system.py` — system introspection is empty.
- `backend/api/routes/sandbox_api.py` — list flow returns an empty list rather than querying a real provider/state store.

## 3. P1: explicit unimplemented integrations and plugins

- `backend/core/plugins/experimental/gmail_plugin.py` — raises `NotImplementedError`.
- `backend/core/plugins/experimental/google_drive_plugin.py` — raises `NotImplementedError`.
- `backend/core/plugins/experimental/slack_plugin.py` — raises `NotImplementedError`.
- `backend/core/plugins/experimental/telegram_plugin.py` — raises `NotImplementedError`.
- `backend/core/plugins/experimental/notion_plugin.py` — raises `NotImplementedError`.
- `backend/core/plugins/official/google_drive_plugin.py` — delegates to the unimplemented experimental plugin.
- `backend/core/plugins/official/github_plugin.py` — returns a fake PR number and URL instead of creating a real PR.
- `backend/api/routes/integrations.py` — Slack dock route returns HTTP 501.
- `backend/api/routes/integrations.py` — Gmail OAuth callback returns HTTP 501.
- `backend/adaptive_engine/mcp_skeleton.py` — forecast, correlation, capability creation, and Kaggle operations are stubs or incomplete dispatches.
- `backend/tools/creative/__init__.py` — empty module with no implemented exports.

## 4. P2: mounted but currently orphaned backend endpoints

The sentinel reports many mounted endpoints with no active frontend consumer. These are not automatically broken, but they are not reachable through the current UI and must remain on the non-working/unknown list until an intentional consumer or documented API contract exists.

- Workspace capabilities: `backend/api/routes/workspace_capabilities.py`
- Artifacts: `backend/api/routes/artifacts.py`
- MCP marketplace: `backend/api/routes/mcp_marketplace.py`
- Intelligence insights: `backend/api/routes/intelligence_insights.py`
- Social growth: `backend/api/routes/social_growth.py`
- Tenant administration: `backend/api/routes/tenant_admin.py`
- Diagram-to-architecture tools: `backend/tools/code/diagram_to_architecture.py`
- Admin v1: `backend/api/routes/admin_v1.py`
- Crawler administration: `backend/api/routes/crawler_admin.py`
- Task gateway and conversation branching: `backend/api/routes/task_gateway.py`, `backend/api/routes/branch_conversations.py`
- Chat upload/export and deep research: `backend/api/routes/chat_upload.py`, `backend/api/routes/chat_export.py`, `backend/api/routes/deep_research.py`
- Vulnerability scanner: `backend/agents/code_vulnerability_scanner_agent.py`
- Billing: `backend/api/routes/billing_api.py`
- Reasoning: `backend/api/routes/reasoning.py`
- Voice coder: `backend/api/routes/voice_coder.py`
- AI pair programmer: `backend/api/routes/ai_pair_programmer.py`
- Knowledge: `backend/api/routes/knowledge.py`
- Preferences: `backend/api/routes/preferences.py`
- Health agents and usage metrics: `backend/api/routes/health.py`, `backend/api/routes/usage_metrics.py`
- Agent execution, config validation, evolution metrics, kernel dispatch, memory messages, prompt template use, scheduled task toggles, command execution, traffic monitoring, video-to-code, self-planning, and command-center health routes

The current scan also identifies suspicious doubled paths such as `/admin-api/admin-api/...` from the admin dashboard aggregation. These need route-prefix normalization.

## 5. P2: ghost or disconnected frontend components

These components exist but are not currently proven to be rendered from the active `App.tsx` route tree:

- `frontend/src/components/admin/security/RulesEnginePanel.tsx`
- `frontend/src/components/dashboard/HITLModal.tsx`
- `frontend/src/components/dashboard/OneLinerMCPConnect.tsx`
- `frontend/src/components/swarm/HoldToKillButton.tsx`
- `frontend/src/components/dashboard/LivingActionDock.tsx`
- `frontend/src/components/ui/GlassUiPrimitives.tsx`

Previously baselined disconnected components also include `ErrorBoundary`, `FixPreviewModal`, `OnboardingWizard`, `OperatorStudio`, `AdminDashboardHome`, `HealthBanner`, `DeploymentModal`, `ServiceHealthMonitor`, `ActionDock`, `AutomationQueuePage`, `ConnectedPlatformsVault`, `KnowledgePage`, `LivingDashboardShell`, `LlmGatewayPage`, `SessionDetailPage`, `UsagePage`, `DynamicActionDock`, `MainLayout`, `Shell`, `SwarmHealthDashboard`, `SkillForgeWidget`, `TelemetryDashboardWidget`, `LoginScreen`, and `RegisterScreen`. These require either an explicit route/consumer or removal from the active feature inventory.

## 6. Unmounted or incompletely mounted routers

The current sentinel output must be treated as authoritative for the remaining unmounted-router findings. The historically affected modules include:

- `api.routes.skills`
- `api.routes.byoc_api`
- `api.routes.periodic_task_scheduler`
- `api.routes.auto_test_generator`
- Other legacy route modules listed by the sentinel baseline

The previously identified admin dashboard and Telegram router mounts were changed in earlier repair commits, but they still require a real application startup and route-table assertion after dependencies are installed.

## 7. UNVERIFIED: components that could not be audited completely

These are deliberately retained because the environment did not provide enough evidence to call them working:

- FastAPI application startup and import graph — blocked by missing runtime packages.
- All endpoint response behavior — no dependency-complete TestClient run was possible.
- Database-backed health, memory, billing, usage, artifact, and preference flows — no verified database connection or fixtures.
- External provider integrations: Telegram, Slack, Gmail, Google Drive, Notion, GitHub, Kaggle, model providers, storage, and messaging — credentials and live-provider tests were unavailable.
- Authentication, authorization, tenant isolation, and admin permissions — static review is not proof of enforcement.
- Frontend browser behavior, lazy route loading, error boundaries, API error states, and responsive interaction — no browser smoke test was completed in this audit.
- WebSocket and SSE flows — no live client/server connection test was completed.
- Background workers, queues, scheduled jobs, and workflow recovery — no worker runtime was available.
- CI/CD and deployment paths — no complete CI run or deployment verification was performed.
- Every component matched only by static sentinel heuristics — a match means a route/name relationship, not successful execution.

## 8. Recommended repair order

1. Install the declared backend dependencies in the project-managed environment and run application startup checks.
2. Resolve all HIGH missing frontend routes, beginning with the shared admin API contract.
3. Add route-table and endpoint smoke tests for sandbox, skills, connections, access, agent, and task APIs.
4. Replace fabricated/mock success paths with explicit provider errors or real adapters.
5. Wire or remove orphan backend endpoints and ghost frontend components.
6. Run browser smoke tests for each active frontend route and update the sentinel baseline only after review.

## Audit conclusion

The repository compiles at the Python bytecode level, but it cannot currently be called fully working. The active evidence shows **643 parity findings**, confirmed simulated/stubbed functionality, unresolved frontend/backend route drift, disconnected UI assets, and runtime validation blocked by missing dependencies. All items in this document should remain tracked until a passing runtime test, integration test, or deliberate deprecation decision provides evidence otherwise.

## Reproduction commands

```bash
python scripts/feature_parity_sentinel.py --fail-on never
python -m compileall -q backend
# After installing project dependencies:
python -m pytest
```

Do not update `feature_parity_baseline.json` merely to hide unresolved findings; update it only after the corresponding behavior is fixed or intentionally accepted with evidence.

---

**Source audit:** `user_read_only_context/text_attachments/NON_WORKING_COMPONENTS_AUDIT-k0oez.md`  
**Generated from:** current source tree plus the Feature Parity Sentinel scan on 2026-09-14
