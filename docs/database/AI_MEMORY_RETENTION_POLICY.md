# ai_memory — Data Retention & Privacy Policy (issue #1109)

> Status: **policy codified** (2026-09-24). The enforcement surfaces listed
> below are live code paths in this repository; runtime activation of the
> scheduled agent is environment-gated (see §2).

## 1. What is stored in `ai_memory`

| Data | Column | Privacy class |
|---|---|---|
| Memory content / summary | `content`, `summary` | user-derived text (may contain task context) |
| Vector embedding | `embedding vector(384)` | derived from content — same privacy class as the content |
| Ownership | `user_id` (JWT `sub`), `session_id` | pseudonymous identifier (no direct PII column) |
| Context | `agent_type`, `task_type`, `metadata` JSONB | operational metadata |
| Lifecycle | `created_at`, `updated_at` | TTL drivers |

`user_id` is the Supabase `auth.uid()` rendered as text — the schema
deliberately stores **no email / name / password** in this table (see
`models/ai_memory.py` header, audit §3).

## 2. Retention / TTL contract

| Parameter | Default | Where enforced |
|---|---|---|
| TTL (`AI_MEMORY_RETENTION_DAYS`) | **180 days** | SQL `fn_ai_memory_retention_cleanup(p_days)` — fail-closed `p_days >= 1`; Python mirror `core/ai_memory/retention.py::get_retention_days()` (invalid values raise, never silently default) |
| Cleanup schedule | daily (86400s) | app agent in `core/startup/agents.py` — **enabled only with `ENABLE_AI_MEMORY_RETENTION=true`**; deploy environments MUST set it true in production |
| Deletion semantics | hard DELETE | both enforcement paths physically remove rows (no soft-delete, no archive copy) |
| Index support | `ix_ai_memory_created_at_desc` | makes TTL sweeps index-range scans, not full scans |

Enforcement layers (RPC-first, fail-honest):

1. **Canonical (RPC):** `fn_ai_memory_retention_cleanup` (SECURITY DEFINER,
   service_role only — `REVOKE ... FROM PUBLIC, anon, authenticated`).
2. **Fallback (direct):** `core/ai_memory/retention.py::cleanup_expired()`
   SQLAlchemy DELETE against `ai_memory.created_at` — used when the Supabase
   REST client is unavailable, so TTL hygiene never depends on one transport.
   Every pass returns a `CleanupResult(deleted, mode, retention_days)` and is
   logged — a silent no-op cleanup is not possible.
3. **Optional pg_cron:** scheduled SQL hook documented inline in the
   `ai_memory_phase_c.sql` Part 8 (owner decision to enable; avoid double
   scheduling with the app agent).

## 3. GDPR / privacy boundaries

* **Right to erasure (self-service):** `DELETE /api/preferences/memory/user-data`
  (router `api/routes/global_memory.py`) erases **all** rows where
  `user_id = JWT.sub`. The user_id comes exclusively from the verified token —
  a caller can never erase another user's memories.
* **Row-level erasure:** existing `DELETE /api/preferences/memory/{memory_id}`
  verifies ownership before deleting.
* **Erasure mechanics:** `core/ai_memory/retention.py::delete_user_memories()`
  — REST-client first, async-SQLAlchemy fallback; returns the honest deleted
  count for receipt/audit logging.
* **Observability:** `retention_stats()` reports row counts by staleness
  bucket (`fresh_lt_7d` … `older_than_90d`) — the evidence source for TTL
  audits without exposing row contents.
* **Non-goals (documented residual risks):** embeddings are derived data; if
  the same content is re-embedded after erasure, the new row is a new
  lifecycle. Backups/replicas restore under the same TTL (retention applies to
  restored copies too because the sweep is `created_at`-driven).

## 4. Owner sign-off checklist

- [x] Retention function + indexes shipped (`ai_memory_phase_c.sql` Part 8)
- [x] App-side scheduled cleanup agent wired (env-gated)
- [x] Python pruning utilities + GDPR erasure path (`core/ai_memory/retention.py`)
- [x] Self-service erasure endpoint (JWT-scoped)
- [x] This policy document committed
- [ ] **Owner action:** set `ENABLE_AI_MEMORY_RETENTION=true` and
      `AI_MEMORY_RETENTION_DAYS` in the production vault (Infisical) — the
      default-off gate means the policy is NOT enforcing in prod until this is
      done (tracked here; do not close #1109 until confirmed).
