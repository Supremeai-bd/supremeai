# SupremeAI — AGENTS.md

> **Agent Entry Point / Universal Constitution**
>
> **Freedom:** Agent controls **HOW** to solve an assigned task inside its contract.
> **Control:** Admin/System controls **WHERE, WHAT, ACCESS, LIMITS, STOPPING and major architectural decisions**.
>
> **Canonical rule source:** [`AGENT_RULES.md`](./AGENT_RULES.md)
> **Governance issue:** [#3095](https://github.com/SaifulHaqueNiloy/supremeai/issues/3095)

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
  → CLAIM
  → WORK INSIDE SCOPE
  → VERIFY
  → RECORD EVIDENCE + DECISION LEDGER
  → PR / HANDOFF
  → CLEAN EXIT
```

Never invent a parallel workflow. The task contract is the common envelope for every model and role.

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
