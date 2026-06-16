# Master Plan Actionable Progress Checklist

This checklist converts the high-level plan into executable, verifiable items. Each item should be tracked with status: TODO, IN PROGRESS, or DONE.

## Smart Router (Top 50 AI Model Plan)
- [ ] DONE: `brain/model_router.py` provider fallback chain and routing logic
- [ ] TODO: Route tier 1 tasks to frontier models when keys are available
- [ ] TODO: Route tier 2-3 tasks to value models by cost/speed
- [ ] TODO: Route tier 5 tasks to free models
- [ ] TODO: Add tier-to-model auto-selection from `brain/model_registry.py`
- [ ] TODO: Add complexity estimation based on task_type and prompt length

## Local Frontier Replication
### 1. CoT Reasoning Engine
- [x] TODO: `tools/cot_reasoner.py` - step-by-step thought tag parser
- [ ] TODO: Hook CoT reasoner into `brain/model_router.py` route pipeline
- [ ] TODO: Add self-verification via Python executor

### 2. Local Web RAG & Search
- [x] TODO: `tools/local_search_rag.py` - DDG scrape + page fetch
- [ ] TODO: Add ChromaDB embedding storage path in `tools/local_search_rag.py`
- [ ] TODO: Add semantic search query against stored embeddings

### 3. Local OCR & Table Extractor
- [x] TODO: `tools/local_ocr_extractor.py` - EasyOCR local OCR
- [x] TODO: `tools/local_ocr_extractor.py` - Pandas pipe-delimited table parser
- [ ] TODO: Add Excel export via openpyxl

### 4. Schema Validator (Structured Output)
- [x] TODO: `core/schema_validator.py` - Pydantic validation wrapper
- [ ] TODO: Add retry-on-validation-fail helper in task execution layer

## Meta-AI Capability Absorption
### 1. Agentic & Autonomous
- [ ] TODO: MCP server integration tooling in `tools/mcp_client.py`
- [ ] TODO: Checkpoint/resume logic for long task runs
- [ ] TODO: Celery/Redis async task queue scaffolding

### 2. Reasoning & Context
- [ ] TODO: SymPy integration for symbolic math verification
- [ ] TODO: Sliding window + summary tree for large docs in `memory/`

### 3. Specialized & Multimodal
- [ ] TODO: Vision pipeline linking OCR to schema validation
- [ ] TODO: Streaming response helper in `brain/model_router.py`
- [ ] TODO: Language detection and routing for GLM-5 / Yi-34B
- [ ] TODO: GDPR audit logging scaffold

## Verification Checklist
- [ ] DONE: ruff check passes for new files
- [ ] DONE: pytest `tests/` suite passes
- [ ] TODO: Add dedicated unit tests for `tools/cot_reasoner.py`
- [ ] TODO: Add dedicated unit tests for `tools/local_search_rag.py`
- [ ] TODO: Add dedicated unit tests for `tools/local_ocr_extractor.py`
- [ ] TODO: Add dedicated unit tests for `core/schema_validator.py`
