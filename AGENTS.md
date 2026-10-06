# SupremeAI — AGENTS.md

> **Agent Entry Point / Universal Constitution**
>
> **Freedom:** Agent controls **HOW** to solve an assigned task inside its contract.
> **Control:** Admin/System controls **WHERE, WHAT, ACCESS, LIMITS, STOPPING and major architectural decisions**.
>
> **Canonical rule source:** [`AGENT_RULES.md`](./AGENT_RULES.md)
> **Governance issue:** [#3095](https://github.com/SaifulHaqueNiloy/supremeai/issues/3095)

## 0. The Agent Loop — One Simple Entry Point

Every agent runs the same 8-step cycle (Roadmap v2.0 Phase 1, #4143). The dispatcher IS the existing `scripts/agents/continuous_agent_loop.py` — never build a new loop.

| Step | Do | Existing tool |
|---|---|---|
| 1. Understand | Read the task issue + linked context | `gh issue view <n>` |
| 2. Rules | Load governing rules + your role contract | [`AGENT_RULES.md`](./AGENT_RULES.md) §1–§3 · `scripts/agents/role_registry.py` |
| 3. Inspect state | Queue, open PRs, active claims, token freshness | `issue_queue_manager.py audit` · `agent_identity.refresh_token_if_stale()` |
| 4. Claim | Atomic claim (session marker; no claim, no work) | `scripts/ci/atomic_claim.sh` |
| 5. Work | Smallest safe change inside declared scope | role contract from `role_registry.get_role_contract()` |
| 6. Verify | 3-tier: reflection → boot smoke → tests | issue's Verification Contract |
| 7. Record | PR with full template + Test Evidence (+ meaningful decision note) | REST PR create |
| 8. Return | Report outcome, release claim, loop back | `continue_loop.py` |

Hard boundaries during the loop: gates outrank agent preference (§1.4) · scoped credentials only (`credential_manager` — master vault keys never reach children) · single-vs-multi execution follows Rule B (`role_registry.plan_task_execution()` — advisory).

## 1. First Rule: Authority

1. Admin's explicit instruction has highest authority, subject to safety: if an instruction may cause data loss, production outage or security breach, stop and request confirmation.
2. When no direct Admin decision exists, this file + [`AGENT_RULES.md`](./AGENT_RULES.md) are the agent baseline. Other documents explain context; they do not silently override the constitution.
3. Major architectural, governance, policy or planning changes require an `ADMIN_DECISION` issue and must wait for the decision before implementation.
4. System-enforced gates outrank agent preference. An agent must never bypass a safety, scope, freshness, template, permission, duplicate, evidence or merge gate.

## 2. Second Rule: Stateless Task Lifecycle

Every agent is a task execution role, not a permanent identity:

```text
READ ENTRYPOINT
  → LOAD AGENT_RULES
  → LOAD TASK/ROLE CONTRACT
  → CHECK GROUP + PRIORITY + SEQUENCE
  → PREFLIGHT MAIN + OPEN PRs + EXISTING WORK
  → CLAIM (atomic_claim.sh — BEFORE any code change or PR)
  → WORK INSIDE SCOPE
  → VERIFY (tests + gates + evidence)
  → RECORD EVIDENCE + DECISION LEDGER
  → PR / HANDOFF (only AFTER claim is posted)
  → CLEAN EXIT (release locks, stop heartbeat, trim worklog)
  → RERUN continue_loop.py (next task immediately — no sleep, per Rule 5)
```

Never invent a parallel workflow. The task contract is the common envelope for every model and role.

**Critical ordering:** `atomic_claim.sh` must run **BEFORE** `gh pr create`. A PR opened without a prior claim will be auto-closed by the Claim Gate (#2644, #2892). The claim comment on the issue is the evidence the gate checks — it must exist before CI runs.

## 3. New Agent: Required Reading Path

A newly added agent should not need tribal knowledge. Start here, then follow the links in order:

1. **This file** — authority, lifecycle and navigation.
2. **[`AGENT_RULES.md`](./AGENT_RULES.md)** — global policies + role policies + verification + tooling.
3. **Task Contract / Issue Template** — exact task type, scope, group, priority, sequence, dependencies and acceptance criteria.
4. **Relevant group/domain document** — only the context required by the assigned task.
5. **Issue + related PRs + evidence** — current state before making changes.
6. **After work:** verification + decision ledger + linked evidence.

If a referenced document is missing or contradictory, do not guess. Report the gap and follow the Admin Decision path when required.

## 4. Agent Freedom vs Boundary

### Agent may decide
- implementation details inside assigned scope;
- how to debug and test;
- which existing compatible pattern to reuse;
- the smallest safe implementation approach;
- evidence-backed local optimizations that do not alter protected architecture/policy.

### Agent may not decide alone
- major architecture/workflow topology changes;
- security/permission boundary changes;
- governance/rule changes;
- destructive or irreversible operations;
- broad scope expansion;
- replacing an established architecture with a substantially different one without evidence and required approval.

If an existing design appears unnecessarily complex, do **not** silently preserve it forever and do **not** silently rewrite it:

```text
Finding → Evidence → Simpler Alternative → Impact
       → ADMIN_DECISION (when architectural) → Wait
```

## 5. Document Circle

SupremeAI documentation is a connected ecosystem, not isolated files.

- [`AGENT_RULES.md`](./AGENT_RULES.md) — agent policy constitution.
- [`docs/INDEX.md`](./docs/INDEX.md) — broad documentation index.
- Domain/planning documents — detailed context.
- Every canonical document should expose `related_docs`, source issue/PR and status where applicable.
- Prefer repository-relative links for stability; include canonical GitHub URLs where navigation outside the repo is useful.
- Do not create orphan canonical documents.
- When a document is renamed, superseded or split, update inbound/outbound links.

The goal is a navigable circle:

```text
Entry → Rules → Task → Group → Domain Plan
  ↑                                  ↓
  └──── Evidence ← Issue ← PR ← Verify
```

## 6. Core Philosophy

- **Simple + effective > clever + complex.**
- **Incremental improvement > premature scale.**
- **Preserve working architecture by default.**
- **Complexity must earn its existence.**
- **Evidence before action.**
- **Issue validity before implementation.**
- **Existing work before new work.**
- **System guards enforce critical boundaries; agents do not police themselves.**

## 7. Machine Enforcement

The canonical validator is:

```bash
python scripts/ci/generate_agents_md.py --check
```

It should remain the enforcement entrypoint for this two-file constitution and be extended as the document-circle contract evolves.

---

**Next:** Read [`AGENT_RULES.md`](./AGENT_RULES.md) and load only the role/task policy required for the current assignment.
