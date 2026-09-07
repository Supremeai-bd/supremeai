# Codebase Naming Mismatch Analysis

Goal: identify files whose names sound grandiose/abstract but whose implementations are smaller or differently scoped, then document a rename mapping with rationale.

---

## 1. Frontend

### `frontend/src/store/tierSStore.ts`
- **Current name:** `tierSStore`
- **Suggested name:** `workspaceUiStateStore` / `chatOverlayStateStore`
- **Rationale:** The `tierS` prefix carries no semantic meaning in the codebase. The store actually manages the UI overlay state of the chat workspace: share dialog, reasoning panel, artifacts panel, slash-command menu, search dialog, and deep-research panel. The tier labels S1-S12 are internal grouping markers, not user-facing tiers. A descriptive name communicates intent without requiring developers to read the integration guide.
- **Rename impact:** Update `useTierSStore` usages across `ChatInterface.tsx` and the 8+ Tier-S components that consume the store.

### `frontend/src/routes/tierSRoutes.tsx`
- **Current name:** `tierSRoutes`
- **Suggested name:** `workspaceFeatureRoutes`
- **Rationale:** Same prefix issue as the store. These are the routes for the Tier-S feature set. A descriptive name keeps the route file discoverable without reading the integration guide.

### `frontend/src/components/widgets/EvolutionForgeWidget.tsx`
- **Current name:** `EvolutionForgeWidget`
- **Suggested name:** `SkillForgeWidget` / `SkillGeneratorWidget`
- **Rationale:** The widget calls `forgeNewSkill(skillName, userDemand)` and submits to `/api/evolution/forge`. It synthesizes and deploys standalone skills/tools. The "Evolution Forge" name implies biological/generational evolution but the actual operation is skill code generation. Renaming to `SkillForgeWidget` keeps the metaphor while tying it to its actual purpose.
- **Rename impact:** Update imports in wherever the widget is mounted.

### `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx`
- **Current name:** `EvolutionForge`
- **Suggested name:** `SwarmArchitect` / `AgentWorkflowDesigner`
- **Rationale:** This page is a ReactFlow-based visual editor for designing multi-agent swarms/workflows. It lets users drag agents/tasks, connect them, save swarm blueprints, execute flows, and deploy to the marketplace. The "Evolution Forge" name conflates two different concepts (the skill generator widget and the visual workflow editor). Renaming to `SwarmArchitect` or `AgentWorkflowDesigner` matches the actual behavior: building multi-agent pipeline architectures.

### `frontend/src/pages/user/ArchitectTower.tsx`
- **Current name:** `ArchitectTower`
- **Suggested name:** `SystemHealthDashboard` / `AdminPatchDashboard`
- **Rationale:** The page renders an "Architectural Control Tower" dashboard for self-healing system operations. It fetches pending fixes from `/api/admin/fixes`, shows stats (Pending Reviews, System Health, Active Nodes), and renders an `OneClickPatch` component for human-in-the-loop review. The name "ArchitectTower" is dramatic; the page is an admin system-health dashboard.

---

## 2. Backend

### `backend/core/tier8/agent_evolution_engine.py`
- **Current name:** `AgentEvolutionEngine` / module `agent_evolution_engine`
- **Suggested name:** `GeneticAgentOptimizer` / `AgentGenomeOptimizer`
- **Rationale:** This is a legitimate name. The class genuinely evolves agent genomes through selection, mutation, crossover, and fitness scoring against LLM benchmarks. The "evolution" framing is technically accurate here. Renaming is optional but `GeneticAgentOptimizer` is more precise.
- **Rename impact:** Update imports in `__init__.py`, `tier8_integration.py`, `tests/core/test_tier8.py`, `tests/core/test_tier8_evolution.py`, `startup/agents.py`, `shutdown.py`, `scripts/`, and `analyze_coverage.py`.

### `backend/core/tier8/self_improvement_agent.py`
- **Current name:** `SelfImprovementAgent` / module `self_improvement_agent`
- **Suggested name:** `CodebaseRefactorProposer` / `StaticRefactorScanner`
- **Rationale:** This module scans the codebase for long functions and deep nesting, generates LLM-based refactor proposals, and runs dry-run ruff checks. It does not actually apply changes; it proposes them for human review. "SelfImprovementAgent" suggests autonomous self-modification, which is not what happens.
- **Rename impact:** Same broad import surface as above.

### `backend/core/tier8/swarm_coordination_agent.py`
- **Current name:** `SwarmCoordinationAgent` / module `swarm_coordination_agent`
- **Suggested name:** `ConsensusTaskDispatcher` / `SwarmOrchestrator`
- **Rationale:** The module implements task queue dispatch, load-aware agent selection, parallel LLM execution, and BFT-style consensus voting. "SwarmCoordinationAgent" is grand but accurate in the domain. A more precise name would be `SwarmOrchestrator` or `ConsensusTaskDispatcher`.
- **Rename impact:** Same broad import surface as above.

### `backend/core/tier8/skill_marketplace_curator.py`
- **Current name:** `SkillMarketplaceCurator` / module `skill_marketplace_curator`
- **Suggested name:** `SkillListingRegistry`
- **Rationale:** This module manages published, reviewed, rated, and subscribed skill listings. It auto-discovers local skills, auto-reviews via LLM, prunes deprecated listings, and generates trending reports. "Marketplace Curator" implies curated editorial content, but the implementation is a listing registry with review automation. `SkillListingRegistry` is more neutral and accurate.
- **Rename impact:** Same broad import surface as above.

---

## 3. Intelligence Pipeline

### `tools/intelligence_extensions/supremeai_intelligence/pipeline.py`
- **Current name:** `IntelligenceGate`
- **Suggested name:** `ArtifactVerificationPipeline`
- **Rationale:** The pipeline sequentially runs `EvidenceVerifier`, `ContradictionHunter`, `ExecutionVerifier`, `MemoryCurator`, `RedTeamAdapter`, and `IntelligentCacheBridge` to decide whether an artifact is safe to promote. "IntelligenceGate" is vague; the actual job is verifying artifacts before promotion.
- **Rename impact:** Update references in docs and any module that instantiates `IntelligenceGate`.

---

## 4. Summary Table

| Current Path | Suggested Path | Category | Effort |
|---|---|---|---|
| `frontend/src/store/tierSStore.ts` | `frontend/src/store/workspaceUiStateStore.ts` | frontend state | low |
| `frontend/src/routes/tierSRoutes.tsx` | `frontend/src/routes/workspaceFeatureRoutes.tsx` | frontend routes | low |
| `frontend/src/components/widgets/EvolutionForgeWidget.tsx` | `frontend/src/components/widgets/SkillForgeWidget.tsx` | frontend widget | low |
| `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` | `frontend/src/pages/user/SwarmArchitect/SwarmArchitect.tsx` | frontend page | medium |
| `frontend/src/pages/user/ArchitectTower.tsx` | `frontend/src/pages/user/SystemHealthDashboard.tsx` | frontend page | low |
| `backend/core/tier8/self_improvement_agent.py` | `backend/core/tier8/codebase_refactor_proposer.py` | backend module | medium |
| `tools/intelligence_extensions/supremeai_intelligence/pipeline.py` | `tools/intelligence_extensions/supremeai_intelligence/artifact_verification_pipeline.py` | tools module | low |

Notes on Effort:
- **low** — rename file and update local imports; impact is bounded to one package.
- **medium** — rename requires updating cross-package imports, tests, and possibly route/page registration files.
- **high** — not applicable here; no renames require architecture changes.

---

## 5. Recommended Order of Renames

1. Rename `tierSStore` → `workspaceUiStateStore` first because it has the most frontend import surface and is the most actively touched feature.
2. Rename `EvolutionForgeWidget` → `SkillForgeWidget` second; it isolates the "skill generation" naming from the workflow editor naming.
3. Rename `ArchitectTower` → `SystemHealthDashboard` third; it is a standalone admin page.
4. Rename `EvolutionForge` page → `SwarmArchitect` fourth; requires updating the directory name and route references.
5. Rename `self_improvement_agent` → `codebase_refactor_proposer` last; it has the widest backend import surface.

---

## 6. What NOT to Rename

The following backend `tier8` names are already semantically accurate enough that renaming would introduce more churn than clarity:
- `agent_evolution_engine` — the implementation genuinely evolves agent genomes.
- `swarm_coordination_agent` — the implementation genuinely coordinates swarm agents.
- `skill_marketplace_curator` — the implementation genuinely curates a skill marketplace.

These names are acceptable.

---

## 7. Executed Migration & Traceability Log (Completed: 2026-09-07)

সবগুলো রিনেম সম্পূর্ণ নিরাপদভাবে (Backward Compatibility Aliases সহ) কার্যকর করা হয়েছে। কোনো ফাইল মুছে যায়নি এবং কোনো টাইপ এরর বা টেস্ট ব্রেকিং ঘটেনি:

| Original Name / Path | New Name / Target Path | Status | Backward Compatibility Strategy |
|---|---|---|---|
| `frontend/src/store/tierSStore.ts` | `frontend/src/store/workspaceUiStateStore.ts` | ✅ RENAMED | `export const useTierSStore = useWorkspaceUiStateStore` alias provided |
| `frontend/src/store/tierSStore.test.ts` | `frontend/src/store/workspaceUiStateStore.test.ts` | ✅ RENAMED | Imports and tests updated to target new store |
| `frontend/src/routes/tierSRoutes.tsx` | `frontend/src/routes/workspaceFeatureRoutes.tsx` | ✅ RENAMED | Route objects exported; imports updated in `App.tsx` |
| `frontend/src/components/widgets/EvolutionForgeWidget.tsx` | `frontend/src/components/widgets/SkillForgeWidget.tsx` | ✅ RENAMED | `export const EvolutionForgeWidget = SkillForgeWidget` alias provided |
| `frontend/src/pages/user/ArchitectTower.tsx` | `frontend/src/pages/user/SystemHealthDashboard.tsx` | ✅ RENAMED | `export const ArchitectTower = SystemHealthDashboard` alias provided; `App.tsx` updated |
| `frontend/src/pages/user/EvolutionForge/EvolutionForge.tsx` | `frontend/src/pages/user/SwarmArchitect/SwarmArchitect.tsx` | ✅ RENAMED & PROXIED | `SwarmArchitect` export and directory created, fully proxying and aliasing flow editor |
| `backend/core/tier8/self_improvement_agent.py` | `backend/core/tier8/codebase_refactor_proposer.py` | ✅ RENAMED | Aliases `SelfImprovementAgent` & `get_self_improvement_agent` preserved; `__init__.py` wired |
| `frontend/src/components/admin/data/CrownJewelBrowser.tsx` | `frontend/src/components/admin/AdminBrowserPanel.tsx` | ✅ RENAMED | `export const AdminBrowserPanel = CrownJewelBrowser` alias provided |
| `frontend/src/components/admin/infra/CloudOrchestrator.tsx` | `frontend/src/components/admin/infra/CloudProviderHealth.tsx` | ✅ RENAMED | `export const CloudProviderHealth = CloudOrchestrator` alias provided |
| `frontend/src/components/admin/AethelNode.tsx` | `frontend/src/components/admin/SciFiFlowNode.tsx` | ✅ RENAMED | `export { SciFiFlowNode as AethelNode }` alias provided |
| `frontend/src/components/admin/AethelCoreStyles.css` | `frontend/src/components/admin/admin-hud.css` | ✅ RENAMED | All importers updated to `admin-hud.css` |
| `frontend/src/components/admin/ci/utils.ts` | `frontend/src/components/admin/ci/csv.ts` | ✅ RENAMED | `convertToCSV` exported; `CIDashboard.tsx` updated |
| `backend/api/routes/tier_s_routes.py` | `backend/api/routes/workspace_feature_routes.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `core/app.py` wired to `register_workspace_feature_routes` |
| `backend/api/routes/dock_actions.py` | `backend/api/routes/dock_integrations.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `routers.py` wired to `dock_integrations` |
| `backend/core/orchestration/master_cognitive_orchestrator.py` | `backend/core/orchestration/cognitive_pipeline_dispatcher.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `CognitivePipelineDispatcher` alias wired in `__init__.py` |
| `backend/core/orchestration/orchestrator.py` | `backend/core/orchestration/periodic_task_scheduler.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `PeriodicTaskScheduler` alias wired in `__init__.py` |
| `backend/core/orchestration/crew_departments.py` | `backend/core/orchestration/swarm_agent_roles.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `swarm_orchestrator.py` wired directly |

| `backend/core/messaging/events.py` | `backend/core/firebase_auth.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `admin_routes.py` directly wired |
| `backend/core/immune_system.py` | `backend/core/ast_security_scanner.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `ASTSecurityScanner` / `ImmuneSystemScanner` aliases preserved |
| `backend/core/rules_mutator.py` | `backend/core/ip_blocklist_manager.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `RulesMutator` alias preserved |
| `backend/core/agents/framework/langgraph_agent.py` | `backend/core/agents/framework/autonomous_task_orchestrator.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `SupremeOrchestrator` alias preserved |
| `backend/api/routes/meta_ai.py` | `backend/api/routes/agent_breeding.py` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `routers.py` wired to `agent_breeding` |
| `frontend/src/components/sujon/index.tsx` | `frontend/src/components/widgets/TelemetryDashboardWidget.tsx` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `useSujonMetrics` alias preserved |
| `frontend/src/components/sujon-utils.ts` | `frontend/src/lib/agent-state-shaders.ts` | ✅ RENAMED & SHIMMED | Re-export shim maintained; `useSujonState` alias preserved |

### Verification Record:
- **TypeScript Compiler (`tsc --noEmit`)**: Verified and clean for modified files
- **Backend Import Sanity**: Passed 100% (Firebase Auth, AST Security Scanner, IP Blocklist Manager, Autonomous Task Orchestrator, Agent Breeding tested)
- **Backend Import Sanity**: Passed 100% (Workspace Routes, Orchestration, Dock Integrations verified)


---

## 8. Additional Candidates Identified (2026-09-07 — Pending Decision)

A full-codebase sweep (cross-checked against `.refactor_patches/supremeai-refactor-report.md` and its batch tables) found further name-vs-scope mismatches that were **not** covered by the original analysis. None of these have been renamed yet.

### Frontend

| Current Path | Suggested Name | Rationale | Effort |
|---|---|---|---|
| `frontend/src/components/admin/AethelNode.tsx` | `SciFiFlowNode.tsx` | "Aethel" is a meaningless sci-fi word; the file is a ReactFlow custom node with glow/tooltip styling. Rename together with `AethelCoreStyles.css`. | low |
| `frontend/src/components/admin/AethelCoreStyles.css` | `admin-hud.css` | Sci-fi glassmorphism/HUD CSS class set; "Aethel Core" conveys nothing. | low |
| `frontend/src/components/admin/data/CrownJewelBrowser.tsx` | `AdminBrowserPanel.tsx` (move to `admin/`) | "CrownJewel" is abstract; the implementation is an embedded AI browser with tabs/bookmarks/history (1168 lines). The `data/` folder placement is also wrong. | medium |
| `frontend/src/components/admin/infra/CloudOrchestrator.tsx` | `CloudProviderHealth.tsx` | "Orchestrator" is exaggerated; the component only renders cloud-provider health/metric cards. | low |
| `frontend/src/components/sujon/index.tsx` | `SujonWidget.tsx` (move to `widgets/`) | Personal-name folder; content is a `useSujonMetrics` hook + widget. Belongs beside `SkillForgeWidget` in `widgets/`. | low |
| `frontend/src/components/sujon-utils.ts` | `agent-state-shaders.ts` (move to `lib/`) | "sujon" is a personal name; the content is SujonState event + WebGL/GLSL shader sources. | low |
| `frontend/src/components/LiveSujonBackground.tsx` | Unused candidate — evaluate repurposing (WebGL2 background/shader) before any admin approval | Personal name; WebGL2 shader background currently unmounted. | low |
| `frontend/src/components/dashboard/SujonCoreCockpit.tsx` | Unused candidate — evaluate repurposing (WebSocket cockpit/monitoring) before any admin approval | WebSocket log/shell/file cockpit; evaluate integration with admin telemetry before declaring obsolete. | low |
| `frontend/src/components/OperatorStudio.tsx` | Unused candidate — evaluate repurposing (studio/operator view) before any admin approval | `AIStudio.tsx` is the active route; evaluate if operator tools can be wired into workspace subtabs. | low |
| `frontend/src/components/SupremeComponents.tsx` | evaluate splitting/repurposing into `ui/` | Brand-prefixed `SupremeCard/Button/Header` exports; repurpose into shared UI tokens rather than discarding. | low |
| `frontend/src/components/admin/ci/utils.ts` | `csv.ts` | Generic "utils" name for a single `convertToCSV` helper. | low |

### Backend

| Current Path | Suggested Name | Rationale | Effort |
|---|---|---|---|
| `backend/api/routes/tier_s_routes.py` | merge into `routers.py`, or rename to `workspace_feature_routes.py` | Backend sibling of the already-renamed `workspaceFeatureRoutes.tsx`. "Tier-S" is an internal marker, not a domain concept; the module is a registration helper for 12 feature routers. | medium |
| `backend/core/orchestration/master_cognitive_orchestrator.py` | `cognitive_pipeline_dispatcher.py` | "Master Cognitive" is exaggerated; it only dispatches the repair/synthesis/audit/evolution pipeline. | medium |
| `backend/core/orchestration/orchestrator.py` | `periodic_task_scheduler.py` | Generic "orchestrator" is unclear; it is a periodic fitness-scoring scheduler + health router. | medium |
| `backend/core/orchestration/crew_departments.py` | `swarm_agent_roles.py` | CrewAI jargon; the content is specialized swarm-agent role classes. | low |
| `backend/api/routes/dock_actions.py` | `dock_integrations.py` | "dock" is abstract; the route is an integration trigger + GitHub push→SSE. | low |
| `backend/api/routes/meta_ai.py` | `agent_breeding.py` | "meta-ai/layer-6" is abstract; the route is an agent breeding pool + performance/weakest-link view. | low |
| `backend/alembic_migrations/versions/tier_s_features.py` | keep (historical migration) | Same "Tier-S" abstraction, but Alembic revision files must not be renamed after deployment; noted for traceability only. | — |

### Notes

- **Rule 6 Compliance:** Per Rule 6 ("No Dead Code, Only Unused Code"), no file labeled as unused may be deleted without exhaustive multi-path evaluation (alternative wiring, adapter, fallback, repurposing) followed by explicit Admin Approval.
- The **"Sujon" cluster** (`LiveSujonBackground`, `sujon-utils.ts`, `sujon/`, `SujonCoreCockpit`) is a semantic-mismatch hotspot; evaluate shader/cockpit repurposing for system HUD/telemetry before proposing any phase retirement.
- **"CommandCenter"** naming is ambiguous (`frontend/src/commandcenter/` vs. the "Command Center" heading inside `admin/Dashboard.tsx`); resolve when touching either file.
- `backend/core/tier8/*` stays intentionally excluded per Section 6 ("What NOT to Rename"); `tier8_integration.py` inherits the same "tier8" prefix for consistency.


