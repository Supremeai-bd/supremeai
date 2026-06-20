# 🛠️ Installed Skills & Tools in SupremeAI 2.0

*Last updated: 2026-06-20 (Full project re-audit)*

## Core Tools (`supremeai_2.0/tools/`)

| Tool | Purpose | Status |
|---|---|---|
| multi_account_rotator.py | Multi-account & API key rotation + Playwright signup automation | ✅ Active |
| auto_test_generator.py | Autonomous test file generator | ✅ Active |
| bangla_ai_connector.py | Bengali language connectivity & prompt processor | ✅ Active |
| bengali_ocr_converter.py | Bengali image/document OCR reader | ✅ Active |
| coverage_auditor.py | Test coverage auditing | ✅ Active |
| git_knowledge_extractor.py | Git repo commit & code knowledge extractor | ✅ Active |
| local_ocr_extractor.py | Local OCR engine (EasyOCR + openpyxl export) | ✅ Active |
| local_search_rag.py | Local ChromaDB + search API RAG engine | ✅ Active |
| cot_reasoner.py | Chain-of-Thought reasoning processor | ✅ Active |
| browser_agent.py | Browser automation scripting | ✅ Active |
| playwright_browser_agent.py | Advanced Playwright browser automation | ✅ Active |
| computer_agent.py | OS-level automation processor | ✅ Active |
| sync-features.js | Node.js/JS script sync logic | ✅ Active |
| docker_sandbox.py | Sandboxed Docker command execution | ✅ Active |
| cost_auditor.py | SQLite cost & API usage audit reporter | ✅ Active |
| plan_sorter.py | Plan file sorter (Urgent/Feature/Bug) | ✅ Active |
| health_checker.py | Daily dependency & API key status checker | ✅ Active |
| gcp_cloud_functions.py | Google Cloud Functions HTTP trigger client | ✅ Active |
| bangla_nlp.py | Bengali NLP (NER, sentiment, grammar parsing) | ✅ Active |
| bangla_voice.py | Bengali offline TTS/STT (Coqui/gTTS hybrid) | ✅ Active |
| image_generator.py | Stable Diffusion & DALL-E 3 rotational routing | ✅ Active |
| video_generator.py | AI video generation routing (Runway/HuggingFace) | ✅ Active |
| vision_agent.py | Multi-modal image/PDF/chart analysis agent | ✅ Active |
| vpn_switcher.py | Dynamic VPN rotation for agent security | ✅ Active |
| checkpoint_manager.py | Long-task checkpoint save/restore manager | ✅ Active |
| seed_database.py | Database seeding automation | ✅ Active |
| api_gateway.py | Unified API gateway for external calls | ✅ Active |

## Core Modules (`supremeai_2.0/core/`)

| Module | Purpose | Status |
|---|---|---|
| input_sanitizer.py | Prompt sanitization, ambiguity filter, PII stripping (Layer 1) | ✅ Active |
| generation_monitor.py | Real-time generation tracker & source attribution (Layer 2) | ✅ Active |
| factual_verifier.py | Web search & SymPy proof verification (Layer 3) | ✅ Active |
| code_validator.py | AST syntax, path, URL validator (Layer 4) | ✅ Active |
| output_validator.py | Multi-model consensus, confidence scoring (Layer 5) | ✅ Active |
| error_pattern_db.py | SQLite error logging & prevention (Meta-Layer) | ✅ Active |
| audit_logger.py | AI decision & OTP verification tamper-proof audit trail | ✅ Active |
| config.py | Env config via pydantic-settings | ✅ Active |
| gcp_firestore.py | Firestore verification queue with SQLite fallback | ✅ Active |
| gcp_pubsub_queue.py | Pub/Sub task queue with SQLite fallback | ✅ Active |
| telemetry.py | OpenTelemetry distributed tracing integration | ✅ Active |
| universal_rules.py | Centralized universal rules enforcement engine | ✅ Active |
| upstash_redis_queue.py | Upstash Redis shared distributed queue | ✅ Active |
| schema_validator.py | Pydantic schema validation with retry logic | ✅ Active |
| secure_credential_store.py | Encrypted credential storage | ✅ Active |
| auth_middleware.py | JWT-based API authentication | ✅ Active |
| rate_limiter.py | IP/user-based rate limiting | ✅ Active |
| rbac.py | Role-based access control | ✅ Active |
| circuit_breaker.py | Cascade failure prevention circuit breaker | ✅ Active |
| task_queue.py | Celery/async task queue management | ✅ Active |
| task_router.py | Intelligent task classification and routing | ✅ Active |
| intent.py | User intent classification | ✅ Active |
| language_router.py | Multi-language detection and routing | ✅ Active |
| observability_middleware.py | Request tracking & observability | ✅ Active |
| feedback_loop.py | AI feedback signal collection | ✅ Active |
| evolution_engine.py | Self-evolution & pattern learning engine | ✅ Active |
| mcp_allowlist.py | MCP tool allowlist security filter | ✅ Active |

## Dynamic Skills (`supremeai_2.0/skills/dynamic/`)

| Skill | Purpose | Status |
|---|---|---|
| csv_exporter.py | Excel & CSV file generator/exporter | ✅ Active |
| text_summarizer.py | Dynamic text summarization | ✅ Active |
| web_scraper.py | Dynamic HTML content extractor | ✅ Active |

## API Routes (`supremeai_2.0/api/routes/`)

| Route | Purpose | Status |
|---|---|---|
| task.py | Main task execution endpoint | ✅ Active |
| stream.py | SSE real-time streaming | ✅ Active |
| browser.py | Browser control API | ✅ Active |
| simulator.py | App simulator preview API | ✅ Active |
| memory.py | Memory management API | ✅ Active |
| knowledge.py | Knowledge base API | ✅ Active |
| marketplace.py | Skill marketplace (search/install) | ✅ Active |
| metrics.py | Prometheus metrics endpoint | ✅ Active |
| media.py | Media (image/video/audio) generation API | ✅ Active |
| codeflow.py | Code analysis flow API | ✅ Active |
| agent_tasks.py | Agent task orchestration API | ✅ Active |
| admin_dashboard.py | Admin dashboard & monitoring | ✅ Active |
| feedback.py | User feedback collection | ✅ Active |
| auth.py | Authentication & token management | ✅ Active |

## Integrations

| Interface | Type | Status |
|---|---|---|
| supremeai-vscode-extension | VS Code extension (TypeScript) | ✅ Built (v6.0.0 .vsix packaged) |
| Flutter Mobile App | Mobile interface | ✅ Migrated |
| interfaces/telegram_bot.py | Telegram bot handler | ✅ Active |
| interfaces/discord_bot.py | Discord bot | ✅ Active |
| interfaces/voice.py | Voice STT/TTS (Whisper API + gTTS) | ✅ Active |
| interfaces/cli.py | CLI interface (typer) | ✅ Active |
| interfaces/web_chat/ | Web chat interface | ✅ Active |

## Brain & Routing Modules (`supremeai_2.0/brain/`)

| Module | Purpose | Status |
|---|---|---|
| model_router.py | Model routing based on tier/cost/speed | ✅ Active |
| model_registry.py | Model metadata profile and registry | ✅ Active |
| swarm_orchestrator.py | Async swarm orchestrator | ✅ Active |
| langgraph_agent.py | State-machine based SupremeOrchestrator | ✅ Active |
| crewai_agents.py | Role-based CrewAgent and CrewTask | ✅ Active |
| parallel_cloud_router.py | Multi-cloud active-active routing logic | ✅ Active |
| gcp_router.py | GCP Cloud Run health check and task routing | ✅ Active |
| mcp_client.py | Model Context Protocol tool client | ✅ Active |
| autonomous_agent.py | Fully autonomous long-running agent | ✅ Active |
| agent_department.py | Specialized agent department manager | ✅ Active |
| agent_departments.py | Multi-department agent registry | ✅ Active |
| reasoning_orchestrator.py | Advanced reasoning pipeline orchestrator | ✅ Active |
| nine_router.py | 9Router cost/speed optimization | ✅ Active |
| api_router.py | Brain API routing layer | ✅ Active |

## Memory Modules (`supremeai_2.0/memory/`)

| Module | Purpose | Status |
|---|---|---|
| long_term_memory.py | Conversation history & learned facts (SQLite/Postgres) | ✅ Active |
| episodic_memory.py | Recent interaction learning | ✅ Active |
| chromadb_store.py | ChromaDB vector store | ✅ Active |
| sqlite_store.py | SQLite local state store | ✅ Active |
| sliding_window.py | Large doc sliding window memory | ✅ Active |
| checkpoint_resume.py | Long-task state checkpoint/resume | ✅ Active |
| rag_pipeline.py | RAG retrieval pipeline | ✅ Active |
| supabase_store.py | Supabase cloud state store | ✅ Active |
| vector_store_config.py | Vector store configuration | ✅ Active |

## Other Core Files

| File | Purpose | Status |
|---|---|---|
| skill_loader.py | Runtime skill discoverer/loader/installer | ✅ Active |

## Test Suite (`supremeai_2.0/tests/`)

**34 test files | 127+ test functions | 125 passed, 2 skipped** ✅

---
*Last Synced: 2026-06-20 (Full project re-audit — all new modules discovered and catalogued)*

<!-- Synced: 2026-06-20 (Full project re-audit — 34 test files, all new tools/brain/core/memory/API routes catalogued) -->
