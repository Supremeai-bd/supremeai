# গাইডলাইন ০১ — প্রজেক্ট সেটআপ ও রিপোজিটরি স্ট্রাকচার

> **স্তর:** নতুন থেকে অভিজ্ঞ সকল ডেভেলপার
> **প্রযোজ্য:** যেকোনো বড় Python/TypeScript মনোরেপো

---

## ১.১ — রিপো শুরুর আগে যা ঠিক করতে হবে

একটি বড় প্রজেক্ট শুরুর প্রথম দিনেই নিচের সিদ্ধান্তগুলো নিন। পরে পরিবর্তন করা অনেক কঠিন হয়।

### ফোল্ডার কনভেনশন (একবার ঠিক করুন, সারাজীবন মেনে চলুন)

```
supremeai/                    ← repo root
├── backend/                  ← Python/FastAPI backend (একটাই)
│   ├── core/                 ← business logic (testable, no framework dependency)
│   ├── api/                  ← FastAPI routes only (얇게, logic-free)
│   ├── middleware/           ← request/response interceptors
│   ├── models/               ← SQLAlchemy / Pydantic models
│   ├── tests/                ← backend tests (ONLY এখানে, root tests/ নয়)
│   │   ├── conftest.py       ← shared fixtures
│   │   └── <package>/
│   │       ├── __init__.py   ← আবশ্যক!
│   │       └── test_*.py
│   ├── pyproject.toml        ← Python dependency management
│   └── main.py               ← entry point
├── apps/                     ← frontend apps (React, Flutter, etc.)
│   ├── studio-client/        ← React/Vite
│   └── mobile/               ← Flutter
├── packages/                 ← shared code across apps
├── infrastructure/           ← Docker, Terraform, CI config
├── scripts/                  ← utility scripts (dev tools only, not production)
├── docs/                     ← সব documentation
│   └── guidelines/           ← এই ফোল্ডার
└── .github/
    └── workflows/            ← CI/CD
```

### নিয়ম #১ — একটি কাজ একটি জায়গায়

| কাজ | কোথায় যাবে | কোথায় যাবে না |
|---|---|---|
| Business logic | `backend/core/` | `backend/api/routes/` |
| HTTP routing | `backend/api/routes/` | `backend/core/` |
| DB models | `backend/models/` | `backend/core/` |
| Test fixtures | `backend/tests/conftest.py` | প্রতিটা test file-এ আলাদা |
| Config/secrets | `.env` + `core/config.py` | কোনো Python ফাইলে hardcode |
| Scripts/tools | `scripts/` | `backend/core/` |

---

## ১.২ — `pyproject.toml` — শুরু থেকেই সঠিক কনফিগ

```toml
[tool.pytest.ini_options]
# testpaths: CI যেখান থেকে চালায় সেই rootdir-relative path দিন
# backend/ থেকে চালালে → "tests" (মানে backend/tests)
# repo root থেকে চালালে → "backend/tests"
testpaths = ["tests"]

# import-mode=importlib: duplicate filename collision এড়ায়
# (একই নামের test file দুই ফোল্ডারে থাকলেও কাজ করবে)
addopts = "-ra -q --strict-markers --import-mode=importlib --cov=core --cov-fail-under=75"

asyncio_mode = "auto"  # async টেস্টে @pytest.mark.asyncio লাগবে না

filterwarnings = [
    "error",                          # unlisted warning = test failure
    "ignore::DeprecationWarning",
    "ignore::UserWarning",
]
```

### ⚠️ সবচেয়ে বড় ভুল যা শুরুতেই হয়

```toml
# ❌ WRONG — CI working-directory=backend থেকে চালালে এটা backend/backend/tests খোঁজে (নেই!)
testpaths = ["tests", "backend/tests"]

# ✅ CORRECT
testpaths = ["tests"]
```

---

## ১.৩ — `.gitignore` — শুরুতেই সব যোগ করুন

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
.env
*.egg-info/
dist/
build/
.coverage
htmlcov/
coverage.xml
*.log

# Node
node_modules/
.next/
dist/
.turbo/
*.local

# IDE
.vscode/settings.json    # শুধু local settings, extensions.json রাখুন
.idea/
*.swp

# Test artifacts (CI-তে artifact upload করুন, repo-তে না)
pytest-report.md
coverage.json
vitest-report.json

# OS
.DS_Store
Thumbs.db
```

---

## ১.৪ — Git Branch Strategy

```
main          ← production-ready সবসময়, direct push নিষিদ্ধ
develop       ← integration branch
feature/*     ← নতুন feature (feature/auth-otp-flow)
fix/*         ← bug fix (fix/redis-connection-timeout)
hotfix/*      ← production জরুরি fix
chore/*       ← dependency update, refactor
```

### Commit Message Format (Conventional Commits)

```
<type>(<scope>): <কী করা হয়েছে>

বাংলা: <কেন করা হয়েছে এবং কী প্রভাব>
```

**Type:** `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `ci`

```bash
# উদাহরণ
feat(auth): add OTP cooldown throttling

বাংলা: brute-force OTP attack রোধে 60s cooldown যোগ করা হয়েছে।
Redis-এ attempt count store করা হয়, 5 বার fail হলে block।

fix(tests): resolve import mismatch for duplicate test filenames

বাংলা: --import-mode=importlib যোগ করা হয়েছে pyproject.toml-এ।
একই নামের test file দুই ফোল্ডারে থাকলে আগে collection error দিত।
```

---

## ১.৫ — Environment Variable ম্যানেজমেন্ট (শুরু থেকেই)

```bash
# .env.example — repo-তে commit করুন (real value ছাড়া)
DATABASE_URL=postgresql://user:password@localhost:5432/supremeai
REDIS_URL=redis://localhost:6379
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=development

# .env — কখনো commit করবেন না (gitignore-এ আছে)
```

```python
# backend/core/config.py — একটাই Settings class, সব জায়গায় এটাই import
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    environment: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()  # singleton — from core.config import settings
```

**নিয়ম:** কোনো ফাইলে `os.environ["KEY"]` সরাসরি লিখবেন না — সবসময় `settings.key` ব্যবহার করুন।

---

## ১.৬ — Pre-commit Hook (শুরুতেই লাগান)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: detect-private-key          # hardcoded secret ধরবে
      - id: check-added-large-files
        args: ['--maxkb=500']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

```bash
pip install pre-commit
pre-commit install  # প্রতিটা git commit-এ auto-run হবে
```

---

## চেকলিস্ট — প্রজেক্ট শুরুর ১ম দিন

- [ ] ফোল্ডার স্ট্রাকচার উপরের নিয়ম অনুযায়ী
- [ ] `pyproject.toml`-এ `testpaths`, `asyncio_mode`, `filterwarnings` সেট
- [ ] `.gitignore` সম্পূর্ণ
- [ ] `.env.example` তৈরি (real value ছাড়া)
- [ ] `core/config.py`-তে `Settings` class, সব env var এখানে
- [ ] `pre-commit` install করা
- [ ] Branch protection rule: `main`-এ direct push বন্ধ
- [ ] Conventional Commits format টিমে জানানো
