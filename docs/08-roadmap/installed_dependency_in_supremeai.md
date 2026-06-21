# 📊 Installed Dependencies in SupremeAI 2.0

*Last updated: 2026-06-20 (Full project re-audit)*

## Python Dependencies (from requirements.txt)

| Package | Version | Purpose |
|---|---|---|
| fastapi | >=0.111.0 | Web API server |
| uvicorn[standard] | >=0.30.0 | ASGI server |
| httpx | >=0.27.0 | Async HTTP client |
| loguru | >=0.7.2 | Logging |
| pydantic | >=2.7.0 | Data validation |
| pydantic-settings | >=2.2.0 | Env settings |
| python-dotenv | >=1.0.1 | `.env` file loading |
| pyyaml | >=6.0.1 | YAML config |
| tenacity | >=9.0.0 | Retry logic |
| beautifulsoup4 | >=4.12.0 | HTML parsing |
| lxml | >=5.3.0 | XML/HTML parser |
| sentry-sdk[fastapi] | >=2.0.0 | Error monitoring |
| discord.py | >=2.3.0 | Discord bot integration |
| easyocr | >=1.7.0 | OCR engine |
| pandas | >=2.2.0 | Data handling |
| openpyxl | >=3.1.0 | Excel export |
| chromadb | >=0.4.0 | Local vector DB |
| sentence-transformers | >=2.2.0 | Embeddings |
| sympy | >=1.13.0 | Symbolic math |
| pillow | >=10.0.0 | Image processing |
| matplotlib | >=3.8.0 | Chart generation |
| playwright | >=1.60.0 | Browser automation |
| google-cloud-firestore | >=2.16.0 | Firestore verification queue |
| google-cloud-pubsub | >=2.27.0 | GCP Pub/Sub task queue |
| firebase-admin | >=7.4.0 | Firebase admin integration |
| typer | >=0.12.0 | CLI interface |
| rich | >=13.0.0 | Terminal formatting |
| celery | >=5.4.0 | Async task queue |
| redis | >=5.0.0 | Redis client |
| pytest | >=8.0.0 | Test runner |
| pytest-anyio | >=4.0.0 | Async test support |

## Production-Only Dependencies (`requirements-prod.txt`)

- Heavy ML libraries (diffusers, transformers, coqui-tts) are **excluded** from production image.
- Only lightweight runtime dependencies included for fast cold start.

## Dev-Only Dependencies (`requirements-dev.txt`)

- `pytest-cov` — test coverage reporting
- `ruff` — linting/formatting
- Dev-specific packages only used in local dev/test

## Runtime-Verified Installations (2026-06-20)

All packages installed and verified in `.venv`:
- `playwright` — installed, browser binaries (chromium) initialized ✅
- `sentry-sdk` — installed ✅
- `matplotlib` — installed ✅
- `discord.py` — installed ✅
- `openpyxl` — installed ✅
- `firebase-admin` — installed and verified ✅
- `@testing-library/dom` — installed in React Studio Client frontend ✅

## Test Status (2026-06-20 Full Re-audit)

**34 test files | 125 passed, 2 skipped (total 127+ functions)**
All dependencies installed including Playwright, E2E, Firebase and GCP integration tests.

## Missing Dependencies Status

### Planned (Not yet installed — from roadmap)
| Package | Reason Not Installed | Priority |
|---|---|---|
| sse-starlette>=1.8.0 | SSE streaming (may use httpx streaming instead) | 🟡 Medium |
| supabase>=2.5.0 | Shared PostgreSQL (manual account setup needed) | 🔴 High |
| upstash-redis>=1.1.0 | Distributed Redis (manual account setup needed) | 🔴 High |
| openai>=1.35.0 | Latest OpenAI streaming | 🟡 Medium |
| diffusers>=0.28.0 | Stable Diffusion local (dev only) | 🔵 Low |
| transformers>=4.40.0 | Bengali NLP models (dev only) | 🔵 Low |
| coqui-tts>=0.22.0 | Offline Bengali TTS (dev only) | 🔵 Low |
| langchain>=0.2.0 | LangChain agent framework | 🟡 Medium |
| prometheus-client>=0.20.0 | Metrics (Phase 3) | 🟡 Medium |
| python-jose[cryptography] | JWT Auth enhancement | 🟡 Medium |
| opentelemetry-sdk | Distributed tracing (core/telemetry.py) | 🟡 Medium |

---
*Last Synced: 2026-06-20 (Full project re-audit — production/dev split, planned deps categorized)*

<!-- Synced: 2026-06-20 (Full project re-audit — 34 test files, planned deps catalogued) -->

<!-- Synced with Rule Update: 2026-06-20 (Firestore Secrets and Agent Rules consolidated) -->
