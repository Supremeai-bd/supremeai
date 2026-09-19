# HITL Approval Contract — Canonical Approve-Execution Semantics

> **Status:** CANONICAL (implementation-ratified) — this document is the normative
> state-machine + authorization contract for every Human-In-The-Loop approval surface
> in SupremeAI. Ratified for issue #481 ("Ratify and enforce approve-execution
> semantics"); supersedes the open manual decision previously tracked as
> `docs/audits/MANUAL_STEPS.md` task 9 / `docs/plans/PENDING_APPROVALS.md` TASK-003.
>
> **Scope:** Python backend surfaces (this document) + the MCP control-tower TS
> approval gate (cross-referenced; hardened by PR #718 — `SYS-AUTO-FIX` bypass
> removed, approval overrides verify against a real APPROVED record).

---

## 1. Approval surfaces

| # | Surface | Store | Route owner | Consumed by |
|---|---------|-------|-------------|-------------|
| S1 | **Canonical approval store** | `backend/models/pending_tasks.py` (SQLite, AUD-4 hardened) | `backend/api/routes/approval_manager.py` (`/api/v1/hitl/*` shadow pair, `/admin-api/approvals`) | admin API, MCP proxy, ecosystem workflow |
| S2 | **HITLEngine (producer chain)** | Firestore collection `pending_approvals` (+ write-through mirror into S1 under idempotency key `hitl:<record_id>`) | `backend/api/routes/hitl_admin.py` (mount-order winner for `/api/v1/hitl/pending|approve|reject`) | frontend `ApprovalQueue` (`frontend/src/data/hooks.ts`), `auto_skill_creator` |
| S3 | Run-fabric hook | delegates to S1/S2 | `backend/runs/hitl.py` | runs state machine (`WAITING_APPROVAL`) |
| S4 | Control tower (TS) | tower approval store | `infrastructure/mcp-control-plane/src/actions/executor.ts` + `src/policy/approvals/*` | MCP tool execution gate |

Route ownership is pinned by `backend/tests/api/test_hitl_route_ownership.py` — S2 wins
`/api/v1/hitl/{pending,approve,reject}`; both surfaces implement the SAME contract below.

## 2. Canonical states

Two status vocabularies exist by design (S1 store statuses; S2 record statuses). They are
1:1 mapped at the mirror boundary (S2 → S1, idempotency key `hitl:<record_id>`):

| State | S1 (`pending_tasks`) | S2 (HITLEngine) | Meaning | Terminal? |
|-------|----------------------|-----------------|---------|-----------|
| awaiting decision | `PENDING` | `pending_approval` | suspended for a human decision | no |
| approved | `APPROVED` | `approved` | human approved; execution may proceed | yes (dispatch follows) |
| rejected | `REJECTED` | `rejected` | human declined | yes |
| cancelled | `CANCELLED` | *(mirrors to `CANCELLED` when expired)* | authoritative cancel / system expiry | yes |
| executed | `EXECUTED` | `execution_status="executed"` | side effects ran exactly once | yes |
| expired | decision-time `TaskExpiredError` (row stays `PENDING`, filtered from queues) | `expired` | TTL elapsed before a decision | yes |
| execution failed | `execution_status="failed"` (row returns to `APPROVED`) | `execution_status="failed"` + `execution_error` | approval valid, dispatch raised | approval-side yes; execution loud |

S1 execution micro-states: `execution_status ∈ {pending, running, succeeded, failed}`
(`mark_execution_started` / `mark_execution_result` / `mark_executed` claim-and-commit guards).

### 2.1 Legal transitions (normative)

```text
S1: PENDING ──approve──▶ APPROVED ──mark_executed──▶ EXECUTED
      │  │  └─cancel──▶ CANCELLED
      │  └─reject───▶ REJECTED
      └─(TTL elapsed at decision time)──▶ decision refused (HTTP 410), row stays PENDING (queue-hidden)

S2: pending_approval ──approve──▶ approved ──dispatch ok────▶ execution_status=executed
      │  │  └─reject──▶ rejected
      │  └─(TTL elapsed at decision time)──▶ expired        (record flipped to expired, ledger "approval_expired")
      └─unknown target ──▶ ApprovalDispatchError BEFORE flip (record stays pending_approval)
```

**Nothing else is legal.** A record in a terminal state (`approved`, `rejected`,
`expired`, `EXECUTED`, `CANCELLED`, or any record with `execution_status` set in S2)
rejects every further transition (`HITLStateError` / `TaskAlreadyResolvedError`).
Expired or executed records can never be re-approved, re-rejected, or re-executed
(replay prevention).

### 2.2 Transition table (per store, enforcement evidence)

| From → To | S1 mechanism (evidence) | S2 mechanism (evidence) |
|-----------|--------------------------|--------------------------|
| PENDING → APPROVED | CAS `UPDATE … WHERE status='PENDING' [AND tenant_id=…]` — `models/pending_tasks.py::update_task_status` (AUD-4.6) | `HITLEngine.approve` flip after `_assert_decisionable` guard — `services/hitl/engine.py` |
| PENDING → REJECTED | same CAS | `HITLEngine.reject` (same guard) |
| PENDING → CANCELLED | `cancel_task` (AUD-4.7) | *(S2 expiry mirrors to CANCELLED)* |
| APPROVED → EXECUTED | `mark_executed` guard `WHERE status='APPROVED'` (AUD-4.5); `mark_execution_started` claims `execution_status='running'` exactly once | post-flip dispatch writes `execution_status=executed` |
| terminal → anything | `TaskAlreadyResolvedError` | `HITLStateError("Record … is not in pending state.")` |
| pending + TTL elapsed → decision | `TaskExpiredError` (AUD-4.3) | `ApprovalExpiredError` + record flipped to `expired` |
| concurrent decisions | CAS rowcount=0 → single winner (AUD-4.6) | `client.transaction()` CAS when the store supports it; commit conflict → `HITLStateError` (loser never dispatches) |

## 3. Rules

### 3.1 Authorization (who may decide)

1. **Role gate** — every decision route requires an authenticated admin *from the verified
   token*, never from the request body:
   - S1: `Depends(get_project_admin)` — tenant-bound admin role, subject extracted from the
     JWT (`api/dependencies.py::get_project_admin`, used by `approval_manager.py`);
   - S2: `Depends(get_current_admin)` — `api/dependencies.py::get_current_admin`, used by
     `hitl_admin.py`;
   - S4: tower-side RBAC + real-APPROVED-record verification (PR #718).
2. **Explicit actor at the engine layer** — `HITLEngine.approve/reject` refuse an empty
   actor (`ApprovalNotAuthorizedError`); the recorded approver is the identity the route
   extracted from the token (`subject` / `user_id`).
3. **Tenant match** — when the record is tenant-scoped *and* the caller carries a tenant
   context, they must match (`ApprovalNotAuthorizedError` in S2; tenant predicate inside the
   S1 CAS `WHERE tenant_id=…`).
4. **Not-self-approval** — producers are system components
   (`auto_skill_creator.suspend_for_approval`, automation registry); the requester recorded
   on S1 records (`created_by="system"|"hitl-engine"`) is never the approving human, so
   self-approval of an autonomous action is structurally excluded. Residual: S1 does not
   hard-verify `created_by != resolved_by` for future user-initiated task types — tracked as
   a follow-up, not silently assumed.

### 3.2 Idempotency (approve-then-execute semantics)

**Approve is a decision, execute is its single-shot consequence.**

- The decision flip and the dispatch are separate steps: `resolve_executor` runs BEFORE the
  flip (fail-closed on unknown targets — "approved but nothing happened" is structurally
  impossible, `services/hitl/dispatch.py::resolve_executor`), and the executor runs only
  after the flip committed.
- **A second approve of the same record returns an error and MUST NOT re-execute.**
  S2: state guard raises before dispatch (`HITLStateError`, `test_duplicate_approve_*`).
  S1: CAS rejects (`TaskAlreadyResolvedError` → HTTP 409) and `mark_executed` allows the
  EXECUTED transition exactly once (AUD-4.5).
- Execution failure does NOT undo the approval (the decision is immutable); the record lands
  in `execution_status="failed"` with `execution_error` + ledger entry
  `approval_execution_failed` (S2) / `execution_error` column (S1), and the failure is
  re-raised loudly (HTTP 5xx on S2 routes) — silent no-op execution is forbidden.

### 3.3 Replay prevention

Terminal states are absorbing: `approved`/`rejected`/`expired`/`executed`/`cancelled`
records reject every decision API. S1 additionally verifies the canonical payload SHA-256
(`payload_hash`, AUD-4.4) before any decision, so a tampered payload can neither be approved
nor replayed (`PayloadTamperedError` → HTTP 409).

### 3.4 Expiry

Default decision window: **24h** (`DEFAULT_APPROVAL_TTL_SECONDS`, identical in both stores —
`models/pending_tasks.py`, `services/hitl/engine.py`). `suspend_for_approval` stamps
`expires_at` (S2, since #481) and `create_pending_task` stamps it (S1). Expiry is evaluated
at decision time; expired records are filtered from pending queues (`list_pending`,
`HITLEngine.get_pending_approvals`) and S2 marks the record `expired` on first touch.

### 3.5 Tenant scoping

- S1: records carry `tenant_id` (AUD-4.1); listing is tenant-filtered; the decision CAS
  includes `AND (? IS NULL OR tenant_id = ?)`.
- S2: records may carry `tenant_id` (stamped by `suspend_for_approval(..., tenant_id=…)`);
  decisions pass the caller's tenant context (route) and mismatch → `ApprovalNotAuthorizedError`.
  Records without a tenant stamp remain global-admin decisions (the S2 queue is a platform
  admin queue by design, `hitl_admin.py` module docstring).
- Audit records (`hitl_audit_ledger`) inherit the store's tenant isolation.

### 3.6 Append-only records

- **Status transitions are monotonic and timestamped** (`updated_at` advances on every
  committed transition; S1 additionally stamps `resolved_at`; S2 stamps `expired_at`,
  `executed_at`). No transition ever rewrites a previous decision.
- **The audit trail is strictly append-only**: `HITLAuditLedger` extends the cryptographic
  SHA-256 hash chain (`core/security/cryptographic_ledger.py`) and only ever INSERTs blocks
  (Supabase `hitl_audit_ledger` append-only table + Firestore fallback,
  `services/hitl/hitl_ledger.py` — MANUAL_STEPS 7.5). S1 decisions additionally emit
  security-audit events (`approval_manager._audit`, Redis audit stream).
- Delete/update paths do not exist for ledger blocks in application code.

## 4. API error contract (decision routes)

| Situation | S2 `hitl_admin` | S1 `approval_manager` |
|-----------|-----------------|------------------------|
| missing record | `404` | `404` |
| already decided (duplicate/replay) | `409` (`HITLStateError`) | `409` (`TaskAlreadyResolvedError`) |
| expired approval | `410` (`ApprovalExpiredError`) | `410` (`TaskExpiredError`) |
| unauthorized approver / tenant mismatch | `403` (`ApprovalNotAuthorizedError`) | `403` (auth dependency) |
| unknown target (fail-closed pre-flip) | `400` (`ApprovalDispatchError`) | `400`/`403` (payload validation) |
| execution failure after approval | `500` (record keeps `execution_status=failed`) | `500` (`"Skill execution failed"`) |

## 5. UI contract (frontend ApprovalQueue)

- `ApprovalQueue` polls `GET /api/v1/hitl/pending` (S2, 15s) and posts
  `POST /api/v1/hitl/approve|reject/{record_id}` — records shown are always
  `pending_approval` and unexpired (expiry + terminal states are filtered server-side).
- Approve executes the action synchronously when an executor is registered for the target;
  the response `record.execution_status` ∈ `{executed, failed}` is the authoritative outcome.
- `4xx` error codes above are surfaced to the admin verbatim; a `409`/`410` means the
  decision lost a race or aged out — the UI must re-fetch the queue, not retry blindly.

## 6. Requirement → evidence matrix (#481 acceptance)

| #481 requirement | Evidence |
|------------------|----------|
| canonical state transition documented | this document §2 (S1: `models/pending_tasks.py:36-58,272-355`; S2: `services/hitl/engine.py`) |
| explicit authorization before execution | `api/dependencies.py:143-163`; `hitl_admin.py` decision routes; engine-level `_assert_decisionable` (#481) |
| idempotency check before execution | S2 state guard + pre-flip `resolve_executor` (`dispatch.py:95-110`); S1 CAS + `mark_executed` (`pending_tasks.py:325-350,405-432`) |
| duplicate approvals cannot double-execute | `tests/services/test_hitl_dispatch.py::test_duplicate_approve_rejected_by_state_machine`; `tests/security/test_hitl_state_machine.py::test_duplicate_execution_guard`; `tests/hitl/test_hitl_approval_contract.py` (#481) |
| expired approvals | S1 `TaskExpiredError` (`pending_tasks.py:318-322`); S2 `expires_at` stamp + `ApprovalExpiredError` (#481) |
| unauthorized approvers | route RBAC (above); engine empty-actor + tenant-mismatch gates (#481) |
| execution failures | S2 `execution_status=failed` + ledger `approval_execution_failed` (`engine.py` M17 P-B block); `test_approve_execution_failure_is_loud_and_recorded` |
| tenant-scoped records | S1 `tenant_id` CAS (AUD-4.1); S2 optional `tenant_id` stamp + scope check (#481) |
| append-only records | hash-chain ledger `services/hitl/hitl_ledger.py` (Supabase append-only table); monotonic transition stamps |
| tests consolidated | `backend/tests/hitl/test_hitl_approval_contract.py` (#481) + existing suites above |

## 7. Residuals / follow-ups (tracked, not silently open)

1. S1 `created_by != resolved_by` hard check for future user-initiated task types (§3.1.4).
2. S2 producers do not yet stamp `tenant_id` per record (callers pass none today); scoping is
   enforced the moment both record + caller carry a tenant context.
3. S2 CAS is transactional only on stores exposing `client.transaction()` (real Firestore);
   the in-memory/test fakes exercise the read-guarded path, and the canonical S1 store
   always provides true CAS.
