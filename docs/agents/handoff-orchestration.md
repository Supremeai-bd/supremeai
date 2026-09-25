# Handoff Orchestration — Agent-to-Agent Task Routing

> **Issue:** [#1439](https://github.com/SaifulHaqueNiloy/supremeai/issues/1439)
> **Status:** Pilot (agent-12 chain)
> **Rule:** Role owns responsibility, orchestrator owns routing, GitHub owns events, Merge Guardian owns merge.

---

## Problem (ground experience)

যখন এক agent থামে, পরের agent-কে শুরু করতে হয় — এই handoff-এ সমস্যা হয়:

1. **Signal হারায়** — agent-A থামল, agent-B জানল না
2. **Duplicate কাজ** — দুজন একই কাজ ধরল
3. **কাজ অর্ধেক রইল** — agent-A file পরিবর্তন করল, থামল, agent-B জানে না
4. **Deadlock** — সবাই অপেক্ষা করছে
5. **Token শেষ** — chain-এ সবাই শেষ হয়ে গেল
6. **State inconsistency** — conflict, overwrite
7. **Heartbeat gap** — ৫ মিনিট system-এ কে কাজ করছে?
8. **Branch অসম্পূর্ণ** — agent-A এর branch-এ অর্ধেক কাজ

---

## Solution — Handoff Schema

প্রতিটি task handoff একটা **issue comment** হিসেবে লেখা হয়, সাথে একটা **label** routing signal-এর জন্য।

### Format

```yaml
# Handoff comment (YAML in issue body)
---
task:
  issue: "#123"
  status: completed         # created | in_progress | completed | blocked | failed
  branch: "agent-6/123-fix-lint"
handoff:
  next_role: solver-a       # planner | solver-a | solver-b | pr-verifier | log-fixer | platform-agent | browser-tester
  trigger: issue_created    # issue_created | pr_opened | ci_failed | merged | manual
  reason: "planner finished, solver needs to implement"
constraints:
  scope: implementation-only
  max_retries: 3
  assigned_to: ""           # empty = orchestrator picks
---
```

### Routing Labels

| Label | Meaning | Routes to |
|---|---|---|
| `handoff:planner` | Planning needed | planner-and-issues |
| `handoff:solver` | Implementation needed | solver-a or solver-b (free one) |
| `handoff:verify` | PR needs verification | pr-verifier |
| `handoff:log-fix` | CI/log failure | log-fixer |
| `handoff:platform` | External platform issue | platform-agent |
| `handoff:browser-test` | Browser test needed | browser-tester |
| `handoff:done` | Task complete, no handoff | — |

### Lifecycle

```
1. planner-and-issues
   ↓ creates issue + handoff:solver label
   
2. solver-a (or solver-b, whoever free)
   ↓ claims issue, works, opens PR + handoff:verify
   
3. pr-verifier
   ↓ checks PR, if ok → handoff:browser-test
   ↓ if wrong → handoff:solver (back to solver)
   
4. browser-tester
   ↓ tests in browser, if ok → handoff:done
   ↓ if fail → handoff:solver (back to fix)
   
5. log-fixer (triggered by CI fail event)
   ↓ analyzes log, fixes, handoff:verify
   
6. SupremeAI (orchestrator)
   ↓ watches all handoffs, reassigns if agent inactive
```

---

## Ground Experience — Problems + Solutions

### Problem 1: Signal হারায়
**Solve:** GitHub issue label = permanent signal। কেউ label দিলে webhook fire করবে, orchestrator দেখবে।

### Problem 2: Duplicate কাজ
**Solve:** `assigned_to` field। যখন solver claim করে, সে নিজের নাম লেখে। অন্য solver দেখবে assigned, ছাড়বে।

### Problem 3: কাজ অর্ধেক রইল
**Solve:** `status: in_progress` + branch name। নতুন solver branch দেখবে, commit history দেখবে, সেখান থেকে শুরু করবে।

### Problem 4: Deadlock
**Solve:** SupremeAI (orchestrator) heartbeat watch করে। কেউ ৯০ সেকেন্ড heartbeat না দিলে orchestrator সেই task reassign করে।

### Problem 5: Token শেষ
**Solve:** Orchestrator heartbeat দেখে agent inactive detect করে, active list থেকে অন্য agent-কে assign করে।

### Problem 6: State inconsistency
**Solve:** প্রতিটা agent main থেকে branch করে। Conflict হলে PR verifier ধরবে।

### Problem 7: Heartbeat gap
**Solve:** Heartbeat TTL ৩০০s। কিন্তু orchestrator প্রতি ৩০s check করে। ৯০s ছাড়াই stale → reassign।

### Problem 8: Branch অসম্পূর্ণ
**Solve:** `status: in_progress` + branch name comment-এ। নতুন agent branch reset করে main থেকে শুরু করে (পুরোনো কাজ হারায়, কিন্তু clean state)। অথবা commit history দেখে continue করে।

---

## Safety Rules

1. **Max retries:** প্রতি task-এ ৩ বার। বেশি হলে human escalate।
2. **Loop breaker:** একই issue-তে ৩ বার handoff:solver হলে → `handoff:human` label।
3. **Double verify:** solver + pr-verifier দুজন check = double safety।
4. **Orchestrator override:** SupremeAI যেকোনো সময় reassign করতে পারবে।

---

## Implementation Phases

### Phase 1: Schema + Labels (এখন)
- এই document
- Label definitions
- Handoff comment format

### Phase 2: Webhook (পরে)
- `/api/webhooks/github` route
- Event capture: issue labeled, PR opened, CI fail

### Phase 3: Orchestrator Tool (পরে)
- MCP tower tool `orchestrator_dispatch`
- Heartbeat watch + reassign logic

### Phase 4: Wake-on-Event (পরে)
- `workflow_dispatch` templates per role
- Zero idle cost

### Phase 5: Pilot (পরে)
- agent-12 (log watcher) chain test
- CI fail → orchestrator → agent-12 → fix → handoff to planner

---

## Reference

- **Issue:** #1439 (ecosystem plan)
- **Issue:** #1402 (heartbeat)
- **AGENTS.md:** §4 (persistent agent branches)
- **OPS-06:** multi-agent branching lifecycle
