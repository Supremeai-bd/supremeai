// ============================================================================
// file >> chatClassifier.d.ts
// project >> SupremeAI 2.0
// purpose >> Chat interface
// module >> infrastructure
// ============================================================================
export interface ClassifyResult {
    chatType: ChatType;
    message: string;
    classifiedAt: number;
}
/**
 * Classify a raw user message into a ChatType.
 *
 * Priority order:
 *   1. GREETING  — hi / hello / hællo / etc.
 *   2. SIMILAR   — "how are you" / "কেমন আছো"
 *   3. COMMAND   — starts with a known command keyword
 *   4. FOLLOW_UP — "tell me more", "আরও", etc.
 *   5. COMPLEX_QUESTION — sub-string hint words (compare, vs, analysis …)
 *   6. SIMPLE_QUESTION — ends with "?"
 *   7. SIMPLE_QUESTION — short messages (< 20 chars after trim)
 *   8. COMPLEX_QUESTION — fallback (assume complex)
 */
export declare function classifyIntent(message: string, nowMs?: number): ClassifyResult;
//# sourceMappingURL=chatClassifier.d.ts.map