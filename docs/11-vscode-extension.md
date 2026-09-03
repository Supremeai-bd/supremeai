# 11 — VS Code Extension

`tools/vscode-extension/` — **supremeai-vscode v6.0.0**, publisher `supremeai`, displayName "SupremeAI - AI-Powered Development Assistant". MIT licensed, engines `vscode ^1.85.0`, activation `*`, esbuild-bundled to `out/extension.js` (~328 KB VSIX per changelog).

## Design Philosophy: Thin Client

The extension ships **no client-side LLM keys**. `src/ai/AIService.ts` documents the policy explicitly: all AI orchestration runs through the SupremeAI backend (`supremeai.backendUrl`, fallback `https://supremeai-worker.paykaribazaronline.workers.dev`), with offline failover to a local **Ollama** (`http://localhost:11434/api/chat`). Backend cold starts (Render free tier can take 60+ s) are tolerated via a 5-second `Promise.race` on auth init and automatic guest login.

## Contributed Commands (31, category "SupremeAI")

**Auth:** `login`, `loginAsGuest`, `logout`
**Chat & AI:** `openChat`, `sendMessageToChat`, `aiComplete`, `aiExplain`, `aiReview`, `generateCode`, `suggestRefactoring`, `performSecurityScan`, `analyzePerformance`, `aiComplete`
**Analysis:** `analyzeCodeFlow`, `resolveError`, `showSecurityIssues`, `showDependencies`, `showDependencyGraph`, `showArchitectureMap`, `showFlowChart`, `visualizeCode`, `refreshCodeFlow`
**Swarm:** `swarmPipeline` ("Run Swarm Pipeline (SupremeAI + detected AIs)"), `trioPipeline` ("Run Trio Pipeline (Gemini → Kilo → Cline)")
**Feedback & learning:** `acceptSuggestion`, `rejectSuggestion`, `sendFeedback`, `reportError`, `forceLearn`
**Misc:** `createProject`, `viewHistory`, `openExtensionSettings`

Editor context-menu items: resolveError, aiExplain, aiReview, sendMessageToChat, analyzeCodeFlow, performSecurityScan, analyzePerformance.

## Views & Theming

Activity-bar container `supremeai-sidebar` (`$(sparkle)` icon) with webviews: `supremeaiChat`, `supremeaiDependencyGraph`, `supremeaiArchitectureMap`, `supremeaiFlowChart`, `supremeaiSecurityIssues`, `supremeaiPerformanceInsights`, `supremeaiAdminDashboard` (visible when `supremeai.authenticated && supremeai.isAdmin`), `supremeaiCustomerDashboard` ("User Settings"). Theme "SupremeAI Dark" is generated from `@supremeai/design-tokens/outputs/vscode/supremeai-theme.json`.

## Configuration (`supremeai.*`, 13 properties)

| Setting | Default | Purpose |
|---------|---------|---------|
| `backendUrl` | worker URL fallback | SupremeAI backend base URL |
| `aiApiKey` | — (SecretStorage) | API key, stored in VS Code SecretStorage (`supremeai.aiApiKey`) |
| `aiModel` | `supreme-large` | Model preference |
| `codegeex4.enabled` / `codegeex4.model` | true / `codegeex-4` | CodeGeeX integration |
| `enableRealTimeLearning` | true | Learning loop participation |
| `autoReportErrors` | true | Error telemetry |
| `enableCodeFlow` | true | Code-flow visualization |
| `autoAnalyzeOnSave` | false | Save-triggered analysis |
| `inlineCompletionDebounce` | 800 ms (100–2000) | Inline completion delay |
| `swarmBackendUrl` | `http://localhost:8080` | Swarm/trio pipeline backend |
| `enableAgentDetection` | false | Detect nearby AI extensions (CrossAiObserverService) |
| `performanceMode` | `balanced` | `balanced \| powerful \| efficient` |

## Architecture (`src/`)

```mermaid
flowchart TB
    EXT[extension.ts activate] --> AUTH[AuthService<br/>SecretStorage + guest login]
    EXT --> AI[AIService · CodeGenerationService · CodeReviewService · ContextBuilder]
    EXT --> CHAT[Chat + Dashboard webviews<br/>SupremeAIChatProvider · StreamingChatProvider]
    EXT --> SW[SwarmPipelineProvider<br/>POST /api/v1/ide-trio/execute]
    EXT --> ACA[AutonomousCodingAgent<br/>thin client → OpenHands agent-server]
    EXT --> H[Handlers: Auth · CodeEdit · Error · Feedback · CodeFlow · Visualization]
    EXT --> PERF[PerformanceMonitor · TerminalActivitySensor]
    AUTH & AI & CHAT & SW & H --> BRIDGE[SupremeAIService<br/>@supremeai/shared-services]
    BRIDGE --> API[(SupremeAI backend)]
```

- **`services/AuthService.ts`** — singleton; token in SecretStorage; sets context `supremeai.authenticated`; `onAuthStateChanged` event; OAuth via URI handler (`AuthHandler.registerAuthCallback`).
- **`services/SwarmPipelineProvider.ts`** — posts to `{swarmBackendUrl}/api/v1/ide-trio/execute` running **GeminiWriter → KiloReviewer → ClineChecker**; uses `agentDetector` SwarmState; offline rule-based review fallback; output channel "SupremeAI Swarm".
- **`services/AutonomousCodingAgent.ts`** — "OpenHands-type" thin client controlling a self-hosted OpenHands agent-server REST API; disabled by default ($0 philosophy); results `status: ok|skipped|error`, `engine: upstream|fallback`.
- **`ai/`** — `AIService` (thin-client policy), `CodeGenerationService`, `CodeReviewService` (`reviewCode()` → `CodeReviewIssue[]` with heuristic fallback), `ContextBuilder` (language, filePath, open files, selection, cursor, imports/exports/dependencies), `EnhancedAIService`.
- **`providers/`** — chat, sidebar, activity, admin/customer dashboards, `CodeFlowPanel`, `BrowserPreviewProvider`, `DependencyGraphProvider`, `SupremeAIActionProvider`, inline-completion provider (debounced).
- **`ui/HealingStatusBar.ts`** — status-bar self-healing indicator; **`ui/JitOtpDialog.ts`** — JIT-OTP elevation UI (paired with `ScopeGuardService` from shared-services).
- **`performance/`** — `PerformanceMonitor`, `TerminalActivitySensor`; **`utils/`** — `DynamicSignatureRegistry`, `BaseDisposable`, logger; **`adapters/VsCodePlatformAdapter.ts`** — maps the `vscode` API onto shared-services platform interfaces.

## Build, Test, Package

```bash
cd tools/vscode-extension
pnpm install
pnpm compile          # tsc -p ./
pnpm watch            # dev loop
pnpm build            # esbuild bundle → out/extension.js (scripts/build.mjs)
pnpm test             # vitest run (pretest compiles)
pnpm lint             # eslint src
pnpm package:vsix     # npx @vscode/vsce package --no-dependencies --skip-license
```

Debug: press **F5** (Extension Development Host). Tests use `vitest.config.ts` (node env, `vscode` aliased to `test/mocks/vscode.ts`, v8 coverage) — suites: `auth-service.test.ts`, `supremeai-service.test.ts`, `ScopeGuardService.test.ts`, `autonomous-coding-agent.test.ts`.

## Docs & Localization

The extension is the most bilingual part of the repo: `README_BANGLA.md`, `README_BN.md`, `ARCHITECTURE_BN.md`, `INTEGRATION_GUIDE_BN.md`, `package.nls.bn.json` (Bengali command titles). `CHANGELOG.md` 6.0.0 highlights: JIT OTP Security Shield, DeepSeek-V3 & Kimi K2.5 smart routing, Bengali NLS, debounced diagnostics.

## Known Quirks

- **Stray Java files** in the extension root (`AdminMetricsController.java`, `FeatureRegistryService.java`, `GlobalMetrics*.java`, `CodebaseAuditService.java`, `FeatureRegistryController.java`, `FeatureDefinition.java`) — not part of the extension build; likely misplaced backend scaffolding.
- `scripts/build.mjs` implements a custom pnpm-store resolution for `openai` — if dependency resolution fails during bundling, check that path first.
- eLai Code references (`apps/docs/docs/elai-code-extension-reference.md`) describe a related analysis surface; the shipped extension is supremeai-vscode v6.
