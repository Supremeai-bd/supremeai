# SupremeAI — Rules Index (Canonical Map)

> **If it is a rule and it is not indexed here, it does not exist.**
> One page. Every rule document, what it owns, and which lane may change it.
> Entry point for agents: [`AGENTS.md`](../../AGENTS.md) · Daily core: [`GOLDEN_RULES.md`](GOLDEN_RULES.md)

---

## Layer 0 — Entry (read first, every agent)

| Document | Owns | Changed by |
| :--- | :--- | :--- |
| [`AGENTS.md`](../../AGENTS.md) | Universal constitution + self-serve bootstrap + lane table + universal loop | coder lane, via founder-directed issues only |

## Layer 1 — Golden Rules (the easy-but-effective core)

| Document | Owns | Changed by |
| :--- | :--- | :--- |
| [`GOLDEN_RULES.md`](GOLDEN_RULES.md) | The 8 one-line rules that keep the ecosystem safe | coder lane, via founder-directed issues only |

## Layer 2 — Boundaries (who may do what)

| Document | Owns | Changed by |
| :--- | :--- | :--- |
| [`AGENT_WORK_BOUNDARIES_CHARTER.md`](AGENT_WORK_BOUNDARIES_CHARTER.md) | Lane pools, allowed/forbidden scopes, charter invariants | coder lane (charter handoff issues) |
| [`roles/planner.md`](roles/planner.md) | Planner card — **issue-output only, never PRs** (#1864) | coder lane |
| [`roles/coder.md`](roles/coder.md) | Coder card — implementation & tests | coder lane |
| [`roles/ci.md`](roles/ci.md) | CI card — workflows fast, green, consolidated | ci lane |
| [`roles/pr-helper.md`](roles/pr-helper.md) | PR Helper card — verification & the single merge door | ci lane (with pr-helper review) |
| [`roles/browser.md`](roles/browser.md) | Browser card — live-environment evidence | ci lane |
| [`roles/super.md`](roles/super.md) | Super agent card — omni-lane executor (#1924) | coder lane |
| [`roles/platform.md`](roles/platform.md) | Platform card — cloud health & cost | platform lane |

## Layer 3 — Mechanics (how the machine runs)

| Document | Owns | Changed by |
| :--- | :--- | :--- |
| [`../master_docs/AGENT_SLOT_REGISTRY.yaml`](../master_docs/AGENT_SLOT_REGISTRY.yaml) | Slot/pool definitions, acquisition rules (CAS, 15-min staleness) | coder lane (registry handoff) |
| [`../master_docs/OPS-05-PR-HELPER-LIFECYCLE.md`](../master_docs/OPS-05-PR-HELPER-LIFECYCLE.md) | PR lifecycle, merge train, hold semantics | ci lane |
| [`../master_docs/OPS-06-MULTI-AGENT-BRANCHING-LIFECYCLE.md`](../master_docs/OPS-06-MULTI-AGENT-BRANCHING-LIFECYCLE.md) | Branching lifecycle, naming patterns, mutex claiming | ci lane |
| [`../master_docs/OPS-07-DEVELOPER-AGENT-LIFECYCLE.md`](../master_docs/OPS-07-DEVELOPER-AGENT-LIFECYCLE.md) | Developer-agent end-to-end workflow | coder lane |
| [`../master_docs/OPS-08-SUPREMEAI-RUNTIME-WORK-PROCESS.md`](../master_docs/OPS-08-SUPREMEAI-RUNTIME-WORK-PROCESS.md) | Runtime work process | coder lane |
| [`handoff-orchestration.md`](handoff-orchestration.md) | Agent-to-agent handoff schema (issue comments + labels) | coder lane |
| [`ISSUE_PRIORITY_POLICY.md`](ISSUE_PRIORITY_POLICY.md) | Priority ladder, claim order (P0→P3, FIFO within level), auditor priority stewardship, age policy | coder lane (policy handoff); priority labels on issues = auditor |
| [`heartbeat-integration.md`](heartbeat-integration.md) | Agent heartbeat protocol | ci lane |
| [`platform-agent-charter.md`](platform-agent-charter.md) | Platform agent operating charter | platform lane |

## Layer 4 — Memory (learning, one-way door)

| Document | Owns | Changed by |
| :--- | :--- | :--- |
| [`../../LESSONS_LEARNED.md`](../../LESSONS_LEARNED.md) | Mistake ledger — reverse-chronological, never delete entries | **any lane** (a mistake + its prevention may be logged by the agent who made/found it) |
| [`../plans/`](../plans/) | Approved plans (role-pool model, CI consolidation, ...) | planner-authored specs, landed via coder issues |

---

## Change control (how rules change)

1. Rules change the same way code changes: **1 issue = 1 branch = 1 PR** through the single merge door.
2. Layer 0/1 (constitution, golden rules): founder-directed issues only — an agent may propose, the founder decides.
3. Layer 2 cards: charter handoff issues (`handoff:coder` / `handoff:ci`).
4. Layer 3 mechanics: owning lane, with the OPS doc updated in the same PR as the mechanism it describes.
5. Layer 4 memory: append-only; entries require Date / Issue / Fix / Lesson.

## The bootstrap test (maintained invariant)

A brand-new agent told only **"You are `<lane>`. Start working."** must reach, from
[`AGENTS.md`](../../AGENTS.md) alone: the golden rules, its role card, the claim command,
its slot pattern, the PR format, the gates, its blocked-behavior, and every deep doc above.
**Dead link or missing step = P1 bug — file a discovery issue.**
