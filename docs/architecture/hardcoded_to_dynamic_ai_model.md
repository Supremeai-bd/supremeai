# Dynamic AI Model Configuration — Hardcode Elimination Plan & Implementation Status

**Document Version:** 2.0.0  
**Last Updated:** 2026-09-11  
**Status:** In Progress (Phase 1 Partially Complete — Audit & Alignment)  
**Single Source of Truth:** `STATUS.md` & `backend/core/config_fields.py`

---

## সমস্যার সারসংক্ষেপ

Codebase-এ বিভিন্ন AI model নাম hardcode অবস্থায় ছিল (যেমন `gpt-4o-mini`, `gemini-2.0-flash`, `llama-3.3-70b-versatile` ইত্যাদি)। যদি কোনো provider তাদের policy পরিবর্তন করে বা model deprecate করে, তাহলে সরাসরি code deploy না করে যাতে Infisical Vault / Environment Variable দিয়ে runtime-এ model পরিবর্তন ও override করা যায়, তার জন্যই এই আর্কিটেকচারাল রিফ্যাক্টরিং।

**মূল লক্ষ্য:** সমস্ত hardcoded model name-কে Pydantic Settings (`config_fields.py`) ও Infisical Vault / Environment Variable-চালিত করা এবং frontend-এ runtime public/branding config এর মাধ্যমে মডেল ডাইনামিকালি প্রোভাইড করা।

---

## কোডবেস অডিট ও রিয়েল স্ট্যাটাস (Current Codebase Audit vs Plan)

বর্তমান কোডবেস পুঙ্খানুপুঙ্খভাবে যাচাই করে দেখা গেছে যে আর্কিটেকচারের বেশ কিছু কোর কম্পোনেন্ট ইতোমধ্যে `settings`-চালিত করা হয়েছে, এবং কিছু ফাইলে এখনও হার্ডকোড বা আংশিক ডাইনামিক স্ট্যাটাসে রয়েছে:

### 📊 বাস্তবায়ন ট্র্যাকার (Implementation Matrix)

| ফাইল / কম্পোনেন্ট | প্ল্যানের প্রস্তাবনা | বর্তমান কোডের বাস্তব অবস্থা (Current Reality) | বর্তমান স্ট্যাটাস |
|---|---|---|---|
| [`backend/core/config_fields.py`](file:///f:/supremeai/backend/core/config_fields.py) | `model_coding`, `model_reasoning`, `model_vision`, `model_chat`, `model_general`, `model_multilingual`, `embedding_model`, `route_ladder_*` যোগ করা | ইতোমধ্যে সম্পন্ন (`model_coding`, `model_reasoning`, `model_vision`, `model_chat`, `model_general`, `model_multilingual`, `embedding_model`, `route_ladder_simple`, `route_ladder_medium`, `route_ladder_complex` এবং `task_models`, `route_ladders` properties বিদ্যমান)। | ✅ **COMPLETED** |
| [`backend/engine/cost_optimizer.py`](file:///f:/supremeai/backend/engine/cost_optimizer.py) | `ROUTE_LADDER` ডাইনামিক করা | সম্পন্ন (`settings.route_ladders` ব্যবহার করছে, কোনো হার্ডকোডেড ডিকশনারি নেই)। ইউনিট টেস্ট ১০০% পাস। | ✅ **COMPLETED** |
| [`backend/engine/smart_router.py`](file:///f:/supremeai/backend/engine/smart_router.py) | `model_map` কে `settings` থেকে নেওয়া | সম্পন্ন (`settings.task_models` থেকে ডাইনামিকালি `coding`, `reasoning`, `chat`, `general` ম্যাপ করছে)। | ✅ **COMPLETED** |
| [`backend/memory/supabase_store.py`](file:///f:/supremeai/backend/memory/supabase_store.py) | Embedding model ডাইনামিক করা | সম্পন্ন (`settings.embedding_model` ব্যবহার করছে)। | ✅ **COMPLETED** |
| [`backend/core/embeddings.py`](file:///f:/supremeai/backend/core/embeddings.py) | Remote embedding model ডাইনামিক করা | সম্পন্ন (`_REMOTE_MODEL = settings.embedding_model`)। | ✅ **COMPLETED** |
| [`backend/services/llm/providers.py`](file:///f:/supremeai/backend/services/llm/providers.py) | `GroqProvider` default model ডাইনামিক করা | সম্পন্ন (`getattr(settings, "model_general", "llama-3.3-70b-versatile")` ব্যবহার করছে)। | ✅ **COMPLETED** |
| [`backend/core/tier8/*.py`](file:///f:/supremeai/backend/core/tier8) | Tier 8 এজেন্ট মডেল ডাইনামিক করা | সম্পন্ন (`SWARM_MODEL`, `SELF_IMPROVE_MODEL`, `EVO_MODEL` এবং `settings.model_general`/`model_coding` ফলব্যাক যুক্ত)। | ✅ **COMPLETED** |
| [`backend/core/config_classification.py`](file:///f:/supremeai/backend/core/config_classification.py) | কনফিগ ক্লাসিফিকেশন ও অডিট স্পেক যুক্ত করা | সম্পন্ন (`MODEL_CODING`, `MODEL_REASONING`, `MODEL_VISION`, `MODEL_CHAT`, `MODEL_GENERAL`, `MODEL_MULTILINGUAL`, `EMBEDDING_MODEL`, `ROUTE_LADDER_*` অন্তর্ভুক্ত)। | ✅ **COMPLETED** |
| [`backend/api/routes/public_config.py`](file:///f:/supremeai/backend/api/routes/public_config.py) | Frontend ও Client-এর জন্য public model config endpoint | সম্পন্ন (`/config/public` এ `chat`, `general`, `multilingual` মডেল এবং `/config/public/branding` এ মডেল ও প্রোভাইডার ডিসপ্লে ম্যাপ এক্সপোজড)। | ✅ **COMPLETED** |
| [`backend/core/llm/advanced_model_router.py`](file:///f:/supremeai/backend/core/llm/advanced_model_router.py) | `_load_model_preferences()` ডাইনামিক করা | আংশিক (`settings.model_chat` ব্যবহার হচ্ছে, তবে কিছু মডেল লিস্টে `"groq/llama-3.3-70b-versatile"`, `"gemini/gemini-2.5-flash"` এখনও স্ট্যাটিক)। | 🟡 **IN PROGRESS** |
| [`backend/core/language_router.py`](file:///f:/supremeai/backend/core/language_router.py) | `LANGUAGE_MODEL_MAP` ডাইনামিক করা | এখনও স্ট্যাটিক (`"zh": "01-ai/yi-34b-chat"`, `"ar": "openai/gpt-4o"` ইত্যাদি)। | ⏳ **PENDING** |
| [`backend/tools/social/telegram_bot.py`](file:///f:/supremeai/backend/tools/social/telegram_bot.py) | Gemini URL এ ডাইনামিক মডেল ব্যবহার | এখনও হার্ডকোড (`gemini-2.5-flash:generateContent`)। `settings.model_chat` বা `settings.model_vision` দিয়ে ডাইনামিক করতে হবে। | ⏳ **PENDING** |
| [`infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts`](file:///f:/supremeai/infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts) | MCP Tower models env-driven করা | এখনও স্ট্যাটিক (`gemini-1.5-flash`, `llama-3.3-70b-versatile` ইত্যাদি)। `process.env` ওভাররাইড যুক্ত করতে হবে। | ⏳ **PENDING** |
| [`frontend/src/lib/llm.router.ts`](file:///f:/supremeai/frontend/src/lib/llm.router.ts) | Frontend LLM Router কে server config ভিত্তিক করা | এখনও স্ট্যাটিক ডিকশনারি `PROVIDERS` রয়েছে। `/config/public` থেকে মডেল ওভাররাইড নেওয়া প্রয়োজন। | ⏳ **PENDING** |
| [`frontend/src/components/Onboarding/StepModelSelect.tsx`](file:///f:/supremeai/frontend/src/components/Onboarding/StepModelSelect.tsx) | অনবোর্ডিং মডেল সিলেক্টর ডাইনামিক করা | `modelBranding.ts`-এর `SUPREME_AVAILABLE_MODELS` ও `/config/public/branding` থেকে ডাইনামিকালি প্রোভাইড করা যায়। | ⏳ **PENDING** |

---

## আর্কিটেকচারাল ডিজাইন প্যাটার্ন (Single Source of Truth Pattern)

```
                     ┌────────────────────────┐
                     │     Infisical Vault    │
                     │  (Encrypted Cloud Env) │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │   Environment Vars     │
                     │  (e.g. MODEL_CODING)   │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │  config_fields.py      │
                     │  Settings (Pydantic)   │
                     └─────┬────────────┬─────┘
                           │            │
            ┌──────────────┘            └──────────────┐
            ▼                                          ▼
┌────────────────────────┐                ┌────────────────────────┐
│    Backend Engines     │                │   /config/public API   │
│ - cost_optimizer.py    │                │   (Zero Leak, Branded) │
│ - smart_router.py      │                └────────────┬───────────┘
│ - llm_gateway.py       │                             │
│ - supabase_store.py    │                             ▼
└────────────────────────┘                ┌────────────────────────┐
                                          │   Frontend & Clients   │
                                          │ - modelBranding.ts     │
                                          │ - SettingsPage.tsx     │
                                          │ - Thin Clients (Tauri) │
                                          └────────────────────────┘
```

---

## কেন্দ্রীয় কনফিগ ফিল্ডসমূহ (`config_fields.py` তে যা সক্রিয় আছে)

```python
# Task-based model defaults (Vault/env থেকে override করা যায়)
model_coding: str = Field(
    default="groq/llama-3.3-70b-versatile", validation_alias="MODEL_CODING"
)
model_reasoning: str = Field(
    default="openrouter/meta-llama/llama-3.3-70b-instruct", validation_alias="MODEL_REASONING"
)
model_vision: str = Field(
    default="gemini/gemini-2.0-flash", validation_alias="MODEL_VISION"
)
model_chat: str = Field(
    default="gemini/gemini-2.0-flash", validation_alias="MODEL_CHAT"
)
model_general: str = Field(
    default="gemini/gemini-2.0-flash", validation_alias="MODEL_GENERAL"
)
embedding_model: str = Field(
    default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL"
)
model_multilingual: str = Field(
    default="openrouter/meta-llama/llama-3.3-70b-instruct",
    validation_alias="MODEL_MULTILINGUAL",
)

# Cost optimizer route ladders (Vault/env থেকে override করা যায়)
route_ladder_simple: str | list[str] = Field(
    default="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct",
    validation_alias="ROUTE_LADDER_SIMPLE",
)
route_ladder_medium: str | list[str] = Field(
    default="gemini/gemini-2.0-flash,groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct",
    validation_alias="ROUTE_LADDER_MEDIUM",
)
route_ladder_complex: str | list[str] = Field(
    default="groq/llama-3.3-70b-versatile,openrouter/meta-llama/llama-3.3-70b-instruct,gemini/gemini-2.0-flash",
    validation_alias="ROUTE_LADDER_COMPLEX",
)
```

---

## পরবর্তী অবশিষ্ট কাজের রূপরেখা (Next Action Steps)

### ধাপ ১: ব্যাকএন্ড অবশিষ্টাংশ ফাইনাল টিউনিং (Backend Remainder)
1. **[`backend/core/llm/advanced_model_router.py`](file:///f:/supremeai/backend/core/llm/advanced_model_router.py)**:
   `_load_model_preferences()`-এ বাকি হার্ডকোডেড স্ট্রিংগুলোকে `settings.model_coding`, `settings.model_reasoning`, `settings.model_general` এবং `settings.model_multilingual` এর মাধ্যমে ডাইনামিক প্রেফারেন্স লিস্টে সংযুক্ত করা।
2. **[`backend/core/language_router.py`](file:///f:/supremeai/backend/core/language_router.py)**:
   `LANGUAGE_MODEL_MAP`-কে `settings.model_multilingual` এবং env ওভাররাইড ভিত্তিক করা।
3. **[`backend/tools/social/telegram_bot.py`](file:///f:/supremeai/backend/tools/social/telegram_bot.py)**:
   Gemini API URL জেনারেশনে `gemini-2.5-flash` স্ট্রিং সরাসরি না রেখে `getattr(settings, "model_vision", "gemini-2.5-flash")` বা env ভিত্তিক ডাইনামিক মডেল পাথ ব্যবহার করা।

### ধাপ ২: ইনফ্রাস্ট্রাকচার ও MCP কন্ট্রোল প্লেইন
4. **[`infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts`](file:///f:/supremeai/infrastructure/mcp-control-plane/src/adapters/ai/analyze.ts)**:
   প্রোভাইডার মডেল ইনিশিয়ালাইজেশনে `process.env.MCP_GEMINI_MODEL`, `process.env.MCP_GROQ_MODEL`, `process.env.MCP_OPENROUTER_MODEL` যুক্ত করা।

### ধাপ ৩: ফ্রন্টএন্ড ইন্টিগ্রেশন
5. **[`frontend/src/lib/llm.router.ts`](file:///f:/supremeai/frontend/src/lib/llm.router.ts)**:
   ক্লায়েন্ট-সাইড রাউটারে `/config/public` API কল করে ডাইনামিক মডেল কনফিগ ক্যাশ করে ব্যবহার করা।
6. **[`frontend/src/components/Onboarding/StepModelSelect.tsx`](file:///f:/supremeai/frontend/src/components/Onboarding/StepModelSelect.tsx)** ও **[`SettingsPage.tsx`](file:///f:/supremeai/frontend/src/components/dashboard/SettingsPage.tsx)**:
   `modelBranding.ts`-এর `SUPREME_AVAILABLE_MODELS` ও `/config/public/branding` এর সাথে সম্পূর্ণ সিঙ্ক রাখা।

---

## ভেরিফিকেশন ও টেস্ট নির্দেশনা

### Automated Tests
- `pytest backend/tests/engine/test_cost_optimizer.py` (পাস ✅)
- `pytest backend/tests/core/test_core_config.py`
- `pytest backend/tests/services/`
- Frontend type check & tests: `npm --prefix frontend run test:unit`

### ম্যানুয়াল ভেরিফিকেশন
```bash
# Env variable override টেস্ট:
MODEL_GENERAL=groq/llama-3.3-70b-versatile MODEL_CHAT=gemini/gemini-2.5-flash python -c "from core.config import settings; print('Chat:', settings.model_chat, '| General:', settings.model_general, '| Task Models:', settings.task_models)"
```
