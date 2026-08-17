# গাইডলাইন ০২ — টেস্টিং স্ট্র্যাটেজি

> **স্তর:** নতুন থেকে অভিজ্ঞ সকল ডেভেলপার
> **প্রযোজ্য:** Python/FastAPI backend + React/TypeScript frontend

---

## ২.১ — টেস্টের তিনটি স্তর (Testing Pyramid)

```
         /\
        /E2E\          ← কম (ধীর, ভঙ্গুর, ব্যয়বহুল)
       /------\
      /Integr. \       ← মাঝারি (API endpoint, DB interaction)
     /----------\
    /  Unit Tests \    ← বেশি (দ্রুত, নির্ভরযোগ্য, সস্তা)
   /--------------\
```

**নিয়ম:** Unit > Integration > E2E — এই অনুপাত বজায় রাখুন।

---

## ২.২ — ফাইল কোথায় রাখবেন

```
backend/
└── tests/
    ├── conftest.py              ← shared fixtures (ONLY এখানে)
    ├── __init__.py
    ├── core/
    │   ├── __init__.py          ← আবশ্যক প্রতি subfolder-এ!
    │   └── test_config.py       ← core/ মডিউলের টেস্ট
    ├── api/
    │   ├── __init__.py
    │   └── test_admin.py
    ├── middleware/
    │   ├── __init__.py
    │   └── test_anti_hacking.py
    └── test_health.py           ← top-level integration smoke test

apps/studio-client/
└── src/
    └── components/
        ├── Button.tsx
        └── Button.test.tsx      ← component-এর পাশে (colocated)
```

### ⚠️ দুটো test root রাখবেন না

```
# ❌ WRONG — দুইটা root conftest আলাদা mock strategy ব্যবহার করলে conflict হয়
/tests/conftest.py        (sys.modules['core'] = MagicMock())
/backend/tests/conftest.py (sys.path তে backend/ যোগ করে real import করে)

# ✅ CORRECT — একটাই test root
/backend/tests/conftest.py  ← সবকিছু এখানে
```

---

## ২.৩ — `conftest.py` — সঠিক প্যাটার্ন

```python
# backend/tests/conftest.py
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import importlib.machinery
import pytest

# backend/ কে sys.path এ যোগ করুন — "from core.config import settings" কাজ করবে
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# External SDK গুলো mock করুন — CI তে install নাও থাকতে পারে
def create_mock_module(name, is_package=False):
    m = MagicMock()
    m.__spec__ = importlib.machinery.ModuleSpec(name=name, loader=MagicMock(), is_package=is_package)
    if is_package:
        m.__path__ = []
    return m

sys.modules["pinecone"] = create_mock_module("pinecone", is_package=True)
sys.modules["chromadb"] = create_mock_module("chromadb", is_package=True)
sys.modules["nats"] = create_mock_module("nats", is_package=True)
# নতুন external SDK যোগ করলে এখানে mock যোগ করুন

# Test env defaults — settings.<field> টেস্টে None হবে না
_TEST_ENV_DEFAULTS = {
    "TESTING": "True",
    "ENVIRONMENT": "test",
    "DATABASE_URL": "sqlite:///./test.db",
    "REDIS_URL": "redis://mocked-redis-url",
    "SECRET_KEY": "test-secret-key-minimum-32-characters",
    # নতুন env var যোগ করলে এখানে placeholder দিন
}

@pytest.fixture(autouse=True)
def isolate_env():
    """প্রতিটা টেস্টের আগে env সেট করুন, পরে রিস্টোর করুন।"""
    originals = {k: os.environ.get(k) for k in _TEST_ENV_DEFAULTS}
    for k, v in _TEST_ENV_DEFAULTS.items():
        os.environ.setdefault(k, v)
    yield
    for k, v in originals.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
```

---

## ২.৪ — Mock করার সঠিক নিয়ম

### নিয়ম: Importing namespace-এ patch করুন, definition namespace-এ নয়

```python
# middleware/anti_hacking.py এ লেখা আছে:
from core.cache import redis_manager

# ❌ WRONG — definition জায়গায় patch (কাজ করবে না)
with patch('core.cache.redis_manager') as mock:
    ...

# ✅ CORRECT — importing module-এর namespace-এ patch
with patch('middleware.anti_hacking.redis_manager') as mock:
    mock.get_cache = AsyncMock(return_value=None)
    mock.set_cache = AsyncMock()
    ...
```

### Redis mock pattern

```python
@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    with patch('middleware.anti_hacking.redis_manager') as mock_redis:
        mock_redis.get_cache = AsyncMock(return_value="5")  # 5 attempts already
        mock_redis.set_cache = AsyncMock()

        with patch('middleware.anti_hacking.settings') as mock_settings:
            mock_settings.max_attempts = 3
            mock_settings.enforce_mode = True

            result = await check_rate_limit("192.168.1.1")
            assert result is False  # blocked
```

### Settings mock pattern

```python
# ❌ WRONG — real settings object কে ভুল attribute দিচ্ছে
mock_settings.enforce_anti_hacking = MagicMock(return_value=False)

# ✅ CORRECT — simple value assignment
mock_settings.enforce_anti_hacking = False
mock_settings.otp_cooldown_seconds = 60
```

---

## ২.৫ — Async টেস্ট

```python
# pyproject.toml-এ asyncio_mode = "auto" থাকলে decorator ছাড়াও চলে
# কিন্তু consistency-র জন্য explicitly লিখুন:

import pytest

@pytest.mark.asyncio
async def test_something_async():
    result = await some_async_function()
    assert result == expected

# FastAPI endpoint টেস্ট — async httpx client ব্যবহার করুন
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_api_endpoint(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
```

---

## ২.৬ — Auth-protected Endpoint টেস্ট

```python
from backend.api.dependencies import get_current_user_token
from backend.main import app

def test_admin_endpoint_authorized(client):
    # admin role দিয়ে override
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin@test.com",
        "role": "admin"
    }
    resp = client.get("/api/admin/dashboard")
    assert resp.status_code == 200
    app.dependency_overrides = {}  # ← টেস্ট শেষে অবশ্যই reset করুন!

def test_non_admin_blocked(client):
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "user@test.com",
        "role": "user"
    }
    resp = client.post("/api/admin/action")
    assert resp.status_code == 403
    app.dependency_overrides = {}  # ← reset!
```

### ⚠️ dependency_overrides reset না করলে পরের টেস্টে leak হবে

---

## ২.৭ — Coverage নিয়ম

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=core --cov-fail-under=75"

[tool.coverage.run]
source = ["core"]
omit = ["*/tests/*", "*/migrations/*", "*/alembic/*"]
```

**নিয়ম:**
- নতুন function = কমপক্ষে ১টা happy-path + ১টা error-path টেস্ট
- `if/else` দুই branch-ই টেস্ট করুন
- 75% coverage threshold — এর নিচে CI fail করবে

```bash
# লোকাল coverage দেখুন
cd backend
poetry run pytest --cov=core --cov-report=term-missing -q
```

---

## ২.৮ — Frontend টেস্ট (Vitest)

```typescript
// Button.test.tsx — component-এর পাশে রাখুন
import { render, screen } from '@testing-library/react'
import { Button } from './Button'

describe('Button', () => {
  it('renders with label', () => {
    render(<Button label="Click me" />)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const handleClick = vi.fn()
    render(<Button label="Submit" onClick={handleClick} />)
    await userEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledOnce()
  })
})
```

### ⚠️ "Found multiple elements" এড়ানো

```typescript
// ❌ WRONG — UI তে "Submit" text একাধিকবার থাকলে fail
screen.getByText('Submit')

// ✅ CORRECT — role দিয়ে specific করুন
screen.getByRole('button', { name: 'Submit' })
// অথবা data-testid ব্যবহার করুন
screen.getByTestId('submit-button')
```

---

## ২.৯ — PR পাঠানোর আগে লোকাল চেকলিস্ট

```bash
# Backend
cd backend
poetry run pytest -n auto --dist=loadfile --timeout=120 -q
poetry run pytest --cov=core --cov-report=term-missing --cov-fail-under=75 -q

# Frontend
pnpm --dir apps/studio-client exec vitest run
```

- [ ] নতুন function-এর জন্য positive + negative টেস্ট আছে
- [ ] নতুন env var `_TEST_ENV_DEFAULTS`-এ placeholder দেওয়া হয়েছে
- [ ] নতুন external SDK `sys.modules` mock-এ যোগ করা হয়েছে
- [ ] টেস্ট ফাইল `backend/tests/` এ রাখা হয়েছে, root `tests/`-এ নয়
- [ ] নতুন subfolder-এ `__init__.py` আছে
- [ ] `app.dependency_overrides` ব্যবহার করলে শেষে reset করা হয়েছে
- [ ] Parallel run (`-n auto`) এ টেস্ট করা হয়েছে — race condition ধরা পড়ে
