# SupremeAI IDE Trio Pipeline

**Antigravity IDE / Gemini (Code Writer) → Kilo Code (Code Reviewer) → Cline (Production Checker)**

এই সিস্টেম আপনার IDE-তে থাকা তিনটি AI টুলকে (Antigravity Gemini, Kilo Code, Cline) a single
assembly-line pipeline-এ সংযুক্ত করে — কোনো একটা কাজ শেষ হলে পরেরটা স্বয়ংক্রিয়ভাবে
শুরু হয়।

> 🗺️ **Verification:** `C:\Users\N\.antigravity-ide\` = Antigravity IDE (Google-এর Gemini-native fork)।
> এখানে Kilo Code `kilocode.kilo-code` (7.4.22) এবং Cline `saoudrizwan.claude-dev` (4.1.10) ইনস্টলড।
> Gemini ঠিক একটি IDE-এর কোরে বিল্ট-ইন — তাই Stage 1-এ `GEMINI_API_KEY` দিয়ে সরাসরি কল হয়।

---

## 🔀 কিভাবে কাজ করে

```
User Prompt
    │
    ▼
┌─────────────────────┐
│  Stage 1:  Gemini    │  ✍️ Writer — কোড তৈরি করে (via GEMINI_API_KEY)
│  (Code Writer)       │
└─────────┬───────────┘
          │  generated code
          ▼
┌─────────────────────┐
│  Stage 2:  Kilo      │  🔍 Reviewer — কোড রিভিউ করে (GuardianAgent + Kilo rules)
│  (Code Reviewer)     │
└─────────┬───────────┘
          │  review issues
          ▼
┌─────────────────────┐
│  Stage 3:  Cline     │  🚀 Checker — production-readiness চেক (lint/tests/security)
│  (Production Check)  │
└─────────┬───────────┘
          │
          ▼
   Final Result + Ready-for-production flag

---

## 📦 ফাইলসমূহ

| ফাইল | অবস্থান | উদ্দেশ্য |
|------|---------|----------|
| `trio_adapters.py` | `backend/agents/ide/` | GeminiWriter / KiloReviewer / ClineChecker adapters |
| `trio_pipeline.py` | `backend/core/orchestration/` | Pipeline orchestration logic |
| `ide_trio.py` | `backend/api/routes/` | REST endpoint `/api/v1/ide-trio/execute` |
| `mcp_ide_trio.py` | `backend/tools/mcp/` | MCP server (`trio_execute_pipeline` tool) |
| `IdeTrioPipeline.ts` | `tools/vscode-extension/src/services/` | VS Code client service |
| extension.ts | `tools/vscode-extension/src/` | `supremeai.trioPipeline` command |
| `config.json` | `.kilo/agent/` | MCP server registered for Kilo Code |

---

## 🚀 ব্যবহারের উপায় (৩টি পথ)

### 1. VS Code Extension Command
কমান্ড প্যালেটে (`Ctrl+Shift+P`) চাপুন এবং সিলেক্ট করুন:

```
SupremeAI: Run Trio Pipeline (Gemini→Kilo→Cline)
```

এরপর prompt দিলে পুরো pipeline চলে যাবে এবং কোড ফাইল ও রিপোর্ট দেখাবে।

### 2. REST API
```bash
curl -X POST http://localhost:8080/api/v1/ide-trio/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Build a FastAPI health-check endpoint with JWT auth",
    "language": "python",
    "filePath": "backend/api/routes/health.py"
  }'
```

### 3. MCP (Kilo Code / Cline / Continue)
`.kilo/agent/config.json`-এ `ide-trio` MCP সার্ভার রেজিস্টার করা আছে।
যেকোনো MCP ক্লায়েন্ট থেকে `trio_execute_pipeline` tool কল করতে পারবেন।

---

## 🔑 Required API Keys

| Key | Status | Used By |
|-----|--------|---------|
| `GEMINI_API_KEY` | ✅ `.env` এ আছে | Stage 1 Gemini Writer |
| Kilo Code extension | ✅ Installed | Stage 2 Reviewer (via backend GuardianAgent) |
| `CLINE_API_KEY` | ⚠️ Empty (optional) | Stage 3 (falls back to local checks) |

> **Fallback:** কোনো stage এর backend/API না থাকলে পুরো pipeline
> local-fallback mode-এ ঘুরে যায় — VS Code এ সাজেশন দেখায়।

---

## 🧪 Validation

```bash
python -m py_compile backend/agents/ide/trio_adapters.py
python -m py_compile backend/core/orchestration/trio_pipeline.py
python -m py_compile backend/tools/mcp/mcp_ide_trio.py
python -m py_compile backend/api/routes/ide_trio.py
```

---

## 🔮 Future Improvements

1. **Auto-retry loop:** Stage 2 এ issue পেলে Stage 1-এ ফেরত পাঠিয়ে স্বয়ংক্রিয়ভাবে ফিক্স
2. **IDE command trigger:** `vscode.commands.executeCommand('kilocode.something')` দিয়ে Kilo extension সরাসরি কল
3. **Cline streaming:** Cline-এর terminal feedback এর জন্য SSE streaming
4. **History/leaderboard:** প্রতিটি pipeline run লগ করে agent quality score বের করা
5. **Prompt template bank:** Bengali prompt templates রেডি