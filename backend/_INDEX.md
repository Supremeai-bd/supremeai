# backend/ — File Index
> AI: পুরো ফোল্ডার স্ক্যান না করে এই index পড়ুন। প্রয়োজনীয় ফাইলটি খুঁজে সরাসরি যান।

## Entry Points
| File | কী করে |
|---|---|
| `main.py` | FastAPI app entry point, server startup |
| `app.py` | FastAPI app assembly — create_app + middleware + registry mount (moved from `core/app.py`, #683; `core/app.py` = re-export shim) |
| `core/lifespan.py` | Startup/shutdown lifecycle handlers |
| `core/config.py` | All environment settings (Pydantic Settings) |

## Key Directories
| Directory | কী আছে |
|---|---|
| `core/` | App config, middleware, LLM router, health check, security — **সবচেয়ে গুরুত্বপূর্ণ** |
| `api/` | Route handlers — `v1/`, `routes/`, dependencies |
| `services/` | Business logic — memory, LLM, billing, vision, sandbox |
| `models/` | SQLAlchemy DB models |
| `schemas/` | Pydantic request/response schemas |
| `tests/` | pytest test suite |
| `agents/` | AI agent implementations |
| `workers/` | Background task workers |
| `memory/` | Vector memory + context management |

## Core Files (Most Edited)
| File | কী করে |
|---|---|
| `core/config.py` | Settings class — সব env vars এখানে |
| `core/config_secrets.py` | Secret loading from Infisical/env |
| `core/universal_rules.py` | Global business rules (24KB) |
| `core/llm_router.py` | LLM provider routing logic |
| `core/router.py` | Main API router registration |
| `core/health_check.py` | `/health` endpoint logic |
| `core/security/` | JWT, auth, RBAC |
| `core/cost_guard.py` | $0 cost enforcement, budget tracking |
| `services/memory_service.py` | AI memory read/write (19KB) |

> Note (audit 2026-10-10): `services/llm/` was retired by the LLM Gateway Consolidation (#2249) — routing now lives in `core/llm_router.py` / `core/router.py` and the LLM gateway package. The empty package plus stale bytecode was removed.

## Tests
```bash
cd backend && poetry run pytest          # all tests
cd backend && poetry run pytest tests/   # specific folder
```
