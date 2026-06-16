// ─────────────────────────────────────────────────────────────────
// chatClassifier.ts
// Intent / ChatType classifier for the SupremeAI scraping pipeline.
//
// Extracted from classifyIntent() in scrapeEngine.ts so that
// ChatProcessingService.java and other callers can invoke intent
// classification without depending on the full scraping engine.
// ─────────────────────────────────────────────────────────────────

/** All supported chat types returned by classifyIntent() */
export type ChatType =
  | "GREETING"
  | "SIMILAR"
  | "SIMPLE_QUESTION"
  | "COMPLEX_QUESTION"
  | "FOLLOW_UP"
  | "COMMAND"
  | "UNKNOWN";

/** Result of a single-classify call */
export interface ClassifyResult {
  chatType: ChatType;
  message: string;
  classifiedAt: number; // epoch ms
}

// ─────────────────────────────────────────────────────────────────
// Regex patterns — kept identical to scrapeEngine.ts for backwards
// compatibility with any existing compare-diff expectations.
// ─────────────────────────────────────────────────────────────────

const GREETING_WORDS = /^(hi|hello|hlw|hey|good\s*(morning|afternoon|evening)|হ্যালো|নমস্কার|হাই)\s*$/i;
const SIMILAR_WORDS  = /^(how are you|কেমন আছো|কেমন আছ|কেমন Chao|what'?s up|how'?s it going)/i;
const FOLLOW_UP_WORDS = /^(tell me more|more|and\?|আরও|আরও বলো|而且|その他)/i;
const COMMAND_WORDS  = /^(deploy|run|test|build|reboot|kill|restart|ডিপ্লয়|রান|টেস্ট)/i;
const COMPLEX_HINTS  = /(compare|vs|versus|benchmark|review|analysis|difference|মতামত|তুলনা|বিবরণ)/i;
const QUESTION_MARK  = /\?$/;

// ─────────────────────────────────────────────────────────────────
// classifyIntent
// ─────────────────────────────────────────────────────────────────

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
export function classifyIntent(message: string, nowMs?: number): ClassifyResult {
  const trimmed = message.trim().toLowerCase();

  let chatType: ChatType;
  if (GREETING_WORDS.test(trimmed))      chatType = "GREETING";
  else if (SIMILAR_WORDS.test(trimmed))  chatType = "SIMILAR";
  else if (COMMAND_WORDS.test(trimmed))  chatType = "COMMAND";
  else if (FOLLOW_UP_WORDS.test(trimmed)) chatType = "FOLLOW_UP";
  else if (COMPLEX_HINTS.test(trimmed))  chatType = "COMPLEX_QUESTION";
  else if (QUESTION_MARK.test(trimmed))  chatType = "SIMPLE_QUESTION";
  else if (trimmed.length < 20)           chatType = "SIMPLE_QUESTION";
  else                                    chatType = "COMPLEX_QUESTION";

  return {
    chatType,
    message,
    classifiedAt: nowMs ?? Date.now(),
  };
}
