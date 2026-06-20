# 📊 Installed Dependencies in SupremeAI 2.0

*Last updated: 2026-06-19*

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
| playwright | >=1.60.0 | Browser automation for signups |
| google-cloud-firestore | >=2.16.0 | Firestore verification queue |
| google-cloud-pubsub | >=2.27.0 | GCP Pub/Sub task queue |
| firebase-admin | >=7.4.0 | Firebase admin integration and testing |

## Runtime-Verified Installations (2026-06-20)

All 25 packages (including `requirements.txt` packages and manual installations) are installed and verified:
- `playwright` — installed and browser binaries (chromium) initialized.
- `sentry-sdk` — installed (fixes test collection in `tests/test_api.py`)
- `matplotlib` — installed (fixes test collection in `tests/test_monitoring.py`)
- `discord.py` — installed (fixes test collection in `tests/test_new_interfaces.py`)
- `openpyxl` — installed (fixes `test_local_ocr_extractor` Excel export test)
- `firebase-admin` — installed and verified (fixes integration tests)
- `@testing-library/dom` — installed in React Studio Client frontend for unit testing.

## Test Status

**125 passed, 2 skipped (total 127 functions)** with all dependencies installed (including Playwright, E2E, Firebase and GCP integration tests).

## Missing Dependencies (From Code Imports Analysis)
The following dependencies were used in the codebase but were missing from `requirements.txt`. They have now been added:
* `typer>=0.12.0` ✅
* `rich>=13.0.0` ✅
* `celery>=5.4.0` ✅
* `redis>=5.0.0` ✅
* `google-cloud-firestore>=2.16.0` ✅
* `google-cloud-pubsub>=2.27.0` ✅
* `pytest>=8.0.0` ✅
* `pytest-anyio>=4.0.0` ✅

---
*Last Synced with supremeai_1.0 Reusable Options Analysis: 2026-06-20 (Firebase Deployed)*

<!-- Synced with Rule Update: 2026-06-20 (Bangla Pro Tips Rule added) -->

<!-- Synced with Project Status Update: 2026-06-20 (React Studio Client Modularized) -->

<!-- Synced with Backend Optimization Update: 2026-06-20 (Backend production-ready optimized) -->

<!-- Synced with CI/CD Fix: 2026-06-20 (Pytest PYTHONPATH issue resolved in workflow) -->
