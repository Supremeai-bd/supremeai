# Production Tool Execution Inventory (AUD-3.1)

> Scope: every path through which a tool / side-effecting action can be executed in
> production, and which policy controls apply. The **canonical policy boundary** is
> `backend/core/security/tool_gateway.py` (`tool_policy_gateway`).

## 1. Canonical policy boundary (P0 remediation, AUD-3.2)

All side-effecting tool executions MUST pass `ToolPolicyGateway.enforce()` /
`evaluate()` before running. The gateway enforces, in order:

1. **Identity** — authenticated principal (`user.sub`) required (fail-closed).
2. **Tenant** — tenant binding resolved from the JWT (`tenant_id` or `sub`).
3. **Role vs risk** — `high`/`critical` risk tools require the `admin` role.
4. **Risk** — tools not registered in the gateway's risk registry default to `high`
   (fail-closed until classified).
5. **Budget** — per-tenant spend check via `core.cost_guard` for costed calls.
6. **Audit** — decision/execution/failure events emitted to the security audit log
   (`core.security.audit_logger`, Redis stream `audit:recent:`).

## 2. Execution paths and their controls

| # | Path | Entry point | Policy controls |
|---|------|-------------|-----------------|
| 1 | External platform actions (Slack/Notion/GitHub) | `POST /agent/action` → `api/routes/agent_action.py` → `ZeroCostSwarmOrchestrator` | AuthMiddleware JWT + **ToolPolicyGateway (risk=high)** + per-user integration ownership |
| 2 | Remote MCP tools | `core/mcp_client.py::MCPRegistryClient.execute_tool` | SSRF allowlist (`mcp_security.py`) + params JSON validation + **ToolPolicyGateway (risk=medium)** |
| 3 | MCP tool discovery (read-only) | `MCPRegistryClient.connect_and_discover`, `swarm_orchestrator` | SSRF allowlist; no side effects |
| 4 | Automation webhooks (n8n) | `core/automation/dispatcher.py::AutomationDispatcher.dispatch` | AuthMiddleware + idempotency store + execution recorder (`execution_recorder.py`) |
| 5 | Skill code execution | `core/skill_manager.py::get_skill` (`exec`) | AST vetting + locked builtins + DB-registered skills only |
| 6 | Synthesized tool execution | `services/tool_forge.py::ToolForgeService.execute_tool` | AST sandbox scan; **gateway enforcement pending (see §4)** |
| 7 | Ephemeral sandbox execution | `agents/ephemeral_executor.py` | Docker/microVM sandbox + path-traversal guard (currently no live production caller) |
| 8 | HITL-approved side effects | `POST /api/v1/hitl/approve/{id}` → `api/routes/approval_manager.py` | `verify_admin_session_fail_closed` + atomic PENDING-only state machine + payload hash + audit events |
| 9 | Browser automation | `api/routes/browser.py` | Router JWT + `require_admin_token` on credentials/scrape/browse/extract/URL-permission decisions |
| 10 | HTTP edge (all routes) | `core/app_builder.py` middleware stack | AuthMiddleware (fail-closed, public-path allowlist) → API key auth → AutonoGuard → idempotency (per-credential scoped) → rate limit |

## 3. Risk registry

Classify tools at registration: `tool_policy_gateway.register_tool(name, risk)`.
Unclassified tools are treated as `high` → admin-only. Example classifications:

| Tool pattern | Risk | Rationale |
|---|---|---|
| `platform_action.slack|notion|github` | high | external irreversible writes |
| `mcp.*` remote tools | medium | network calls, no local mutation |
| `read.*` / discovery tools | low | read-only |

## 4. Known residual gaps (tracked)

- `services/tool_forge.py` executes AST-vetted synthesized tools directly; wiring the
  gateway there requires a caller-identity context that the current API does not carry
  (all Forge callers are internal). Tracked for the identity-context refactor.
- `AutomationDispatcher` enforces idempotency + recording; integrating the gateway's
  budget check needs per-tenant mapping for webhook callers (service-to-service auth).

## 5. Adversarial test coverage (AUD-3.9)

- `backend/tests/security/test_tool_policy_gateway.py` — identity/tenant/role/risk/budget
  enforcement, unauthenticated denial, non-admin denial of high-risk tools, audit emission.
- `backend/tests/security/test_cross_tenant_isolation.py` — cross-tenant adversarial API
  matrix (attachment IDOR, conversation write isolation, HITL replay/tamper/expiry,
  API-key usage-record ownership, preference stream scoping).
- `backend/tests/core/test_multi_tenant_isolation.py` — TenantAwareFirestore scoping.
- `backend/tests/api/test_route_rbac_matrix.py` — admin-route guard matrix.
