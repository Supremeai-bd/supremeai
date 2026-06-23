/** Filter options for listHistory() */
export interface HistoryFilter {
    chatType?: string;
    minConfidence?: number;
    userId?: string;
    startDate?: Date;
    endDate?: Date;
    searchQuery?: string;
}
/** Pagination options */
export interface PaginationOptions {
    pageSize: number;
    pageToken?: string;
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
    rawChunks: Array<{
        url: string;
        text: string;
    }>;
    finalAnswer: string;
    confidence: number;
    timestamp: Date;
    userFeedback?: string;
    scrapedPages?: number;
    cached?: boolean;
    skipped?: boolean;
    [key: string]: unknown;
}
/**
 * Add a new scraping history entry.
 * Use a provided sessionId for updates, or let one be auto-generated.
 */
export declare function addEntry(entry: Partial<HistoryEntry>): Promise<string>;
/**
 * Fetch a single history entry by document ID.
 */
export declare function getEntry(sessionId: string): Promise<HistoryEntry | null>;
/**
 * Get all entries for a given session (by sessionId field).
 * Returns them ordered newest-first.
 */
export declare function getSessionHistory(sessionId: string): Promise<HistoryEntry[]>;
/**
 * List history entries with optional filters and pagination.
 */
export declare function listHistory(filter: HistoryFilter | undefined, pagination: PaginationOptions): Promise<PaginatedHistory>;
/**
 * Get the total count of history entries (uncapped).
 */
export declare function getHistoryCount(filter?: HistoryFilter): Promise<number>;
/**
 * Delete a single history entry by session/document ID.
 */
export declare function deleteEntry(sessionId: string): Promise<void>;
/**
 * Purge all scraping history entries. Use with caution; returns the
 * number of documents deleted.
 */
export declare function deleteAllHistory(): Promise<number>;
/**
 * Record user feedback (thumbs-up / thumbs-down / correction) on a history entry.
 *
 * @param sessionId   Document ID of the history entry
 * @param feedback    "up" | "down" | "corrected:{text}"
 */
export declare function recordFeedback(sessionId: string, feedback: string): Promise<void>;
//# sourceMappingURL=scrapeHistoryManager.d.ts.map