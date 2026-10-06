# Local Inference Benchmark: Strata vs Colibrì vs llama.cpp (issue #4060)

> **Priority:** P4 — research only, no implementation
> **Date:** 2026-10-06
> **Roadmap v2 section:** Phase 2 → §2.2 Integration Matrix (rows #9 Strata, #10 Colibrì)

## Mission

Benchmark local inference providers (Strata, Colibrì) against llama.cpp baseline. Determine which provider for which workload (or reject all if llama.cpp wins).

## What are Strata and Colibrì?

### Strata
- Local inference framework optimized for layered model staging
- Focus: VRAM layer management for large models on consumer GPUs
- Use case: Running 70B+ models on 8GB VRAM via layer offloading

### Colibrì
- VRAM/RAM layer staging research project
- Focus: Intelligent layer placement (GPU VRAM ↔ system RAM ↔ SSD)
- Use case: Optimizing inference speed across heterogeneous memory tiers

### llama.cpp (baseline)
- Canonical local inference engine
- GGUF model format, CPU+GPU hybrid execution
- Mature, widely tested, excellent community support
- Already referenced in SupremeAI as the local-inference baseline

## SupremeAI's Current Local Inference (verified on main)

| Component | File | Purpose |
|---|---|---|
| Ollama Adapter | `backend/core/llm/providers/ollama_adapter.py` | Local Ollama execution (governed provider) |
| Ollama Provider | `backend/core/llm/llm_gateway/registry.py` → `ollama` | Registered in `_MODEL_KEY_MAP` |
| Ollama Health | `service_topology.py` (if wired) | Health check |

**SupremeAI already uses Ollama** as its local inference provider. Ollama is built on llama.cpp internally, so the llama.cpp baseline is already covered.

## Benchmark Methodology (not run — P4 research only)

A formal benchmark would require:
1. Deploying Strata + Colibrì + llama.cpp on identical hardware
2. Testing 3 representative models (small/medium/large)
3. Measuring: tokens/sec, VRAM usage, RAM usage, setup complexity, model compatibility
4. Cross-referencing with Ollama (SupremeAI's current local provider)

**Not run because:** P4 priority — research stage only. Hardware + time investment not justified at this priority level.

## Architectural Comparison (sufficient evidence at P4)

| Dimension | Strata | Colibrì | llama.cpp | Ollama (SupremeAI's current) |
|---|---|---|---|---|
| Maturity | Early-stage research | Research project | ✅ Mature, widely tested | ✅ Mature, production-ready |
| Model format | Custom | Custom | GGUF (standard) | GGUF (via llama.cpp) |
| API compatibility | Custom | Custom | CLI + server | OpenAI-compatible REST API |
| SupremeAI integration | None | None | Via Ollama | ✅ Already integrated |
| VRAM optimization | ✅ Layer offloading | ✅ Layer staging | ⚠️ Basic (mmap) | Via llama.cpp |
| Community support | Small | Small | ✅ Large | ✅ Large |
| Setup complexity | High (custom build) | High (research build) | Medium | ✅ Low (Docker / native install) |

## Decision: **REFERENCE ONLY** — Ollama (llama.cpp) remains the local inference provider

**Rationale:**
1. SupremeAI already uses Ollama (built on llama.cpp) as its local inference provider — the baseline is already covered
2. Strata and Colibrì are early-stage research projects with small communities — high maintenance risk
3. Their VRAM optimization benefits (layer offloading/staging) are incremental over llama.cpp's mmap approach
4. Custom model formats would break compatibility with Ollama's GGUF ecosystem
5. No current SupremeAI use case requires running 70B+ models on consumer GPUs (the primary Strata/Colibrì use case)

If a future use case needs VRAM-optimized local inference for large models, open a NEW issue with:
- Specific model size requirement (e.g., "need to run 70B locally on 8GB VRAM")
- Benchmark evidence that Ollama/llama.cpp cannot meet the requirement
- Then re-evaluate Strata/Colibrì with a formal benchmark

## Bengali Note

Strata ও Colibrì — দুটোই early-stage research project। SupremeAI-তে ইতিমধ্যে Ollama (llama.cpp-ভিত্তিক) আছে। ৭০B+ মডেল ৮GB VRAM-এ চালানোর প্রয়োজন না হলে Strata/Colibrì যোগ করার দরকার নেই। ভবিষ্যতে প্রয়োজন হলে নতুন issue + formal benchmark দরকার।
