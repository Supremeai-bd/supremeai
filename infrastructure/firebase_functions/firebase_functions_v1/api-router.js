const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const externalClient = require('./utils/externalClient');
const axios = require('axios');

const app = express();

const allowedOrigins = [
  'http://127.0.0.1:3000',
  'http://127.0.0.1:5173',
  'http://127.0.0.1:5000',
  'http://127.0.0.1:3000',
  'http://127.0.0.1:5173',
  'http://127.0.0.1:5000',
];

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.includes(origin) || origin.includes('supremeai')) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
}));
app.use(express.json());

const DEFAULT_SCRAPE_ENDPOINT = process.env.SCRAPE_ENGINE_URL || 'https://us-central1-supremeai.cloudfunctions.net/scrapeAndRespondFn';
const DEFAULT_CHAT_ENDPOINT = process.env.CHAT_API_URL || 'https://supremeai-a.web.app/api/chat/send';

function shouldUseScrapeEngine(req) {
  const preferScrape = (req.headers['x-use-scrape'] === 'true') || (req.body && req.body.useScrape === true);
  return !!preferScrape;
}

async function proxyToScrapeEngine(message, userId) {
  const url = DEFAULT_SCRAPE_ENDPOINT;
  const response = await axios.post(url, { message, userId }, { timeout: 30000 });
  return response.data;
}

app.get(['/health', '/api/health'], (req, res) => {
  res.json({
    status: 'ok',
    mode: 'coordinator',
    scrapeEngine: DEFAULT_SCRAPE_ENDPOINT,
    chatBackend: DEFAULT_CHAT_ENDPOINT,
  });
});

// REAL LLM Connection (Gemini / OpenAI Fallback)
async function callChatBackend(message, token) {
  const apiKey = process.env.SUPREME_API_KEY || process.env.GEMINI_API_KEY || process.env.OPENAI_API_KEY;
  const targetModel = process.env.SUPREME_CORE_MODEL || 'gemini-pro';

  if (!apiKey) {
    // Fallback to local neural core if no API key
    return generateSmartAIResponse(message);
  }

  try {
    // Attempt Gemini call
    const response = await axios.post(
      `https://generativelanguage.googleapis.com/v1beta/models/${targetModel}:generateContent`,
      {
        contents: [{ parts: [{ text: message }] }]
      },
      {
        headers: {
          'x-goog-api-key': apiKey,
          'Content-Type': 'application/json'
        },
        timeout: 10000
      }
    );

    if (response.data && response.data.candidates && response.data.candidates.length > 0) {
      const text = response.data.candidates[0].content.parts[0].text;
      return {
        message: text,
        confidence: 0.95,
        chatType: 'LLM_RESPONSE',
        sourceType: 'SUPREME_CORE_API',
        sources: [`${process.env.SUPREME_BRAND_NAME || 'SupremeAI'} Intelligence`]
      };
    }
    throw new Error('Invalid LLM response format');
  } catch (err) {
    console.error('[LLM] API call failed:', err.message);
    return generateSmartAIResponse(message);
  }
}

async function unifiedChatHandler(req, res) {
  const message = (req.body && req.body.message) ? String(req.body.message) : '';
  const userId = (req.body && req.body.userId) ? String(req.body.userId) : 'anonymous';
  const token = req.headers['authorization'] ? String(req.headers['authorization']).split('Bearer ')[1] : null;

  if (!message || !message.trim()) {
    return res.status(400).json({ success: false, message: 'Message is required', sourceType: 'error' });
  }

  try {
    let answer = '';
    let sources = [];
    let confidence = 0.2;
    let chatType = 'UNKNOWN';
    let sourceType = 'UNKNOWN';
    let scrapedPages = 0;

    if (shouldUseScrapeEngine(req)) {
      try {
        const scrapeResult = await proxyToScrapeEngine(message.trim(), userId);
        if (scrapeResult && scrapeResult.answer) {
          answer = scrapeResult.answer;
          sources = Array.isArray(scrapeResult.sources) ? scrapeResult.sources : [];
          confidence = typeof scrapeResult.confidence === 'number' ? scrapeResult.confidence : 0.55;
          chatType = scrapeResult.chatType || 'COMPLEX_QUESTION';
          sourceType = scrapeResult.cached ? 'SCRAPE_CACHE' : 'SCRAPE_ENGINE';
          scrapedPages = typeof scrapeResult.scrapedPages === 'number' ? scrapeResult.scrapedPages : sources.length;
        }
      } catch (scrapeError) {
        console.warn('[api-router] Scrape engine failed, falling back to chat backend:', scrapeError.message);
      }
    }

    if (!answer) {
      try {
        const chatResult = await callChatBackend(message, token);
        if (chatResult && chatResult.message) {
          answer = chatResult.message;
          confidence = typeof chatResult.confidence === 'number' ? chatResult.confidence : 0.5;
          chatType = chatResult.chatType || 'SIMPLE_QUESTION';
          sourceType = chatResult.source_type || chatResult.sourceType || 'CORE_API';
          sources = Array.isArray(chatResult.sources) ? chatResult.sources : [];
        }
      } catch (chatError) {
        console.warn('[api-router] Chat backend failed, using virtual crawler:', chatError.message);
      }
    }

    if (!answer) {
      // Both scraping and LLM failed or yielded empty
      chatType = 'UNKNOWN';
      sourceType = 'ERROR';
      confidence = 0;
      answer = "সিস্টেম তথ্য সংগ্রহ করতে পারেনি। অনুগ্রহ করে আবার চেষ্টা করুন।";
    }

    return res.json({
      success: true,
      message: answer,
      sources,
      confidence,
      chatType,
      sourceType,
      scrapedPages,
      userId,
    });
  } catch (error) {
    console.error('[api-router] Unified chat error:', error && error.message);
    return res.status(500).json({ success: false, message: 'Service unavailable. Please try again later.', sourceType: 'error', chatType: 'UNKNOWN' });
  }
}

app.post(['/api/chat/send', '/chat/send'], async (req, res) => {
  return unifiedChatHandler(req, res);
});

app.post(['/api/scrape/and-respond', '/scrape/and-respond'], async (req, res) => {
  const message = (req.body && req.body.message) ? String(req.body.message) : '';
  const userId = (req.body && req.body.userId) ? String(req.body.userId) : 'anonymous';
  if (!message || !message.trim()) {
    return res.status(400).json({ error: 'Missing required field: message' });
  }
  try {
    const result = await proxyToScrapeEngine(message.trim(), userId);
    return res.json({ success: true, ...result });
  } catch (error) {
    console.error('[api-router] Scrape proxy error:', error && error.message);
    return res.status(502).json({ success: false, error: 'Scrape engine unavailable', details: error && error.message });
  }
});

app.post(['/api/chat/classify', '/chat/classify'], async (req, res) => {
  const message = (req.body && req.body.message) ? String(req.body.message) : '';
  if (!message || !message.trim()) {
    return res.status(400).json({ error: 'message required' });
  }
  try {
    const scrapeUrl = DEFAULT_SCRAPE_ENDPOINT.replace('/scrapeAndRespondFn', '/classifyIntentFn');
    const response = await axios.post(scrapeUrl, { message }, { timeout: 10000 });
    return res.json({ success: true, ...response.data });
  } catch (error) {
    return res.status(500).json({ success: false, error: 'Classification failed' });
  }
});

function calculateOverlapScore(query, task) {
  const q = (query || '').toLowerCase().replace(/[^\u0000-\u007F\u0980-\u09ff\w\s]/g, '');
  const a = (task || '').toLowerCase().replace(/[^\u0000-\u007F\u0980-\u09ff\w\s]/g, '');
  const queryWords = new Set(q.split(/\s+/).filter(w => w && w.length > 2));
  const taskWords = a.split(/\s+/).filter(w => w && w.length > 2);
  if (queryWords.size === 0) return 0;
  let match = 0;
  for (const w of taskWords) if (queryWords.has(w)) match++;
  return match / Math.max(1, queryWords.size);
}

function searchCoreKnowledge(userMessage) {
  try {
    const knowledgePath = path.join(__dirname, '..', 'src', 'main', 'resources', 'core_knowledge.json');
    if (!fs.existsSync(knowledgePath)) return null;
    const raw = fs.readFileSync(knowledgePath, 'utf8');
    const list = JSON.parse(raw || '[]');
    let best = null;
    let bestScore = 0;
    for (const item of list) {
      const score = calculateOverlapScore(userMessage, item.task || item.question || '');
      if (score > bestScore) {
        bestScore = score;
        best = item;
      }
    }
    if (best && bestScore >= 0.3) {
      return { solution: best.solution || best.answer || '', score: bestScore, category: best.category };
    }
    return null;
  } catch (e) {
    console.error('[CoreKnowledge] read error', e && e.message);
    return null;
  }
}

function classifySemanticIntent(userMessage) {
  const q = (userMessage || '').toLowerCase();
  if (/exception|error|compile|run|bug|nullpointer|git|npm|gradle|dependency|api|db|class|function|method|import|debug|stack trace/i.test(q)) {
    return { categoryId: 'coding', name: 'Coding', timeout: 3000 };
  }
  if (/bangladesh|govt|government|সরকার|কর|দাপ্তরিক|মন্ত্রণালয়/i.test(q)) {
    return { categoryId: 'bangladesh_govt', name: 'Bangladesh Govt', timeout: 3500 };
  }
  if (/weather|temperature|rain|আবহাওয়া|বৃষ্টি|তাপমাত্রা/i.test(q)) {
    return { categoryId: 'weather', name: 'Weather', timeout: 2000 };
  }
  if (/tech|nvidia|gpu|cpu|openai|gemini|llama|release|প্রযুক্তি/i.test(q)) {
    return { categoryId: 'tech_news', name: 'Tech News', timeout: 3000 };
  }
  if (/health|doctor|hospital|medicine|স্বাস্থ্য|চিকিৎসা/i.test(q)) {
    return { categoryId: 'health', name: 'Health', timeout: 3000 };
  }
  return { categoryId: 'general', name: 'General', timeout: 3000 };
}

// Virtual crawler removed in favor of unified scrapeEngine
function generateSmartAIResponse(userMessage) {
  const msg = (userMessage || '').trim();
  if (!msg) {
    return { success: false, message: 'Empty input. Please enter a valid message.', agent_name: 'SupremeAI Neural Core', confidence: 0, source_type: 'error' };
  }

  if (/who are you|আপনি কে/i.test(msg)) {
    return {
      success: true,
      message: `আমি ${process.env.SUPREME_BRAND_NAME || 'SupremeAI'}। আমি আপনার ডিজিটাল অ্যাসিস্ট্যান্ট।`,
      agent_name: process.env.SUPREME_BRAND_NAME || 'SupremeAI',
      confidence: 0.99,
      source_type: 'LOCAL_SEED',
    };
  }
  if (/time|সময়|বাজে|time now/i.test(msg)) {
    const bdTime = new Date().toLocaleString('bn-BD', { timeZone: 'Asia/Dhaka' });
    return {
      success: true,
      message: `বর্তমান সময়: ${bdTime} (বাংলাদেশ সময়)`,
      agent_name: 'SupremeAI Neural Core',
      confidence: 1.0,
      source_type: 'LOCAL_SEED',
    };
  }
  if (/date|তারিখ|today/i.test(msg)) {
    const bdDate = new Date().toLocaleDateString('bn-BD', { timeZone: 'Asia/Dhaka', year: 'numeric', month: 'long', day: 'numeric' });
    return {
      success: true,
      message: `আজকের তারিখ: ${bdDate}`,
      agent_name: 'SupremeAI Neural Core',
      confidence: 1.0,
      source_type: 'LOCAL_SEED',
    };
  }

  const core = searchCoreKnowledge(userMessage);
  if (core) {
    return {
      success: true,
      message: core.solution,
      agent_name: 'SupremeAI Neural Core',
      confidence: core.score,
      source_type: 'CORE_KNOWLEDGE',
    };
  }

  return {
    success: true,
    message: 'আমি তথ্যটি বিশ্লেষণ করতে পারছি না।',
    agent_name: 'SupremeAI Neural Core',
    confidence: 0.1,
    source_type: 'DEFAULT_FALLBACK',
  };
}

app.post(['/api/chat/legacy', '/chat/legacy'], async (req, res) => {
  const userMessage = (req.body && req.body.message) || '';
  if (!userMessage || !userMessage.trim()) {
    return res.status(400).json({ success: false, message: 'Message is required', source_type: 'error' });
  }
  try {
    const resp = generateSmartAIResponse(userMessage);
    return res.json(resp);
  } catch (e) {
    console.error('[API] chat handler error', e && e.message);
    return res.status(500).json({ success: false, message: 'Internal server error. Please try again later.', source_type: 'error' });
  }
});

app.get(['/api/projects', '/projects', '/api/api/projects'], (req, res) => {
  res.json({ success: true, data: [] });
});

app.use(['/api/admin/*', '/admin/*'], (req, res) => {
  const requestPath = req.path;
  let data = null;

  if (requestPath.includes('users')) data = [];
  if (requestPath.includes('rules')) data = [];
  if (requestPath.includes('plans')) data = [];
  if (requestPath.includes('chat')) data = [];
  if (requestPath.includes('logs')) data = [];
  if (requestPath.includes('quotas')) data = { usage: 0, limit: 1000 };

  res.json({ success: true, data, note: 'Emulator stub - real implementation pending on coordinator server' });
});

app.use((req, res) => {
  res.status(404).json({ error: 'Not found in api-router coordinator', path: req.path });
});

module.exports = app;
