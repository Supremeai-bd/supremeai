# Frontend Maintenance Debt Register

**Reviewed:** 2026-09-11
**Command:** `pnpm --dir frontend lint`
**Result:** 0 errors, 123 warnings

## Completed in this pass

- Removed the unused `LandingRedirect` path from `frontend/src/App.tsx`.
- Removed unused flow, icon, dashboard, and health-state variables.
- Removed dead chat panel/audio queue state from `ChatInterface.tsx`.
- Removed unused imports from command, test, customer, theme, and prompt-template modules.
- Re-ran ESLint after each cleanup batch and kept the command passing.

## Remaining warning categories

| Category | Policy |
|---|---|
| Unused imports and variables | Fix in small behavior-preserving batches; do not delete code without checking callers. |
| Explicit `any` | Replace at API and event boundaries with shared unknown-based or domain types. Test doubles may use narrow local casts when necessary. |
| Console statements | Keep `warn`/`error` for user-visible failures; migrate operational diagnostics to the frontend logging service. |
| Hook dependency warnings | Stabilize callbacks or move handlers into effects; avoid suppressions unless the dependency is intentionally non-reactive. |
| Fast-refresh export warnings | Split non-component exports from component modules where practical. |

## Exit criteria

The maintenance task is considered triaged, not debt-free, when:

1. ESLint exits successfully with zero errors.
2. The current warning count is recorded here and in the CI baseline.
3. Each remaining category has an owner strategy and no warning is silently ignored.
4. New changes do not increase the warning budget above the current CI threshold.

The remaining 123 warnings are therefore an explicit follow-up queue, not evidence of a failed lint command. Further cleanup should proceed in focused batches, beginning with unused symbols and hook dependency correctness before broad `any` replacement.
