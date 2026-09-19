# Learning Platform Enablement Runbook (Owner Decision Sheet)

**Issue:** #441 — "Self-learning platform is OFF by default in production: 12/13 agent flags false"
**Scope:** `backend/core/startup/agents.py` gates the background agents behind `ENABLE_*` env flags. This runbook is the **owner-facing decision sheet** for enabling them. It makes **no changes** to Render env vars and flips **no defaults** — every enable step below **REQUIRES OWNER APPROVAL**.

---

## 1. Current state (verified on main, branch `fix/issue-441-449-decision-support`)

* `backend/core/startup/agents.py` declares **14** `ENABLE_*` agent flags:
  * **12 default `false`** — Sentinel, System Telemetry, Bug Prophet, Tier-8, Evolution, Daily Learner, Auto Healer, Auto-Scaling, Performance Tuning, Cost Optimization, Disaster Recovery, ai_memory Retention.
  * **2 default `true`** — `ENABLE_LEARNING_LOOP` (agents.py:213) and `ENABLE_SYNAPTIC_DREAM` (agents.py:452, flipped post-issue via #453 Wave 4 / M05 P-A). The issue's "12/13" count predates the Synaptic Dream default change; today's honest count is **12 of 14 false**.
* Render production sets only `ENABLE_LEARNING_LOOP=true` (plus `LOW_MEMORY_MODE=true`). The platform's "learning" in prod is therefore **telemetry + proposal-only**, not adaptation.
* Under `LOW_MEMORY_MODE=true` the local memory stack is disabled: `adaptive_engine/experience_db.py:14` (module default is **even** `true`), `:17-23` (`_check_module()` returns `False` for `sentence_transformers`/`chromadb`/`qdrant_client`), and `:100-138` (`__init__` declares the pass-through: `_degraded_no_store = True`). Writes degrade at `:317-325` (`record_experience` → `return 0` unless the Supabase pgvector backend is alive) and reads at `:507-511` (`find_similar` → no matches). A one-time `🚨 BOOT-TIME WARNING` now announces this at first construction (this branch, mirroring the PR #716 `config_validation.py` warning style).
* **Always-on (not env-gated) learning components** in `agents.py`: LearningStore flush loop (:197-204, durable `learning_events` telemetry via PostgREST — bounded in-process buffer, no LLM), SelfHealer error listener (:261-267), scheduled-task sweep (:429-441), swarm-cache invalidator (:32-38), supervisor health monitor (:469).

**Honest one-line current state:** with `LOW_MEMORY_MODE=true`, `ExperienceDatabase` is a pass-through no-op for local learning storage (`experience_db.py:14`, `:17-23`, `:100-138`) — so the only *active* learning component is the LearningLoopAgent's observe→aggregate→**propose** cycle (never auto-applies, `core/learning/loop.py:1-21`) plus LearningStore telemetry and the SynapticDream prune.

---

## 2. Flag table (exact names, `backend/core/startup/agents.py`)

Cost classes: **low** = in-process reads/one RPC per day/5-min PostgREST aggregates; **med** = periodic LLM tokens or subprocess/DB fan-out; **high** = continuous LLM loops, 5s heartbeats, or autonomous mutation of runtime behavior.

| # | Flag (default) | agents.py | Starts | Writes / reads | Cost | Safe in current LOW_MEMORY_MODE prod? | Enabling precondition |
|---|---|---|---|---|---|---|---|
| 1 | `ENABLE_SENTINEL_AGENT` (false) | :17 | Sentinel endpoint monitor + dependency audit | SQLAlchemy: `api_endpoints`, `system_incidents`, `system_dependencies`; httpx polls per endpoint (60s); **subprocess** `pip-audit`/`pip list` (12h) | **med** (audit subprocess CPU spike; needs SQL DB) | **Conditional** | Working SQL session (prod DB currently degraded/REST-only); expect 12h pip-audit CPU hit on 512MB container |
| 2 | `ENABLE_SYSTEM_TELEMETRY` (false) | :63 | System Telemetry Broadcaster (5s cadence) | psutil CPU/mem + in-process error-rate → Redis pub/sub (`swarm_streamer.broadcast`) | **low** | **Yes** | None (Redis already provisioned) |
| 3 | `ENABLE_BUG_PROPHET` (false) | :89 | BugProphet anomaly detector (ErrorEventBus listener, 60s baseline update) | In-memory Z-score history only; no DB, no LLM in loop (imports `litellm` at module load) | **low** | **Yes** | None; review the pre-existing corrupted-identifier lines in `scripts/devops/bug_prophet.py` first (silent_errors_baseline entries) |
| 4 | `ENABLE_TIER8` (false) | :109 | Tier-8 meta-self subsystem (4 agents, auto-starts unless `TIER8_AUTO_START=false`) | LLM benchmark loops (`agent_evolution_engine` via `LLMGateway`), 5s swarm heartbeats, service registry + health probes | **high** | **No** | Requires owner approval + memory headroom + LLM budget; do not enable under 512MB/LOW_MEMORY_MODE |
| 5 | `ENABLE_EVOLUTION` (false) | :121 | SelfEvolutionAgent (5-min cycle, memory-gated) | FitnessEngine reads, `code_proposals` writes (SQLAlchemy), AutoSkillCreator LLM calls when refactors trigger | **med** | **Conditional** | `is_safe_for_heavy_task()` headroom (agents.py:165 pattern); review proposal pipeline; owner approval for code-proposal generation |
| 6 | `ENABLE_DAILY_LEARNER` (false) | :148 | DailyLearner (24h research cycle, memory-gated) | LLMRouter calls (goal decomposition, discovery scans of ArXiv/GitHub), Redis cache, EvolutionEngine integration | **med** (LLM tokens + external HTTP) | **Conditional** | LLM budget approval; acceptable latency spike once/day; memory headroom check already built in (agents.py:165) |
| 7 | `ENABLE_LEARNING_LOOP` (**true**) | :213 | LearningLoopAgent (5-min observe→aggregate→propose; **never auto-applies**) | PostgREST reads `learning_events` (≤2000/window); upserts `provider_metrics`, `skill_metrics`, `fitness_snapshots`; inserts `improvement_proposals` + `improvement_run` (status PROPOSED, HITL only) | **low** (zero LLM — module docstring) | **Yes** (already active) | None — this is the one learning component running in prod today |
| 8 | `ENABLE_AUTO_HEALER` (false) | :236 | AutoHealerService monitor loop (300s; loop itself only sleeps — `services/auto_healer.py:415-423`) | Delegates to proactive_healer; DB/Redis healing actions, GitHub PR creation capability | **low** (monitor) / actions vary | **Conditional** | Owner must review which healing actions are allowed to auto-run against prod DB/Redis before enabling |
| 9 | `ENABLE_AUTOSCALING_AGENT` (false) | :277 | AutoScalingAgent (5-min cycle) | psutil metrics → Redis/`TokenDeductor` cost records; `execute_scaling_action` when confidence > 0.6 (actions largely simulated — `auto_scaling_agent.py:416`) | **low** | **Conditional** | Pointless on single-container Render until a real scaling target exists; owner decision |
| 10 | `ENABLE_PERFORMANCE_TUNING_AGENT` (false) | :307 | PerformanceTuningAgent (15-min cycle) | Reads perf metrics; **auto-applies tuning changes** (config mutations with 5s settle waits — `performance_tuning_agent.py:396`) | **med** | **No** (autonomous mutation) | Owner approval for auto-apply semantics + blast-radius review; not until a dry-run mode exists |
| 11 | `ENABLE_COST_OPTIMIZATION_AGENT` (false) | :327 | CostOptimizationAgent (1h cycle) | `TokenDeductor` cost metrics → Redis; opportunity report rows | **low** | **Yes** | None beyond Redis; observability-only |
| 12 | `ENABLE_DISASTER_RECOVERY_AGENT` (false) | :357 | DisasterRecoveryAgent (6h incremental backups) | Backup artifacts + integrity verification — **writes to the local container disk**, which is ephemeral on Render free tier | **med** (I/O) | **No** (as configured) | Provision a real off-container backup destination first; otherwise backups are lost on restart |
| 13 | `ENABLE_AI_MEMORY_RETENTION` (false) | :390 | ai_memory retention agent (daily, `AI_MEMORY_RETENTION_INTERVAL_SECONDS`) | Supabase RPC `fn_ai_memory_retention_cleanup` (SQL-side decay/cleanup, Phase C indexes shipped) | **low** (one RPC/day) | **Yes** | Supabase service client reachable (already is) |
| 14 | `ENABLE_SYNAPTIC_DREAM` (**true**) | :452 | Synaptic Dream memory-consolidation prune (daily, `SYNAPTIC_DREAM_INTERVAL_SECONDS`) | Supabase `ai_memory` delete: `importance_score < 0.2` older than 30d (`workers/synaptic_dream.py:62-79`); honest idle warnings when store absent | **low** | **Yes** (already active by default) | None; overlaps nothing (distinct from the SQL-side RPC in #13) |

Non-flag note: the Task Queue Worker is lazy (starts on first `enqueue()`, quota-safe — agents.py:41-58) and is Redis-config-gated, not `ENABLE_*`-gated; it is excluded from the table.

---

## 3. Recommended staged enablement order (observability-first)

> Every stage below is **REQUIRES OWNER APPROVAL**. Nothing in this runbook has been applied to Render. Rollback for every stage = remove the env var (or set `false`) and restart; no state migration is needed at any stage.

| Stage | Flags to set | Why this order | Owner approval |
|---|---|---|---|
| **Stage 0 — today** | *(nothing; prod as-is)* | LearningLoop + SynapticDream already active; telemetry-only baseline | — |
| **Stage 1 — telemetry** | `ENABLE_SYSTEM_TELEMETRY=true`, `ENABLE_COST_OPTIMIZATION_AGENT=true`, `ENABLE_AI_MEMORY_RETENTION=true` | Cheapest observability: 5s metrics broadcast, hourly cost rollup, daily retention RPC. All `low` cost, no autonomous actions | ✅ REQUIRES OWNER APPROVAL |
| **Stage 2 — sentinel** | `ENABLE_SENTINEL_AGENT=true` | Adds endpoint monitoring + incidents — but **first** confirm the prod SQL session works (or accept the logged exceptions) and schedule the 12h pip-audit CPU hit off-peak | ✅ REQUIRES OWNER APPROVAL |
| **Stage 3 — daily-learner** | `ENABLE_DAILY_LEARNER=true` | First LLM-consuming stage: one research scan/day, memory-gated; observe token spend for a week before Stage 4 | ✅ REQUIRES OWNER APPROVAL |
| **Stage 4 — evolution** | `ENABLE_EVOLUTION=true` | Full observe→propose loop with code-proposal generation; still proposal-only, but heaviest of the staged set | ✅ REQUIRES OWNER APPROVAL |
| **Deferred (not staged)** | `ENABLE_TIER8`, `ENABLE_PERFORMANCE_TUNING_AGENT`, `ENABLE_DISASTER_RECOVERY_AGENT`, `ENABLE_BUG_PROPHET`, `ENABLE_AUTO_HEALER`, `ENABLE_AUTOSCALING_AGENT` | High cost / autonomous mutation / ephemeral-disk backups / corrupted-source concerns — revisit each with its own mini-review | ⛔ DO NOT ENABLE until owner re-review |

**Memory precondition for any learning stage:** `LOW_MEMORY_MODE` must be raised (i.e. set `false`) *before or together with* Stage 3/4 if you want real semantic memory: under `LOW_MEMORY_MODE=true` the local encoder and vector stores never load (`experience_db.py:17-23`), so experience embeddings rely on the pgvector/remote-embedding chain and local learning storage stays a pass-through. Confirm the 512MB → larger instance change with Render capacity review first. `SUPABASE_ALLOW_DB_DEGRADATION` should stay `false` (fail-closed policy, `core/degraded_mode.py:157-171`).

---

## 4. Owner checklist

- [ ] Approve or reject each stage in §3 (this table is the decision record).
- [ ] Confirm prod SQL session status (Stage 2 gate) and LLM budget (Stage 3/4 gate).
- [ ] Decide the `LOW_MEMORY_MODE` raise order (§ memory precondition).
- [ ] After approval: set flags in Render → redeploy → verify boot log shows the corresponding `✅ ... started` line from `agents.py` and the absence of the `🚨 BOOT-TIME WARNING` (only possible after `LOW_MEMORY_MODE` is raised).
