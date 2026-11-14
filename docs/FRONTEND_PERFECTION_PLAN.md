# Frontend Perfection Implementation Plan

**Scope:** supremeai-frontend (https://github.com/Supremeai-bd/supremeai-frontend) vs SupremeAI gateway backend (F:\supremeai\gateway).  
**Goal:** Eliminate 404/403 on live, remove mock-only calls, add tests/i18n/a11y/perf, verify live endpoints.

## Phase 0 — Baseline & contract
- [ ] Freeze frontend commit SHA; record backend commit SHA
- [ ] Export frontend endpoint list (85) and backend route list (113); generate diff in CI
- [ ] Add contract test: every frontend `/api/*` call must exist in backend route table (or be explicitly allowlisted as CF-function)
- Acceptance: diff report committed; failing endpoints listed

## Phase 1 — Critical live 404/403 fix (P0)
- [ ] Verify backend routes `/api/v1/hitl/pending`, `/api/platform/config`, `/api/mcp-tower/services`, `/api/v1/stream/hitl` deployed on Render
- [ ] Set `SUPREMEAI_BACKEND_URL` on Cloudflare Pages to current Render URL
- [ ] Redeploy frontend; re-test 4 endpoints (expect 200/401, not 404)
- [ ] Migrate `/api/chat` → `/api/v1/stream/chat`; remove `/api/chat/title` (use backend or client-side title gen)
- Acceptance: 0 404 on critical endpoints in smoke test

## Phase 2 — Backend route coverage (decision per endpoint)
For each of 85 missing endpoints choose: IMPLEMENT in backend OR REMOVE from frontend.
- [ ] Admin/control-plane (30+): either implement minimal read-only proxies to existing admin data or remove admin views from frontend (recommend: keep views but back with `/api/admin/*` minimal endpoints)
- [ ] User data (knowledge, webhooks, api-keys, projects, graph): implement backend CRUD or remove UI
- [ ] Billing/usage: implement wallet/summary/history/add-funds or hide billing UI
- [ ] Customers, research, share, browser automation, workspace terminal, agent-swarm stream, avatar analyze: implement or remove
- [ ] MCP tower proxy endpoints: map to existing `/api/mcp-tower/*` (probe/reboot already partial)
- [ ] TTS/transcribe/avatar: keep as CF functions (document allowlist)
- Acceptance: frontend endpoint list subset of backend routes + allowlist; no 404

## Phase 3 — Remove mock-only behavior
- [ ] Set `VITE_USE_MOCK=false` in production env
- [ ] Remove `mockDataManager` fallbacks from services (customerService, mockDataSyncService)
- [ ] Replace mock data with empty-state + retry UI
- Acceptance: no mock data shown in production build; `grep mock` count < 20

## Phase 4 — Auth & session
- [ ] Implement `/api/auth/verify-2fa` in backend or remove 2FA UI
- [ ] Add token refresh + 401 redirect to login
- [ ] Guest mode gating for admin tools
- Acceptance: login/logout/2FA flow passes manual test

## Phase 5 — i18n
- [ ] Audit all JSX for hardcoded English strings
- [ ] Add keys to `src/utils/i18n.ts` for en + bn
- [ ] Use `useI18n()` uniformly; Bengali directive for AI responses
- Acceptance: no hardcoded user-facing English in components; language toggle works offline

## Phase 6 — Error/loading/accessibility/perf
- [ ] Add ErrorBoundary + skeleton + retry to every view
- [ ] Lazy-load 3D avatar (Three.js/tfjs) via dynamic import
- [ ] Run Lighthouse + axe; fix critical a11y issues
- [ ] Code-split heavy chunks; target bundle < 5s build
- Acceptance: Lighthouse a11y >= 90; build < 5s

## Phase 7 — Testing
- [ ] Service unit tests (vitest) for apiClient, authService, chatService
- [ ] Component tests for critical views
- [ ] E2E (Playwright) for chat send, login, language toggle
- [ ] Contract test in CI (Phase 0)
- Acceptance: `npm test` green; coverage >= 60% on services

## Phase 8 — Deploy verification
- [ ] CI smoke: fetch all frontend endpoints against live, assert no 404
- [ ] Update Cloudflare Pages env + Render deploy
- [ ] Document runbook in frontend README
- Acceptance: smoke test green in CI; live endpoints 200/401

## Risks
- Large backend implementation scope; mitigate by removing unused admin UI first
- Mock removal may break demos; keep mock behind dev flag only
- 3D avatar perf on low-end devices

## Definition of Done
- Live frontend has 0 404 on documented endpoints
- `npm run build` < 5s, 0 errors
- `npm test` all green
- i18n bn/en complete for user-facing strings
- Lighthouse a11y >= 90