# SupremeAI 2.0 — Separate Test Environment
## Isolated testing configs for unit, integration, and staging

_Status: ACTIVE_
_Last Updated: 2026-06-22_

---

## 1. Environment Files

| File | Purpose |
|------|---------|
| `.env.test` | Unit tests (local, no external APIs required) |
| `.env.integration` | Integration tests (requires Supabase/Redis) |
| `.env.staging` | Staging deployment (GCP Cloud Run staging service) |
| `.env.production` | Production (never committed) |

## 2. `.env.test` Template
```env
ENV=test
DEBUG=true
JWT_SECRET=test-secret-do-not-use-in-production
OPENROUTER_API_KEY=
GEMINI_API_KEY=
SENTRY_DSN=
SUPABASE_URL=
SUPABASE_KEY=
```

## 3. pytest.ini / pyproject.toml Test Config
```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "integration: requires external services",
    "slow: tests taking >5s",
    "unit: fast isolated tests",
]
```

## 4. CI Test Matrix (GitHub Actions)
```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12"]
    os: ["ubuntu-latest", "windows-latest", "macos-latest"]
```

## 5. Test Isolation Rules
- Unit tests must not require network or database
- Integration tests require `INTEGRATION=1` env flag
- E2E tests require Docker Compose stack running
- Test data uses `backend/tests/fixtures/` (not `data/`)

---

_Next Review: 2026-07-22_
