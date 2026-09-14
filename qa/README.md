# SupremeAI QA Engine — scaffold (Task 7-e)

Machine-readable QA contract for the frontend, built from
`docs/plans/features/qa_engine_auto_checking_implementation_plan.md`
(1018 lines). This pass delivers the **starter scope: 40 items**
(10 guest + 10 customer + 10 admin + 10 security) plus the validator,
audit and report tooling, Playwright projects, and CI workflows.

```
qa/
├── checklist/                  # Single source of truth (Part-1 YAML schema)
│   ├── guest.yaml              # G-01..G-10   10 items
│   ├── customer.yaml           # C-01..C-10   10 items
│   ├── admin.yaml              # A-01..A-10   10 items
│   ├── security.yaml           # S-01..S-10   10 items
│   └── core.yaml               # pre-existing contract inventory (QA-xxx, untouched)
├── scripts/
│   ├── validate-checklist.ts   # Part-1 schema gate (exit 1 on violation)
│   ├── route-audit.ts          # checklist routes must exist in the frontend router
│   ├── coverage-matrix.ts      # checklist <-> spec coverage (advisory, exit 0)
│   └── generate-report.ts      # report aggregator + RELEASE GATE (--self-test)
├── playwright/
│   ├── guest/guest.spec.ts     # 10 tests (10 real)
│   ├── customer/customer.spec.ts # 10 tests (6 real, 4 fixme)
│   ├── admin/admin.spec.ts     # 7 tests (3 real, 4 fixme)
│   ├── security/isolation.spec.ts # 9 tests (4 real, 5 fixme)
│   ├── customer/.auth/setup.ts # auth setup SKELETON (TODO — see below)
│   └── admin/.auth/setup.ts    # auth setup SKELETON (TODO — see below)
└── results/                    # runtime artifacts (gitignored)
```

## Running locally

The scripts run under **bun** (TS executed natively; `yaml` comes from the root
devDependencies):

```bash
bun qa/scripts/validate-checklist.ts        # schema gate
bun qa/scripts/route-audit.ts               # route existence gate (exit 1 on unknown route)
bun qa/scripts/coverage-matrix.ts           # advisory coverage table
bun qa/scripts/generate-report.ts --self-test
bun qa/scripts/generate-report.ts --results qa/results/results.json --out qa/results/report.md
```

Playwright suites (config: `qa/playwright.config.qa.ts`):

```bash
# start the app first, e.g.:
pnpm --filter supremeai-studio-client build
pnpm --filter supremeai-studio-client exec vite preview --host 127.0.0.1 --port 3000

# then run projects:
npx playwright test -c qa/playwright.config.qa.ts --project=guest
npx playwright test -c qa/playwright.config.qa.ts --project=security
# customer/admin need auth setup completed (see below):
npx playwright test -c qa/playwright.config.qa.ts --project=setup-customer --project=customer
```

`QA_BASE_URL` (default `http://127.0.0.1:3000`) points the suites at any app
instance; same-origin `/api/**` works through the vite preview proxy or the
Firebase Hosting rewrite.

## Release gate rules

| Failed severity | Verdict                    | Exit code | Release impact          |
|-----------------|----------------------------|-----------|-------------------------|
| P0              | `STOP RELEASE`             | 1         | Production blocker      |
| P1              | `STOP RELEASE`             | 1         | Critical flow broken    |
| P2              | `WARNING — human decides`  | 0         | Human signs off/defers  |
| P3              | `LOG ONLY`                 | 0         | Cosmetic, log and move  |
| none            | `PASS`                     | 0         | GO                      |

Severity meanings per plan Part 1: P0 = auth failure/data loss/security breach,
P1 = critical user flow (login/chat/upload), P2 = important feature degraded,
P3 = cosmetic.

## Auth setup skeletons (next pass prerequisite)

`qa/playwright/customer/.auth/setup.ts` and `qa/playwright/admin/.auth/setup.ts`
currently fail with explicit `TODO(auth)` messages. They need:

1. Dedicated QA accounts exposed as secrets
   (`QA_CUSTOMER_EMAIL/PASSWORD`, `QA_ADMIN_EMAIL/PASSWORD`, `QA_ADMIN_TOTP_SECRET`
   or a static `QA_ADMIN_OTP`). **Never production credentials** (plan caution).
2. The Part-9 `data-testid` instrumentation on the login/OTP forms
   (`email-input`, `password-input`, `login-submit`, `otp-input`, `otp-submit`).

Until then the `customer`/`admin` projects cannot authenticate; their
credential-free tests (URL guards, API 401/403, CORS, headers) still run.

## Next pass TODOs (in priority order)

1. **Part 9 `data-testid` instrumentation** in the frontend (separate pass, do
   NOT bundle with QA changes): chat composer, auth forms, admin shell/sub-tabs,
   projects/files controls, logout. Every `test.fixme` in `qa/playwright/**`
   lists the selectors it is waiting for — grep `test.fixme` and convert to
   `test` one by one (coverage matrix flips Fixme → Real automatically).
2. User A/B isolation fixtures for S-02 (`QA_USER_A_*`, `QA_USER_B_*`
   secrets + project-id URL scheme) and share-link fixtures for S-06.
3. Admin step-up automation using `QA_ADMIN_TOTP_SECRET` (TOTP generation in
   setup) — unblocks A-02/A-03/A-06/A-07 in CI.
4. Capture the staging security-header baseline, then flip S-09 from fixme to
   a hard assert (see checklist manual_note).
5. Extend the checklists toward the full 300+ item inventory (route-audit
   already prints the uncovered-route radar), then wire
   `08-production-preflight.yml` into the real deploy pipeline as a
   `workflow_call` dependency.

## CI workflows (Part 7, adapted to repo conventions)

| Workflow | Trigger | Notes |
|----------|---------|-------|
| `05-e2e-guest.yml` | PR touching `frontend/**` or `qa/**` | fast gate → build → vite preview → guest project |
| `06-e2e-customer.yml` | manual + nightly schedule | requires customer secrets; report + release gate |
| `07-e2e-admin.yml` | manual | A-04 runs credential-free; rest need secrets + Part 9 |
| `08-production-preflight.yml` | `workflow_call` / manual | @smoke suites + health contract + release gate (exit 1 blocks deploy) |
| `09-post-deploy-smoke.yml` | after "Production Deploy" | guest canary against `PRODUCTION_URL` |

`@smoke`-tagged tests today: G-01, C-04, A-01, S-01 (grow this set to the plan's
20 most-critical tests as specs graduate from fixme).

## Honesty notes

- 23 of 36 automated items are real, runnable tests; 13 are `test.fixme` with
  the blocker recorded in both the test title and the checklist `manual_note`.
- 4 items are `automated: false` **by design** (RBAC drill, TOTP recovery drill,
  copy/visual review, rollback drill) — see plan Part 10.
- The guest chat specs rely only on stable ARIA/attribute selectors and the
  local chat state machine (no backend), so they pass against a bare preview
  build; customer/admin/security API checks assume the origin proxies `/api/**`.
