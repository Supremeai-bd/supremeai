# SupremeAI Master Roadmap

**Version:** 1.0  
**Date:** 4 September 2026  
**Purpose:** Consolidate the repository’s active plans, implementation audits, real-life failure analysis, security governance, and go-live requirements into one executable roadmap.

> This is the planning index, not a claim that every capability is complete. A capability is **connected** only when it has a real implementation, runtime registration/caller, authenticated tenant scope, durable state, event/audit propagation, failure handling, and automated evidence.

## 1. Product North Star

SupremeAI is a chat-centered, self-learning agent platform. Chat is the control plane; agents, models, memory, browser, tasks, files, realtime, integrations, admin controls, and evolution are governed spokes. Human-in-the-loop is permanent: low-risk work may run automatically, while sensitive, destructive, external, or irreversible work requires explicit approval and audit.

```text
Client / Chat
  -> typed request + identity + tenant + project + trace
  -> intent + capability discovery
  -> reusable implementation / resource discovery
  -> cost, risk, policy, quota and HITL decision
  -> model/tool/task/browser execution
  -> validation + evidence + persistence
  -> event/audit/metrics
  -> streamed result and next action in Chat
```

## 2. Authority and Plan Reconciliation

When documents disagree, apply this order:

1. Current production code and tests
2. Current security/policy constraints
3. `docs/plans/implementation_plan.md`
4. Current specialized master plans
5. Older plans, treated as historical input

Active production topology is **Render Docker FastAPI + Supabase/PostgreSQL + Firebase Hosting**. Kubernetes, Cloud Run, GCP Functions, account multiplication, stealth keep-alives, CAPTCHA bypass, and unrestricted self-rewrite are not active commitments. Free-tier services are replaceable execution surfaces, never correctness dependencies.

## 3. Current Baseline

| Domain | Current status | Roadmap interpretation |
|---|---|---|
| App bootstrap and route registry | Connected but overloaded | Generate authoritative route metadata and remove drift |
| Chat and frontend API foundation | Connected, fragmented | Make Chat the only governed execution entrypoint |
| Auth/RBAC/tenant isolation | Partial | Prove object-level authorization adversarially |
| Orchestration hub | Foundation connected | Replace bounded adapters with real use-case services |
| Memory and knowledge | Partial | Canonical recall, provenance, quarantine, promotion |
| Browser | Partial | Unify session/action/preview/HITL state |
| Realtime | Partial | One event envelope, replay, dedupe, backpressure |
| Tasks/queue | Partial | Durable state, cancellation, retry, idempotency |
| Models/providers | Partial | Neutral registry, budgets, health, deterministic fallback |
| Admin/evolution | Partial/research | Controlled workflows with approval and signed artifacts |
| Persistence | Partial | Remove process-local source-of-truth state |
| Scale/deployment | Not proven | Measure first; keep Render as active track |
| Release readiness | Controlled beta | Go-live only after critical/high gates are evidenced |

## 4. Non-Negotiable Cross-Cutting Contract

Every chat-originated execution must carry:

```json
{
  "execution_id": "uuid",
  "actor_id": "uuid",
  "tenant_id": "uuid",
  "project_id": "uuid|null",
  "conversation_id": "uuid|null",
  "trace_id": "string",
  "intent": "string",
  "capability": "string",
  "policy_decision": "allow|deny|approval_required",
  "status": "queued|running|blocked|succeeded|failed|cancelled",
  "budget": {"input": 0, "output": 0, "currency": "token"},
  "tool_calls": [],
  "evidence": []
}
```

The contract must be implemented in API schemas, service calls, task records, model routing, browser actions, memory writes, events, audit logs, frontend state, and tests. Client-supplied `user_id` or `tenant_id` is never authoritative.

## 5. Master Execution Phases

### Phase 0 — Baseline, drift control, and release safety (P0)

- [ ] Freeze active architecture and mark conflicting docs historical.
- [ ] Generate route inventory from FastAPI/OpenAPI with auth, tenant, persistence, event, owner, and test metadata.
- [ ] Create a module-to-capability matrix linking route, service, repository, event, UI caller, and test.
- [ ] Add CI drift checks for route registry/OpenAPI/frontend callers and forbidden `backend.` imports.
- [ ] Close import/runtime failures; no silent `ImportError` capability checks.
- [ ] Add evidence records with commit SHA, test command, owner, and expiry date.
- [ ] Enforce go-live rule: Critical 100%, High 100%, Medium known/accepted/documented.

**Exit evidence:** clean boot, generated inventory, no unowned P0 gaps, reproducible CI gates.

### Phase 1 — Canonical chat control plane (P0)

- [ ] Define typed `ExecutionContext`, `ExecutionResult`, `Capability`, `PolicyDecision`, `Approval`, and `EventEnvelope` contracts.
- [ ] Make Chat the canonical entrypoint for all user-visible execution; retain legacy routes only as authenticated compatibility shims.
- [ ] Add intent resolution followed by capability discovery, reusable implementation discovery, resource authorization, cost/risk evaluation, and methodology selection.
- [ ] Route every capability through policy, quota, idempotency, timeout, cancellation, retry, audit, and evidence hooks.
- [ ] Add model-neutral provider registry with health, latency, cost, quota, circuit breaker, and deterministic fallback.
- [ ] Add persistent execution records and correlation-aware event emission.

**Exit evidence:** one end-to-end chat request can plan, approve, execute, stream, persist, audit, and recover.

### Phase 2 — Identity, security, and HITL enforcement (P0)

- [ ] Centralize authenticated session handling; remove client token query strings and unsafe local token patterns.
- [ ] Enforce actor → tenant → workspace/project → resource ownership on every read and write.
- [ ] Build a single approval service for external, destructive, privileged, financial, credential, browser takeover, and production actions.
- [ ] Add short-lived approval tokens, expiry, replay protection, actor binding, reason, and audit trail.
- [ ] Add prompt-injection and tool-confusion defenses before model/tool execution.
- [ ] Treat AST scanning as a pre-filter only; use isolated process/container execution with no-network, read-only filesystem, resource limits, and kill verification.
- [ ] Add adversarial IDOR/BOLA, cross-tenant, forged identity, expired session, admin boundary, approval replay, and secret-exfiltration tests.

**Exit evidence:** all critical paths fail closed and every sensitive action has verifiable human decision history.

### Phase 3 — Durable state and real spoke adapters (P0/P1)

- [ ] Make Supabase/PostgreSQL the source of truth for execution logs, task state, browser session metadata, approvals, audit, model usage, and memory candidates.
- [ ] Use Redis only for cache, locks, rate limits, queues, cursors, and ephemeral coordination.
- [ ] Replace process-local browser/task/credential/permission state with durable metadata plus worker-owned handles.
- [ ] Connect Task spoke to durable queue semantics: idempotency, backpressure, priority, cancellation, retry policy, dead-letter state, and progress events.
- [ ] Connect Artifact/File spoke with ownership, content hashing, malware/type checks, retention, and evidence links.
- [ ] Connect Admin and Evolution spokes to real services, never status-only adapters; require approval for mutations.
- [ ] Connect External/MCP tools through scoped authorization and provider-neutral adapters; never expose credentials to clients.

**Exit evidence:** restart/redeploy does not lose authoritative state; each spoke has a real handler and integration test.

### Phase 4 — Memory, learning, and controlled self-evolution (P1/P2)

- [ ] Implement canonical pipeline: consent → tenant-scoped recall → provenance/trust filter → context budget → response → evaluator → quarantine → promotion.
- [ ] Add deduplication, retention, compaction, source timestamps, retrieval quality, contradiction detection, and deletion/export controls.
- [ ] Connect working, summary, and persistent memory to the same chat execution context.
- [ ] Keep evolution learning disabled until a real consumer and evaluation dataset exist.
- [ ] Implement candidate skill/code artifact → tests → red-team evaluation → human approval → signed promotion → rollback.
- [ ] Treat digital twin, Theory of Mind, genetic rewrite, and autonomous deployment as opt-in controlled research, not default production behavior.

**Exit evidence:** every promoted lesson or skill has provenance, evaluator result, approver, signed artifact, and rollback path.

### Phase 5 — Browser intelligence and secure HITL (P1)

- [ ] Select one canonical browser state model and retire duplicate legacy state.
- [ ] Build typed frontend browser client for session creation, actions, screenshots, semantic DOM, status, close, and takeover.
- [ ] Enforce SSRF/DNS-rebinding/redirect/egress policy and action limits.
- [ ] Add semantic DOM pruning and vision grounding behind confidence thresholds with human fallback.
- [ ] Add secure screencast events, reconnect cursor, ownership checks, and signed takeover handoff.
- [ ] Add bounded swarm sessions with per-tenant quotas, cancellation, and aggregate resource limits.
- [ ] Do not implement CAPTCHA or anti-abuse circumvention; pause and request human action where required.

**Exit evidence:** create → navigate → action → screenshot/DOM → optional takeover → audit → close passes in Playwright E2E.

### Phase 6 — Unified realtime and frontend experience (P1)

- [ ] Define one versioned event envelope for Redis, SSE, and WebSocket.
- [ ] Add replay cursors, deduplication, authorization re-check, heartbeat, backpressure, and reconnect recovery.
- [ ] Convert each frontend feature to typed client → SWR/query hook → API contract → real loading/error/empty/retry states.
- [ ] Remove portal build branching; use one role-aware application shell and backend-authoritative admin permissions.
- [ ] Connect Command Center, browser, tasks, approvals, memory, evolution, health, and artifacts to live event/state contracts.
- [ ] Add accessibility and responsive tests for the primary chat/control-plane journey.

**Exit evidence:** a user can observe and resume any owned execution from Chat without stale or fake UI state.

### Phase 7 — Free-tier reliability and measured scale (P1/P2)

- [ ] Add Render cold-start UX, health wake-up, boot-time budget, and graceful degradation.
- [ ] Cap voice buffers, browser concurrency, request payloads, memory use, and event-loop blocking work.
- [ ] Use PgBouncer paths, DB circuit breakers, queued writes, cache fallback, and explicit idempotent migrations.
- [ ] Add SSE heartbeats and partial-result recovery; sweep stale WebSocket connections.
- [ ] Add OpenTelemetry traces, SLOs, error budgets, cost/usage dashboards, and provider failure metrics.
- [ ] Run k6/load and chaos tests before changing topology. Consider read replicas, multi-region, Kubernetes, or paid capacity only when measurements justify them.

**Exit evidence:** measured beta SLOs, capacity model, failure recovery report, and cost envelope.

### Phase 8 — Controlled production release (P0 gate)

- [ ] Complete full backend/frontend/type/lint/security/secret/dependency/build gates.
- [ ] Apply reviewed migrations explicitly; verify backup and restore.
- [ ] Verify authentication, RBAC, tenant isolation, billing/quota, HITL, browser, memory, task, artifact, and external tool flows.
- [ ] Remove debug/mock/development paths and verify production environment matrix.
- [ ] Produce release SHA, evidence bundle, known limitations, rollback tag, incident contacts, and post-deploy health report.
- [ ] Release only through PR and approved deployment path; never push directly to production branch.

**Exit evidence:** go-live checklist is fully evidenced, not merely checked.

## 6. Capability Acceptance Matrix

| Capability | Must prove |
|---|---|
| Chat | Authenticated request, plan, stream, persistence, retry, audit |
| Model fleet | Registry, budget, health, fallback, provider isolation |
| Memory | Scoped recall, provenance, quarantine, promotion, deletion |
| Task | Durable queue, progress, cancellation, retry, idempotency |
| Browser | Session owner, safe URL, action validation, screenshot, takeover |
| Artifact | Upload/output ownership, hash, scan, retention, retrieval |
| Realtime | Versioned events, auth, heartbeat, replay, dedupe |
| Admin | RBAC, step-up approval, audit, rollback |
| Evolution | Candidate-only mutation, evaluation, approval, signed promotion |
| External tools | Scoped consent, short-lived credentials, timeout, audit |

## 7. Definition of Done

A milestone is complete only when:

- source implementation exists;
- runtime registration and a real caller exist;
- auth, tenant, resource and approval policy is enforced;
- authoritative state is persisted;
- events, audit, metrics and evidence are emitted;
- success, failure, timeout, retry, cancellation and restart paths are tested;
- frontend and client contracts consume the real result;
- documentation status is updated with commit SHA and remaining limitations.

## 8. Immediate Build Order

1. Canonical execution/event contracts and persistent execution records.
2. Route/capability inventory and drift CI.
3. Identity, tenant, approval, audit, and adversarial authorization tests.
4. Durable task/artifact/browser state and real spoke service adapters.
5. Unified memory/evaluation/promotion pipeline.
6. Browser typed client, semantic DOM, vision, screencast, and takeover.
7. Realtime replay and unified frontend shell/state.
8. Reliability, observability, load evidence, and go-live gates.

This roadmap supersedes competing roadmap claims while preserving specialized plans as implementation references. It does not treat planned capability as delivered capability.
