# SupremeAI Federated Capability Circle Architecture (FCC)

> Status: **Implemented** · Contract version: `1` · Owner: backend/core/circles
>
> This document is the living specification of the FCC. It replaces the idea
> of one giant central control plane ("God Object") with **multiple connected
> circles**, each owning its domain locally, coordinated by a **small Global
> Governance Core**.

---

## 1. The idea in one picture

```text
                 Global Governance Core  (SMALL — cross-cutting only)
                 identity · policy · approval · correlation
                 lifecycle · audit · cross-circle events · realtime sync
                /   |   |   |   |   |   |   |   \ \
   LLM  Memory  Task  Browser  MCP  Admin  Realtime  Artifact  Evolution  Gateway
   Center Center Center Center Center Center Center  Center    Center    Center
     |      |      |       |      |      |        |         |          |       |
  adapters adapters adapters adapters adapters adapters adapters adapters adapters
```

**Rule:** modules never talk to modules directly. Traffic is always
`module → own circle center → shared control protocol (envelope) → other
circle center → module`. This avoids the `N² connections` trap.

---

## 2. What is central vs. what is local (the contract)

### Centralised — Global Governance Core (`core/circles/governance_core.py`)

| Concern | Implementation |
|---|---|
| identity / context | `ExecutionEnvelope` requires `tenant_id` + `actor_id` (JWT-derived at the API edge) |
| global policy | injectable `PolicyEvaluator`; default rejects missing context |
| approval | `approval_required` capabilities short-circuit to `APPROVAL_REQUIRED` before any handler runs |
| correlation | `correlation_id` propagates through envelope → events → journal → realtime mirror |
| execution lifecycle | overall deadline (`deadline_ms` ∩ capability `timeout_ms`), status normalization |
| audit | every routed execution event appended to `circle_event_journal` |
| cross-circle events | subscriber fan-out (`GovernanceCore.subscribe`) |
| realtime synchronization | the Realtime Circle subscribes to the core — zero-infrastructure event bus |

The core **must never** import domain modules (brain, memory, storage, api
routes, models…). Enforced by `tests/test_fcc_boundaries.py::GovernanceCoreBoundaryTests`.

### NOT centralised — owned by each Circle Center (`core/circles/centers/`)

| Local concern | Base-class surface |
|---|---|
| local registry | `register(spec, handler)` / `describe()` / `capabilities()` |
| local permissions | `local_permission(envelope) -> reason \| None` |
| local retries | `RetryPolicy(max_attempts, backoff_ms)` — exceptions retried, deadlines never |
| local health | `health() -> CenterHealth` (counters, latency EMA, last error) |
| local caching | opt-in `cache_ttl_ms` per capability (tenant-scoped keys) |
| local events | every handle returns `events: [EventEnvelope]` |
| local adapter selection | `resolve_adapter(envelope)` — lazy domain imports |
| domain logic | LLM routing, memory ranking, browser DOM, MCP providers, retry strategy, provider caches — **stay in the domain modules** |

---

## 3. The canonical wire contract (envelopes)

`core/circles/envelopes.py` — the ONLY permitted cross-circle format.

Request:

```json
{
  "execution_id": "exec_...",
  "circle": "memory",
  "capability": "memory.recall",
  "tenant_id": "tenant_1",
  "actor_id": "admin_1",
  "correlation_id": "corr_...",
  "payload": {},
  "policy": {},
  "deadline_ms": 3000
}
```

Result:

```json
{
  "execution_id": "exec_...",
  "status": "succeeded",
  "circle": "memory",
  "data": {},
  "events": [],
  "error": null
}
```

Statuses: `accepted · approval_required · running · succeeded · failed ·
rejected · cancelled · unavailable`. Errors are structured:
`{"code": "...", "message": "..."}` with stable codes:
`unknown_circle`, `unknown_capability`, `central_policy_denied`,
`local_permission_denied`, `human_approval_required`,
`execution_context_incomplete`, `deadline_exceeded`,
`capability_not_registered`, `circle_handler_failed`.

Legacy interop: `ExecutionEnvelope ⇄ CapabilityRequest` and
`ExecutionResult → ResultEnvelope` converters keep the pre-FCC
`circle_registry` surface working (kernel falls back to it when the
federation cannot serve a capability).

---

## 4. The circles (as implemented)

| Circle | Center file | Domain adapters (lazy) | Capabilities |
|---|---|---|---|
| Gateway | `centers/gateway_center.py` | conversation orchestrator, cognitive pipeline, `api.routes.health` | `system.health.read`*, `conversation.orchestrate`, `customer_support.resolve` |
| LLM | `centers/llm_center.py` | `brain.model_router.ModelRouter` | `llm.generate` |
| Memory | `centers/memory_center.py` | `memory.rag_pipeline.RAGPipeline` (threaded) | `memory.recall`*, `memory.store` |
| Task | `centers/task_center.py` | `core.queue.task_queue.RedisTaskQueue` | `task.submit` |
| Browser | `centers/browser_center.py` | `core.browser_session_manager.session_manager` | `browser.session.create`, `browser.session.close`, `browser.sessions.snapshot`* |
| MCP | `centers/mcp_center.py` | MCP config + `brain.mcp_client.MCPClient` (threaded) | `mcp.server.status`*, `mcp.tools.list`, `mcp.invoke`† |
| Admin | `centers/admin_center.py` | `models.pending_tasks` HITL service (threaded) | `admin.approvals.list`*, `admin.approve`†, `admin.reject`†, `admin.cancel` |
| Realtime | `centers/realtime_center.py` | in-process ring + subscribers | `realtime.publish` |
| Artifact | `centers/artifact_center.py` | `storage.asset_manager.AssetManager` | `artifact.url`* |
| Evolution | `centers/evolution_center.py` | `adaptive_engine.approval_workflow` | `evolution.approval.required`*, `evolution.proposals.pending`*, `evolution.evaluate`† |

\* tenant-scoped TTL cache · † approval-gated (governed path)

Honest degradation: when a backing service is unavailable (e.g. Redis for
`task.submit`), the center returns a **failed result with a machine-readable
code** — it never fakes success. Zero-infrastructure principle preserved:
the hot path needs no database or external queue.

---

## 5. Execution paths

**Hot path (zero infrastructure):**

```text
request → GovernanceCore.route → circle center.handle → local adapter → ResultEnvelope
```

**Governed path (risky / durable work):**

```text
request → global policy → approval gate → circle center → adapter → audit/event fan-out
```

Risk semantics: `approval_required` capabilities NEVER reach a handler via
`route()` — the core returns `APPROVAL_REQUIRED` and journals the request;
a human decision through the HITL surface (`models.pending_tasks`) is the
gate. The post-approval execution path is the center handler itself.

---

## 6. Public API surface

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/circles` | user token | federation topology: centers, capabilities, health |
| `GET /api/v1/circles/health` | user token | aggregated center health (`healthy/degraded/unavailable`) |
| `GET /api/v1/circles/events` | user token | recent realtime event mirror |
| `POST /api/v1/circles/dispatch` | **admin** | governed envelope dispatch — identity from JWT, never from body |

In-process doors:

- `get_governance_core().route(envelope)` — canonical cross-circle call
- `get_governance_core().dispatch_to(circle, capability, payload, actor_id=…, tenant_id=…)` — convenience
- `SupremeKernel.dispatch(KernelRequest)` — federation-first, legacy-registry fallback
- `circle_registry` (legacy flat registry) — unchanged compatibility surface

---

## 7. How to add a new circle (checklist)

1. Add the `CircleName` member in `core/circles/contracts.py` (if new).
2. Create `core/circles/centers/<name>_center.py`:

   ```python
   class <Name>Center(CircleCenter):
       circle = CircleName.<NAME>
       display_name = "…"
       owner = "backend/<module>"
   ```

3. Register capabilities with `LocalCapability` specs + handlers; wire
   domain modules via **lazy imports inside handlers** (adapter selection).
4. Add the center class to `_CENTER_TYPES` in `core/circles/centers/__init__.py`.
5. Mirror the capabilities in `core/circles/manifests.py` (same order).
6. Expose it via `POST /api/v1/circles/dispatch` automatically — no router change needed.
7. Add unit tests; run the boundary guard: `pytest tests/test_fcc_boundaries.py`.

The boundary guard will fail CI if you import another center, touch the
legacy registry, or grow the governance core with domain imports.

---

## 8. Verification matrix

| Guarantee | Enforced by |
|---|---|
| envelope wire format is exactly the FCC contract | `test_fcc_boundaries.py::test_envelope_is_the_only_wire_contract` |
| no center imports another center | `test_fcc_boundaries.py::test_no_center_imports_another_center` |
| centers never touch core/legacy registry directly | `test_centers_do_not_touch_governance_core_or_legacy_registry` |
| governance core has no domain imports | `test_governance_core_has_no_domain_imports` |
| every circle has a center | `test_centers_exist_for_every_circle` |
| manifests advertise only locally-served capabilities | `test_federation_advertises_registered_capabilities_only` |
| local concerns exist on the base class | `test_centers_local_concerns_present` |
| policy deny / approval / deadline / retry / cache / health behavior | `tests/test_circle_centers.py`, `tests/test_governance_core.py` |
| legacy registry + kernel + capability gateway keep working | `tests/test_circle_registry.py`, `tests/test_supreme_kernel.py`, `tests/core/test_capability_gateway.py` |

---

## 9. Design decisions log

- **Additive migration, no big-bang rewrite**: the pre-FCC flat registry
  remains as a compatibility surface; the kernel prefers the federation and
  falls back only when the federation cannot serve a capability.
- **Sync handlers run in worker threads** inside centers so local deadlines
  are enforceable and the event loop never blocks.
- **Approval requests are audited**: `execution.approval_required` events hit
  the journal (you can always answer "who asked for what").
- **Deadlines are never retried**; only transient handler exceptions are.
- **Realtime sync without infrastructure**: the core mirrors every routed
  execution event into the Realtime Center ring; durable stores can
  subscribe to the journal later.
