# SupremeAI Frontend Simplification & Consolidation Plan

> Purpose: reduce frontend complexity and file/component sprawl **without reducing any real SupremeAI capability**.

## 1. Non-negotiable rules

1. Do NOT remove functionality just to reduce file count.
2. Do NOT classify code as dead code and delete it. Dead/unused-looking assets require explicit owner approval and a separate intervention.
3. Prefer **merge, reuse, move, and simplify** over delete.
4. Preserve public routes, API contracts, permissions, realtime behavior, i18n, accessibility, and existing capabilities.
5. Before changing a component, search for direct imports, dynamic imports, route registration, lazy loading, feature flags, string-based references, tests, and documentation references.
6. Keep a capability ledger during refactoring: every existing capability must have a known new location.
7. Make small, reversible commits.

## 2. Target frontend shape

Use a feature-oriented structure instead of a large flat component/page/service collection:

```text
frontend/src/
├── app/                    # bootstrap, router, providers, global error handling
├── features/
│   ├── auth/
│   ├── chat/
│   ├── research/
│   ├── browser/
│   ├── agents/
│   ├── memory/
│   ├── automation/
│   ├── artifacts/
│   ├── admin/
│   └── settings/
├── shared/
│   ├── ui/                 # reusable visual primitives
│   ├── forms/
│   ├── tables/
│   ├── modals/
│   ├── layout/
│   └── hooks/
├── core/
│   ├── api/
│   ├── auth/
│   ├── realtime/
│   ├── state/
│   ├── i18n/
│   └── config/
├── pages/                  # only route-level composition shells
└── types/
```

The existing project documentation already describes `main.tsx`, `components/`, `pages/`, services and state; this plan is a consolidation target, not permission to blindly rewrite those areas.

## 3. Component consolidation

### Merge candidates

- Similar dashboard cards → common dashboard primitives.
- Repeated modal implementations → one modal framework + feature-specific content.
- Repeated forms → shared form primitives + schemas.
- Repeated table/list patterns → shared DataTable/List components.
- Repeated loading/error/empty states → common state components.
- Feature-specific components that only belong to one capability → move under that feature instead of keeping them in a global `components/` directory.

### Do not merge when

- Two components have materially different domain responsibilities.
- Different permission/security boundaries exist.
- Different realtime lifecycle or performance characteristics exist.
- Merging would create a giant component with many unrelated props.

## 4. Services and state

Consolidate duplicate API/service logic around the existing canonical API client. Do not create another fetch wrapper for a feature unless there is a documented architectural reason.

Use this separation:

```text
core/api        → transport/auth/retry/error handling
features/*/api  → feature endpoints and schemas
features/*/state → feature state
shared/         → reusable UI and utilities
```

Keep domain state separate from purely visual/transient state.

## 5. Pages and routing

Pages should become thin composition layers:

```text
Route → Page shell → Feature components → Feature API/state
```

Do not put large business logic inside route/page files.

Keep the existing Admin/User boundary clear. Avoid creating a separate page for every tiny operation if an existing workspace can host the capability.

## 6. Refactoring workflow for an AI agent

For every frontend area:

1. Inventory files.
2. Build import/usage map.
3. Identify duplicate patterns.
4. Map every capability to a destination.
5. Propose merges before editing.
6. Move/merge in small batches.
7. Update imports and route references.
8. Run typecheck/lint/tests.
9. Run the real frontend flow for affected features.
10. Compare capability inventory before vs after.

## 7. Success criteria

- Fewer duplicated components and services.
- Fewer giant or unrelated global folders.
- Pages become thin.
- One canonical API/realtime/auth path.
- Existing capabilities remain discoverable.
- No route silently disappears.
- No feature is removed merely because it appears unused.
- Build, lint, typecheck and tests remain green.

## 8. Explicit stop condition

If an AI agent cannot prove what a component/service does, **do not delete it**. Mark it `NEEDS HUMAN REVIEW` and continue with safe consolidation elsewhere.
