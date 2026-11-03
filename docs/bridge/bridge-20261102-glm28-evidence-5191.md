# CI Evidence — #5191 vscode satellite lockfile desync blocks desktop release (2026-11-02, GLM Agent 28 / Job ID 486832)

- Bridge taskId: `bridge-20261102-ci-vscode-lockfile-glm28`
- Row: #5191 `fix(ci): [vscode] Regenerate npm workspace lockfile for desktop release`
  (P1-high, area:ci, repo:vscode, handoff:coder, ci-failed, status:runway)
- Dispatch: continuous_agent_loop assigned this lane the solver (ci-fixer) role
  for #5191 at ~21:28+08, cycle 64.

## Envelope classification (why this is evidence-only)

The remedy lives in `Supremeai-bd/supremeai-vscode` — a **satellite repository**
outside this board repo, on three independent grounds:

1. **Satellite repo** — the row itself carries `repo:vscode`; satellite code and
   its CI live strictly in the domain mirror, never here (the same ground on
   which #5192 was discharged evidence-only, twice over).
2. **No write channel** — the bridge submit pipeline runs `targetMode: monorepo`
   against `Supremeai-bd/supremeai(-open)`; it cannot open PRs into a satellite.
   This sandbox has no `gh` CLI and no direct push credentials (credential
   zero-leak rule), so there is no legitimate path to commit the lockfile.
3. **Loop's own mandate** — "If the remedy lives outside the agent envelope …
   submit evidence via the bridge and do NOT auto-close: leave the closure
   decision to the verdict plane/admin — a Closes line on an un-remedied issue
   is a false closure (#2211/#2225 family)." **No `Closes` line is emitted and
   `closesOriginalIssue` is false.**

## Incident restatement (from the row's own evidence)

- Satellite repo `Supremeai-bd/supremeai-vscode`, main-branch release workflow,
  job "Build & Release Desktop Client" fails at `npm ci` with
  "package.json and package-lock.json are not in sync".
- Claimed cause: the root lockfile lacks entries for packages declared by the
  desktop workspace; no desktop/package-lock.json exists.

## Premise verification — CONFIRMED on live main (anonymous read)

Unlike #5192 (transports dark, premise taken from row evidence), this cycle the
premise was **independently verified** by anonymous raw.githubusercontent reads
of the satellite at `main`:

- `package.json` (685 B): `workspaces: ["extension", "desktop", "mobile"]` —
  npm workspace layout confirmed.
- `package-lock.json` (184,089 B, `lockfileVersion: 3`, **358 package entries**).
- `desktop/package.json` (893 B) declares dependencies:
  `@tauri-apps/api, @types/three, react, react-dom, react-markdown, remark-gfm, three`.
- **Missing from the root lock: `three` and `@types/three`** — neither
  `node_modules/three` nor `node_modules/@types/three` exists in
  `lock.packages`, while the desktop workspace declares both. `npm ci` treats
  manifest/lock divergence as fatal → the release job fails exactly as
  reported. (Note: `@dimforge/rapier3d-compat`, named in the issue text, is no
  longer in the current desktop manifest — the desync surface has evolved
  slightly since the row was filed; the two entries above are the live gap.)
- Cross-scan backstop: the issue page shows **no open PRs and no claim
  branches** for this row, which closes the gap the loop flagged this run
  ("landing cross-scan DARK — both transports failed"); the bridge feedback
  plane (recovered after the pick-time 503) shows `latestClaim: null`.

## Remediation (one-for-one with the acceptance criteria)

1. In the satellite repo root (workspace-aware): regenerate the lockfile with
   `npm install --package-lock-only` — this adds `three`, `@types/three` and
   their transitive deps to `lock.packages` from the manifests, with **no
   hand-edited package metadata** (the row's own acceptance constraint).
   Commit the regenerated `package-lock.json`.
2. Acceptance check: `npm ci` succeeds at the root; the "Build & Release
   Desktop Client" job goes green on main.
3. **Class fix (root cause, prevents recurrence):** add a lockfile-sync gate to
   the satellite CI — `npm install --package-lock-only && git diff --exit-code
   package-lock.json` as a fast PR check, so manifest/lock divergence fails at
   PR time instead of at release time. This converts the failure mode from
   "release-day breakage" to "PR-time red", the same early-gate philosophy the
   board applies to its committed-blob freshness gate (#4612).

## Stale-incident / U3 note

The Actions-run-level re-check ("does the referenced run still fail?") is not
possible anonymously (Actions API requires credentials for run logs). However,
unlike a flaky-infra incident, this premise is **manifest-verifiable**: the
desync is a static fact of the two files, confirmed above on live `main` today.
The stale-claim guard is therefore satisfied by direct evidence rather than run
status.

## Admin checklist

- [ ] Regenerate root lockfile in supremeai-vscode via npm (no hand edits).
- [ ] Verify `npm ci` and the desktop release job on main.
- [ ] Consider the PR-time lockfile-sync gate (class fix).
- [ ] Closure decision stays with the verdict plane/admin.
