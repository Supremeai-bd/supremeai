# গাইডলাইন ০৩ — CI/CD পাইপলাইন

> **স্তর:** Junior থেকে Senior ডেভেলপার
> **প্রযোজ্য:** GitHub Actions, যেকোনো Python/Node.js মনোরেপো

---

## ৩.১ — CI/CD এর মূল নীতি

> "CI-তে যা ফেল করে, production-এ ডিপ্লয় হয় না।"

একটি সুস্থ CI পাইপলাইন মানে:
1. **Fast feedback** — 10 মিনিটের মধ্যে ফেল/পাস জানা
2. **Deterministic** — একই কোড, একই ফলাফল — সবসময়
3. **No secrets in logs** — env var কখনো print হয় না
4. **Fail loud** — silent failure নেই; fail হলে স্পষ্টভাবে fail

---

## ৩.২ — Workflow ফাইল স্ট্রাকচার

```yaml
# .github/workflows/backend-ci.yml
name: 🐍 Backend CI

on:
  push:
    branches: [main, develop]
    paths:
      - 'backend/**'         # শুধু backend পরিবর্তনে run হবে
      - '.github/workflows/backend-ci.yml'
  pull_request:
    branches: [main]
    paths:
      - 'backend/**'

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend    # ← সব step এই directory থেকে

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: '1.7.1'
          virtualenvs-in-project: true   # ← .venv/ প্রজেক্টের ভেতরে

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: backend/.venv
          key: venv-${{ runner.os }}-${{ hashFiles('backend/poetry.lock') }}

      - name: Install dependencies
        run: poetry install --no-interaction --no-ansi

      - name: Run tests
        run: |
          poetry run pytest \
            -n auto \
            --dist=loadfile \
            --timeout=120 \
            --cov=core \
            --cov-report=json:coverage.json \
            --cov-report=term-missing \
            --cov-fail-under=75 \
            -q
```

---

## ৩.৩ — সবচেয়ে বড় CI ভুলগুলো

### ভুল ১ — `working-directory` এবং `testpaths` সামঞ্জস্যহীন

```yaml
# CI তে:
working-directory: backend
run: poetry run pytest   # rootdir = backend/

# pyproject.toml তে:
testpaths = ["tests", "backend/tests"]
#                      ↑ এটা রিজলভ হয় backend/backend/tests — নেই!
```

**ফিক্স:**
```toml
testpaths = ["tests"]   # backend/ থেকে চালালে এটাই যথেষ্ট
```

### ভুল ২ — Coverage threshold CI তে আলাদা, local এ আলাদা

```yaml
# CI — 38% দিয়ে পাস করাচ্ছে
--cov-fail-under=38

# pyproject.toml — 75% threshold আছে কিন্তু CI bypass করছে
addopts = "--cov-fail-under=75"
```

**নিয়ম:** একটাই জায়গায় threshold রাখুন — `pyproject.toml` এ। CI command-এ override করবেন না।

### ভুল ৩ — Secret log-এ প্রিন্ট হয়ে যাওয়া

```yaml
# ❌ WRONG
- run: echo "Using key: ${{ secrets.API_KEY }}"

# ✅ CORRECT — GitHub automatically masks secrets in logs
- run: poetry run pytest
  env:
    API_KEY: ${{ secrets.API_KEY }}  # env var হিসেবে পাঠান, echo করবেন না
```

### ভুল ৪ — Fail-open deploy gate

```yaml
# ❌ WRONG — test fail হলেও deploy চলে
- run: poetry run pytest || true

# ✅ CORRECT — test fail হলে deploy বন্ধ
- run: poetry run pytest
# exit code non-zero হলে পরের step চলবে না (GitHub-এর default behavior)
```

---

## ৩.৪ — Dependency Caching (CI দ্রুত করুন)

```yaml
# Poetry (Python)
- name: Cache Poetry venv
  uses: actions/cache@v4
  with:
    path: backend/.venv
    key: venv-${{ runner.os }}-py3.11-${{ hashFiles('backend/poetry.lock') }}
    restore-keys: |
      venv-${{ runner.os }}-py3.11-

# pnpm (Node.js)
- name: Cache pnpm store
  uses: actions/cache@v4
  with:
    path: ~/.pnpm-store
    key: pnpm-${{ runner.os }}-${{ hashFiles('pnpm-lock.yaml') }}
```

**গুরুত্বপূর্ণ:** `key` তে `poetry.lock` / `pnpm-lock.yaml` এর hash দিন — lock file পরিবর্তন হলে cache invalidate হবে।

---

## ৩.৫ — Path-based Job Filtering (অপ্রয়োজনীয় job বন্ধ)

```yaml
# শুধু backend পরিবর্তনে backend test চলবে
on:
  push:
    paths:
      - 'backend/**'
      - '.github/workflows/backend-ci.yml'

# অথবা jobs level-এ condition
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
    steps:
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'backend/**'
            frontend:
              - 'apps/**'

  backend-test:
    needs: detect-changes
    if: needs.detect-changes.outputs.backend == 'true'
    # ...
```

---

## ৩.৬ — Service Container (DB, Redis টেস্টে)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: supremeai_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
        ports:
          - 6379:6379

    steps:
      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/supremeai_test
          REDIS_URL: redis://localhost:6379
        run: poetry run pytest -q
```

**নোট:** Service hostname হয় service name — `postgres`, `redis` — `localhost` নয়। কিন্তু `ports` mapping থাকলে runner থেকে `localhost:5432` দিয়েও access হয়।

---

## ৩.৭ — Deploy Job — সঠিক sequencing

```yaml
jobs:
  test:
    # ... test job

  deploy:
    needs: test          # ← test পাস না হলে deploy হবে না
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production    # ← manual approval gate (optional)

    steps:
      - name: Deploy to Render
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
        # deploy hook URL secrets-এ রাখুন, workflow-এ hardcode নয়
```

---

## ৩.৮ — Workflow PAT Token Scope

GitHub Actions workflow ফাইল push করতে PAT Token-এ `workflow` scope লাগে।

| Token Permission | কোন কাজে লাগে |
|---|---|
| `repo` | code read/write, PR create |
| `workflow` | `.github/workflows/` ফাইল push |
| `packages` | GitHub Container Registry push |
| `read:org` | Organization-level access |

```bash
# নতুন PAT তৈরির সময় check করুন:
# Settings → Developer settings → Personal access tokens → Fine-grained tokens
# Repository permissions: Contents (write) + Workflows (write)
```

---

## ৩.৯ — CI Notification (Discord/Slack)

```yaml
- name: Notify on Failure
  if: failure()
  uses: sarisia/actions-status-discord@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK_URL }}
    status: ${{ job.status }}
    title: "CI Failed on ${{ github.ref_name }}"
    description: |
      Commit: ${{ github.sha }}
      Author: ${{ github.actor }}
```

---

## চেকলিস্ট — নতুন Workflow তৈরির সময়

- [ ] `working-directory` এবং `testpaths` সামঞ্জস্যপূর্ণ
- [ ] Coverage threshold CI এবং pyproject.toml-এ একই
- [ ] Secrets কখনো `echo` বা log-এ প্রিন্ট হয় না
- [ ] Deploy job `needs: test` দিয়ে test-এর উপর নির্ভরশীল
- [ ] `|| true` দিয়ে failure লুকানো হয়নি
- [ ] Service container-এ health check আছে
- [ ] Cache key-এ lock file hash আছে
- [ ] Path filter আছে — সব commit-এ সব job না চলুক
