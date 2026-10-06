# DuckDB Analytics Layer — Workload-Driven Adoption (issue #4056)

> **Priority:** P3 — workload-driven (only adopt when Postgres analytics insufficient)
> **Date:** 2026-10-06
> **Roadmap v2 section:** Phase 4 → §4.3 DuckDB Analytics Layer

## Mission

Add DuckDB as a governed analytics engine. **v2 change:** deprioritized P2 → P3. Only adopt when daily analytics workload exceeds Postgres capability.

## Architecture

```
Supabase/Postgres (operational DB)
      ↓
Export/Event stream (when analytics volume grows)
      ↓
DuckDB (analytics engine — NOT operational DB)
      ↓
Daily ecosystem audit + cost + latency + regression reports
```

## Workload Trigger (NOT premature adoption)

Adopt DuckDB ONLY when ALL of the following are true:
- [ ] Daily analytics query volume > 10k rows scanned per report
- [ ] Postgres analytics queries > 5s p95
- [ ] At least 3 distinct daily report types (cost, latency, regression, ecosystem audit)

**Until then:** Postgres is sufficient. Do NOT add DuckDB prematurely.

## Current State Assessment (verified on main)

| Check | Status |
|---|---|
| Daily analytics query volume | Unknown (no monitoring in place) |
| Postgres analytics query latency | Unknown (no p95 measurement) |
| Daily report types | 0 (no daily reports exist yet — Evaluation Engine #4047 not built) |
| Decision: Adopt DuckDB now? | **NO** — workload trigger not met |

## What DuckDB Would Do (if adopted)

| Report type | Source data | DuckDB query | Frequency |
|---|---|---|---|
| Cost report | Provider call logs (token cost per call) | `SELECT provider, SUM(cost) FROM calls GROUP BY provider` | Daily |
| Latency report | Provider call latency (p50/p95/p99) | `SELECT provider, percentile_cont(0.95) WITHIN GROUP (...) FROM calls` | Daily |
| Regression report | Evaluation Engine scores (#4047) | `SELECT provider, AVG(score) FROM eval_scores WHERE run_date > now() - 7d GROUP BY provider` | Daily |
| Ecosystem audit | Scout findings (#4055) | `SELECT source, COUNT(*) FROM discoveries GROUP BY source` | Daily |

## Implementation Plan (when trigger met)

1. `backend/analytics/duckdb_layer.py` — DuckDB connection + query runner
2. `backend/analytics/export_stream.py` — Postgres → DuckDB export (daily or real-time)
3. `backend/analytics/reports/{cost,latency,regression,ecosystem_audit}.py` — report queries
4. `backend/observability/service_topology.py` — DuckDB health check (tri-state)
5. DuckDB as governed provider: `SUPREMEAI_DUCKDB_ENABLED` flag + Policy Engine gate
6. Postgres remains operational DB — DuckDB NEVER writes back to operational tables

## Decision: DEFERRED — workload trigger not met

**Rationale:**
1. Evaluation Engine (#4047) not yet built → no regression reports possible
2. Ecosystem Scout (#4055) not yet built → no ecosystem audit reports
3. No current analytics workload that Postgres cannot handle
4. Premature adoption would add a dependency for zero benefit

**Next steps:**
1. Build Evaluation Engine (#4047) — this will create the first analytics workload
2. Build Scout (#4055) — this will create ecosystem audit data
3. Measure Postgres analytics query p95 latency once these are in production
4. If p95 > 5s on > 10k rows → adopt DuckDB (open new implementation issue)
5. If p95 < 5s → Postgres is sufficient; DuckDB not needed

## Bengali Note

DuckDB এখন P3 — workload-driven। Postgres analytics-এ ধীল হয়ে গেলে (p95 > 5s, daily 10k+ rows), তখনই DuckDB। আগে নয় — over-engineering পরিহার্য। এটা v2 feedback-এর গুরুত্বপূর্ণ পরিবর্তন। Evaluation Engine (#4047) + Scout (#4055) তৈরি হওয়ার আগে এই trigger মেটানো সম্ভব নয়।
