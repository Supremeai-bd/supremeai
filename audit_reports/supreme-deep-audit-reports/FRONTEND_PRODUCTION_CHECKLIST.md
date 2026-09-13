# SupremeAI Frontend Production Checklist

Use this checklist against the deployed frontend bundle, not only local development. Record `PASS`, `FAIL`, `BLOCKED`, or `N/A`, plus evidence for every failure or blocked item.

## 1. Test record

- Environment: Production / staging
- Frontend URL:
- Backend URL:
- Commit/build:
- Browser/device:
- Tester/date:

## 2. Build and configuration

- [ ] Production build completes with no warnings that hide failures.
- [ ] The deployed bundle contains the intended API and WebSocket base URLs.
- [ ] No production bundle references localhost, staging hosts, test keys, or debug endpoints.
- [ ] Required build-time variables are validated before deployment.
- [ ] Public variables contain no secrets.
- [ ] Frontend, backend, proxy, and WebSocket origins use the same HTTPS deployment contract.

## 3. Guest experience

- [ ] `/` loads on a hard refresh and in a private window without authentication.
- [ ] Public navigation works for chat, models, features, pricing, docs, about, and contact.
- [ ] Sign-in and registration links reach the intended routes.
- [ ] Mobile menu, browser back/forward, loading, empty, and error states work.
- [ ] Guest chat handles empty submit, Enter, Shift+Enter, long text, Bangla, emoji, rapid submits, scrolling, and refresh.
- [ ] Guest model selection is verified as either backend-affecting or presentation-only.
- [ ] Attachment and tools CTAs either work for guests or clearly request authentication.

## 4. Authentication and authorization

- [ ] Registration validates required fields, invalid email, weak password, mismatch, and duplicate account.
- [ ] Login handles invalid credentials, refresh, expiry, logout, and safe redirect behavior.
- [ ] Protected routes redirect unauthenticated users.
- [ ] Browser Back after logout does not expose private data.
- [ ] Customer cannot access another user's projects, files, conversations, keys, or settings.
- [ ] Admin routes deny guests and customers and enforce role/permission checks.
- [ ] Admin step-up authentication, OTP/TOTP failure, expiry, and audit behavior are verified.

## 5. Authenticated customer journeys

- [ ] Workspace shell, sidebar, mobile navigation, modals, toasts, route state, and error boundaries work.
- [ ] Chat supports streaming, cancellation, markdown, code blocks, regeneration, new conversations, history, multi-turn context, model switching, provider failure, and rate limits.
- [ ] Projects support create, rename, reopen, delete confirmation, persistence, and isolation.
- [ ] Files support upload, download, delete, invalid/large-file handling, and chat attachment context.
- [ ] Agents support create, configure, run, cancel, failure recovery, and history.
- [ ] IDE supports explorer, open/edit/save, tabs, Monaco, AI assistance, and defined refresh behavior.
- [ ] Integrations support connect, invalid credential, disconnect, reconnect, provider failure, and masked secrets.
- [ ] Research, memory, scheduled tasks, usage, billing, profile, settings, API keys, swarm, marketplace, and runs verify persistence and permissions where enabled.
- [ ] Memory is proven to affect a later conversation; UI presence alone is not sufficient.

## 6. Network and API contract

- [ ] Browser requests use the production API and never localhost or staging.
- [ ] HTTPS is used for API, WebSocket, SSE, uploads, and callbacks.
- [ ] CORS preflight succeeds for the deployed origin and required headers.
- [ ] `Authorization`, `X-CSRF-Token`, `X-JIT-OTP`, `X-Device-Fingerprint`, `X-Request-ID`, and `X-Correlation-ID` are sent only where required.
- [ ] 401, 403, 404, 409, 429, 500, timeout, and network-offline responses map to usable UI states.
- [ ] Streaming/WebSocket connections open, close, cancel, reconnect, and recover without duplicate mutations.
- [ ] Request bodies, methods, paths, and response shapes match the backend contract.
- [ ] Secrets never appear in rendered HTML, client logs, analytics payloads, or error messages.

## 7. Responsive and accessibility checks

- [ ] 320px, 375px, 414px, tablet, desktop, and large desktop layouts have no unintended overflow.
- [ ] Keyboard navigation, visible focus, modal escape, labels, form errors, and screen-reader names work.
- [ ] Long usernames, filenames, prompts, code blocks, and AI responses do not corrupt layout.
- [ ] Loading, empty, success, error, and destructive confirmation states are understandable.
- [ ] Supported theme behavior is consistent.
- [ ] Chrome, Firefox, Edge, Safari desktop, Chrome Android, and Safari iPhone receive a smoke pass or are explicitly marked unsupported.

## 8. Critical end-to-end journeys

- [ ] Guest → chat → signup → workspace.
- [ ] Guest → chat → login → saved work.
- [ ] Customer → chat → file → AI analysis.
- [ ] Customer → project → files → agent.
- [ ] Customer → IDE → AI → save.
- [ ] Customer → research → result → save.
- [ ] Customer → memory → new chat.
- [ ] Customer → scheduled task → execution.
- [ ] Admin → login → step-up → dashboard.
- [ ] Admin → user/role change → restriction verification.
- [ ] Admin → MCP → health → connection.
- [ ] Logout → protected URL and User A/B isolation.

## 9. Release gate

- [ ] Frontend lint, typecheck, tests, and production build pass.
- [ ] QA contract and route/config drift checks pass.
- [ ] Deployed bundle and live browser network inspection pass.
- [ ] No unresolved P0/P1 frontend defect.
- [ ] Blocked live checks are recorded in `MANUAL_STEPS.m` with owner, procedure, evidence, and rollback impact.

**Decision:** GO / NO-GO
**Evidence links:**
**Known non-blocking issues:**
**Release owner:**

> This checklist confirms frontend readiness only. Production readiness also requires backend, infrastructure, security, privacy, backup/restore, rollback, and operational sign-off.

---

## Evidence record

| Check/ID | Result | Evidence | Owner | Follow-up |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |
