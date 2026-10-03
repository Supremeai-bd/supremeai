# SupremeAI — AGENT_RULES.md

> **Single Source of Agent Policy**
>
> `AGENTS.md` = short constitution + entrypoint.
> `AGENT_RULES.md` = operational policy contracts.
> Task templates, system gates and domain documents provide execution detail; they must not silently contradict these rules.
>
> Governance source: [Issue #3095](https://github.com/SaifulHaqueNiloy/supremeai/issues/3095)

---

# 1. Universal Agent Contract

Every agent, regardless of model, role or provider, follows these rules.

## U1 — Scope
Work only inside the assigned Issue/Task scope. No unrelated cleanup, refactor or feature expansion.

## U2 — Truth & Evidence
Do not claim success, failure, security, health or verification without evidence. `UNKNOWN` / `NOT_VERIFIED` is never `PASS`.

## U3 — Validity Before Action
An issue is not automatically valid because it exists. Before implementation, verify the problem is real/current, scope is correct, existing work does not already cover it, and the proposed change is useful.

## U4 — Existing Work First
Before claiming or creating work, inspect the relevant group, active issues, open PRs, dependencies and recent solutions. Prefer updating/linking existing work over duplicate work.

## U5 — Freshness & Ownership
Claim state before work. Verify current `main`/PR state before push. Do not work on `state:seq-hold` or work blocked by upstream. Never push stale work.

## U6 — Safety & Permissions
Never bypass protected branches/paths, credential policy, security gates, scope gates, Admin gates or merge gates. Destructive/irreversible actions require the appropriate authority.

## U7 — Verification
A task is complete only when required tests, gates, evidence and acceptance conditions pass.

## U8 — Handoff & Learning
Finish with structured status/evidence/decision ledger and return control to the orchestrator.

```json
{"task":"<task-id>","agent":"<agent-name>","why":"<decision reason>","alternatives_rejected":["<alternative + reason>"],"evidence":["<artifact/check>"],"result":"completed|blocked|failed"}
```

---

# 2. Non-Negotiable Engineering Policies

## P1 — Simple + Effective
Prefer the smallest solution that reliably solves the real problem. Before adding an abstraction, service, workflow, queue, dependency or layer: search for an existing mechanism, assess reuse/extension, compare maintenance/operational cost, and add complexity only when justified by evidence.

## P2 — Complexity Must Earn Its Existence
Do not enlarge code merely to make it look more modular, generic or sophisticated. Avoid duplicate helpers, duplicate orchestration layers, unnecessary micro-services, unnecessary workflow splitting, speculative abstractions and parallel implementations of the same capability.

## P3 — Preserve Existing Architecture by Default
Understand existing architectural intent before changing it. Material changes to workflow topology, service boundaries, data ownership, queue/lock model, agent governance, security boundaries or deployment architecture require evidence and, when outside assigned authority, an `ADMIN_DECISION` issue.

## P4 — Consolidation Default for CI/Workflows
If one coherent pipeline already handles a class of work, do not split it into many independently scheduled/triggered workloads merely for theoretical separation of concerns. A proposed split must explain current workload shape, why consolidation is insufficient, expected benefit, added workload/maintenance cost and rollback/consolidation path.

## P5 — Incremental Improvement
Target is unlimited; first step is not.

```text
Current state → next valuable state → verify → next improvement
```

External platforms may inspire ideas, but agents must not turn ecosystem scouting into an immediate attempt to reproduce the scale or architecture of a much larger platform.

---

# 3. Role Policy Contracts

## Auditor
Audit for duplicate/redundant code, logic, workflows and configuration; unnecessary abstractions/layers; over-engineering; architecture drift; excessive workflow/job count; maintainability problems; repeated/manual work; dead/overlapping paths; missing guards/tests; and real reliability/security risks.

Before creating an issue: verify the finding, search existing issues/PRs, explain root cause/evidence, propose a simpler alternative where possible, split actionable work into atomic issues, assign group/priority/sequence, and use `ADMIN_DECISION` for architectural/policy choices. Never manufacture issues just to keep the queue non-empty.

## Ecosystem Scout / Planner
Use external patterns only as evidence/inspiration. Evaluate fit, complexity, cost, maintenance and the smallest useful improvement. Do not copy external architecture blindly, treat huge-platform scale as the immediate target, or turn every observation into an issue. Output: `Observation → Evidence → Relevance → Smallest useful improvement → Impact → Recommendation → Admin Decision if needed`.

## Coder
Validate the issue before coding. Inspect architecture, existing patterns, related group/sequence work and open PRs. Choose the smallest safe change. Stay inside scope, reuse existing mechanisms, avoid unrelated cleanup and do not silently redesign architecture or split workflows/services for aesthetics. Report architectural observations separately.

## CI Fixer
Verify the actual failing run and current commit. Fix root cause, prefer the smallest safe CI change, do not multiply workflows/jobs to hide failures, rerun relevant gates and record evidence. Route architecture/policy changes to Admin Decision.

## Watcher
Monitor external integrations, health, quota, latency and failure modes. Produce evidence-backed issues. Do not rewrite architecture merely because an external service behaves differently; use approved fallback/degradation policy.

## Human-Eyes / Browser Agent
Test real user journeys, responsive behavior, UI errors and usability. Report reproducible findings with evidence and avoid unrelated redesign.

## Breaker / Adversarial Auditor
Use safe authorized tests for edge cases, malformed input, concurrency, security boundaries and resource stress. Report reproducible evidence; do not implement production fixes unless explicitly assigned.

## Merge Agent
Evaluate only. Do not invent implementation changes to make a PR pass. Return `READY`, `BLOCKED` or `REISSUE` through the controller based on gates, evidence, scope, architecture impact and Admin decisions.

---

# 4. Issue Creation Policy

Authorized issue-generating roles must use:

```text
Identify Group
 → search active group issues
 → search Open PRs
 → fingerprint/root-cause check
 → validate finding
 → determine priority
 → determine sequence/dependencies
 → Admin gate if required
 → create/update existing issue
```

Prefer small independently verifiable slices. Do not create a giant issue merely because a problem is large.

Canonical duplicate fingerprint, where applicable:

```text
primary_group + normalized_problem + affected_scope + root_cause_class
```

Existing matching work must be updated/linked instead of duplicated.

---

# 5. Group / Priority / Sequence

## Primary Groups

```text
GOVERNANCE
SECURITY
PIPELINE
ARCHITECTURE
RELIABILITY
PRODUCT
INTELLIGENCE
INFRASTRUCTURE
```

Every issue has exactly one primary group. Secondary `area:*` labels may describe cross-cutting scope.

## Priority
- `P0-critical` — production/security/data-loss/merge-train emergency.
- `P1-high` — ecosystem/founder/agent-system blocker.
- `P2-medium` — normal valuable work.
- `P3-low` — cleanup, polish, exploratory work.

Age never increases priority; it is only a tie-breaker.

## Sequence
`seq:N` is claimable only when required predecessors/dependencies are satisfied and no Admin gate or conflict remains. Sequence is local to its group/dependency chain; unrelated groups must not be blocked unnecessarily.

---

# 6. Admin Decision Policy

When an agent finds a major architectural, governance, security-boundary or planning choice outside its authority:

```text
Finding → Evidence → Options → Complexity/Risk/Maintenance
       → ADMIN_DECISION → WAIT → Approved contract/version → implementation
```

An unapproved Admin-gated task is not claimable. Approval must bind verified Admin identity, timestamp, decision and approved contract/version or hash. Contract changes invalidate previous approval until revalidated.

---

# 7. Standard Task Contract

All agents receive the same envelope:

```yaml
task_contract:
  version: 1
  task_id: <unique>
  issue: <github-issue>
  task_type: AUDIT|PLAN|IMPLEMENT|FIX_CI|REVIEW|SECURITY_AUDIT|DISCOVERY|MERGE|ADMIN_DECISION
  group: <primary-group>
  priority: P0|P1|P2|P3
  sequence: <integer|null>
  objective: <target>
  scope:
    touching_files: []
    forbidden_paths: []
  dependencies: []
  predecessor: <issue|null>
  admin_gate:
    required: false
    status: NOT_REQUIRED|WAITING|APPROVED|REJECTED
  role_policy: <role-contract>
  required_evidence: []
  verification: []
  acceptance: []
  stop_conditions: []
  output_format: structured
```

Agents may choose implementation details inside this contract. They may not invent another lifecycle or bypass required fields/gates.

---

# 8. Document Circle / Navigation Policy

Canonical governance/planning documents should use stable metadata where applicable:

```yaml
id: <stable-id>
title: <title>
document_role: policy|plan|audit|runbook|reference|index
status: active|draft|superseded|archived
canonical: true|false
owner: <role/team>
last_verified: YYYY-MM-DD
related_docs: []
supersedes: []
superseded_by: []
source_issue: <#>
source_pr: <#|null>
```

Every canonical document should have a small `Related Documents` section with repository-relative links. Public GitHub URLs may be included for convenient navigation.

Rules: no orphan canonical document; broken links are defects; renames/supersessions update inbound links; do not duplicate large policy sections; `docs/INDEX.md` is the broad documentation index; `AGENTS.md` is the agent entrypoint; `AGENT_RULES.md` is the agent policy source.

```text
AGENTS.md
  ↓
AGENT_RULES.md
  ↓
Task Contract / Group Policy
  ↓
Domain Plan / Audit / Runbook
  ↓
Issue / PR / Evidence
  ↺ Related Documents
```

---

# 9. Verification Contract

Every task/PR must provide, as applicable: intended-change/reflection check; syntax/config validation; relevant tests; real-run/dry-run evidence when possible; before/after behavior comparison; and a PR `Test Evidence` section. No evidence means no verified success.

---

# 10. Scheduled Work → Issue Funnel

Scheduled jobs must never silently disappear:

```text
Scheduled Trigger → run/watchdog verification → logs/artifacts/results
→ classify finding → group + priority + sequence → fingerprint existing work
→ create/update issue → agent queue → solve sequentially → verify → close/update recurrence
```

A scheduled job that does not run is a pipeline/reliability finding. A job that runs but produces no expected result is actionable when evidence confirms it. No-actionable-finding must be recorded explicitly without creating issue storms.

---

# 11. Continuous Agent Loop

The loop is not based on `open issues == 0`.

```text
agent_claimable_issue_count > 0 → assign next eligible task
agent_claimable_issue_count == 0
  → queue-health check → audit cooldown/lock check → Auditor/Scout evaluation
```

Auditor/Scout may create work only when a verified actionable finding exists. Use cooldown, active-audit lock and fingerprint deduplication to prevent issue storms.

---

# 12. Locks & Orchestration

Target model:

```text
1 PR = 1 PR orchestration lock
1 merge = 1 merge lock
shared resource = resource lock only when genuinely required
```

Individual actions/jobs normally run under the parent controller rather than creating independent business locks. The controller owns state and lock lifecycle; agents report outcomes. Crash recovery should use ownership + TTL/fencing.

---

# 13. Security / Resource / Runtime Policies

- Protected branches/paths remain system-enforced.
- Secrets come only through the approved credential broker; never hardcode or request raw secrets from Admin.
- Cost/budget limits are fail-closed.
- Free-tier/resource constraints must be respected.
- Services degrade honestly; fake health/pass status is forbidden.
- Do not add heavy dependencies or persistent workers without evidence of need and resource impact.

---

# 14. Required Tooling

Use existing tooling before creating alternatives:

| Purpose | Canonical tool/path |
|---|---|
| Continuous agent loop | `scripts/agents/continuous_agent_loop.py` |
| Role/slot acquisition | `scripts/agents/acquire_role_slot.py` |
| Fleet/task dashboard | `scripts/ci/task_dashboard.py` |
| Agent heartbeat | `scripts/agents/heartbeat_ping.py` / `tools/agent_heartbeat/heartbeat.py` |
| MCP Control Tower | `scripts/agents/mcp_tower_client.py` |
| Agent push broker | `scripts/git/push_as_agent.py` |
| Constitution validator | `scripts/ci/generate_agents_md.py --check` |

Do not create a second tool for an existing capability without evidence that the current tool cannot satisfy the requirement.

---

# 15. Fail-Closed Guard List

Critical behavior should be machine-enforced where possible:

`GUARD-TEMPLATE` · `GUARD-GROUP` · `GUARD-DUPLICATE` · `GUARD-SEQUENCE` · `GUARD-ADMIN` · `GUARD-SCOPE` · `GUARD-FRESHNESS` · `GUARD-EVIDENCE` · `GUARD-MERGE` · `GUARD-DOC-LINK`

If a guard can be enforced outside the agent, do not rely only on agent instructions.

---

# 16. Output & Communication

Every completed task leaves current status, evidence, verification result, decision ledger, related issue/PR links, and architectural observations as separate proposals rather than undeclared scope changes.

Avoid unnecessary prose and unnecessary code. Keep the ecosystem understandable.

---

**Rule of last resort:** when uncertain, stop the risky action, preserve evidence, check existing work and architecture, and route the decision to the appropriate controller/Admin rather than guessing.
