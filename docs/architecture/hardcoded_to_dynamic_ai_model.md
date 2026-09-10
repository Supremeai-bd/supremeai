# Dynamic AI Model Configuration — Hardcode Elimination Plan

## সমস্যার সারসংক্ষেপ

Codebase-এ অনেক জায়গায় AI model নাম hardcode করা আছে যেমন `gpt-4o-mini`, `gemini-2.0-flash`, `llama-3.3-70b-versatile` ইত্যাদি। যদি কোনো provider তাদের policy change করে বা model deprecated হয়, তাহলে code update না করলে system ভেঙে পড়বে।

**লক্ষ্য:** সব hardcoded model name কে Infisical Vault / Environment Variable দিয়ে override করার সুবিধা দেওয়া, যাতে code deploy না করে যেকোনো সময় মডেল পরিবর্তন করা যায়।

## কোথায় কোথায় Hardcode আছে — Audit Summary

### 🔴 Critical (Production traffic directly affected)

| File | Lines | Hardcoded Model | Risk |
|------|-------|-----------------|------|
| [`backend/engine/cost_optimizer.py`](file:///f:/supremeai/backend/engine/cost_optimizer.py) | L26-38 | `gemini/gemini-2.0-flash`, `groq/llama-3.3-70b-versatile`, `openrouter/meta-llama/llama-3.3-70b-instruct` | ROUTE_LADDER এখানে সরাসরি model ঠিক করে দেয় |
| [`backend/engine/smart_router.py`](file:///f:/supremeai/backend/engine/smart_router.py) | L20-28 | `groq/llama-3.3-70b-versatile`, `gemini/gemini-2.0-flash` | Fallback string hardcode |
| [`backend/core/llm/advanced_model_router.py`](file:///f:/supremeai/backend/core/llm/advanced_model_router.py) | L374-416 | `groq/llama-3.3-70b-versatile`, `gpt-4o-mini`, `gemini/gemini-2.5-flash` | `_load_model_preferences()` এ per-task model list |
| [`backend/services/llm/providers.py`](file:///f:/supremeai/backend/services/llm/providers.py) | L596 | `llama-3.3-70b-versatile` | `GroqProvider.__init__()` তে hardcode |
| [`backend/core/language_router.py`](file:///f:/supremeai/backend/core/language_router.py) | L21-38 | `openai/gpt-4o`, `01-ai/yi-34b-chat` | Language→model mapping |
| [`backend/memory/supabase_store.py`](file:///f:/supremeai/backend/memory/supabase_store.py) | L231 | `text-embedding-3-small` | Embedding fallback hardcode |
| [`backend/core/embeddings.py`](file:///f:/supremeai/backend/core/embeddings.py) | L20 | `text-embedding-3-small` | Remote embedding model |
| [`infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts`](file:///f:/supremeai/infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts) | L27,56,59,62 | `gemini-1.5-flash`, `llama-3.3-70b-versatile`, `claude-3.5-sonnet`, `gpt-4o-mini` | MCP tower provider models |

### 🟠 High (Service-level impact)

| File | Lines | Hardcoded Model |
|------|-------|-----------------|
| [`frontend/src/lib/llm.router.ts`](file:///f:/supremeai/frontend/src/lib/llm.router.ts) | L52,63,74,84 | `gemini-2.0-flash`, `llama-3.1-8b-instant`, `gpt-4o-mini`, `claude-3-haiku-20240307` |
| [`frontend/src/components/Onboarding/StepModelSelect.tsx`](file:///f:/supremeai/frontend/src/components/Onboarding/StepModelSelect.tsx) | L10 | `gpt-4o`, `llama-3-70b-versatile`, `claude-3-5-sonnet` |
| [`frontend/src/components/Onboarding/OnboardingWizard.tsx`](file:///f:/supremeai/frontend/src/components/Onboarding/OnboardingWizard.tsx) | L10 | `gpt-4o` |
| [`frontend/src/components/dashboard/SettingsPage.tsx`](file:///f:/supremeai/frontend/src/components/dashboard/SettingsPage.tsx) | L19 | `gpt-4o` |
| [`backend/tools/social/telegram_bot.py`](file:///f:/supremeai/backend/tools/social/telegram_bot.py) | L1331 | `gemini-2.5-flash` (direct URL) |
| [`backend/core/unified_router.py`](file:///f:/supremeai/backend/core/unified_router.py) | L216-219, 337, 348, 369 | `gpt-4`, `claude-3.5-sonnet`, `llama-3.1-405b` |
| [`backend/core/competitive_kit.py`](file:///f:/supremeai/backend/core/competitive_kit.py) | L1207,1217,1343,1348 | `gpt-4o-mini`, `claude-3-haiku` |

### 🟡 Medium (Internal tools, less user-facing)

| File | Hardcoded Model |
|------|-----------------|
| [`backend/tools/langchain_agent_example.py`](file:///f:/supremeai/backend/tools/langchain_agent_example.py) | `claude-3-5-sonnet-20241022`, `gemini-2.5-flash` |
| [`backend/core/tier8/agent_evolution_engine.py`](file:///f:/supremeai/backend/core/tier8/agent_evolution_engine.py) | `gpt-4o-mini` (partially os.getenv wrapped) |
| [`backend/core/tier8/skill_marketplace_curator.py`](file:///f:/supremeai/backend/core/tier8/skill_marketplace_curator.py) | `gpt-4o-mini` (partially os.getenv wrapped) |
| [`backend/core/config_cache.py`](file:///f:/supremeai/backend/core/config_cache.py) | `gpt-4`, `gpt-4o-mini`, `gpt-3.5-turbo` |
| [`tools/multi_model_knowledge_distiller.py`](file:///f:/supremeai/tools/multi_model_knowledge_distiller.py) | `llama-3.3-70b-versatile`, `llama-3.1-8b-instruct` |

---

## Proposed Solution Architecture

### Strategy: Single Source of Truth — `config_fields.py` + Infisical Vault

আমরা একটাই কেন্দ্রীয় pattern ব্যবহার করব:

```
Infisical Vault → env variable → config_fields.py Settings → কোড পড়বে settings থেকে
```

#### ধাপ ১: `config_fields.py` — নতুন Model Config Fields যোগ (Central Hub)

সব task-type ও provider-এর জন্য `settings.XYZ_MODEL` field তৈরি করব:

```python
# Task-based model defaults (Vault/env থেকে override করা যাবে)
model_chat: str = Field(default="gemini/gemini-2.0-flash", validation_alias="MODEL_CHAT")
model_coding: str = Field(default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_CODING")
model_reasoning: str = Field(default="groq/deepseek-r1-distill-llama-70b", validation_alias="MODEL_REASONING")
model_creative: str = Field(default="gemini/gemini-2.5-flash", validation_alias="MODEL_CREATIVE")
model_general: str = Field(default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_GENERAL")
model_bengali: str = Field(default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_BENGALI")
model_embedding: str = Field(default="text-embedding-3-small", validation_alias="MODEL_EMBEDDING")

# Provider-level model defaults
model_groq_default: str = Field(default="llama-3.3-70b-versatile", validation_alias="MODEL_GROQ_DEFAULT")
model_gemini_default: str = Field(default="gemini-2.0-flash", validation_alias="MODEL_GEMINI_DEFAULT")
model_openai_default: str = Field(default="gpt-4o-mini", validation_alias="MODEL_OPENAI_DEFAULT")
model_anthropic_default: str = Field(default="claude-3-haiku-20240307", validation_alias="MODEL_ANTHROPIC_DEFAULT")
model_openrouter_default: str = Field(default="anthropic/claude-3.5-sonnet", validation_alias="MODEL_OPENROUTER_DEFAULT")

# Cost optimizer route ladder (JSON string from env)
route_ladder_simple: str = Field(default="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile", validation_alias="ROUTE_LADDER_SIMPLE")
route_ladder_medium: str = Field(default="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile", validation_alias="ROUTE_LADDER_MEDIUM")
route_ladder_complex: str = Field(default="groq/llama-3.3-70b-versatile,gemini/gemini-2.0-flash", validation_alias="ROUTE_LADDER_COMPLEX")

# MCP Tower analyze.ts models (env-driven)
mcp_gemini_model: str = Field(default="gemini-1.5-flash", validation_alias="MCP_GEMINI_MODEL")
mcp_groq_model: str = Field(default="llama-3.3-70b-versatile", validation_alias="MCP_GROQ_MODEL")
mcp_openrouter_model: str = Field(default="anthropic/claude-3.5-sonnet", validation_alias="MCP_OPENROUTER_MODEL")
mcp_github_model: str = Field(default="gpt-4o-mini", validation_alias="MCP_GITHUB_MODEL")
```

---

### Proposed Changes — File by File

---

## Backend Changes

### [`backend/core/config_fields.py`](file:///f:/supremeai/backend/core/config_fields.py)
#### [MODIFY] নতুন Model Config block যোগ করা

`claude_openrouter_model` field-এর পরে নতুন section যোগ করব:
```python
# ── Dynamic AI Model Config — All overridable via Vault/env ──────────────
# বাংলা: এই fields Infisical Vault থেকে override করা যাবে, code deploy ছাড়াই।
model_chat: str = Field(default="gemini/gemini-2.0-flash", validation_alias="MODEL_CHAT")
model_coding: str = Field(default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_CODING")
model_reasoning: str = Field(default="groq/deepseek-r1-distill-llama-70b", validation_alias="MODEL_REASONING")
model_creative: str = Field(default="gemini/gemini-2.5-flash", validation_alias="MODEL_CREATIVE")
model_general: str = Field(default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_GENERAL")
model_bengali: str = Field(default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_BENGALI")
model_embedding: str = Field(default="text-embedding-3-small", validation_alias="MODEL_EMBEDDING")
model_local_embedding: str = Field(default="all-MiniLM-L6-v2", validation_alias="MODEL_LOCAL_EMBEDDING")
model_groq_default: str = Field(default="llama-3.3-70b-versatile", validation_alias="MODEL_GROQ_DEFAULT")
model_gemini_default: str = Field(default="gemini-2.0-flash", validation_alias="MODEL_GEMINI_DEFAULT")
model_openai_default: str = Field(default="gpt-4o-mini", validation_alias="MODEL_OPENAI_DEFAULT")
model_anthropic_default: str = Field(default="claude-3-haiku-20240307", validation_alias="MODEL_ANTHROPIC_DEFAULT")
model_openrouter_default: str = Field(default="anthropic/claude-3.5-sonnet", validation_alias="MODEL_OPENROUTER_DEFAULT")
route_ladder_simple: str = Field(default="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct", validation_alias="ROUTE_LADDER_SIMPLE")
route_ladder_medium: str = Field(default="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct", validation_alias="ROUTE_LADDER_MEDIUM")
route_ladder_complex: str = Field(default="groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct,gemini/gemini-2.0-flash", validation_alias="ROUTE_LADDER_COMPLEX")
```

---

### [`backend/engine/cost_optimizer.py`](file:///f:/supremeai/backend/engine/cost_optimizer.py)
#### [MODIFY] ROUTE_LADDER কে dynamic করা

```python
# BEFORE:
ROUTE_LADDER = {
    "simple": ["gemini/gemini-2.0-flash", "groq/llama-3.3-70b-versatile", ...],
    ...
}

# AFTER:
@staticmethod
def _build_route_ladder() -> dict[str, list[str]]:
    from core.config import settings
    return {
        "simple": [m.strip() for m in settings.route_ladder_simple.split(",") if m.strip()],
        "medium": [m.strip() for m in settings.route_ladder_medium.split(",") if m.strip()],
        "complex": [m.strip() for m in settings.route_ladder_complex.split(",") if m.strip()],
    }

def get_optimal_route(self, ...):
    ladder = self._build_route_ladder()
    candidates = ladder.get(complexity, ladder["simple"])
    ...
```

---

### [`backend/engine/smart_router.py`](file:///f:/supremeai/backend/engine/smart_router.py)
#### [MODIFY] MODEL_MAP fallback strings dynamic করা

```python
# AFTER: fallback strings settings থেকে নেবে
MODEL_MAP = {
    "code": TASK_MODEL_MAP.get("coding") or settings.model_coding,
    "reasoning": TASK_MODEL_MAP.get("reasoning") or settings.model_reasoning,
    "bengali": TASK_MODEL_MAP.get("chat") or settings.model_bengali,
    "math": TASK_MODEL_MAP.get("reasoning") or settings.model_reasoning,
    "general": TASK_MODEL_MAP.get("general") or settings.model_general,
}
```

---

### [`backend/core/llm/advanced_model_router.py`](file:///f:/supremeai/backend/core/llm/advanced_model_router.py)
#### [MODIFY] `_load_model_preferences()` dynamic করা

```python
def _load_model_preferences(self) -> dict[str, dict]:
    from core.config import settings
    return {
        "bengali": {
            "preferred_models": [
                settings.model_bengali,
                settings.model_chat,
                settings.model_general,
            ],
            ...
        },
        "coding": {
            "preferred_models": [
                settings.model_coding,
                f"openrouter/deepseek/deepseek-coder",  # এটা provider-specific, আলাদা env হবে
                settings.model_openai_default,
            ],
            ...
        },
        ...
    }
```

---

### [`backend/services/llm/providers.py`](file:///f:/supremeai/backend/services/llm/providers.py)
#### [MODIFY] `GroqProvider.__init__()` model hardcode সরানো

```python
# BEFORE:
self.model = "llama-3.3-70b-versatile"

# AFTER:
from core.config import settings
self.model = settings.model_groq_default
```

---

### [`backend/core/language_router.py`](file:///f:/supremeai/backend/core/language_router.py)
#### [MODIFY] LANGUAGE_MODEL_MAP কে settings-driven করা

```python
# AFTER: settings থেকে build করবে
@classmethod
def _build_language_model_map(cls) -> dict:
    from core.config import settings
    return {
        "ar": os.getenv("MODEL_ARABIC", "openai/gpt-4o"),
        "bn": os.getenv("MODEL_BENGALI_LANG", settings.model_bengali),
        "zh": os.getenv("MODEL_CHINESE", "01-ai/yi-34b-chat"),
        ...
    }
```

---

### [`backend/memory/supabase_store.py`](file:///f:/supremeai/backend/memory/supabase_store.py)
#### [MODIFY] Embedding model hardcode সরানো

```python
# BEFORE:
response = litellm.embedding(model="text-embedding-3-small", input=text)

# AFTER:
from core.config import settings
response = litellm.embedding(model=settings.model_embedding, input=text)
```

---

### [`backend/core/embeddings.py`](file:///f:/supremeai/backend/core/embeddings.py)
#### [MODIFY] Remote model ও local model dynamic করা

```python
# BEFORE:
_LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"
_REMOTE_MODEL = "text-embedding-3-small"

# AFTER: settings থেকে নেবে (lazy load)
def _get_local_model_name() -> str:
    from core.config import settings
    return settings.model_local_embedding

def _get_remote_model() -> str:
    from core.config import settings
    return settings.model_embedding
```

---

### [`backend/tools/social/telegram_bot.py`](file:///f:/supremeai/backend/tools/social/telegram_bot.py)
#### [MODIFY] Direct Gemini URL hardcode সরানো

```python
# BEFORE:
gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gem_key}"

# AFTER:
from core.config import settings
gem_model = settings.model_gemini_default  # env: MODEL_GEMINI_DEFAULT=gemini-2.5-flash
gem_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gem_model}:generateContent?key={gem_key}"
```

---

## Infrastructure Changes (TypeScript)

### [`infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts`](file:///f:/supremeai/infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts)
#### [MODIFY] Model names env থেকে নেওয়া

```typescript
// BEFORE:
model: "gemini-1.5-flash"
openaiCompatProvider("groq", ..., "llama-3.3-70b-versatile", 20)

// AFTER: env.ts তে নতুন fields যোগ করে সেখান থেকে নেবে
function geminiProvider(): ProviderSpec {
  return {
    model: process.env.MCP_GEMINI_MODEL ?? "gemini-1.5-flash",
    ...
  };
}
function buildProviders(): ProviderSpec[] {
  providers.push(openaiCompatProvider("groq", ..., 
    process.env.MCP_GROQ_MODEL ?? "llama-3.3-70b-versatile", 20));
  providers.push(openaiCompatProvider("openrouter", ..., 
    process.env.MCP_OPENROUTER_MODEL ?? "anthropic/claude-3.5-sonnet", 30));
  providers.push(openaiCompatProvider("github", ..., 
    process.env.MCP_GITHUB_MODEL ?? "gpt-4o-mini", 40));
}
```

---

## Frontend Changes

### [`frontend/src/lib/llm.router.ts`](file:///f:/supremeai/frontend/src/lib/llm.router.ts)
#### [MODIFY] PROVIDERS config API থেকে নেওয়া

Frontend সরাসরি env access করতে পারে না (security)। তাই `/api/v1/ai/config` endpoint দিয়ে backend থেকে active model config নামাবে:

```typescript
// নতুন pattern: server-fetched config
const PROVIDER_CONFIG_URL = '/api/v1/ai/provider-config';

let cachedProviderConfig: Record<string, {model: string}> | null = null;

async function getProviderConfig() {
  if (!cachedProviderConfig) {
    const res = await fetch(PROVIDER_CONFIG_URL);
    cachedProviderConfig = await res.json();
  }
  return cachedProviderConfig;
}
```

#### [NEW] Backend Endpoint: `/api/v1/ai/provider-config`
Frontend-এর জন্য একটি public (auth-optional) endpoint যা active model config return করবে (provider name + model name, কিন্তু API key কখনো না):
```json
{
  "gemini": {"model": "gemini-2.0-flash"},
  "groq": {"model": "llama-3.3-70b-versatile"},
  "openai": {"model": "gpt-4o-mini"},
  "anthropic": {"model": "claude-3-haiku-20240307"}
}
```

### [`frontend/src/components/Onboarding/StepModelSelect.tsx`](file:///f:/supremeai/frontend/src/components/Onboarding/StepModelSelect.tsx)
#### [MODIFY] Model list API থেকে নেওয়া (existing `/api/v1/ai/providers` endpoint ব্যবহার করে)

---

## Infisical Vault Keys (নতুন keys যোগ করতে হবে)

```
MODEL_CHAT=gemini/gemini-2.0-flash
MODEL_CODING=groq/llama-3.3-70b-versatile
MODEL_REASONING=groq/deepseek-r1-distill-llama-70b
MODEL_CREATIVE=gemini/gemini-2.5-flash
MODEL_GENERAL=groq/llama-3.3-70b-versatile
MODEL_BENGALI=groq/llama-3.3-70b-versatile
MODEL_EMBEDDING=text-embedding-3-small
MODEL_LOCAL_EMBEDDING=all-MiniLM-L6-v2
MODEL_GROQ_DEFAULT=llama-3.3-70b-versatile
MODEL_GEMINI_DEFAULT=gemini-2.0-flash
MODEL_OPENAI_DEFAULT=gpt-4o-mini
MODEL_ANTHROPIC_DEFAULT=claude-3-haiku-20240307
MODEL_OPENROUTER_DEFAULT=anthropic/claude-3.5-sonnet
ROUTE_LADDER_SIMPLE=gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct
ROUTE_LADDER_MEDIUM=gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct
ROUTE_LADDER_COMPLEX=groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct,gemini/gemini-2.0-flash
MCP_GEMINI_MODEL=gemini-1.5-flash
MCP_GROQ_MODEL=llama-3.3-70b-versatile
MCP_OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
MCP_GITHUB_MODEL=gpt-4o-mini
```

---

## Implementation Priority & Execution Order

### Phase 1 — Backend Core (সবচেয়ে critical, আগে করব)
1. `config_fields.py` — নতুন fields যোগ
2. `backend/engine/cost_optimizer.py` — ROUTE_LADDER dynamic
3. `backend/engine/smart_router.py` — fallback dynamic
4. `backend/core/llm/advanced_model_router.py` — `_load_model_preferences()` dynamic
5. `backend/services/llm/providers.py` — GroqProvider model dynamic
6. `backend/core/embeddings.py` — embedding models dynamic
7. `backend/memory/supabase_store.py` — embedding fallback dynamic

### Phase 2 — Supporting Services
8. `backend/core/language_router.py` — language model map dynamic
9. `backend/tools/social/telegram_bot.py` — gemini URL dynamic
10. `backend/core/unified_router.py` — model name references
11. New backend API endpoint `/api/v1/ai/provider-config`

### Phase 3 — Infrastructure & Frontend
12. `infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts` — env-driven models
13. `frontend/src/lib/llm.router.ts` — API-fetched config
14. `frontend/src/components/Onboarding/StepModelSelect.tsx` — dynamic model list

### Phase 4 — Vault & Documentation
15. Infisical Vault-এ নতুন keys যোগ
16. `.env.example` update
17. `docs/` তে Dynamic Model Configuration guide লেখা

---

## Verification Plan

### Automated Tests
- `pytest backend/tests/engine/test_cost_optimizer.py` — ROUTE_LADDER override test
- `pytest backend/tests/core/test_core_config.py` — নতুন model fields test
- `pytest backend/tests/services/` — provider model override test

### Manual Verification
```bash
# env override করে test:
MODEL_GROQ_DEFAULT=llama-3.1-70b-versatile \
MODEL_GEMINI_DEFAULT=gemini-1.5-flash \
uvicorn backend.main:app --reload

# তারপর curl করে check:
curl http://localhost:8080/api/v1/ai/provider-config
```

> [!IMPORTANT]
> Phase 1 এবং 2 এর changes backward compatible — default values আগেরটাই থাকবে। কোনো existing behavior break হবে না।

> [!NOTE]
> `backend/utils/branding.py` এবং `frontend/src/lib/modelBranding.ts` — এই দুটোতে model→display-name mapping আছে। এগুলো hardcode রাখা **ঠিক আছে** কারণ এগুলো UI branding এর জন্য, runtime routing এর জন্য নয়। নতুন model এলে শুধু এই দুই ফাইলে একটা entry যোগ করলেই হবে।

> [!NOTE]
> Test files (`backend/tests/`) এর hardcoded model names ইচ্ছাকৃত — tests specific model behavior test করে। এগুলো change করার দরকার নেই।
