# AETHEL Command Center — TODO Completion Plan

3 uncompleted feature groups remain. Plan below maps each TODO to exact files and concrete implementation.

---

## Current State Analysis

| TODO Item | Status | Gap |
|-----------|--------|-----|
| Mini Infra Topology (node graph) | ❌ Missing | No file exists — needs ReactFlow graph in `CommandDeck` |
| Code splitting (React.lazy per module) | ✅ Already done | `WorkspaceViewport.tsx` already uses `React.lazy` for all 30 modules |
| Virtualized tables (>50 rows) | ⚠️ Partial | `DataTable.tsx` uses CSS `maxHeight` scroll, NOT true windowed virtualization |
| WS payload diffing (2s delta, 30s snapshot) | ❌ Missing | `websocketManager.ts` applies all payloads blindly — no diff/delta logic |
| Bundle check (<250KB gz initial, <900KB total) | ❌ Not validated | No bundle analysis script or CI gate exists |
| axe-core scan (0 known issues) | ❌ Missing | No a11y test setup |
| Playwright smoke tests | ❌ Missing | No `e2e/` directory or playwright config |
| No hardcoded values grep check | ❌ Missing | No CI grep step to enforce |
| WS/SSE error → degraded state test | ❌ Missing | No test coverage for error fallback paths |

> [!IMPORTANT]
> **Code splitting is ALREADY implemented** via `WorkspaceViewport.tsx` — mark that TODO as ✅ before starting.

---

## Open Questions

> [!NOTE]
> **ReactFlow dependency**: `Swarm.tsx` already uses ReactFlow. The `InfraTopology` component can reuse that dep. Confirm: should topology be a separate file `modules/deck/InfraTopology.tsx` or inlined in `CommandDeck.tsx`?
>
> **Playwright target URL**: What URL does the local dev server run on? Assumed `http://localhost:5173` — correct if different.

---

## Proposed Changes

### Group 1 — Mini Infra Topology (P3 CommandDeck)

#### [NEW] [InfraTopology.tsx](file:///g:/supremeai backup/apps/studio-client/src/commandcenter/modules/deck/InfraTopology.tsx)

A ReactFlow canvas rendering the live infra node graph. Nodes sourced from `useHealthMap` data. Each node shows status color/glow matching `StatusPill` tone system. Edges represent dependency connections.

**Node types:**
- Cloud providers: GCP, Railway, Render (top tier)
- Core services: API Gateway, WS Server, Postgres, Redis, Firestore (mid tier)
- AI providers: dynamically from `useProviders()` (bottom tier)

**Features:**
- Status-colored node borders (healthy=cyan glow, degraded=amber, down=rose)
- Zoom + pan via ReactFlow controls
- Click a node → navigates to relevant module (`health`, `providers`, etc.)
- Auto-layout using dagre (already in Swarm.tsx transitive deps)

#### [MODIFY] [CommandDeck.tsx](file:///g:/supremeai backup/apps/studio-client/src/commandcenter/modules/deck/CommandDeck.tsx)

Add `InfraTopology` import and render it as the final section below the Live Event Feed.

```diff
+ import { InfraTopology } from './InfraTopology';
...
+ {/* ── Mini Infra Topology ── */}
+ <div className="rounded-xl border border-[var(--sa-line)] bg-[var(--sa-bg-1)] p-4">
+   <div className="text-[9px] font-mono uppercase tracking-widest text-[var(--sa-text-2)] mb-3">
+     INFRA TOPOLOGY
+   </div>
+   <InfraTopology health={health} providers={providers} onNavigate={setActiveModule} />
+ </div>
```

---

### Group 2 — WS Payload Diffing

#### [MODIFY] [websocketManager.ts](file:///g:/supremeai backup/apps/studio-client/src/commandcenter/realtime/websocketManager.ts)

Add a `PayloadDiffer` class with:
- **Delta mode (2s interval):** Server sends `{ type: "delta", channel: "...", patch: {...} }` — apply shallow merge onto cached snapshot
- **Snapshot mode (30s interval):** Server sends `{ type: "snapshot", channel: "...", data: {...} }` — replace full cache entry
- **Stale guard:** If >35s pass without a snapshot, force-refetch via React Query `invalidateQueries`

```ts
// বাংলা: পেলোড ডিফিং — ২s ডেল্টা, ৩০s ফুল স্ন্যাপশট
private snapshotCache = new Map<string, unknown>();
private lastSnapshotTime = new Map<string, number>();

private applyPayload(type: string, payload: unknown) {
  const p = payload as { channel?: string; patch?: Record<string,unknown>; data?: unknown; mode?: 'delta'|'snapshot' };
  if (!p?.channel) { this.options.onEvent(type, payload); return; }

  if (p.mode === 'delta' && p.patch) {
    const existing = this.snapshotCache.get(p.channel) ?? {};
    const merged = { ...(existing as object), ...p.patch };
    this.snapshotCache.set(p.channel, merged);
    this.options.onEvent(type, merged);
  } else {
    // full snapshot
    this.snapshotCache.set(p.channel, p.data ?? payload);
    this.lastSnapshotTime.set(p.channel, Date.now());
    this.options.onEvent(type, p.data ?? payload);
  }
}
```

---

### Group 3 — True Row Virtualization in DataTable

#### [MODIFY] [DataTable.tsx](file:///g:/supremeai backup/apps/studio-client/src/commandcenter/kit/DataTable.tsx)

Current implementation renders all rows in DOM. Replace `<tbody>` rendering with a windowed virtual scroller using `useVirtualizer` from `@tanstack/react-virtual` (already part of TanStack family, zero-cost addition since it's free/OSS).

**Approach:**
- If `data.length <= 50`: render normally (no overhead for small datasets)
- If `data.length > 50`: activate `useVirtualizer` with fixed `rowHeight=32`, render only visible rows

```ts
// বাংলা: ৫০+ রো হলে ভার্চুয়াল উইন্ডো অ্যাক্টিভ — DOM নোড কম
const virtualizer = useVirtualizer({
  count: sorted.length,
  getScrollElement: () => containerRef.current,
  estimateSize: () => 32,
  overscan: 5,
});
```

> [!WARNING]
> `@tanstack/react-virtual` must be added to `package.json`. Run `pnpm add @tanstack/react-virtual` in `apps/studio-client/`.

---

### Group 4 — Bundle Size Check

#### [NEW] [scripts/bundle-check.sh](file:///g:/supremeai backup/apps/studio-client/scripts/bundle-check.sh)

Post-build script that greps Vite build output, extracts gzipped sizes, and fails if:
- Initial chunk > 250KB gz
- Total bundle > 900KB gz

Integrated into the existing `monorepo_ci_cd.yml` after the `build` step.

---

### Group 5 — Quality Gates

#### [NEW] e2e/commandcenter.spec.ts (Playwright smoke test)

Tests:
1. Login → navigate to Command Center
2. OTP modal appears for gate lock/unlock
3. Deck module loads KPI tiles
4. Navigate to each of the 7 suite groups (Observe, Operate, Build, Secure, Money, System)
5. WS disconnect → `EmptyState` degraded banner appears

#### [NEW] .github/workflows/quality-gates.yml

Separate CI job running:
- `axe-core` via `@axe-core/playwright` on each module route
- Playwright smoke tests
- `grep -rn 'localhost\|hardcode\|TODO_FIXME' src/commandcenter/` hardcoded value check

---

## Execution Order

```
1. InfraTopology.tsx (NEW) + CommandDeck.tsx patch         ~2h
2. websocketManager.ts WS diffing patch                    ~1h
3. DataTable.tsx virtualization patch                      ~1h
4. Bundle check script + CI integration                    ~30m
5. Playwright e2e setup + smoke tests                      ~3h
6. axe-core + hardcoded grep CI job                        ~1h
```

## Verification Plan

### Automated
```bash
# TypeScript check
pnpm --filter studio-client tsc --noEmit

# Unit tests
pnpm --filter studio-client test

# Build + bundle size check
pnpm --filter studio-client build && bash scripts/bundle-check.sh

# Playwright smoke
pnpm --filter studio-client exec playwright test e2e/commandcenter.spec.ts
```

### Manual
- Open Command Center → Command Deck → verify InfraTopology node graph renders with live health colors
- Open Agents module with 50+ agents → scroll table → verify smooth windowed rendering
- Kill WS connection in DevTools → verify degraded state banner appears
