# 📊 Installed Dependencies in SupremeAI 2.0

*Last updated: 2026-06-16*

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

## Runtime-Verified Installations (2026-06-16)

All 23 packages (including `requirements.txt` packages and manual installations) are installed and verified:
- `playwright` — installed and browser binaries (chromium) initialized.
- `sentry-sdk` — installed (fixes test collection in `tests/test_api.py`)
- `matplotlib` — installed (fixes test collection in `tests/test_monitoring.py`)
- `discord.py` — installed (fixes test collection in `tests/test_new_interfaces.py`)
- `openpyxl` — installed (fixes `test_local_ocr_extractor` Excel export test)

## Test Status

**48/48 tests passing** with all dependencies installed (including Playwright tests).
