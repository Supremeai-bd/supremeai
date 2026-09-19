# Service-Level Objectives & Alerting Thresholds (P2)

> Status: **Proposed baseline** — values derived from measured production
> behaviour (Render free-tier cold starts, health contract, rate-limit docs)
> and the 2026-09-13/14 log audits. Owner sign-off required before wiring to a
> paging system; until then this is the reference for dashboards and review.

## Service inventory & objectives

| Service (Render) | Role | Availability SLO (30-day) | Latency objective | Notes |
| --- | --- | --- | --- | --- |
| `supremeai-primary-node` (`srv-dabm7dfqj5pc738jkbmg`) | Core API | 99.0% | `/health/live` p95 < 300 ms; chat first-token p95 < 8 s (LLM chain budget from PR #286) | Free tier: 50-60 s cold start after 15 min idle is EXPECTED and must not page |
| `supremeai-worker-node` (`srv-dabm7evqj5pc738jkf30`) | Background jobs | 98.0% (degradable role) | queue drain lag p95 < 5 min | DB failure → degraded, NOT READY (health_policy) |
| `supremeai-scraper-node` (`srv-dabm7gfqj5pc738jkicg`) | Browser/scraping | 98.0% (degradable role) | per-scrape budget 60 s | Playwright memory spikes tolerated |
| `supremeai-mcp-tower` (`srv-dabm7inqj5pc738jkrt0`) | MCP control plane | 99.0% | tool call p95 < 2 s | |
| Frontend (firebase web.app) | SPA | 99.5% (host-managed) | build-contract check in CI | Vercel projects in Error are pre-existing (see ENV_EVIDENCE_MATRIX §5) |

## Error budget policy

- Budget = 100% − SLO, tracked monthly per service.
- Budget burned > 50% in the first half of the month → freeze non-critical
  deploys for that service until budget recovers.
- Free-tier cold starts are EXEMPT from the budget (documented platform
  behaviour, not a regression); repeated cold-start complaints should drive a
  paid-tier decision instead of paging.

## Alert thresholds (all probes hit canonical `/health/*` only)

| Alert | Condition | Severity | Rationale |
| --- | --- | --- | --- |
| Primary down | `GET /health/live` non-200 for 3 consecutive probes (15 s apart) | page | process-level failure; independent of cold start because liveness only fails when the process is truly dead |
| Primary not ready | `GET /health/ready` → 503 `not ready` for 10 consecutive minutes | page | per health_policy, core in production = NOT READY only on real DB failure |
| Primary degraded | `/health/ready` → `degraded` for 30 min | ticket | non-critical dependency issue |
| Cold start flap | ≥ 6 liveness losses in 1 h each recovering within 90 s | ticket | traffic pattern / free-tier review, not paging |
| Rate-limit exhaustion | log phrase `in-memory emergency limiter` on any instance | **page** | means Redis is unreachable — multi-instance limiting is bypassed (see RATE_LIMITING.md) |
| Rate-limit pressure | 429 rate > 5% of responses for 15 min on core | ticket | possible abuse or overly tight limit |
| DB degraded-mode ignore | boot log contains `SUPABASE_ALLOW_DB_DEGRADATION` ignored warning in prod | page | policy bypass attempt (compose must never set it true for core) |
| Docs exposure | any 200 from `/docs`, `/redoc`, `/openapi.json` in prod | **page** | must 404/401 per docs policy |
| Frontend contract drift | `verify_frontend_build_contract.py` failure in CI | build blocker | loopback/empty backend baked into bundle |
| Backup age | newest restorable backup > 24 h old | page | see BACKUP_RESTORE_DRILL.md |

## Monitoring wiring (owner action)

1. Render dashboard health checks → point core at `https://<render-primary-url>/health/ready` (canonical).
2. External uptime probe (Cloudflare Worker or UptimeRobot-class) → `/health/live` every 60 s for the page-level "Primary down" alert.
3. Log-phrase alerts scrape the Render log stream for the exact phrases above (they were chosen to be greppable and unique).
4. Fill the Verified column here once wired — this doc must never drift to "assumed".
