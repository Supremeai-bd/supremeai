# 🛠️ Installed Skills & Tools in SupremeAI 2.0

*Last updated: 2026-06-16*

## Core Tools (`supremeai_2.0/tools/`)

| Tool | Purpose | Status |
|---|---|---|
| multi_account_rotator.py | Multi-account & API key rotation | ✅ Active |
| auto_test_generator.py | Autonomous test file generator | ✅ Active |
| bangla_ai_connector.py | Bengali language connectivity & prompt processor | ✅ Active |
| bengali_ocr_converter.py | Bengali image/document OCR reader | ✅ Active |
| coverage_auditor.py | Test coverage auditing | ✅ Active |
| git_knowledge_extractor.py | Git repo commit & code knowledge extractor | ✅ Active |
| local_ocr_extractor.py | Local OCR engine (EasyOCR + openpyxl export) | ✅ Active |
| local_search_rag.py | Local ChromaDB + search API RAG engine | ✅ Active |
| cot_reasoner.py | Chain-of-Thought reasoning processor | ✅ Active |
| browser_agent.py | Browser automation scripting | ✅ Active |
| computer_agent.py | OS-level automation processor | ✅ Active |
| sync-features.js | Node.js/JS script sync logic | ✅ Active |
| docker_sandbox.py | Sandboxed Docker command execution | ✅ Active |
| cost_auditor.py | SQLite cost & API usage audit reporter | ✅ Active |
| plan_sorter.py | Plan file sorter (Urgent/Feature/Bug) | ✅ Active |
| health_checker.py | Daily dependency & API key status checker | ✅ Active |
| gcp_cloud_functions.py | Google Cloud Functions HTTP trigger client | ✅ Active |

## Core Modules (`supremeai_2.0/core/`)

| Module | Purpose | Status |
|---|---|---|
| input_sanitizer.py | Prompt sanitization, ambiguity filter, PII stripping (Layer 1) | ✅ Active |
| generation_monitor.py | Real-time generation tracker & source attribution (Layer 2) | ✅ Active |
| factual_verifier.py | Web search & SymPy proof verification (Layer 3) | ✅ Active |
| code_validator.py | AST syntax, path, URL validator (Layer 4) | ✅ Active |
| output_validator.py | Multi-model consensus, confidence scoring (Layer 5) | ✅ Active |
| error_pattern_db.py | SQLite error logging & prevention (Meta-Layer) | ✅ Active (timezone fix applied) |
| audit_logger.py | AI decision & OTP verification tamper-proof audit trail | ✅ Active |
| config.py | Env config via pydantic-settings | ✅ Active |
| gcp_firestore.py | Firestore verification queue with SQLite fallback | ✅ Active |
| gcp_pubsub_queue.py | Pub/Sub task queue with SQLite fallback | ✅ Active |

## Dynamic Skills (`supremeai_2.0/skills/dynamic/`)

| Skill | Purpose | Status |
|---|---|---|
| csv_exporter.py | Excel & CSV file generator/exporter | ✅ Active |
| text_summarizer.py | Dynamic text summarization | ✅ Active |
| web_scraper.py | Dynamic HTML content extractor | ✅ Active |

## Integrations

| Interface | Type | Status |
|---|---|---|
| supremeai-vscode-extension | VS Code extension (TypeScript) | ✅ Built (v6.0.0 .vsix packaged) |
| Flutter Mobile App | Mobile interface | ✅ Migrated |
| interfaces/telegram_bot.py | Telegram bot handler | ✅ Active |
| interfaces/discord_bot.py | Discord bot | ✅ Active |
| interfaces/voice.py | Voice STT/TTS (Whisper API) | ⚠️ Stub implemented |
| interfaces/cli.py | CLI interface (typer) | ✅ Active |

## Brain & Routing Modules (`supremeai_2.0/brain/`)

| Module | Purpose | Status |
|---|---|---|
| model_router.py | Model routing based on tier/cost/speed | ✅ Active |
| model_registry.py | Model metadata profile and registry | ✅ Active |
| swarm_orchestrator.py | Async swarm orchestrator | ✅ Active |
| langgraph_agent.py | State-machine based SupremeOrchestrator | ✅ Active |
| crewai_agents.py | Role-based CrewAgent and CrewTask | ✅ Active |
| parallel_cloud_router.py | Multi-cloud active-active routing logic | ⚠️ Pending deployment |
| gcp_router.py | GCP Cloud Run health check and task routing | ✅ Active |

## Other Core Files

| File | Purpose | Status |
|---|---|---|
| skill_loader.py | Runtime skill discoverer/loader/installer | ✅ Active |

## Missing/Pending Modules & Skills (From Code Analysis)
* None (All core framework missing modules resolved)

---
*Last Synced with supremeai_1.0 Reusable Options Analysis: 2026-06-17*

