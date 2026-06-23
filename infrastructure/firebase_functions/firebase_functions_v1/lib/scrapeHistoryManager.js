"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.addEntry = addEntry;
exports.getEntry = getEntry;
exports.getSessionHistory = getSessionHistory;
exports.listHistory = listHistory;
exports.getHistoryCount = getHistoryCount;
exports.deleteEntry = deleteEntry;
exports.deleteAllHistory = deleteAllHistory;
exports.recordFeedback = recordFeedback;
const firestore_1 = require("firebase-admin/firestore");
// ─────────────────────────────────────────────────────────────────
// Initialisation — singleton-safe
// ─────────────────────────────────────────────────────────────────
let db = null;
function getDb() {
    db ?? (db = (0, firestore_1.getFirestore)());
    return db;
}
// ─────────────────────────────────────────────────────────────────
// Helper — convert Firestore doc → HistoryEntry
// ─────────────────────────────────────────────────────────────────
function docToEntry(doc) {
    const data = doc.data();
    return {
        sessionId: doc.id,
        query: data.query ?? "",
        chatType: data.chatType ?? "UNKNOWN",
        sources: data.sources ?? [],
        rawChunks: data.rawChunks ?? [],
        finalAnswer: data.finalAnswer ?? "",
        confidence: data.confidence ?? 0,
        timestamp: (data.timestamp && typeof data.timestamp.toDate === "function" ? data.timestamp.toDate() : new Date()),
        userFeedback: data.userFeedback,
        scrapedPages: data.scrapedPages,
        cached: data.cached,
        skipped: data.skipped,
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
async function addEntry(entry) {
    const id = entry.sessionId ?? `hist_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const payload = {
        query: entry.query ?? "",
        chatType: entry.chatType ?? "UNKNOWN",
        sources: entry.sources ?? [],
        rawChunks: entry.rawChunks ?? [],
        finalAnswer: entry.finalAnswer ?? "",
        confidence: entry.confidence ?? 0,
    };
    if (entry.timestamp)
        payload.timestamp = entry.timestamp;
    else
        payload.timestamp = new Date();
    if (entry.userFeedback !== undefined)
        payload.userFeedback = entry.userFeedback;
    if (entry.scrapedPages !== undefined)
        payload.scrapedPages = entry.scrapedPages;
    if (entry.cached !== undefined)
        payload.cached = entry.cached;
    if (entry.skipped !== undefined)
        payload.skipped = entry.skipped;
    await getDb().collection(COL).doc(id).set(payload, { merge: true });
    return id;
}
/**
 * Fetch a single history entry by document ID.
 */
async function getEntry(sessionId) {
    const snap = await getDb().collection(COL).doc(sessionId).get();
    return snap.exists ? docToEntry(snap) : null;
}
/**
 * Get all entries for a given session (by sessionId field).
 * Returns them ordered newest-first.
 */
async function getSessionHistory(sessionId) {
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
async function listHistory(filter = {}, pagination) {
    let query = getDb().collection(COL);
    // Apply filters
    if (filter.chatType)
        query = query.where("chatType", "==", filter.chatType);
    if (filter.minConfidence != null)
        query = query.where("confidence", ">=", filter.minConfidence);
    if (filter.startDate)
        query = query.where("timestamp", ">=", filter.startDate);
    if (filter.endDate)
        query = query.where("timestamp", "<=", filter.endDate);
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
async function getHistoryCount(filter = {}) {
    let query = getDb().collection(COL);
    if (filter.chatType)
        query = query.where("chatType", "==", filter.chatType);
    if (filter.startDate)
        query = query.where("timestamp", ">=", filter.startDate);
    if (filter.endDate)
        query = query.where("timestamp", "<=", filter.endDate);
    const snap = await query.get();
    return snap.size;
}
/**
 * Delete a single history entry by session/document ID.
 */
async function deleteEntry(sessionId) {
    await getDb().collection(COL).doc(sessionId).delete();
}
/**
 * Purge all scraping history entries. Use with caution; returns the
 * number of documents deleted.
 */
async function deleteAllHistory() {
    const snap = await getDb().collection(COL).get();
    const batch = getDb().batch();
    snap.docs.forEach((doc) => batch.delete(doc.ref));
    if (snap.size > 0)
        await batch.commit();
    return snap.size;
}
/**
 * Record user feedback (thumbs-up / thumbs-down / correction) on a history entry.
 *
 * @param sessionId   Document ID of the history entry
 * @param feedback    "up" | "down" | "corrected:{text}"
 */
async function recordFeedback(sessionId, feedback) {
    await getDb().collection(COL).doc(sessionId).update({
        userFeedback: feedback,
    });
}
//# sourceMappingURL=scrapeHistoryManager.js.map