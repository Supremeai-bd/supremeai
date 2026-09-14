# SLOs and Alerts — Starter Targets

> Task: production contract closure, 2026-09-14.
>
> ⚠️ **These are STARTING values.** They were chosen from free-tier infrastructure
> reality (Render free nodes, Supabase/Upstash free tiers), not from measured traffic.
> **Re-tune every number in this file after 30 days of real traffic data** (render
> metrics + Sentry + `/metrics` history). Do not treat them as contractual promises
> until that review has happened.

## Measurement sources (what exists today)

| Source | What it provides | Notes |
|---|---|---|
| `GET /metrics` (Prometheus text) | `superai_requests_total`, `superai_errors_total`, `superai_error_rate`, `superai_response_time_ms{p50,p95,p99}`, `superai_cache_hit_rate`, `superai_llm_cost_usd`, `superai_uptime_seconds` | `backend/core/monitoring.py` (`MetricsCollector.export_prometheus`), mounted in `backend/core/app_builder.py` **only when `MONITORING_DETAILED=true`** — set it on all long-running services. In-process (5-min rolling window, per instance). |
| `GET /health` (full) | Per-check status + latency (DB, memory, …) | `backend/core/health_routes.py`; canonical paths per `docs/operations/OPERATIONAL_CONTRACTS.md` §1 |
| Sentry (`SENTRY_DSN`) | Exception rates, latency traces, release health (crash-free sessions) | Lazy init in `backend/core/app_builder.py::_init_sentry` |
| Render dashboard | CPU/memory, request count, HTTP status per service, spin-ups | Free tier: basic; scrape manually or via Render API |
| Query timing middleware | Slow-request log + in-process percentiles | `backend/core/middleware/query_timing.py`, threshold `SLOW_REQUEST_MS` (default 2000), history `QUERY_TIMING_HISTORY` (default 1000) |
| Keep-alive workflow | External reachability probes of `/health/live` | `.github/workflows/keepalive.yml` (manual `workflow_dispatch`) |
| LLM telemetry | Provider routing, costs, token totals | `backend/core/llm/telemetry.py`, `superai_llm_cost_usd` on `/metrics` |

> There is **no hosted Prometheus/Grafana yet** — until one exists, "alert" means:
> Sentry alert rules (free tier supports email alerts) + scheduled GitHub Action that
> scrapes `/metrics` and `/health` and opens an issue via `scripts/maintenance/create_issue.py`.

## Starter SLOs

| # | SLO | Target | How measured | Suggested alert |
|---|---|---|---|---|
| 1 | **Availability** (core API) | **99.5%** monthly, measured on `/health/live` + real user requests (free-tier infra; excludes deliberate maintenance windows) | External probe of `/health/live` (keep-alive workflow / uptime service) + Render HTTP metrics; `superai_uptime_seconds` for restarts | Page when 2 consecutive probes fail (probe every 5–10 min); warning at 99.5% month-to-date, page at < 99.0% |
| 2 | **API latency** (non-LLM) | **p95 < 1500 ms** | `superai_response_time_ms{p95}` on `/metrics` (5-min window); cross-check QueryTimingMiddleware percentiles and Sentry traces | Warning at p95 > 1500 ms for 15 min; page at p95 > 3000 ms for 15 min |
| 3 | **LLM streaming first token** | **p95 < 30 s** (time-to-first-chunk) | Not on `/metrics` — derive from Sentry traces / app logs around `core/llm/llm_gateway/streaming.py`; add a dedicated metric later | Warning when p95 > 30 s over 1 h; page at p95 > 60 s (user-visible stall) |
| 4 | **LLM request success rate** | **≥ 95%** of completed LLM requests (excluding client-aborted streams) | LLM telemetry counters + `superai_error_rate`; per-provider breakdown via `backend/core/llm/telemetry.py` | Warning < 95% over 1 h for any provider; page < 90% over 1 h (router failover failing too) |
| 5 | **5xx error rate** | **< 1%** of all requests (rolling 1 h) | `superai_error_rate` on `/metrics`; Render HTTP 5xx count; Sentry issue rate | Warning > 1% over 10 min; page > 5% over 10 min or any 5-minute window with 0 successful requests |
| 6 | **WebSocket/SSE connection failures** | **< 5%** of connection attempts failing per hour | WS handshake errors in logs (`backend/ws/`, `backend/core/security/ws_auth.py`) + Sentry; no dedicated counter yet — add `superai_ws_connections_{total,failed}` when tuning | Page when > 5 failures in 15 min from production traffic, or failure rate > 5%/h |
| 7 | **DB query latency** | **p95 < 500 ms** | QueryTimingMiddleware percentiles (filter DB-heavy paths), Supabase dashboard query performance, `supabase-pgbouncer` stats if enabled | Warning p95 > 500 ms for 15 min; page p95 > 1 s for 15 min (check pooler saturation / connection limits first) |
| 8 | **Redis failure handling** | Rate limiting & cache **degrade, never outage**: fallback limiter absorbs load, core stays available | Watch logs for `"Rate limiter failed to get redis client"` / `"falling back to in-memory"` (`core/rate_limit.py`); Upstash dashboard for evictions/latency | Warning on > 10 fallback log lines in 1 h (Redis unreachable); Redis loss is NOT an availability incident while the fallback is active — but it removes multi-instance limiting, so escalate if it lasts > 1 h |

Note on SLO 1 vs SLO 5: availability is measured from **outside** (can the client reach a
working service?), the 5xx rate from **inside** (is the service healthy while reachable?).
Both are needed because Render free-tier spin-ups produce reachability failures that are
not app errors.

## Monthly error budget

Formula: `error budget = (1 − SLO) × minutes in month`.

- **99.5% availability ⇒ 216 min (~3.6 h) of allowed downtime per 30-day month**
  (43,200 min × 0.5%).
- Spending rules (starters):
  - Remaining budget > 50% mid-month: normal pace, ship freely.
  - 25–50% remaining: freeze risky deploys to the affected service; only fixes roll.
  - < 25% remaining: change freeze on the core node + incident review of what is
    burning the budget (typically: free-tier spin-up gaps, OOM restarts at 512 MiB,
    failed deploys).
- Budget resets on the 1st of each month (UTC). Track manually in this file's
  changelog below until an uptime service automates it.

## 30-day tuning plan (required before these numbers are "real")

1. Set `MONITORING_DETAILED=true` and `SENTRY_DSN` on all services (see
   `docs/deployment/ENV_EVIDENCE_MATRIX.md`).
2. Schedule the keep-alive/uptime probe to run at a fixed cadence and persist results.
3. After 30 days: compare SLO 2/5/7 targets against measured p95s; if a target is
   trivially met (p95 < 50% of target) tighten it; if it burns > 50% of budget,
   either fix the cause or re-baseline with justification.
4. Add missing counters found during tuning (WS connections, TTFT for LLM streams,
   per-provider LLM success rate) to `backend/core/monitoring.py`.
5. Record the review outcome in a new dated section at the bottom of this file.

## Changelog

| Date | Change | Author |
|---|---|---|
| 2026-09-14 | Initial starter SLOs defined (pre-traffic baselines) | Task 2-e |
