import { getFirestore, Firestore } from "firebase-admin/firestore";

// ─────────────────────────────────────────────────────────────────
// Initialisation — singleton-safe
// ─────────────────────────────────────────────────────────────────
let db: Firestore | null = null;

function getDb(): Firestore {
  db ??= getFirestore();
  return db;
}

// ─────────────────────────────────────────────────────────────────
// Type definitions (mirrors ScrapeHistoryEntry from scrapeEngine.ts)
// ─────────────────────────────────────────────────────────────────

/** Filter options for listHistory() */
export interface HistoryFilter {
  chatType?: string;
  minConfidence?: number;
  userId?: string;
  startDate?: Date;
  endDate?: Date;
  searchQuery?: string;   // substring match on query field
}

/** Pagination options */
export interface PaginationOptions {
  pageSize: number;       // ≤ 100
  pageToken?: string;     // last doc id from previous page
}

/** Paginated response */
export interface PaginatedHistory {
  entries: HistoryEntry[];
  nextPageToken: string | null;
  totalCount: number;
}

/**
 * Shallow copy of a Firestore history document.
 * Mirrors the interface in scrapeEngine.ts to avoid a circular import.
 */
export interface HistoryEntry {
  sessionId: string;
  query: string;
  chatType: string;
  sources: string[];
  rawChunks: Array<{ url: string; text: string }>;
  finalAnswer: string;
  confidence: number;
  timestamp: Date;
  userFeedback?: string;
  scrapedPages?: number;
  cached?: boolean;
  skipped?: boolean;
  [key: string]: unknown;
}

// ─────────────────────────────────────────────────────────────────
// Helper — convert Firestore doc → HistoryEntry
// ─────────────────────────────────────────────────────────────────

function docToEntry(doc: FirebaseFirestore.DocumentSnapshot<FirebaseFirestore.DocumentData>): HistoryEntry {
  const data = doc.data() as Record<string, unknown>;
  return {
    sessionId: doc.id,
    query: (data.query as string) ?? "",
    chatType: (data.chatType as string) ?? "UNKNOWN",
    sources: (data.sources as string[]) ?? [],
    rawChunks: (data.rawChunks as Array<{ url: string; text: string }>) ?? [],
    finalAnswer: (data.finalAnswer as string) ?? "",
    confidence: (data.confidence as number) ?? 0,
    timestamp: (data.timestamp && typeof (data.timestamp as any).toDate === "function" ? (data.timestamp as any).toDate() : new Date()),
    userFeedback: data.userFeedback as string | undefined,
    scrapedPages: data.scrapedPages as number | undefined,
    cached: data.cached as boolean | undefined,
    skipped: data.skipped as boolean | undefined,
  };
}

// ─────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────

const COL = "scrapeHistory";

/**
 * Add a new scraping history entry.
 * Use a provided sessionId for updates, or let one be auto-generated.
 */
export async function addEntry(
  entry: Partial<HistoryEntry>,
): Promise<string> {
  const id = entry.sessionId ?? `hist_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const payload: Record<string, unknown> = {
    query:   entry.query ?? "",
    chatType: entry.chatType ?? "UNKNOWN",
    sources: entry.sources ?? [],
    rawChunks: entry.rawChunks ?? [],
    finalAnswer: entry.finalAnswer ?? "",
    confidence: entry.confidence ?? 0,
  };
  if (entry.timestamp)  payload.timestamp = entry.timestamp;
  else                  payload.timestamp = new Date();
  if (entry.userFeedback !== undefined) payload.userFeedback = entry.userFeedback;
  if (entry.scrapedPages !== undefined) payload.scrapedPages = entry.scrapedPages;
  if (entry.cached !== undefined)       payload.cached       = entry.cached;
  if (entry.skipped !== undefined)      payload.skipped      = entry.skipped;

  await getDb().collection(COL).doc(id).set(payload, { merge: true });
  return id;
}

/**
 * Fetch a single history entry by document ID.
 */
export async function getEntry(sessionId: string): Promise<HistoryEntry | null> {
  const snap = await getDb().collection(COL).doc(sessionId).get();
  return snap.exists ? docToEntry(snap) : null;
}

/**
 * Get all entries for a given session (by sessionId field).
 * Returns them ordered newest-first.
 */
export async function getSessionHistory(sessionId: string): Promise<HistoryEntry[]> {
  const snap = await getDb()
    .collection(COL)
    .where("sessionId", "==", sessionId)
    .orderBy("timestamp", "desc")
    .get();
  return snap.docs.map(docToEntry);
}

/**
 * List history entries with optional filters and pagination.
 */
export async function listHistory(
  filter: HistoryFilter = {},
  pagination: PaginationOptions,
): Promise<PaginatedHistory> {
  let query: FirebaseFirestore.Query = getDb().collection(COL);

  // Apply filters
  if (filter.chatType)  query = query.where("chatType", "==", filter.chatType);
  if (filter.minConfidence != null)
    query = query.where("confidence", ">=", filter.minConfidence);
  if (filter.startDate) query = query.where("timestamp", ">=", filter.startDate);
  if (filter.endDate)   query = query.where("timestamp", "<=", filter.endDate);

  query = query.orderBy("timestamp", "desc");

  const pageSize = Math.min(pagination.pageSize, 100);
  if (pagination.pageToken) {
    const cursorSnap = await getDb().collection(COL).doc(pagination.pageToken).get();
    query = query.startAfter(cursorSnap);
  }

  const snap = await query.limit(pageSize + 1).get();
  const docs = snap.docs;

  const entries = docs.slice(0, pageSize).map(docToEntry);
  const nextPageToken = docs.length > pageSize ? docs[snap.size - 2].id : null;

  return { entries, nextPageToken, totalCount: snap.size };
}

/**
 * Get the total count of history entries (uncapped).
 */
export async function getHistoryCount(filter: HistoryFilter = {}): Promise<number> {
  let query: FirebaseFirestore.Query = getDb().collection(COL);
  if (filter.chatType)  query = query.where("chatType", "==", filter.chatType);
  if (filter.startDate) query = query.where("timestamp", ">=", filter.startDate);
  if (filter.endDate)   query = query.where("timestamp", "<=", filter.endDate);
  const snap = await query.get();
  return snap.size;
}

/**
 * Delete a single history entry by session/document ID.
 */
export async function deleteEntry(sessionId: string): Promise<void> {
  await getDb().collection(COL).doc(sessionId).delete();
}

/**
 * Purge all scraping history entries. Use with caution; returns the
 * number of documents deleted.
 */
export async function deleteAllHistory(): Promise<number> {
  const snap = await getDb().collection(COL).get();
  const batch = getDb().batch();
  snap.docs.forEach((doc) => batch.delete(doc.ref));
  if (snap.size > 0) await batch.commit();
  return snap.size;
}

/**
 * Record user feedback (thumbs-up / thumbs-down / correction) on a history entry.
 *
 * @param sessionId   Document ID of the history entry
 * @param feedback    "up" | "down" | "corrected:{text}"
 */
export async function recordFeedback(
  sessionId: string,
  feedback: string,
): Promise<void> {
  await getDb().collection(COL).doc(sessionId).update({
    userFeedback: feedback,
  });
}
