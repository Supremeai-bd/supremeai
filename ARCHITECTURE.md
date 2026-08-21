# SupremeAI — Architecture Reference

> **AI Agent:** এই ফাইলটি "New Feature" বা "Refactor" কাজের সময় পড়ুন।
> নতুন কোড লেখার আগে এখানকার stack, structure, এবং contracts চেক করুন।

---

## 1. Project Goal & Scope

**Mission:** SupremeAI একটি self-learning AI infrastructure যা নিজের "Eternal Brain" তৈরি করছে।
Third-party AIs (GPT-4, Gemini, Claude) শুধু temporary "muscle" — SupremeAI নিজেই একদিন সব করবে।

**Core Product:**
- **VS Code Extension** — SupremeAI-branded AI coding assistant (100% Thin Client)
- **Backend** — FastAPI service যা সব LLM orchestration গোপনে করে
- **Frontend (Studio)** — React/Vite dashboard

**Non-Scope (আর্কাইভ করা হয়েছে):**
- Mobile App, Desktop App, Java Workers, Cloudflare Workers — সব `_archive/` ফোল্ডারে

---

## 2. Folder / File Structure

```
supremeai/
├── backend/              # Python FastAPI (User + Admin API একসাথে)
│   ├── core/             # App config, DB setup, middleware
│   ├── api/              # Route handlers (user + admin, JWT role-guarded)
│   ├── services/         # Business logic layer
│   ├── models/           # SQLAlchemy / Pydantic models
│   └── tests/            # pytest test suite
│
├── frontend/             # React + Vite (Studio dashboard)
│   └── src/
│       ├── components/
│       ├── pages/
│       └── services/
│
├── tools/
│   └── vscode-extension/ # VS Code Extension (Thin Client)
│       └── src/
│           └── services/
│               └── SupremeAIService.ts  # 100% Thin Client (OpenRouter completely removed)

│
├── apps/                 # Monorepo apps (pnpm workspace)
├── packages/             # Shared packages
├── scripts/              # Automation scripts (Python)
│   ├── checkpoint_update.py   # Auto CHECKPOINT.md update
│   ├── context_snapshot.py    # Pre-task context generator
│   └── ai/
│       ├── memory_write.py    # Supabase vector memory write
│       └── memory_read.py     # Supabase vector memory read (semantic)
│
├── docs/                 # Technical documentation + SQL migrations
├── infrastructure/       # Docker, Terraform configs
│
├── AGENTS.md             # AI behavior rules (পড়া MANDATORY)
├── CHECKPOINT.md         # Last session state (পড়া MANDATORY)
├── ARCHITECTURE.md       # এই ফাইল — tech reference
├── DECISION_LOG.md       # Architecture decisions (ADR)
├── LESSONS_LEARNED.md    # Past mistakes + fixes
├── KNOWN_ISSUES.md       # Active bugs
├── DEPLOYMENT_CHECKLIST.md # Pre/post deploy checklist
├── ACTION_PLAN.md        # Current roadmap
└── render.yaml           # Render deployment blueprint
```

---

## 3. Tech Stack & Versions

### Backend (Python)
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Core language |
| FastAPI | latest | Web framework |
| SQLAlchemy | 2.0 | ORM |
| Pydantic | V2 | Data validation |
| Poetry | latest | Dependency management |
| Uvicorn | latest | ASGI server |
| pytest | latest | Testing |

### Frontend (TypeScript)
| Technology | Version | Purpose |
|---|---|---|
| TypeScript | ^5.4.5 | Language |
| React | ^19.2.0 | UI framework |
| Vite | 7.3.5 | Build tool |
| pnpm | 9.0.0 | Package manager |
| Turbo | ^2.0.0 | Monorepo task runner |

### Infrastructure
| Technology | Version | Purpose |
|---|---|---|
| Supabase (PostgreSQL) | latest | Primary database + auth |
| Supabase pgvector | latest | AI vector memory |
| Redis (Render) | latest | Caching / rate limiting |
| Firebase | ^12.15.0 | Static hosting (Studio + Admin) |
| Render | — | Backend + Frontend deployment |
| Infisical | — | Secrets vault |

### VS Code Extension
| Technology | Purpose |
|---|---|
| TypeScript | Extension language |
| VS Code API | Extension host |
| `SupremeAIService.ts` | Backend communication layer |

---

## 4. Database / API Contracts

### Supabase Tables (Key)
```sql
-- User auth
auth.users (managed by Supabase)

-- AI Eternal Brain memory
ai_memory (
  id UUID, session_id TEXT, agent_type TEXT,
  task_type TEXT, summary TEXT,
  embedding VECTOR(384), metadata JSONB, created_at TIMESTAMPTZ
)
```

### Backend API Endpoints (Key)
```
POST /api/chat/stream     — LLM streaming chat (SSE)
POST /api/auth/login      — User login
GET  /api/health          — Health check
POST /admin/...           — Admin routes (JWT role: admin required)
```

### Extension → Backend Contract
- Extension শুধু `SupremeAIService.ts` → `/api/chat/stream` কল করে
- কোনো third-party AI key এক্সটেনশনে expose হবে না
- Auth: SupremeAI API Key (Bearer token)

---

## 5. Testing Requirements

```bash
# Backend tests
cd backend && poetry run pytest

# Frontend tests
pnpm run test

# E2E tests
pnpm run test:e2e  # Playwright

# Affected tests only (CI-friendly)
pnpm run test:affected
```

**Rules:**
- নতুন feature → minimum 1 unit test
- Bug fix → regression test যোগ করতে হবে
- API endpoint → integration test যোগ করতে হবে
- Production deploy এর আগে `pnpm run test:affected` পাস করতে হবে

---

## 6. Security Rules

1. **No Secrets in Code:** সব secrets `.env` + Infisical vault-এ
2. **Brand Exclusivity:** Extension-এ GPT/OpenAI/Groq/OpenRouter নাম বা API key কখনো expose নয়
3. **JWT Role Guards:** Admin routes-এ `role: admin` JWT claim mandatory
4. **CORS:** Backend-এ শুধু whitelist domains (`USER_CORS_ORIGINS`)
5. **Input Validation:** সব user input Pydantic V2 দিয়ে validate
6. **TypeScript Strict:** `strict: true` — কোনো `any` type নয়
7. **Gitleaks:** `.gitleaks.toml` — pre-commit hook এ secrets scan চলে

---

## 7. Git / Branch / PR / Commit Workflow

```
main          ← production (direct push নিষিদ্ধ)
├── develop   ← staging / integration branch
│   ├── feature/[ticket]-description
│   ├── fix/[ticket]-description
│   └── chore/[ticket]-description
```

**Commit Format (Conventional Commits):**
```
feat: add memory write script for Phase C
fix: remove OpenRouter fallback from SupremeAIService
chore: update CHECKPOINT.md after session
docs: update ARCHITECTURE.md tech stack
```

**PR Rules:**
- Main-এ merge করতে হলে PR দরকার
- CI পাস করতে হবে (lint + test + typecheck)
- Squash merge preferred

---

## 8. Deployment Rules

**Render (Auto-deploy from `main`):**
```yaml
# render.yaml controls everything:
# - supremeai-backend (Web Service, Python/FastAPI)
# - supremeai-frontend (Static Site, Vite)
```

**Firebase (Manual deploy):**
```bash
pnpm run deploy:studio   # Studio frontend
pnpm run deploy:admin    # Admin frontend
```

**Pre-deploy checklist:** দেখুন `DEPLOYMENT_CHECKLIST.md`

**Deploy করার আগে mandatory:**
1. `pnpm run test:affected` পাস
2. `pnpm run lint` পাস
3. `DEPLOYMENT_CHECKLIST.md` চেক

---

## 9. Environment / Secrets Management

**Policy:**
- সব keys `.env` ফাইলে locally (git-ignored)
- Production secrets → Render Dashboard (sync: false for critical keys)
- Master vault → Infisical (`scripts/upload_to_infisical.py`)
- Firebase auth → `FIREBASE_SERVICE_ACCOUNT_JSON` (Render env var)

**Key Variables:**
```bash
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_DATABASE_URL=
REDIS_URL=
FIREBASE_SERVICE_ACCOUNT_JSON=
# LLM keys (backend only — never in extension)
OPENAI_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
```

**Sync secrets:**
```bash
python scripts/upload_to_infisical.py    # Local → Infisical
python scripts/push_all_render_envs.py  # Infisical → Render
```

---

## 10. Context Mesh (AI Memory System)

```bash
# কাজ শুরুর আগে (context snapshot)
python scripts/context_snapshot.py --task "your task description"

# কাজ শুরুর আগে (past memory query)
python scripts/ai/memory_read.py --task "your task description"

# কাজ শেষে (checkpoint update)
python scripts/checkpoint_update.py -m "what was accomplished"

# কাজ শেষে (memory save)
python scripts/ai/memory_write.py --from-checkpoint
```

---
*Last updated: 2026-08-16 | Next review: when major architecture changes happen*
