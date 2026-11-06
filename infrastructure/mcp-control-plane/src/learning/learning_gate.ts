import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STORE_PATH = path.resolve(__dirname, "../../data/learning_store.json");

export type MemoryTier = "episodic" | "semantic" | "procedural";
export type MemoryStatus = "candidate" | "trusted" | "quarantined";

export interface LearningRecord {
  id: string;
  tier: MemoryTier;
  fact: string;
  evidence: Record<string, unknown>;
  status: MemoryStatus;
  verifiedBy: string | null;
  contradictionWith: string | null;
  createdAt: string;
  promotedAt: string | null;
}

interface StoreShape {
  records: LearningRecord[];
}

function loadStore(): StoreShape {
  try {
    if (fs.existsSync(STORE_PATH)) {
      const raw = fs.readFileSync(STORE_PATH, "utf-8");
      const parsed = JSON.parse(raw) as StoreShape;
      if (parsed && Array.isArray(parsed.records)) return parsed;
    }
  } catch {
    // Corrupt store → start empty; never crash the tool.
  }
  return { records: [] };
}

function saveStore(store: StoreShape): void {
  try {
    fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
    fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2), "utf-8");
  } catch {
    // Best-effort persistence; in-memory still works for the session.
  }
}

const NEGATION_TOKENS = new Set(["not", "never", "no", "avoid", "block", "don't", "dont", "without", "disable", "reject"]);

function tokenize(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((t) => t.length >= 3),
  );
}

function hasNegation(text: string): boolean {
  const tokens = tokenize(text);
  for (const t of tokens) if (NEGATION_TOKENS.has(t)) return true;
  return false;
}

function overlap(a: Set<string>, b: Set<string>): number {
  let n = 0;
  for (const t of a) if (b.has(t)) n++;
  return n;
}

/**
 * Quality gate: a candidate learning may only be promoted to `trusted`
 * when (a) a verifier identity is supplied and (b) no contradiction with
 * an existing trusted fact in the same tier is detected.
 */
export function evaluateLearning(input: {
  tier: MemoryTier;
  fact: string;
  evidence: Record<string, unknown>;
  verifiedBy: string | null;
}): { status: MemoryStatus; contradictionWith: string | null; reason: string } {
  const store = loadStore();
  const newTokens = tokenize(input.fact);
  const sameTierTrusted = store.records.filter((r) => r.tier === input.tier && r.status === "trusted");

  // Contradiction detection: same subject (>=3 shared tokens) but opposite polarity.
  let contradictionWith: string | null = null;
  for (const existing of sameTierTrusted) {
    const existingTokens = tokenize(existing.fact);
    if (overlap(newTokens, existingTokens) >= 3) {
      if (hasNegation(input.fact) !== hasNegation(existing.fact)) {
        contradictionWith = existing.id;
        break;
      }
    }
  }

  if (contradictionWith) {
    return { status: "quarantined", contradictionWith, reason: "Contradiction detected against trusted fact; quarantined for review." };
  }

  if (input.verifiedBy && input.verifiedBy.trim().length > 0) {
    return { status: "trusted", contradictionWith: null, reason: "Verified by supplied verifier; promoted to trusted." };
  }

  return { status: "candidate", contradictionWith: null, reason: "No verifier supplied; stored as candidate (not trusted)." };
}

export function recordLearning(input: {
  tier: MemoryTier;
  fact: string;
  evidence?: Record<string, unknown>;
  verifiedBy?: string | null;
}): LearningRecord {
  const gate = evaluateLearning({
    tier: input.tier,
    fact: input.fact,
    evidence: input.evidence ?? {},
    verifiedBy: input.verifiedBy ?? null,
  });

  const record: LearningRecord = {
    id: `learn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    tier: input.tier,
    fact: input.fact,
    evidence: input.evidence ?? {},
    status: gate.status,
    verifiedBy: input.verifiedBy ?? null,
    contradictionWith: gate.contradictionWith,
    createdAt: new Date().toISOString(),
    promotedAt: gate.status === "trusted" ? new Date().toISOString() : null,
  };

  const store = loadStore();
  store.records.push(record);
  saveStore(store);
  return record;
}

export function recallLearnings(input: {
  query?: string;
  tier?: MemoryTier | null;
  status?: MemoryStatus | null;
  limit?: number;
}): LearningRecord[] {
  const store = loadStore();
  const limit = Math.min(Math.max(1, input.limit ?? 20), 100);
  const qTokens = input.query ? tokenize(input.query) : null;

  let results = store.records.filter((r) => {
    if (input.tier && r.tier !== input.tier) return false;
    if (input.status && r.status !== input.status) return false;
    return true;
  });

  if (qTokens && qTokens.size > 0) {
    results = results
      .map((r) => ({ r, score: overlap(qTokens, tokenize(r.fact)) }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.r);
  } else {
    results = results.slice().reverse();
  }

  return results.slice(0, limit);
}

export function learningStats(): { total: number; byTier: Record<MemoryTier, number>; byStatus: Record<MemoryStatus, number> } {
  const store = loadStore();
  const byTier: Record<MemoryTier, number> = { episodic: 0, semantic: 0, procedural: 0 };
  const byStatus: Record<MemoryStatus, number> = { candidate: 0, trusted: 0, quarantined: 0 };
  for (const r of store.records) {
    byTier[r.tier]++;
    byStatus[r.status]++;
  }
  return { total: store.records.length, byTier, byStatus };
}
