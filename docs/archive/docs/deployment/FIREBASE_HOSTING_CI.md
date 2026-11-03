# Firebase Hosting CI deploy runbook (FB-09, issue #590)

> **Status — historical (issue #1261):** the `.github/workflows/deploy-firebase-hosting.yml`
> workflow described below was **removed** in the Wave 3.5 workflows consolidation:
> it was `workflow_dispatch`-only and had zero callers (no `uses:` references from
> any workflow, no `gh workflow run` invocations in any script), so it never ran on
> its own. Everything below documents how that workflow worked and is kept for
> reference; `scripts/deploy/generate_firebase_config.py` remains in use by other
> build scripts. If CI-driven Firebase deploys are ever re-introduced, this runbook
> and its `FIREBASE_TOKEN` provisioning steps still apply.

## What changed

Firebase Hosting deploys used to be **manual-only**: a developer ran
`pnpm deploy:frontend` locally with a personal `firebase login` session.
That meant no deploy gate, no audit trail of who deployed what when, no
deterministic rollback, and a personal project-owner account used for prod
deploys.

`.github/workflows/deploy-firebase-hosting.yml` adds a manual
(`workflow_dispatch`-only) pipeline that:

1. fails closed if the `FIREBASE_TOKEN` secret is absent (before building),
2. builds the single shared SPA artifact (`pnpm --filter
   supremeai-studio-client build`),
3. runs the deterministic config generator
   (`scripts/deploy/generate_firebase_config.py --require-build`),
4. deploys with `firebase deploy --only hosting` + the CI token (both hosting
   targets `user` + `admin` — one shared artifact, see FB-06/issue #587),
   or, when a `preview_channel` input is provided, deploys both targets to a
   Firebase Hosting preview channel
   (`firebase hosting:channel:deploy <channel> --only <target> --expires`).

## One-time secret provisioning (repository owners)

The `FIREBASE_TOKEN` secret **does not exist yet**; every workflow run stops
at the fail-closed guard until it is added.

1. From an account whose Firebase role is scoped to Hosting on project
   `supremeai-a` (least privilege — **not** a personal project-owner account),
   mint a CI token:
   ```bash
   firebase login:ci
   ```
   Prefer a dedicated service/deploy account over any personal login.
2. GitHub repo → **Settings → Secrets and variables → Actions → New
   repository secret**
   - Name: `FIREBASE_TOKEN`
   - Value: the token from step 1
3. (Optional but recommended) add repository **Variables** so the CI build
   bakes real backend origins into the bundle instead of degraded-viewer
   mode:
   - `VITE_USER_BACKEND`, `VITE_ADMIN_BACKEND`, `VITE_API_BASE`,
     `VITE_API_URL`, `BACKEND_URL`
4. Rotate the token on the same schedule as other CI credentials
   (`scripts/security/secrets_rotation_manager.py` already tracks a
   `firebase-service-account` rotation target).

## Running a deploy

- **Production:** Actions → *Firebase Hosting Deploy* → *Run workflow* →
  leave `preview_channel` empty. Deploys the built bundle to both
  `user` (`supremeai-a.web.app`) and `admin` (`supremeai-admin.web.app`).
- **Preview:** set `preview_channel` to e.g. `pr-1234` (and optionally
  `channel_expires`, default `7d`). The channel URL can be shared for review
  without touching production. Channels expire automatically.

## Notes & limits

- The workflow is intentionally **dispatch-only**: it does not fire on push
  or PRs. Wiring it into the CI graph (auto-deploy on main after the
  production preflight) is an owner decision, not part of issue #590.
- The token is passed to the CLI via the `FIREBASE_TOKEN` **environment
  variable** (the CLI consumes it natively) rather than string-interpolating
  `${{ secrets.FIREBASE_TOKEN }}` into a command line — same deploy command
  as suggested in the issue, without risking the token leaking through shell
  tracing or logs.
- Rollback: redeploy a known-good commit by running the workflow from that
  ref (Actions → Run workflow → use branch/tag selector), or use the Hosting
  console release history to restore a previous release.
