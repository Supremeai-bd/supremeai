# ARCHITECTURE — Plan v1.0 বিশ্লেষণ ও v1.1 বাস্তবায়ন-স্থাপত্য

> **বাংলা:** User-এর "SupremeAI API Key & Unified Provider Gateway — Planning Draft v1.0" নথির
> প্রমাণ-ভিত্তিক বিশ্লেষণ। মূলমন্ত্র: **স্বাধীনতা দিয়ে জটিলতা কমানো যায়, বাড়ানো যায় না।**
> প্রতিটি রায়ের পেছনে monolith `main` @ `1deba24e`-যুগের প্রত্যক্ষ প্রমাণ আছে — অনুমান নয়।

## §১. প্রমাণ-ভিত্তিক আবিষ্কার: plan v1.0-এর ~৮৫% monolith-এ ইতিমধ্যে আছে

| Plan ধারা | বিষয় | Monolith-প্রমাণ (backend/) | রায় |
|---|---|---|---|
| §৪ Provider Layer | Adapter/interface | `core/llm/interfaces.py` → `ModelProvider` Protocol (generate/stream/health_check) | **চুক্তি আছে — নতুন প্রোটোকল নিষেধ** |
| §৪ | Provider registry | `core/llm/provider_registry.py` + `services/dynamic_ai/provider_registry.py` (runtime-discovery, health states) + `core/llm/llm_gateway/registry.py` | **৩টি সমান্তরাল registry — জটিলতা-ঋণ**, ঐক্য দরকার |
| §৫-৬ Fallback/Routing | Router | `core/llm/provider_router.py` (latency-aware weighted RR + circuit breaker), `core/llm/advanced_model_router.py`, `brain/model_router.py`, `brain/cognitive_router.py` ইত্যাদি | **৪+ রাউটার — আরও রাউটার লেখা নিষেধ** |
| §৫ | Runtime | `core/llm/llm_gateway/` — gateway, litellm_runtime, resilience, streaming, spend_meter | LiteLLM-ভিত্তিক পূর্ণ gateway আছে |
| §৭ | LiteLLM ভিত্তি | `llm_gateway/litellm_runtime.py` | LiteLLM নিজেই ১০০+ provider adapter — নিজে লেখা adapter-কৃত্রিম পুনরাবৃত্তি |
| §৯-১০, §১৪ Key management | Key CRUD/rotation/revocation/quota | `models/api_key.py`, `api/routes/api_keys.py` (create/revoke/rotate/usage/stats/quota-alert/bulk), `core/security/api_key_middleware.py`, `api_key_limiter.py` | **Key-plane আছে — নতুন key-code নিষেধ** |
| §১২ Usage | Metering | `llm_gateway/spend_meter.py` — সততা-মতবাদ সহ (provider usage না পেলে কিছুই record নয়) | ডকট্রিন গৃহীত, নতুন স্তরে একই নীতি |
| §৮, §১১, §১৭, §২১ | **SUPREMEAI_API_KEY-যুক্ত স্থিতিশীল বাইরের পৃষ্ঠ** | `api/routes/web_ai_proxy.py` এ `/v1/chat/completions` আছে, কিন্তু **admin-JWT-gated + zero-cost session pool**; api-key plane সেই পৃষ্ঠের মুখ নয় | **এটিই আসল gap #১** |
| §২, §১৯ | Repository boundary | সবকিছু monolith-এ; federation-এ api-plane রেপো নেই | **এটিই আসল gap #২** |

> **সিদ্ধান্ত:** plan-এর আসল মূল্য নতুন gateway-engine লেখা নয় — বিদ্যমান engine-এর সামনে
> **স্থিতিশীল বাইরের চুক্তি + পৃথক key/config-plane** দাঁড় করানো। v1.0-এর §৪-৬ আবার লেখা
> মানে ৪র্থ registry — জটিলতা বৃদ্ধি, হ্রাস নয়।

## §২. v1.1 স্থাপত্য — thin, contract-first

```text
CLIENT (Cursor/Aider/agent/GitHub-automation)
   │  X-SupremeAI-Key: sk-…          ← §৮: consumer শুধু এটা জানে
   ▼
┌──────────────────────────────────────────────┐
│ supremeai-api (এই রেপো — private, thin)      │
│  ১. key-auth (sha256 যাচাই — vault থেকে)      │
│  ২. scope/quota gate (config-driven)          │
│  ৩. routing_policy.json → fallback chain      │
│  ৪. adapter: Gemini / Groq (vault-key সার্ভার-পার্শ্বে) │
│  ৫. honest usage log (JSONL v0)               │
└──────────────────────────────────────────────┘
   ▼ provider-native API (Gemini/Groq/…)  — creds কখনো বাইরে যায় না (§১১)
```

**সচেতন সরলীকরণ (complexity-reduction ledger):**

| v1.0 প্রস্তাব | v1.1 রায় | কারণ |
|---|---|---|
| নতুন provider-adapter গ্রন্থাগার লেখা | ২টি adapter (Gemini/Groq) — monolith `ModelProvider` আকৃতিতে; পরে LiteLLM-এ অর্পণ (P4) | §২০-ও বলছে "start small"; LiteLLM যা দেয় তা পুনর্লিখন বৃথা |
| নতুন key-management ইঞ্জিন | v0: vault-এ key-**hash** তালিকা (plaintext কখনো নয়); P1: monolith api-key plane-এর সাথে ঐক্য | key-code দুইবার লেখা = জটিলতা; monolith-এ rotate/revoke/quota ইতিমধ্যে আছে |
| Admin panel + DB config-store | v0: `routing_policy.json` (git-পরিচালিত, schema-যাচাইকৃত) | অপারেশনাল বদল এখনই "config-change"; panel P4-এ তবেই scale ন্যায্য |
| Cost-analytics স্ট্যাক | v0: JSONL usage log — সততা-মতবাদ সহ | analytics ছাড়াও routing সিদ্ধান্তে config যথেষ্ট; data সংগ্রহ এখন থেকেই |
| Backend-compute provider (Kaggle §৭) | বাদ — শুধু interface-এ জায়গা রাখা | YAGNI; abstraction থাকায় পরে যোগ করা সস্তা |

## §৩. সীমানা-চুক্তি (§১৯-এর বিশ্লেষণ-সংস্করণ)

**এই রেপো মালিক:** বাইরের OpenAPI চুক্তি, key-auth, routing-policy schema+ডেটা, বাইরের adapter,
usage-log ফরম্যাট।
**এই রেপো মালিক নয়:** tenant-ledger, CostGuard, agent-orchestration, memory — এগুলো monolith-এই থাকবে;
দুই পাশ যুক্ত হবে শুধু এই চুক্তি দিয়ে।
**Core-freeze সম্মতি:** monolith `backend/core/` কোনো পরিবর্তন ছাড়াই v0 দাঁড়ায় — extraction নয়,
নতুন পৃষ্ঠ।

## §৪. সাফল্য-মানদণ্ডের ম্যাপিং (§২১)

- এক key → এক অনুরোধ → provider-অজ্ঞেয়বাদী উত্তর: `service/app.py` + `contracts/openapi.yaml`
- provider বদল/fallback/limit বদল = `config/routing_policy.json` এডিট + রিলোড — client অচেতন
- credential rotation = vault-এ মান বদল — repo ও client অচেতন

## §৫. পরবর্তী ধাপ (README-Phases-এর সাথে সংগত)

P1 (সম্পন্ন): monolith `api_keys` টেবিল-ই SSOT — `service/keyplane.py` read-only mirror
(monolith `hash_api_key`/`mask_api_key`/middleware-SQL/Redis-TTL-300s-এর হুবহু প্রতিলিপি;
হ্যাশ-secret = `API_KEY_SIGNING_SECRET`→`JWT_SECRET` একই রেজলিউশন-ক্রম)। নতুন key-code নেই —
create/revoke/rotate monolith-এই থাকবে। ব্যর্থতা-রায়: DB-অপ্রাপ্য = 503, অবৈধ key = 401 (সৎ-বিভাজন)।

P2 deploy-এ `FEDERATION_WIRING.md` §৭-এর ৩-জায়গা নিবন্ধন (infra রেপো)।

P3 (সম্পন্ন): consumer-kit — `docs/CONSUMERS.md` (§15/§16 চুক্তি + deterministic-protections
লৌহদণ্ড) + `scripts/clients/gateway_client.py` (zero-dep, typed errors, retry-নীতি)।

P4 (সম্পন্ন): ① `strategy=cost` — fallback-chain খরচ-ক্রমে পুনঃসাজানো (config-driven,
ordering-heuristic; metering সত্য provider-ই দেয়) ② provider-health circuit — ৩ টানা
ব্যর্থতা → ৬০s খোলা → half-open probe (auto-fallback সচেতন) ③ Groq pool-rotation —
`GROQ_API_KEY_POOL` = env-**নামের** তালিকা (মান vault-ই), round-robin, 403→900s /
429→60s cooldown।

**সরলীকরণ-ledger সংযোজন:** LiteLLM-অর্পণ (P4-মূল-পরিকল্পনা) সচেতনভাবে মুলতবি — ২টি
adapter ~১২০ লাইনে কাজ করছে; litellm যোগ = নতুন dependency-পৃষ্ঠ, একই ক্ষমতা। ৩য়
provider যোগের সময়ে পুনর্মূল্যায়ন (তখন LiteLLM-এর ১০০+ adapter প্রকৃত মূল্যবান)।
