"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.scrapeHealthFn = exports.classifyIntentFn = exports.scrapeAndRespondFn = void 0;
exports.scrapeAndRespond = scrapeAndRespond;
const app_1 = require("firebase-admin/app");
const firestore_1 = require("firebase-admin/firestore");
const https = __importStar(require("firebase-functions/v2/https"));
const axios_1 = __importDefault(require("axios"));
const httpsOptions = { region: "us-central1" };
// ─────────────────────────────────────────────────────────────────
// Firebase initialisation (singleton-safe)
// ─────────────────────────────────────────────────────────────────
let db = null;
function getDb() {
    db ?? (db = (0, firestore_1.getFirestore)((0, app_1.initializeApp)({})));
    return db;
}
// ─────────────────────────────────────────────────────────────────
// Firestore collection constants
// ─────────────────────────────────────────────────────────────────
const COL = {
    policies: "scrapePolicies",
    presets: "scrapePresets",
    domains: "scrapeAllowedDomains",
    history: "scrapeHistory",
    events: "scrapeEvent",
};
const GREETING_WORDS = /^(hi|hello|hlw|hey|good\s*(morning|afternoon|evening)|হ্যালো|নমস্কার|হাই)\s*$/i;
const SIMILAR_WORDS = /^(how are you|কেমন আছো|কেমন আছ|কেমন Chao|what'?s up|how'?s it going)/i;
const FOLLOW_UP_WORDS = /^(tell me more|more|and\?|আরও|আরও বলো|而且|その他)/i;
const COMMAND_WORDS = /^(deploy|run|test|build|reboot|kill|restart|ডিপ্লয়|রান|টেস্ট)/i;
const COMPLEX_HINTS = /(compare|vs|versus|benchmark|review|analysis|difference|মতামত|তুলনা|বিবরণ)/i;
const QUESTION_MARK = /\?$/;
function classifyIntent(message) {
    const msg = message.trim().toLowerCase();
    if (GREETING_WORDS.test(msg))
        return "GREETING";
    if (SIMILAR_WORDS.test(msg))
        return "SIMILAR";
    if (COMMAND_WORDS.test(msg))
        return "COMMAND";
    if (FOLLOW_UP_WORDS.test(msg))
        return "FOLLOW_UP";
    if (COMPLEX_HINTS.test(msg))
        return "COMPLEX_QUESTION";
    if (QUESTION_MARK.test(msg))
        return "SIMPLE_QUESTION";
    if (msg.length < 20)
        return "SIMPLE_QUESTION";
    return "COMPLEX_QUESTION";
}
// ─────────────────────────────────────────────────────────────────
// Step 2 — Firestore config loader helpers
// ─────────────────────────────────────────────────────────────────
async function getGlobalPolicy() {
    const snap = await getDb().collection(COL.policies).doc("global").get();
    return snap.exists ? snap.data() : null;
}
async function getPolicy(type) {
    const snap = await getDb().collection(COL.policies).doc(type).get();
    return snap.exists ? snap.data() : null;
}
async function getPreset(presetId) {
    const snap = await getDb().collection(COL.presets).doc(presetId).get();
    return snap.exists ? snap.data() : null;
}
async function getAllowedDomains() {
    const snap = await getDb().collection(COL.domains).get();
    return snap.docs.map((d) => d.data()).filter((d) => d.enabled);
}
async function findCachedAnswer(query, cacheTTLSeconds) {
    const threshold = firestore_1.Timestamp.fromMillis(Date.now() - cacheTTLSeconds * 1000);
    const snap = await getDb()
        .collection(COL.history)
        .where("query", "==", query)
        .where("timestamp", ">", threshold)
        .orderBy("timestamp", "desc")
        .limit(1)
        .get();
    if (snap.empty)
        return null;
    const d = snap.docs[0].data();
    return { ...d, sessionId: snap.docs[0].id };
}
// ─────────────────────────────────────────────────────────────────
// Step 6 helpers — domain allow /Trust-scores
// ─────────────────────────────────────────────────────────────────
function extractHost(url) {
    try {
        return new URL(url).hostname;
    }
    catch {
        return url;
    }
}
function isDomainAllowed(domain, domains) {
    const entry = domains.find((d) => domain === d.domain || domain.endsWith("." + d.domain));
    if (!entry)
        return { allowed: true, trustLevel: "standard" }; // open by default — admin can restrict via Firestore
    return { allowed: entry.enabled, trustLevel: entry.trustLevel };
}
async function extractFromPage(pageUrl, strategy, eventId) {
    const result = await callPlaywright("extract", { url: pageUrl, strategy, eventId });
    return {
        url: pageUrl,
        title: result?.title ? String(result.title) : pageUrl,
        text: result?.text ? String(result.text) : "",
        strategy,
    };
}
// ─────────────────────────────────────────────────────────────────
// Playwright proxy helper
// ─────────────────────────────────────────────────────────────────
const PLAYWRIGHT_URL = process.env.BROWSER_AUTOMATION_URL || "http://127.0.0.1:3001";
async function callPlaywright(action, body) {
    try {
        const res = await axios_1.default.post(`${PLAYWRIGHT_URL}/${action}`, body, {
            timeout: parseInt(process.env.SCRAPE_TIMEOUT_MS || "30000"),
        });
        return res.data;
    }
    catch (err) {
        throw new https.HttpsError("unavailable", `Browser automation unavailable for ${action}: ${err.message}`);
    }
}
// ─────────────────────────────────────────────────────────────────
// Step 9 — Firestore history writer
// ─────────────────────────────────────────────────────────────────
async function writeHistory(entry) {
    const ref = entry.sessionId
        ? getDb().collection(COL.history).doc(entry.sessionId)
        : getDb().collection(COL.history).doc();
    await ref.set({
        ...entry,
        timestamp: firestore_1.Timestamp.now(),
    });
    return ref.id;
}
async function logEvent(sessionId, type, payload) {
    await getDb()
        .collection(COL.events)
        .doc()
        .set({
        sessionId,
        type,
        payload,
        timestamp: firestore_1.Timestamp.now(),
    });
}
// ─────────────────────────────────────────────────────────────────
// Public scrape flow
// ─────────────────────────────────────────────────────────────────
/**
 * Main scraping entry point — called by the chat-processing pipeline.
 *
 * @param message  User message text
 * @param userId    Firebase UID of the caller
 * @returns         { answer, sources, confidence, sessionId }
 */
async function scrapeAndRespond(message, userId) {
    const sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const chatType = classifyIntent(message);
    // ── Step 2: policy lookup ──────────────────────────────────────
    const globalPolicy = await getGlobalPolicy();
    if (!globalPolicy?.enabled) {
        return { answer: "Web scraping is currently disabled by global policy.", sources: [], confidence: 0 };
    }
    const perTypePolicy = await getPolicy(chatType);
    if (!perTypePolicy?.enabled) {
        // Skipped — return empty, caller falls back to local knowledge
        return { answer: "", sources: [], confidence: 0, chatType, sessionId, skipped: true };
    }
    const policy = { ...globalPolicy, ...perTypePolicy };
    // ── Cache check for FOLLOW_UP ──────────────────────────────────
    if (chatType === "FOLLOW_UP" || chatType === "SIMPLE_QUESTION" || chatType === "COMPLEX_QUESTION") {
        const cached = await findCachedAnswer(message, policy.cacheTTL);
        if (cached) {
            await logEvent(sessionId, "cached_answer", { fromSession: cached.sessionId, query: message });
            return {
                answer: cached.finalAnswer,
                sources: cached.sources,
                confidence: cached.confidence,
                chatType,
                sessionId,
                cached: true,
                originalSessionId: cached.sessionId,
            };
        }
    }
    // Skip heavy flow for GREETING / SIMILAR / COMMAND
    if (chatType === "GREETING" || chatType === "SIMILAR") {
        return { answer: "", sources: [], confidence: 0, chatType, sessionId, skipped: true };
    }
    // ── Step 3: build search entry point ───────────────────────────
    const domains = await getAllowedDomains();
    const allSearchEngines = policy.searchEngines || ["google"];
    const maxResults = policy.maxResults || 3;
    const maxDepth = policy.maxDepth ?? 1;
    const strategy = policy.extractStrategy || "article-extract";
    const builtUrls = [];
    for (const engine of allSearchEngines) {
        const preset = await getPreset(engine);
        if (!preset || !preset.searchUrlTemplate)
            continue;
        const queryParam = encodeURIComponent(message);
        const engineUrl = preset.searchUrlTemplate.replace("{q}", queryParam);
        // trust gate
        const host = extractHost(engineUrl);
        const { allowed } = isDomainAllowed(host, domains);
        if (!allowed) {
            await logEvent(sessionId, "domain_skipped", { url: engineUrl, reason: "not_in_allowed_domains" });
            continue;
        }
        builtUrls.push({ engine, url: engineUrl });
    }
    if (builtUrls.length === 0) {
        return { answer: "No search engine configured or all domains blocked.", sources: [], confidence: 0, chatType, sessionId };
    }
    // ── Step 4: launch navigate sessions in parallel ───────────────
    const searchEventId = `${sessionId}_search`;
    await logEvent(sessionId, "navigate_start", { urls: builtUrls.map((b) => b.url) });
    // Dispatch all search-engine navigations via Playwright, but don't block the
    // event loop — fire and await.
    const navigatePromises = builtUrls.map(async ({ engine, url }) => {
        try {
            await callPlaywright("navigate", { url, eventId: searchEventId });
            await logEvent(sessionId, "navigate_complete", { engine, url });
        }
        catch (err) {
            await logEvent(sessionId, "error", { engine, url, error: err.message });
        }
    });
    await Promise.allSettled(navigatePromises);
    // ── Step 5: extract result links ───────────────────────────────
    let resultLinks = [];
    try {
        const searchContent = await callPlaywright("extract", { url: builtUrls[0]?.url || "", strategy: "search-links", eventId: searchEventId });
        resultLinks = Array.isArray(searchContent)
            ? searchContent.map((r) => r.href).filter(Boolean)
            : [];
    }
    catch (extractionError) {
        console.error(`[ScrapeEngine] Failed to extract search result links:`, extractionError);
        // If link extraction fails, fall back to navigating each engine URL directly
        resultLinks = builtUrls.map((b) => b.url);
    }
    // cap to top N results
    resultLinks = resultLinks.slice(0, maxResults);
    // ── Step 6: crawl deeper (maxDepth > 0) ───────────────────────
    const allExtracted = [];
    const crawl = async (url, depth) => {
        if (depth > maxDepth || resultLinks.length === 0)
            return;
        for (const link of resultLinks) {
            const host = extractHost(link);
            const { allowed, trustLevel } = isDomainAllowed(host, domains);
            if (!allowed || trustLevel === "suspicious") {
                await logEvent(sessionId, "domain_skipped", { url: link, reason: trustLevel === "suspicious" ? "suspicious_domain" : "not_allowed", trustLevel });
                continue;
            }
            await logEvent(sessionId, "extract_start", { url: link, depth });
            try {
                const page = await extractFromPage(link, strategy, `${sessionId}_d${depth}`);
                allExtracted.push(page);
                await logEvent(sessionId, "extract_complete", { url: link, depth, textLength: page.text.length, strategy: page.strategy });
                // shallow follow links one level deeper
                if (depth < maxDepth) {
                    const outbound = (await callPlaywright("extract", { url: link, strategy: "outbound-links", eventId: `${sessionId}_out_${depth}` }));
                    const nextUrls = outbound?.map((r) => r.href).filter(Boolean) || [];
                    for (const next of nextUrls.slice(0, 2))
                        await crawl(next, depth + 1);
                }
            }
            catch (err) {
                await logEvent(sessionId, "error", { url: link, phase: "extract", error: err.message });
            }
        }
    };
    // crawl the top results
    await crawl(builtUrls[0]?.url || "", 0);
    // ── Step 7: merge, deduplicate, summarize ─────────────────────
    const mergedText = mergeAndDeduplicate(allExtracted);
    const answer = summarise(mergedText, message);
    // ── Step 8: store session history ──────────────────────────────
    const firestoreDocId = await writeHistory({
        sessionId,
        query: message,
        chatType,
        sources: allExtracted.map((p) => p.url),
        rawChunks: allExtracted.map((p) => ({ url: p.url, text: p.text })),
        finalAnswer: answer,
        confidence: allExtracted.length > 0 ? Math.min(0.85, 0.55 + allExtracted.length * 0.07) : 0,
        timestamp: firestore_1.Timestamp.now(),
    });
    sessionId; // used; intentionally shadowed by const above — keep local sessionId for return
    // ── Step 9: return ─────────────────────────────────────────────
    return {
        answer,
        sources: allExtracted.map((p) => p.url),
        confidence: allExtracted.length > 0 ? Math.min(0.90, 0.55 + allExtracted.length * 0.08) : 0.2,
        chatType,
        sessionId: firestoreDocId,
        scrapedPages: allExtracted.length,
    };
}
// ─────────────────────────────────────────────────────────────────
// Text processing helpers
// ─────────────────────────────────────────────────────────────────
const TEXT_SIMILARITY_THRESHOLD = 0.85;
function jaccard(a, b) {
    const setA = new Set(a.toLowerCase().split(/\s+/));
    const setB = new Set(b.toLowerCase().split(/\s+/));
    const intersection = [...setA].filter((w) => setB.has(w)).length;
    const union = new Set([...setA, ...setB]).size;
    return union === 0 ? 0 : intersection / union;
}
function contentHash(text) {
    let hash = 0;
    const normalized = text.replace(/\s+/g, " ").slice(0, 2000);
    for (let i = 0; i < normalized.length; i++) {
        hash = ((hash << 5) - hash + normalized.charCodeAt(i)) | 0;
    }
    return hash.toString(16);
}
function mergeAndDeduplicate(pages) {
    // Deduplicate by URL
    const urlMap = new Map();
    for (const p of pages)
        if (!urlMap.has(p.url))
            urlMap.set(p.url, p);
    // Deduplicate by content similarity (Jaccard ≥ threshold)
    const unique = [];
    const hashes = new Set();
    const textContent = new Set();
    for (const p of urlMap.values()) {
        const hash = contentHash(p.text);
        const isNearDuplicate = [...textContent].some((existing) => jaccard(p.text, existing) >= TEXT_SIMILARITY_THRESHOLD);
        if (!hashes.has(hash) && !isNearDuplicate) {
            hashes.add(hash);
            textContent.add(p.text.slice(0, 500));
            unique.push(p);
        }
    }
    return unique.map((p) => `### ${p.title}\n${p.text}`).join("\n\n");
}
function summarise(mergedText, query) {
    // Local extractive summary — first 3 most informative paragraphs
    if (!mergedText.trim())
        return `No useful content was found for "${query}". Try rephrasing the question or checking the configured search engines.`;
    const paragraphs = mergedText.split(/\n\n+/).filter((p) => p.length > 60);
    const topThree = paragraphs.slice(0, 3).join("\n\n");
    const wordCount = mergedText.split(/\s+/).length;
    return `**Research Summary** (${wordCount} words total)\n\n${topThree}`;
}
// ─────────────────────────────────────────────────────────────────
// Cloud Function entry points
// ─────────────────────────────────────────────────────────────────
/**
 * POST /scrapeAndRespond — main scraping endpoint.
 * Body: { message: string, userId: string }
 */
exports.scrapeAndRespondFn = https.onRequest({ ...httpsOptions, cors: true }, async (req, res) => {
    if (req.method !== "POST") {
        res.status(405).json({ error: "Method Not Allowed" });
        return;
    }
    const { message, userId } = req.body;
    if (!message || !userId) {
        res.status(400).json({ error: "Missing required field: message or userId" });
        return;
    }
    try {
        const result = await scrapeAndRespond(message, userId);
        res.status(200).json(result);
    }
    catch (err) {
        console.error("[scrapeEngine]", err);
        res.status(500).json({ error: err.message });
    }
});
/**
 * POST /classifyIntent — classifier-only endpoint for testing.
 * Body: { message: string }
 */
exports.classifyIntentFn = https.onRequest({ ...httpsOptions, cors: true }, async (req, _res) => {
    if (req.method !== "POST") {
        _res.status(405).end();
        return;
    }
    const { message } = req.body;
    if (!message) {
        _res.status(400).json({ error: "message required" });
        return;
    }
    _res.status(200).json({ chatType: classifyIntent(message), message });
});
/**
 * GET /health
 */
exports.scrapeHealthFn = https.onRequest({ ...httpsOptions, cors: true }, async (_req, res) => {
    const playStatus = (await (async () => {
        try {
            const r = await axios_1.default.get(`${PLAYWRIGHT_URL}/health`, { timeout: 5000 });
            return { ok: r.status === 200, status: r.status };
        }
        catch {
            return { ok: false };
        }
    })());
    res.status(200).json({
        service: "scrapeEngine",
        playwright: playStatus,
        uptime: process.uptime(),
    });
});
//# sourceMappingURL=scrapeEngine.js.map