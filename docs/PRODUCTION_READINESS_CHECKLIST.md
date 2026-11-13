# SupremeAI — Production Readiness Checklist

> Format: `[ ]` = Not checked yet | `[x]` = Passed | `[!]` = Failed — reason noted

---

## A. Infrastructure & Service Health

| # | Check Item | Status | Note |
|---|---|---|---|
| A1 | Render Primary (Core API) — service healthy | `[!]` Failed | `update_failed` — degraded, redeploy needed |
| A2 | Render CI Runner — response latency normal | `[!]` Failed | Latency `null` — runner response unverified |
| A3 | Cloudflare Edge Mesh — latency < 400ms | `[!]` Failed | 1632ms detected — edge worker check needed |
| A4 | Worker service — healthy | `[x]` Passed | |
| A5 | Scraper service — healthy | `[x]` Passed | |
| A6 | MCP service — healthy | `[x]` Passed | |
| A7 | API Shield — healthy | `[x]` Passed | |
| A8 | Brain service — healthy | `[x]` Passed | |
| A9 | Supabase — healthy | `[x]` Passed | |
| A10 | Redis — PONG response confirmed | `[x]` Passed | |
| A11 | Infisical secrets — reachable | `[x]` Passed | |
| A12 | Kaggle pool — healthy | `[x]` Passed | |
| A13 | Telegram bot — healthy | `[x]` Passed | |

---

## B. Deployment Parity (Release Gate)

| # | Check Item | Status | Note |
|---|---|---|---|
| B1 | API Gateway SHA — deployed SHA matches repo HEAD | `[!]` Failed | `5386e64 ≠ d4c273d` — redeploy to `d4c273d` |
| B2 | Core service — parity verified | `[x]` Passed | |
| B3 | MCP service — parity verified | `[x]` Passed | |
| B4 | Worker service — parity verified | `[x]` Passed | |
| B5 | Scraper service — parity verified | `[x]` Passed | |
| B6 | Brain service — parity verified | `[x]` Passed | |
| B7 | Monorepo SSOT — satellites archived/read-only | `[ ]` | Confirm all satellite repos archived |
| B8 | Re-audit: release gate PASSED | `[ ]` | Blocked by B1 |

---

## C. Authentication & User Accounts

| # | Check Item | Status | Note |
|---|---|---|---|
| C1 | Signup flow (Supabase Auth + Firebase) — E2E | `[ ]` | |
| C2 | Login flow — E2E | `[ ]` | |
| C3 | SSO login — works | `[ ]` | |
| C4 | Session refresh — works | `[ ]` | |
| C5 | Logout — invalidates session | `[ ]` | |
| C6 | Onboarding flow (adaptive_onboarding flag ON) | `[ ]` | |
| C7 | Profile routes — save/update verified | `[ ]` | |
| C8 | Preferences routes — save/update verified | `[ ]` | |
| C9 | API keys — generate works | `[ ]` | |
| C10 | API keys — revoke works | `[ ]` | |
| C11 | API keys — scoping enforced | `[ ]` | |

---

## D. Chat & AI Interface

| # | Check Item | Status | Note |
|---|---|---|---|
| D1 | Chat — send message, receive response | `[ ]` | |
| D2 | Chat — history persists | `[ ]` | |
| D3 | Chat — branch conversations | `[ ]` | |
| D4 | SSE streaming chat — works | `[ ]` | |
| D5 | swarm_stream — works | `[ ]` | |
| D6 | Chat search — works | `[ ]` | |
| D7 | Chat export — works | `[ ]` | |
| D8 | File upload in chat (chat_upload.py) | `[ ]` | |
| D9 | Voice: WebSocket voice route — real call test | `[ ]` | |
| D10 | Deep research route — works | `[ ]` | |
| D11 | Reasoning route — works | `[ ]` | |
| D12 | Cognitive route — works | `[ ]` | |
| D13 | meta_ai route — works | `[ ]` | |
| D14 | Prompt templates — render correctly | `[ ]` | |
| D15 | Slash commands — route correctly | `[ ]` | |

---

## E. Agent System

| # | Check Item | Status | Note |
|---|---|---|---|
| E1 | Agent create/edit/delete — works | `[ ]` | |
| E2 | Agent registry — accurate | `[ ]` | |
| E3 | Agent workspace — works | `[ ]` | |
| E4 | Agent tasks — works | `[ ]` | |
| E5 | Agent actions — works | `[ ]` | |
| E6 | Agent breeding — works | `[ ]` | |
| E7 | AI assignment — works | `[ ]` | |
| E8 | Missions: create → state machine → complete (E2E) | `[ ]` | |
| E9 | Task gateway — works | `[ ]` | |
| E10 | Async task router — works | `[ ]` | |
| E11 | Scheduled tasks — works | `[ ]` | |
| E12 | HITL: approval_manager — works | `[ ]` | |
| E13 | HITL: websocket_hitl — works | `[ ]` | |
| E14 | HITL: SSE stream — works | `[ ]` | |
| E15 | Session stream — live monitoring works | `[ ]` | |
| E16 | Session takeover — works | `[ ]` | |

---

## F. Projects, Files & Workspaces

| # | Check Item | Status | Note |
|---|---|---|---|
| F1 | Project CRUD — works | `[ ]` | |
| F2 | task_workspace — works | `[ ]` | |
| F3 | codeflow — works | `[ ]` | |
| F4 | File upload (with upload_validator) — works | `[ ]` | |
| F5 | File download — works | `[ ]` | |
| F6 | Artifacts — persist correctly | `[ ]` | |
| F7 | GitHub repos.py — works | `[ ]` | |
| F8 | GitHub webhooks — HMAC signature verified | `[ ]` | |
| F9 | PR review API — works | `[ ]` | |
| F10 | IDE trio — works | `[ ]` | |
| F11 | code_dependency_graph — builds correctly | `[ ]` | |
| F12 | Markdown tools — works | `[ ]` | |
| F13 | Share route — public link with correct permissions | `[ ]` | |

---

## G. Browser, Scraper & Sandbox

| # | Check Item | Status | Note |
|---|---|---|---|
| G1 | Stealth browser: session_manager — works | `[ ]` | |
| G2 | Stealth browser: vault — works | `[ ]` | |
| G3 | Browser action registry — works | `[ ]` | |
| G4 | Scraper E2E — works | `[ ]` | |
| G5 | selector_healing — works | `[ ]` | |
| G6 | Crawler admin — works | `[ ]` | |
| G7 | Sandbox API — works | `[ ]` | |
| G8 | MicroVM isolation — untrusted code contained | `[ ]` | |
| G9 | IP blocklist manager — active | `[ ]` | |
| G10 | Human behavior simulation — active | `[ ]` | |
| G11 | Internet monitor — works | `[ ]` | |

---

## H. Memory, Knowledge & RAG

| # | Check Item | Status | Note |
|---|---|---|---|
| H1 | Chat memory — persists across sessions | `[ ]` | |
| H2 | global_memory — works | `[ ]` | |
| H3 | Memory MCP — works | `[ ]` | |
| H4 | Knowledge base: index — works | `[ ]` | |
| H5 | Knowledge base: hybrid search — works | `[ ]` | |
| H6 | Knowledge base: semantic search — works | `[ ]` | |
| H7 | Knowledge base: QA — works | `[ ]` | |
| H8 | Feature flag: mem0 ON → premium path | `[ ]` | |
| H9 | Feature flag: mem0 OFF → free fallback | `[ ]` | |
| H10 | Feature flag: graphiti ON → premium path | `[ ]` | |
| H11 | Feature flag: graphiti OFF → free fallback | `[ ]` | |
| H12 | Living brain / living engine — works | `[ ]` | |
| H13 | Cache predictions — works | `[ ]` | |

---

## I. Integrations, MCP & Marketplace

| # | Check Item | Status | Note |
|---|---|---|---|
| I1 | Integrations — connect/disconnect each connector | `[ ]` | |
| I2 | MCP hub — works | `[ ]` | |
| I3 | MCP marketplace — works | `[ ]` | |
| I4 | mcp_tower route — works | `[ ]` | |
| I5 | Skills marketplace — works | `[ ]` | |
| I6 | Plugin submissions — works | `[ ]` | |
| I7 | tools_registry — works | `[ ]` | |
| I8 | n8n webhooks — works | `[ ]` | |
| I9 | CDC webhooks — works | `[ ]` | |
| I10 | CI webhooks — works | `[ ]` | |
| I11 | webhooks_ai — works | `[ ]` | |
| I12 | BYOC API — works | `[ ]` | |
| I13 | Kaggle route — works | `[ ]` | |
| I14 | Cloud mesh — works | `[ ]` | |
| I15 | Mesh mailbox — works | `[ ]` | |
| I16 | Mesh tasks — works | `[ ]` | |

---

## J. Billing, Payments & Tiers

| # | Check Item | Status | Note |
|---|---|---|---|
| J1 | Subscription plan upgrade flow — works | `[ ]` | |
| J2 | Subscription plan downgrade flow — works | `[ ]` | |
| J3 | Payment webhook — verified | `[ ]` | |
| J4 | Escrow service — transaction test passed | `[ ]` | |
| J5 | Usage metrics — accurate | `[ ]` | |
| J6 | Quota enforcement (rate_limit_quota) — active | `[ ]` | |
| J7 | cost_guard — active | `[ ]` | |
| J8 | Tier-S route permissions — enforced | `[ ]` | |

---

## K. Admin Auth & Dashboard

| # | Check Item | Status | Note |
|---|---|---|---|
| K1 | Admin login — works | `[ ]` | |
| K2 | JIT OTP via Discord — works | `[ ]` | |
| K3 | JIT OTP via Email — works | `[ ]` | |
| K4 | JIT OTP Discord fallback to Email — works | `[ ]` | |
| K5 | All admin dashboard pages — load correctly | `[ ]` | |
| K6 | Realtime dashboard — live data showing | `[ ]` | |
| K7 | admin_god (super-admin guard) — enforced | `[ ]` | |
| K8 | Tenant admin — works | `[ ]` | |
| K9 | Access control — enforced | `[ ]` | |
| K10 | admin_decisions — works | `[ ]` | |

---

## L. Admin Operations & Governance

| # | Check Item | Status | Note |
|---|---|---|---|
| L1 | admin_llm — model routing control works | `[ ]` | |
| L2 | admin_routing — works | `[ ]` | |
| L3 | advanced_router — works | `[ ]` | |
| L4 | admin_policies — enforced | `[ ]` | |
| L5 | execution_policies — enforced | `[ ]` | |
| L6 | MCP policy allowlist — active | `[ ]` | |
| L7 | HITL admin — works | `[ ]` | |
| L8 | external_agents_admin — works | `[ ]` | |
| L9 | simulator_admin — works | `[ ]` | |
| L10 | Ecosystem admin — works | `[ ]` | |
| L11 | Crawler admin — works | `[ ]` | |
| L12 | render_preflight_admin — works | `[ ]` | |
| L13 | Maintenance mode — works | `[ ]` | |
| L14 | Healing / healing_stats — active | `[ ]` | |
| L15 | syncguard — active | `[ ]` | |
| L16 | CI dashboard — data showing | `[ ]` | |
| L17 | traffic_monitor — active | `[ ]` | |
| L18 | service_topology — accurate | `[ ]` | |

---

## M. Admin Analytics & Learning

| # | Check Item | Status | Note |
|---|---|---|---|
| M1 | Analytics dashboard — data showing | `[ ]` | |
| M2 | Metrics dashboard — data showing | `[ ]` | |
| M3 | Usage dashboard — data showing | `[ ]` | |
| M4 | admin_evaluation — feedback loop works | `[ ]` | |
| M5 | admin_learning — works | `[ ]` | |
| M6 | merge_learning — feedback recorded | `[ ]` | |
| M7 | Feedback route — user reports reach admin | `[ ]` | |
| M8 | Intelligence insights — works | `[ ]` | |
| M9 | Evolution route — works | `[ ]` | |

---

## N. Studio UI

| # | Check Item | Status | Note |
|---|---|---|---|
| N1 | Login → Dashboard → Chat → Agent → Settings (full user journey) | `[ ]` | |
| N2 | Admin UI: all admin pages load | `[ ]` | |
| N3 | TypeScript typecheck — 0 errors | `[ ]` | |
| N4 | Visual QA — no broken layouts | `[ ]` | |
| N5 | i18n Bengali (bn) — complete | `[ ]` | |
| N6 | i18n English (en) — complete | `[ ]` | |
| N7 | Accessibility — passes | `[ ]` | |
| N8 | Mobile BFF (mobile_bff.py) — mobile view correct | `[ ]` | |

---

## O. Database & Storage

| # | Check Item | Status | Note |
|---|---|---|---|
| O1 | 150 tables schema review — all synced | `[ ]` | |
| O2 | Alembic migrations — synced with schema | `[ ]` | |
| O3 | RLS policies — verified on every user-facing table | `[ ]` | |
| O4 | MinIO/storage — file persistence works | `[ ]` | |
| O5 | Redis cache invalidation — works | `[ ]` | |
| O6 | Redis 5-account rotation — works | `[ ]` | |

---

## P. Security (All Layers)

| # | Check Item | Status | Note |
|---|---|---|---|
| P1 | Gitleaks — zero findings | `[ ]` | |
| P2 | Semgrep — zero findings | `[ ]` | |
| P3 | GitHub secret scanning — zero findings | `[ ]` | |
| P4 | Gateway: prompt injection detection — active | `[ ]` | |
| P5 | Gateway: input sanitization — active | `[ ]` | |
| P6 | Gateway: secret masking — active | `[ ]` | |
| P7 | Gateway: stealth_webhook — tested | `[ ]` | |
| P8 | OTP channel: secret masking in logs — confirmed | `[ ]` | |
| P9 | Error responses: sanitized (no stack traces) | `[ ]` | |
| P10 | Rate limiting — active | `[ ]` | |
| P11 | Circuit breaker — active | `[ ]` | |
| P12 | tool_pruner — active | `[ ]` | |
| P13 | CORS — restricted to allowed origins | `[ ]` | |
| P14 | Auth middleware — protects all private routes | `[ ]` | |
| P15 | Protected paths guard — tested | `[ ]` | |

---

## Q. CI/CD & Deploy Pipeline

| # | Check Item | Status | Note |
|---|---|---|---|
| Q1 | unified-pipeline.yml: 7 PR guards — all green | `[ ]` | |
| Q2 | Python matrix — all pass | `[ ]` | |
| Q3 | Auto-landing (squash merge) — works | `[ ]` | |
| Q4 | Satellite dispatch/sync — works | `[ ]` | |
| Q5 | 4-level runner tier failover — tested | `[ ]` | |
| Q6 | Bridge intake: work_claim → patch → gated PR (E2E) | `[ ]` | |
| Q7 | Zero-residue auto-prune — confirmed | `[ ]` | |

---

## R. Monitoring, Alerts & Testing

| # | Check Item | Status | Note |
|---|---|---|---|
| R1 | Telemetry — active | `[ ]` | |
| R2 | performance_metrics — collecting | `[ ]` | |
| R3 | Grafana dashboard — data showing | `[ ]` | |
| R4 | Telegram alert bot — incident notification delivered | `[ ]` | |
| R5 | Full pytest suite — green | `[ ]` | |
| R6 | Evals suite — green | `[ ]` | |
| R7 | Adversarial suite — green | `[ ]` | |
| R8 | Coverage threshold — met | `[ ]` | |

---

## S. Cost, Docs & Final Gate (Part 1 — Routes Not Covered Above)

> These routes exist in `gateway/routes/` and must be verified before production sign-off.

| # | Check Item | Status | Note |
|---|---|---|---|
| S0a | `access.py` — route loads, auth guard active | `[ ]` | |
| S0b | `capabilities.py` — workspace capabilities return correctly | `[ ]` | |
| S0c | `circles.py` — works | `[ ]` | |
| S0d | `config_routes.py` — config endpoint returns correct values | `[ ]` | |
| S0e | `public_config.py` — public config safe (no secrets exposed) | `[ ]` | |
| S0f | `control_plane.py` — control plane route works | `[ ]` | |
| S0g | `conversations.py` — conversation listing/management works | `[ ]` | |
| S0h | `dock_actions.py` — dock actions work | `[ ]` | |
| S0i | `dock_integrations.py` — dock integrations work | `[ ]` | |
| S0j | `email.py` — email sending route works | `[ ]` | |
| S0k | `events.py` — events route works | `[ ]` | |
| S0l | `graph.py` — graph route works | `[ ]` | |
| S0m | `internal.py` — internal route locked down (not publicly accessible) | `[ ]` | |
| S0n | `kernel_dispatch.py` — kernel dispatch works | `[ ]` | |
| S0o | `llm_gateway_routes.py` — LLM gateway routes work | `[ ]` | |
| S0p | `media.py` — media upload/serve works | `[ ]` | |
| S0q | `plugins.py` — plugin management route works | `[ ]` | |
| S0r | `site_actions.py` — site actions work | `[ ]` | |
| S0s | `social_growth.py` — social growth route works | `[ ]` | |
| S0t | `web_ai_proxy.py` — web AI proxy works | `[ ]` | |
| S0u | `workspace_capabilities.py` — works | `[ ]` | |
| S0v | `workspace_feature_routes.py` — feature flags per workspace correct | `[ ]` | |
| S0w | `zero_cost.py` — zero cost route works | `[ ]` | |

---

## S. Cost, Docs & Final Gate

| # | Check Item | Status | Note |
|---|---|---|---|
| S1 | Render free minutes budget reviewed (364 min remaining) | `[ ]` | |
| S2 | OpenAPI schema — up to date | `[ ]` | |
| S3 | CONSUMERS.md — up to date | `[ ]` | |
| S4 | FAQ — up to date | `[ ]` | |
| S5 | Rollback plan — documented and tested | `[ ]` | |
| S6 | Disaster recovery runbook — tested | `[ ]` | |
| S7 | system_parity_audit — release gate PASSED | `[ ]` | Blocked by B1, A1 |

---

## T. System-Level Production Checks (Missing from Original — Critical)

| # | Check Item | Status | Note |
|---|---|---|---|
| T1 | All required env vars set in production (Infisical/Render) | `[ ]` | DATABASE_URL, REDIS_URL, SUPABASE_URL, OPENAI_API_KEY, NEXTAUTH_SECRET etc. |
| T2 | SSL/TLS — all endpoints HTTPS, certs not expired | `[ ]` | |
| T3 | CORS — wildcard `*` NOT active in production | `[ ]` | Must be restricted to known origins only |
| T4 | k6 load test — API handles expected concurrent users | `[ ]` | scripts/k6/ |
| T5 | Cold start time — Render service responds within 30s after sleep | `[ ]` | |
| T6 | Database backup — restore tested successfully | `[ ]` | |

---

## U. Resilience, Safety & Ops Hardening

| # | Check Item | Status | Note |
|---|---|---|---|
| U1 | Database connection pool exhaustion test | `[ ]` | High-traffic pool starvation & pgBouncer limit check |
| U2 | Idempotency of payment & billing webhooks | `[ ]` | Event ID deduplication to prevent double-charging/credits |
| U3 | File-upload virus/malware scanning & MIME validation | `[ ]` | ClamAV / polyglot file & SVG XSS execution prevention |
| U4 | Graceful shutdown & SIGTERM handling | `[ ]` | In-flight SSE streams & agent tasks not dropped during deploys |
| U5 | Log retention policy & automated PII/secret scrubbing | `[ ]` | Compliance and zero credential leakage in telemetry |
| U6 | Third-party API key zero-downtime rotation drill | `[ ]` | OpenAI, Supabase, Anthropic keys rotatable without outage |
| U7 | Frontend bundle size & performance budget | `[ ]` | Next.js chunks, Core Web Vitals (LCP/INP), size budget |
| U8 | MCP tool-name contract & schema tests | `[ ]` | Dotted vs snake_case naming & parameter regression test |

