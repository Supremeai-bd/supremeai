# Handoff Orchestration — Agent-to-Agent Task Routing

> **Issue:** [#1439](https://github.com/SaifulHaqueNiloy/supremeai/issues/1439)  
> **Status:** Active  
> **Rule:** Role owns responsibility, orchestrator owns routing, GitHub owns events, Merge Guardian owns merge.

---

## 1. Unified Handoff Schema

Every handoff is recorded via an issue comment and an explicit GitHub label for routing.

### Comment Format (YAML frontmatter)

```yaml
---
task:
  issue: "#123"
  status: completed         # created | in_progress | completed | blocked | failed
  branch: "coder-1"
handoff:
  next_role: coder          # planner | coder | pr-helper | ci | platform
  trigger: issue_created    # issue_created | pr_opened | ci_failed | merged | manual
  reason: "planner finished, coder needs to implement"
constraints:
  scope: implementation-only
  max_retries: 3
  assigned_to: ""           # empty = orchestrator picks
---
```

---

## 2. Canonical Routing Labels

| Label | Meaning | Routes to |
|---|---|---|
| `handoff:planner` | Planning / architectural audit needed | `planner` pool (`planner-{N}`) |
| `handoff:coder` | Implementation / bug fix / unit tests needed | `coder` pool (`coder-{N}`) |
| `handoff:pr-helper` | PR gate verification & rollup merge train | `pr-helper` pool (`pr-helper-{N}`) |
| `handoff:ci` | CI workflow failure or pipeline triage | `ci` pool (`ci-{N}`) |
| `handoff:platform` | 3rd-party platform connectivity/health | `platform` pool (`platform-{N}`) |
| `handoff:done` | Task completed, no further routing | Closed / Merged |

---

## 3. Role Pool Responsibilities & Boundaries

- **`planner` (`planner-{N}`)**: Owns issue breakdown, architecture review, and backlog creation. FORBIDDEN from modifying business code or CI workflows.
- **`coder` (`coder-{N}`)**: Owns implementation, bug fixes, unit tests, and browser tests. FORBIDDEN from modifying CI workflows or touching files without an assigned issue.
- **`ci` (`ci-{N}`)**: Owns `.github/workflows/*`, git hooks, and pipeline automation. FORBIDDEN from writing feature business logic.
- **`pr-helper` (`pr-helper-{N}`)**: Owns PR gate evaluation, regression sweeps, and the canonical rollup merge train (`pr-helper-1`). Focuses on preserving beneficial changes and eliminating regressions.
- **`platform` (`platform-{N}`)**: Owns 3rd-party platform health sweeps (Render, Upstash, Supabase, Cloudflare, Infisical).

---

## 4. Lifecycle Workflow

```
1. planner (planner-{N})
   └── Audits issue & specs -> adds label handoff:coder

2. coder (coder-{N})
   └── Claims issue (status:in-progress) -> implements fix & tests -> opens PR -> adds handoff:pr-helper

3. pr-helper (pr-helper-{N})
   ├── Validates gates & runs regression scan
   ├── If green -> merges PR via merge train (pr-helper-1) -> adds handoff:done
   └── If regression / conflict -> creates blocker issue (scripts/agents/create_blocker_issue.py) -> routes to handoff:coder

4. ci (ci-{N})
   └── On workflow/pipeline failure -> diagnoses logs -> fixes CI definitions -> re-triggers verification
```

---

## 5. Invariant Safety Rules

1. **No Claim, No Code**: An agent MUST claim an issue (`status:in-progress`) before editing ANY file.
2. **Never Touch Main**: All code enters `main` via PRs only.
3. **Max Retries**: A task may fail a gate at most 3 times before escalating to `handoff:human`.
4. **Autonomous Blocker Escalation**: When encountering an unrecorded dependency, syntax drift, or merge conflict, run `scripts/agents/create_blocker_issue.py` immediately.
