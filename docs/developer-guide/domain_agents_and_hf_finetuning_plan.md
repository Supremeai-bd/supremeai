# Domain Agents & HF Fine-Tuning — Implementation Plan (DRAFT, for later)

> Status: Planning only. NOT executed. Created 2026-08-16.
> Scope: Two deferred work items discovered during the staging↔prod diff review.
> All file:line references below are verified against the current staging working tree.

---

## 0. Executive Summary

| Item | What we found | Decision needed | Recommended path |
|---|---|---|---|
| **Domain Agents** | 5 vertical-domain agents exist in `backend/agents/domain/` but are orphaned (empty `__init__.py`, no importers, only listed in `scripts/find_dead_code.py`). They are REAL, well-structured specialists — NOT environment agents. | Keep & wire, or delete? | **Wire as specialists** (lang layer + guardrails + tools). Delete only if we confirm zero product need. |
| **HF Fine-Tuning** | User fine-tuned models, deployed to HF Space. Already wired as the **primary** engine in `expert_router.py`. Missed earlier because the provider code wasn't inspected first. | HF Space (keep) vs R2 export? | **Keep HF Space.** No R2 export (cost). Only ops remain: ensure Space live + env set. |

---

## PART A — DOMAIN AGENTS

### A.1 Current verified state
- Location: `backend/agents/domain/`
  - `bangla_nlp_agent.py` — Bengali NLP (transliteration, sentiment, keywords, tokenize)
  - `ecommerce_agent.py` — product recommendations, review summarization
  - `education_agent.py` — curriculum/quiz/learning-path
  - `financial_services_agent.py` — transaction analysis, risk scoring (uses `TenantAwareFirestore`)
  - `healthcare_assistant_agent.py` — health data, **PHI detect/redact**, vitals
- `__init__.py` is empty (no exports). No module imports `backend.agents.domain` except the agents themselves.
- Only references: `scripts/find_dead_code.py` (dead-code watchlist) + `docs/audit_reports/*`.
- Each agent uses `LLMRouter` + `core.cache` → genuinely functional, not stubs.
- **Important correction:** these are *vertical/industry* agents, NOT infra/environment agents. GitHub/Render/Supabase rule-maintenance already lives in:
  - `backend/agents/infrastructure/` (`auto_scaling_agent.py`, `cost_optimization_agent.py`, `disaster_recovery_agent.py`, `performance_tuning_agent.py`)
  - `backend/agents/devops/` (`auto_healer.py`, `cloud_watchman.py`, `cost_sage.py`)
  - `backend/tools/devops/github_agent.py` (has `tests/test_github_agent.py` → active)

### A.2 Options
1. **DELETE** — treat as dead code (cleanest if no product surface needs them).
2. **WIRE AS SPECIALISTS (recommended)** — they become a domain layer on top of the generic engine, not a replacement for it.

### A.3 Recommended wiring (Option 2)
| Agent | Role | Where to wire | Risk |
|---|---|---|---|
| `bangla_nlp_agent` | **Language pre-process layer** — detect Bangla (`contains_bangla`, `get_bangla_ratio`), extract keywords before routing | `backend/core/llm/llm_gateway.py` or intent parser, early in the request path | 🔴 Low — pure preprocessing, big UX win for Bangla-first product |
| `healthcare_assistant_agent` | **PHI guardrail** — `detect_phi`/`redact_phi`/`sanitize_health_data` before any health data hits LLM/vector memory | gateway post-process / `core/llm/llm_gateway.py` sanitize hook | 🟠 Med — compliance scope |
| `financial_services_agent` | **Risk/compliance analyzer** — categorize financial queries, attach disclaimers | tool or gateway middleware | 🟠 Med |
| `ecommerce_agent` | **Shopping/recommendation tool** | `engine/tool_forge.py` (function-call) — only if an e-commerce surface exists | 🟡 Low (feature-gated) |
| `education_agent` | **Tutoring/learning-path tool** | `engine/tool_forge.py` — only if an education surface exists | 🟡 Low (feature-gated) |

### A.4 Concrete steps (when we execute)
1. Populate `backend/agents/domain/__init__.py` with exports (removes them from dead-code list).
2. Add a lightweight **domain classifier** (or reuse `intent_parser`) to route a query to the matching specialist.
3. `bangla_nlp`: call in `llm_gateway.py` request path (pre-process). Add unit test.
4. `healthcare`/`financial`: add sanitize/redact hooks in gateway (post-process + pre-LLM).
5. `ecommerce`/`education`: register as tools in `engine/tool_forge.py`; leave disabled until surfaces exist.
6. Verify `scripts/find_dead_code.py` no longer flags the getters.

### A.5 Risks / caveats
- **Compliance:** `healthcare`/`financial` must stay *wellness/info + redaction/disclaimer* only — no real diagnosis/investment advice (liability).
- **Brand exclusivity (AGENTS.md):** these are internal specialists ("muscle"/logic). Never expose as a third-party brand to end users.
- **Scope creep:** only wire `ecommerce`/`education` if the product actually has those surfaces; otherwise keep as latent, documented capability.

### A.6 Open questions (need user decision)
- [ ] Do we build an e-commerce surface? (gates `ecommerce_agent`)
- [ ] Do we build an education/tutoring surface? (gates `education_agent`)
- [ ] Confirm `bangla_nlp` should run on *every* request or only detected-Bangla requests (perf).

---

## PART B — HF FINE-TUNING

### B.1 Current verified state
- User fine-tuned model(s) deployed to HF Space (`supremeai-hf-space.hf.space`).
- Already wired as **primary** engine:
  - `backend/brain/expert_router.py:27` → `"hf_space/supreme-hybrid-8b"` (fallback: `groq/llama-3.3-70b` → `gemini/2.5-flash`)
  - `backend/services/llm/providers.py:387` → `HuggingFaceSpaceProvider` (reads `hf_space_url`, default `https://supremeai-hf-space.hf.space/v1/chat/completions`, and `hf_api_key`)
  - `backend/core/llm/llm_gateway.py:63` → maps `hf_space` → `HF_API_KEY`
  - `backend/brain/model_router.py:189` → checks `hf_api_key` availability
- Deployment tooling: `scripts/col:193` → `create_hf_space_config()` (redeploy Space from `_archive/hf-space/server.py`, which is an *inference* server, not a trainer).
- Training tooling exists: `backend/tools/learning/model_trainer.py` (so future fine-tunes can be scripted).

### B.2 Options
1. **Keep HF Space (recommended).** Model already deployed + wired. Treat as "muscle" feeding the learning loop.
2. **R2 export (self-host weights).** Rejected for now — hosting an 8B GGUF needs GPU/storage → violates $0-cost; HF free-tier already serves it.

### B.3 Remaining work = OPS, not code
- [ ] Confirm HF Space `supremeai-hf-space.hf.space` is **live**.
- [ ] Set `HF_API_KEY` + `hf_space_url` in staging (Render + Infisical).
- [ ] Verify health via `backend/core/health_check.py:189`.
- [ ] If Space is down: redeploy with `scripts/col` (`create_hf_space_config`) using `_archive/hf-space/server.py`.
- [ ] Add a CI/monitor alert if the `hf_space` engine drops out of the fallback chain (so we notice if the Space dies).

### B.4 Risks / caveats
- **Vendor risk:** HF could rate-limit/remove the Space. If that becomes a real problem later, R2 export is a *future* mitigation — not now.
- **Brand exclusivity:** internal engine only; never surface "HuggingFace fine-tuned model" name to users.
- **Cost:** HF free-tier inference is acceptable as muscle; paid inference tiers must be avoided to honor $0-cost.

### B.5 Open questions
- [ ] Is the Space currently live + keys set in staging? (quick health-check needed)
- [ ] Which fine-tuned model(s) are deployed, and is `supreme-hybrid-8b` the one in `expert_router.py`?
- [ ] Want periodic re-fine-tuning automated via `model_trainer.py`? (future, not now)

---

## C. TODO (for later execution)
- [ ] **Domain Agents:** decide keep-vs-delete (user) → if keep, wire per A.3/A.4
- [ ] **Domain Agents:** resolve A.6 open questions (e-commerce / education surfaces)
- [ ] **HF:** run B.3 ops checklist (live + env + health)
- [ ] **HF:** add fallback-chain monitor alert
- [ ] Re-review after execution; update this doc

## D. References (verified)
- `backend/agents/domain/{bangla_nlp,ecommerce,education,financial_services,healthcare_assistant}_agent.py`
- `backend/agents/domain/__init__.py` (empty)
- `scripts/find_dead_code.py` (dead-code watchlist)
- `backend/agents/infrastructure/*`, `backend/agents/devops/*`, `backend/tools/devops/github_agent.py`
- `backend/brain/expert_router.py:27`, `backend/services/llm/providers.py:387`, `backend/core/llm/llm_gateway.py:63`, `backend/brain/model_router.py:189`
- `scripts/col:193` (`create_hf_space_config`), `_archive/hf-space/server.py`, `backend/tools/learning/model_trainer.py`
