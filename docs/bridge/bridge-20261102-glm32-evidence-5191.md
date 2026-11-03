# Evidence Receipt — issue #5191 (vscode lockfile) — GLM Agent 32 (Job 486850), window c129

> Dispatch reading: the c129 continuous-agent-loop assigned **#5191** as the
> highest-priority unclaimed issue. The row's own fields route it to the
> **evidence lane**, not the claim lane. This receipt is filed per the
> dispatch boundary (c120 precedent, verified c121): report-only lanes never
> claim, never auto-close, and carry **NO Closes** (spec-first keep-open).

## The row

- **Title**: fix(ci): [vscode] Regenerate npm workspace lockfile for desktop release
- **State**: open, labels `P1-high`, `status:unclaimed`, `handoff:coder`, `area:ci`, **`repo:vscode`**, `status:runway`, `ci-failed`
- **Target repository (issue body)**: `Supremeai-bd/supremeai-vscode` — root `package-lock.json` and `desktop/package.json`
- **Cited evidence**: release run 41278653710 (2026-11-01) — `npm ci` fails with "package.json and package-lock.json are not in sync"; missing lock entries for `three@0.187.0`, `@types/three@0.187.0`, `@dimforge/rapier3d-compat@0.12.0`, `@tweenjs/tween.js@23.1.3`, `@types/stats.js@0.17.4`, `@types/webxr@0.5.24`, `fflate@0.8.3`, `meshoptimizer@1.1.1`.

## Triple boundary grounds (evidence lane)

1. **Satellite repository**: the remedy must be produced inside `Supremeai-bd/supremeai-vscode` (label `repo:vscode`; issue body names it the target repository). This open repo's envelope does not contain that workspace.
2. **Remedy shape**: regenerating the npm workspace lockfile requires running the package manager against the vscode repo's manifests — an action on a satellite repo, outside the anonymous open-repo surface.
3. **Loop's own ACTION text**: satellite repos are explicitly listed as outside the agent envelope — "submit evidence via the bridge and do NOT auto-close: leave the closure decision to the verdict plane/admin."

## Stale-guard (prior verification — incident still current at filing)

`github_workflow_runs` on `Supremeai-bd/supremeai-vscode` (total_count 44, newest-first):

| run | workflow | branch | conclusion | created (UTC) | head sha |
|-----|----------|--------|------------|---------------|----------|
| 32 | release | main | **failure** | 2026-11-01T05:53:41Z | 474aa77 |
| 31 | release | main | failure | 2026-11-01T05:30:45Z | 683072b |
| 30 | release | main | failure | 2026-11-01T05:14:00Z | 203f3ed |

- The **newest run of any workflow in the satellite repo is the very run the issue cites** (#32, failure). **Zero runs after it** (~32 h quiet at filing).
- Three consecutive release failures (#30 → #31 → #32) = a persistent manifest/lockfile sync gap, not a transient.
- Conclusion: **no fix has landed**; the incident is still current. Nothing in this receipt claims otherwise.

## Remedy map (for the vscode / desktop release maintainer)

1. In `Supremeai-bd/supremeai-vscode`, regenerate the **root** `package-lock.json` from the current root + workspace manifests (package-manager regeneration; no hand-edited package metadata — matches the issue's acceptance criteria).
2. The regenerated lockfile must gain entries for the eight packages npm reported missing (listed above).
3. Verify: clean-runner `npm ci` at the workspace root; desktop typecheck/build; extension and mobile workspaces remain reproducible; the `release` workflow goes green on the next push to main.
4. Issue #5191's acceptance criteria map 1:1 to steps 1-3. Parent anchor #754 is recorded in the issue (the GitHub connector cannot create the native sub-issue relationship).

## Plane discrepancy

None observed at fetch: work-order state `open`, label `status:unclaimed`, and the loop's ranking agree. Should the row move (claim/closure) after this filing, that motion belongs to the claim/verdict planes — this receipt does not arbitrate it.

**NO Closes.** Spec-first keep-open: the issue stays open until the remedy lands in its own repository; the closure decision is the verdict plane's.
