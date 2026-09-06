# SupremeAI Backend Simplification & Consolidation Plan

> Purpose: reduce backend fragmentation while preserving the full SupremeAI capability surface.

## 1. Non-negotiable rules

1. No capability reduction.
2. No dead-code deletion by AI judgement. Anything that looks unused is an asset until human review proves otherwise.
3. Prefer consolidation of duplicate logic and boundaries over deletion.
4. Preserve API contracts, auth, tenant isolation, security controls, background jobs, MCP, browser automation, memory, providers, governance, and failover.
5. Check static imports, dynamic imports, router registration, dependency injection, startup hooks, scheduled jobs, workers, config-driven references, tests and docs before moving anything.
6. Keep backward-compatible facades temporarily when a move could break hidden/runtime consumers.

## 2. Target backend shape

```text
backend/
├── app/                         # application bootstrap
│   ├── main.py
│   ├── router_registry.py
│   └── dependencies.py
├── api/
│   ├── routes/                  # thin HTTP/WebSocket boundaries
│   └── schemas/
├── core/
│   ├── config/
│   ├── security/
│   ├── database/
│   ├── observability/
│   └── runtime/
├── capabilities/
│   ├── chat/
│   ├── research/
│   ├── browser/
│   ├── agents/
│   ├── memory/
│   ├── automation/
│   ├── artifacts/
│   └── mcp/
├── orchestration/
│   ├── planner.py
│   ├── capability_registry.py
│   ├── executor.py
│   ├── verifier.py
│   └── recovery.py
├── integrations/
│   ├── llm/
│   ├── providers/
│   ├── redis/
│   ├── storage/
│   └── external/
├── workers/
├── models/
└── tests/
```

This is a target organization. An agent must map the current codebase into it incrementally rather than perform a blind rewrite.

## 3. Router consolidation

The repository already uses a central router-registration concept. Keep one authoritative registration boundary.

Rules:

- One canonical router registry.
- Feature routes live with their feature.
- Avoid multiple competing route files for the same API surface.
- Before moving a route, verify it is mounted, referenced by frontend clients/tests, and protected correctly.
- Do not mount every discovered route automatically; verify each route's contract first.

## 4. Service consolidation

Use domain services rather than many tiny one-purpose service files.

Example:

```text
provider_a_service.py
provider_b_service.py
provider_c_service.py
```

should generally become:

```text
integrations/llm/providers/
├── registry.py
├── base.py
└── adapters/
    ├── provider_a.py
    ├── provider_b.py
    └── provider_c.py
```

Only merge classes when they share the same responsibility and lifecycle.

## 5. Orchestration boundary

SupremeAI's core should be small and stable:

```text
Request
  ↓
Planner
  ↓
Capability Registry
  ↓
Policy / Permission
  ↓
Executor
  ↓
Verifier
  ↓
Recovery / Fallback
  ↓
Result + Memory
```

Capabilities should implement the work; orchestration should decide how and when to compose them.

## 6. Shared concerns

Centralize repeated implementations of:

- authentication/authorization
- request validation
- error normalization
- retry/backoff
- rate limiting
- provider selection
- telemetry
- security checks
- database session handling
- cache access

Do not create feature-specific copies of these unless there is a clear isolation requirement.

## 7. Worker/background architecture

Keep HTTP request handling separate from long-running execution.

```text
API → enqueue/dispatch → worker → capability → result store → API/realtime
```

Avoid duplicating the same execution logic in API routes and worker files.

## 8. AI-agent refactoring workflow

For each backend domain:

1. Inventory all files/classes/functions.
2. Build dependency and runtime-reference map.
3. Identify duplicates and overlapping responsibilities.
4. Identify canonical implementation.
5. Move secondary implementations behind the canonical boundary.
6. Add compatibility imports where needed.
7. Run unit + integration + API contract tests.
8. Exercise startup and worker paths.
9. Verify security and authorization again.
10. Update documentation.

## 9. Success criteria

- Smaller number of overlapping routers/services.
- Clear capability boundaries.
- One orchestration path.
- One canonical implementation for shared concerns.
- No loss of existing capability.
- No unexplained API disappearance.
- CI/security checks remain green.

## 10. Human-review rule

Any file/class that appears unused but may represent a future, queryable, dynamically loaded, experimental, MCP, provider, agent, governance, recovery, or self-evolution capability must be classified as:

`PRESERVE — HUMAN REVIEW REQUIRED`

It must not be deleted by an AI agent.
