// ============================================================================
// file >> scrapeEngine.d.ts
// project >> SupremeAI 2.0
// purpose >> General utility
// module >> infrastructure
// ============================================================================
export declare function scrapeAndRespond(message: string, userId: string): Promise<Record<string, unknown>>;
/**
 * POST /scrapeAndRespond — main scraping endpoint.
 * Body: { message: string, userId: string }
 */
export declare const scrapeAndRespondFn: https.HttpsFunction;
/**
 * POST /classifyIntent — classifier-only endpoint for testing.
 * Body: { message: string }
 */
export declare const classifyIntentFn: https.HttpsFunction;
/**
 * GET /health
 */
export declare const scrapeHealthFn: https.HttpsFunction;
//# sourceMappingURL=scrapeEngine.d.ts.map