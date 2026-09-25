---
id: codebase-integration-audit
subject: "SupremeAI — Codebase Integration Audit (key vs code mapping)"
document_role: audit
planning_authority: Architecture Governance / Security Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-25
target_scope: combined_ecosystem
---

# SupremeAI — Codebase Integration Audit

> **Infisical vault (১৮১ secrets) + codebase (৩৫৩ env vars) মিলিয়ে —
> কোন service কোথায় used, কোনটা orphan, কোনটা missing।**

**তৈরি:** 2026-09-25 · **Source:** Codebase grep + INTEGRATION_AUDIT.md
**সম্পর্কিত:** [INTEGRATION_AUDIT.md](./INTEGRATION_AUDIT.md) (API key validity)

---

## ০. সারাংশ

| মেট্রিক | মান |
|---|---|
| Codebase env vars (.env.example) | ৩৫৩ |
| Infisical secrets (prod) | ১৮১ |
| LLM providers in code | ১৮ (GROQ, GEMINI, OPENAI, etc) |
| LLM providers with working key | ৪ (Mistral, OpenRouter, Bynara, BAI) |
| LLM providers with broken key | ৩ (Groq, OpenAI, Cerebras) |
| LLM providers with NO key | ৭ (Anthropic, Cohere, Together, NVIDIA, HF, DeepSeek-standalone) |
| **Orphan keys** (key in Infisical, 0 code refs) | **২** (CEREBRAS, GCP_KMS_KEY_RING) |
| **Missing keys** (code refs, no key in Infisical) | **৭** |
| Duplicate env names | ০ |

---

## ১. LLM Provider Codebase Integration

| Provider | Code Refs | Key in Infisical? | Key Working? | Status |
|---|---|---|---|---|
| **GROQ** | ৩৯ refs | ✅ SET | ❌ 403 | **Fix needed** — re-generate key |
| **GEMINI** | ৫৮ refs | ✅ SET | ⚠️ 400 | Key exists, test inconclusive |
| **OPENAI** | ৩৯ refs | ✅ SET (164 chars!) | ❌ 403 | **Fix needed** — verify key format |
| **ANTHROPIC** | ১২ refs | ❌ MISSING | — | **Add key** or remove code refs |
| **DEEPSEEK** | ১৯ refs | ⚠️ in LLM_PROVIDER_KEYS | ✅ via LPK | OK — uses JSON config |
| **MISTRAL** | ১১ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **OPENROUTER** | ৪৫ refs | ⚠️ in LLM_PROVIDER_KEYS | ✅ via LPK | OK — uses JSON config |
| **HF_API** | ৩৩ refs | ❌ MISSING standalone | — | HF degraded anyway; consider Modal |
| **HUGGINGFACE** | ৬ refs | ❌ MISSING | — | Same as HF_API |
| **NVIDIA** | ১৩ refs | ❌ MISSING | — | **Add key** or remove code refs |
| **TOGETHER** | ৮ refs | ❌ MISSING | — | **Add key** or remove code refs |
| **COHERE** | ৬ refs | ❌ MISSING | — | **Add key** or remove code refs |
| **OLLAMA** | ৪ refs | ❌ MISSING | — | Not needed (no local device) |
| **BYNARA** | ৯ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **BAI** | ৮ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **V0** | ৫ refs | ✅ SET (563 chars!) | ❌ 404 | **Fix needed** — API changed |
| **CEREBRAS** | **০ refs** | ✅ SET | ❌ 403 | **ORPHAN** — key exists but no code! |

### ⚠️ Critical Findings

১. **CEREBRAS = ORPHAN KEY** — Infisical-ে key আছে কিন্তু codebase-এ **০ reference**।
   হয় code থেকে সরানো হয়েছে, বা কখনো add করা হয়নি। Key + code দুটোই fix দরকার।

২. **OPENAI_API_KEY = 164 chars** — সাধারণ OpenAI key ~51 chars। হয়তো:
   - Multiple keys comma-joined
   - Wrong format
   - Different key type (organization key?)
   Verify করো।

৩. **V0_API_KEY = 563 chars** — অস্বাভাবিক। হয়তো JWT token বা full auth object।
   আলাদা env var হিসেবে ভাঙো।

৪. **৭ LLM providers code-এ আছে কিন্তু key নেই** — Anthropic, NVIDIA, Together,
   Cohere, HF, Ollama, DeepSeek(standalone)। হয় key add করো, বা code refs clean করো।

---

## ২. Database/Cache Integration

| Service | Code Refs | Key in Infisical? | Working? | Status |
|---|---|---|---|---|
| **SUPABASE** | ২৫৮ refs | ✅ SET | ✅ 401 (valid) | **Working** ✅ |
| **DATABASE_URL** | ১৮৩ refs | ✅ SET | ✅ | **Working** ✅ |
| **NEON_DATABASE** | ২৫ refs | ✅ SET | ⚠️ untested | Backup DB — verify |
| **REDIS_URL** | ১১২ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **UPSTASH** | ৫০ refs | ✅ SET (৫ accounts) | ✅ 200 (all 5) | **Working** ✅ |
| **QDRANT** | ৩৯ refs | ✅ SET | ✅ 200 | **Working** ✅ (but CP03 says pgvector canonical) |
| **CHROMADB** | ৪ refs | ⚠️ CHROMADB_PATH | — | Minimal use — consider removing |

---

## ৩. Hosting/Infra Integration

| Service | Code Refs | Key in Infisical? | Working? | Status |
|---|---|---|---|---|
| **RENDER** | ১৩৮ refs | ✅ SET (৫ accounts) | ✅ 200 (all 5) | **Working** ✅ |
| **CLOUDFLARE** | ৩০ refs | ✅ SET (৫ accounts) | ⚠️ ১/৫ working | **Fix secondary/tertiary** |
| **FIREBASE** | ৬০ refs | ✅ SET | ✅ | **Working** ✅ |
| **TELEGRAM** | ১০৬ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **DISCORD** | ২১ refs | ✅ SET | ❌ 403 | **Fix webhook** |
| **RESEND** | ১৫ refs | ✅ SET | ❌ 403 | **Fix email** |
| **STRIPE** | ৪৬ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **LAUNCHDARKLY** | ৮ refs | ✅ SET | ✅ 200 | Working but minimal use — consider removing |
| **E2B** | ২৯ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **FIRECRAWL** | ১১ refs | ✅ SET | ✅ 404 (valid) | **Working** ✅ |
| **OPENHANDS** | ১৯ refs | ✅ SET | ❌ DNS | **Fix or remove** |
| **MODAL** | ৭ refs | ✅ SET (token) | ⚠️ untested | **Test needed** |
| **VERCEL** | ২০ refs | ✅ SET | ✅ 200 | **Working** ✅ |
| **GCP_KMS** | **০ refs** | ✅ GCP_KMS_KEY_RING | — | **ORPHAN** — key exists but no code! |
| **N8N** | ৪৫ refs | ⚠️ N8N_BASE_URL | — | Config exists, check if enabled |
| **APPWRITE** | ১২ refs | ⚠️ APPWRITE_ENABLED | — | Config exists, check if enabled |

### ⚠️ Critical Findings

১. **GCP_KMS_KEY_RING = ORPHAN KEY** — Infisical-এ key আছে কিন্তু codebase-এ **০ reference**
   (শুধু `KMS_KEY_NAME` test-এ আছে)। Naming mismatch বা orphan।

২. **CLOUDFLARE ৫ accounts** — শুধু primary working। Secondary auth failed।
   Tertiary/quaternary/quinary untested। Fix দরকার।

৩. **LAUNCHDARKLY** — মাত্র ৮ code refs, হয়তো underutilized। Use বা remove।

৪. **N8N + APPWRITE** — config আছে কিন্তু enabled status অস্পষ্ট। Verify করো।

---

## ৪. Orphan Keys (Key in Infisical, 0 Code Refs)

| Key | Infisical Value | Code Refs | Action |
|---|---|---|---|
| **CEREBRAS_API_KEY** | ✅ SET (52 chars) | **০** | Either add code to use it, or remove key from Infisical |
| **GCP_KMS_KEY_RING** | ✅ SET (21 chars) | **০** (only KMS_KEY_NAME in tests) | Fix naming mismatch (GCP_KMS_KEY_RING → KMS_KEY_NAME) or remove |

**Action:** এই ২টা orphan key হয় code-এ use করো, বা Infisical থেকে remove করো।
Orphan key = security risk (unused key থাকা = attack surface)।

---

## ৫. Missing Keys (Code Refs, No Key in Infisical)

| Provider | Code Refs | Key Status | Action |
|---|---|---|---|
| **ANTHROPIC** | ১২ refs | ❌ NO KEY | Add ANTHROPIC_API_KEY বা remove code |
| **NVIDIA** | ১৩ refs | ❌ NO KEY | Add NVIDIA_API_KEY বা remove code |
| **TOGETHER** | ৮ refs | ❌ NO KEY | Add TOGETHER_API_KEY বা remove code |
| **COHERE** | ৬ refs | ❌ NO KEY | Add COHERE_API_KEY বা remove code |
| **HF_API** (standalone) | ৩৩ refs | ❌ NO KEY | HF degraded — use Modal instead |
| **HUGGINGFACE** | ৬ refs | ❌ NO KEY | Same as HF_API |
| **OLLAMA** | ৪ refs | ❌ NO KEY | Not needed (no local device) — remove code |

**Action:** প্রতিটা provider-এর জন্য decide করো — key add করো বা code clean করো।
Dead code (key ছাড়া provider) = confusion + maintenance burden।

---

## ৬. Duplicate/Redundant Keys

| Key Pair | Status | Action |
|---|---|---|
| `GEMINI_API_KEY` = `GOOGLE_API_KEY` | Same value | ✅ OK — keep both (different code paths) |
| `V0_API_KEY` = `V0_API_KEYS` | Same value (563 chars) | ⚠️ Remove one — redundant |
| `STRIPE_API_KEY` = `STRIPE_SECRET_KEY` | Same value (107 chars) | ⚠️ Remove one — redundant |
| `KAGGLE_API_TOKEN` + `KAGGLE_API_TOKENS` | Single + comma-joined | ✅ OK — both used (single + multi) |
| `GCP_KMS_KEY_RING` vs `KMS_KEY_NAME` | Different names, 0 match | ⚠️ Naming mismatch — fix |

---

## ৭. Better Utilization Recommendations

### এখন working — আরও ব্যবহার করো

| Service | Current Use | Better Use |
|---|---|---|
| **Mistral** (✅) | শুধু coding test | **Primary coding model** (codestral-2508) |
| **OpenRouter** (✅) | via LLM_PROVIDER_KEYS | **Primary fallback** (free models available) |
| **Bynara** (✅) | backup router | **Secondary fallback** (agnes-2.5-flash) |
| **BAI** (✅) | backup router | **Tertiary fallback** (minimax-m3) |
| **E2B** (✅) | sandbox | **Agent code execution** (CP05 verify) |
| **Firecrawl** (✅) | web scraping | **Scout backup** (CP05 research) |
| **Qdrant** (✅) | vector DB | **pgvector backup** (CP03 canonical) |
| **Kaggle** (✅ ৬ tokens) | training | **Specialized fine-tuning** (১৮০h/wk) |

### এখন broken — fix করো

| Service | Fix | Priority |
|---|---|---|
| **Groq** | Re-generate key | P1 (best free LLM) |
| **Cerebras** | Re-generate key + add code | P1 (or remove key) |
| **OpenAI** | Verify 164-char key format | P1 |
| **Discord** | Re-create webhook | P2 |
| **Resend** | Fix IP block | P2 |
| **Cloudflare ৪ accounts** | Verify credentials | P3 |

### এখন missing — decide করো

| Service | Decision | Recommendation |
|---|---|---|
| **Anthropic** | Add key বা remove code | Add key (Claude good for reasoning) |
| **NVIDIA** | Add key বা remove code | Remove code (NIM API limited free) |
| **Together** | Add key বা remove code | Remove code (Modal better) |
| **Cohere** | Add key বা remove code | Remove code (limited free) |
| **HF** | Add key বা remove code | Remove code (HF degraded, use Modal) |
| **Ollama** | Add key বা remove code | Remove code (no local device) |

---

## ৮. Recommended Fallback Chain (fix পরে)

```
Tier 1: Mistral (working, codestral for coding)
Tier 2: OpenRouter (working, free models)
Tier 3: Bynara (working, zero-cost router)
Tier 4: BAI (working, zero-cost router)
Tier 5: Gemini Flash (key exists, needs re-test)
Tier 6: Groq (fix key first — 500 t/s when working)
Tier 7: Modal (deploy own model, $30/mo free)
Tier 8: Honest 501 (all fail — no fake)
```

---

## ৯. Cleanup Actions (reduce technical debt)

### Remove orphan keys
- `CEREBRAS_API_KEY` — add code to use বা remove from Infisical
- `GCP_KMS_KEY_RING` — fix naming (→ `KMS_KEY_NAME`) বা remove

### Remove dead code (no key, no plan to add)
- `OLLAMA` code refs (৪) — no local device, remove
- `NVIDIA` code refs (১৩) — limited free, remove
- `TOGETHER` code refs (৮) — Modal better, remove
- `COHERE` code refs (৬) — limited free, remove
- `HF_API` standalone refs (৩৩) — HF degraded, use Modal

### Remove redundant keys
- `V0_API_KEYS` (duplicate of V0_API_KEY) — remove
- `STRIPE_API_KEY` (duplicate of STRIPE_SECRET_KEY) — remove

### Fix naming mismatch
- `GCP_KMS_KEY_RING` → `KMS_KEY_NAME` (if code uses latter)

---

## ১০. Summary Score

| দিক | Score | মন্তব্য |
|---|---|---|
| Working services | ২১/২৮ (৭৫%) | ভালো, কিন্তু ৩ critical LLM down |
| Multi-account federation | ৩/৪ working | Render+Upstash+Kagley ✅, Cloudflare ⚠️ |
| Orphan keys | ২টা | CEREBRAS + GCP_KMS — cleanup needed |
| Missing keys | ৭টা | Dead code — decide add বা remove |
| Duplicate keys | ২টা | V0 + Stripe — remove redundant |
| Codebase-code sync | ⚠️ | কিছু provider code-এ আছে কিন্তু key নেই |

**Overall:** প্রজেক্ট চলছে, কিন্তু cleanup দরকার। ৮টা broken fix করলে + ৭টা dead
code remove করলে codebase অনেক clean হবে।

---

## রেফারেন্স

- [INTEGRATION_AUDIT.md](./INTEGRATION_AUDIT.md) — API key validity test results
- [ZERO_COST_STRATEGY.md](./ZERO_COST_STRATEGY.md) — zero-cost strategy
- [core-plans/CP02](./core-plans/CP02_VENDOR_NEUTRAL_PROVIDER_GATEWAY.md) — LLM gateway
