/**
 * Cross-tab journal filter intent — lets the dashboard (uptime strip buckets,
 * KPI cards) deep-link into the Journal tab with a pre-applied time window.
 * Module-level singleton: dashboard sets it right before navigating, JournalTab
 * consumes it on mount. No persistence, no store dependency — zero cost.
 */

export interface JournalIntent {
  /** Minutes back from now (window start). */
  sinceMin: number;
  /** Optional minutes back from now (window end, for single-bucket picks). */
  untilMin?: number;
  /** Human label for the active chip, e.g. "14:20–14:40 UTC". */
  label?: string;
  ts: number;
}

let pending: JournalIntent | null = null;

export function setJournalIntent(intent: Omit<JournalIntent, "ts">): void {
  pending = { ...intent, ts: Date.now() };
}

export function consumeJournalIntent(): JournalIntent | null {
  const p = pending;
  pending = null;
  // Intent older than 30s is stale (e.g. user navigated elsewhere first).
  if (p && Date.now() - p.ts > 30_000) return null;
  return p;
}
