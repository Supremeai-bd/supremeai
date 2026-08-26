# 🛡️ AI Agent Coding Anti-Pattern Playbook

> **স্রোত:** SupremeAI regression-fixes-zai branch-এ কাজ করার সময় আত্ম-পর্যালোচনা থেকে শিক্ষা নেওয়া
> **উদ্দেশ্য:** ভবিষ্যতে AI agent (বা মানুষ) যাতে একই ভুল না করে, তার জন্য comprehensive checklist
> **ভাষা:** Bangla + English (technical terms)

---

## 📋 বিষয়সূচি

1. [ভাগ ১: আমাদের আসল ভুলগুলো (Self-Inflicted)](#ভাগ-১-আমাদের-আসল-ভুলগুলো)
2. [ভাগ ২: AI Agent-দের সাধারণ ভুল (General Anti-Patterns)](#ভাগ-২-ai-agent-দের-সাধারণ-ভুল)
3. [ভাগ ৩: Verification Checklist (প্রতিটা commit-এর আগে)](#ভাগ-৩-verification-checklist)
4. [ভাগ ৪: AI Agent-কে prompt করার নিয়ম](#ভাগ-৪-ai-agent-কে-prompt-করার-নিয়ম)
5. [ভাগ ৫: SupremeAI Core Directives (অলঙ্ঘনীয় মূলনীতি)](#ভাগ-৫-supremeai-core-directives)

---

## ভাগ ১: আমাদের আসল ভুলগুলো

### ভুল #১: `ast.parse()` কে verification ভাবা ⚠️

**কী হয়েছিল:**
```python
python -c "import ast; ast.parse(open('stream_voice_sse.py').read())"
# → বলল "✅ valid Python"
# কিন্তু import করলেই ক্র্যাশ করত
```

**কেন ভুল:** `ast.parse` শুধু **syntax** ঠিক আছে কিনা দেখে। এটা import resolution, name lookup, runtime behavior কিছুই যাচাই করে না। এটা একটা false positive generator।

**কীভাবে avoid করবেন:**
```python
# ❌ ভুল verification
python -c "import ast; ast.parse(open('file.py').read())"

# ✅ সঠিক verification (actually import করে)
cd backend
python -c "from api.routes.stream_voice_sse import router; print(router.routes)"

# ✅ আরও ভালো: full app boot test
python -c "from core.app import app; print(f'{len(app.routes)} routes loaded')"
```

---

### ভুল #২: Method names "plausible মনে হচ্ছে" ভেবে guess করা 🎲

**কী হয়েছিল:**
- `llm_gateway._stream_completion_iter()` — এমন কোনো method নেই
- `task_queue.subscribe_hitl_events()` — RedisTaskQueue-তে এমন method নেই
- `from services.voice_service import voice_service` — কোনো singleton export নেই, শুধু `VoiceService` class আছে

**কেন ভুল:** LLM-গুলো "common API patterns" থেকে method name অনুমান করে। এটাকে বলে **hallucination** — "এমন method যা থাকা উচিত" বানিয়ে ফেলা।

**কীভাবে avoid করবেন:**
```bash
# Code লেখার আগে সবসময় grep করুন
grep -nE "def (method_name|similar)" backend/path/to/file.py

# Class এর সব methods দেখুন
grep -nE "(def |async def )" backend/services/voice_service.py

# অথবা Python introspection দিয়ে
python -c "
import sys; sys.path.insert(0, 'backend')
from services.voice_service import VoiceService
print([m for m in dir(VoiceService) if not m.startswith('_')])
"

# Import-এর আসল signature দেখুন
head -50 backend/services/voice_service.py
```

---

### ভুল #৩: `git add` করতে ভুলে যাওয়া 📦

**কী হয়েছিল:**
```bash
mv infrastructure/firebase_functions _archive/firebase_functions_removed_$(date)
# কিন্তু commit করার সময়
git add infrastructure/firebase_functions/ firebase.json package.json
# ❌ _archive/ কখনো git add হয়নি!
# ফলে commit message বলছে "archived" কিন্তু diff-এ শুধু deletions আছে
```

**কেন ভুল:** আমি `git status` দেখে verify করিনি commit করার আগে। Assumed যে সব পরিবর্তন staged হয়ে গেছে।

**কীভাবে avoid করবেন:**
```bash
# নিয়ম: commit করার আগে সবসময় status দেখুন
git status

# বা আরও ভালো: --intent-to-add দিয়ে দেখুন কী যাচ্ছে
git diff --cached --stat

# একটা post-commit hook বানিয়ে রাখুন যেটা verify করে
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
# Check if commit message claims "moved" or "archived" but files are missing
if git log -1 --format=%B | grep -qE "(moved|archived)"; then
    FILES_IN_MSG=$(git log -1 --format=%B | grep -oE "_archive/[a-z_]+" || true)
    if [ -n "$FILES_IN_MSG" ]; then
        for f in $FILES_IN_MSG; do
            if [ ! -d "$f" ]; then
                echo "⚠️ Commit message mentions $f but it doesn't exist!"
            fi
        done
    fi
fi
EOF
chmod +x .git/hooks/post-commit
```

---

### ভুল #৪: Rebase-এর পর commit message amend না করা 📝

**কী হয়েছিল:**
```
Conflict resolve করার সময় R11 এর কোড drop করেছি
কিন্তু commit message "fix(R10+R11): ..." পুরনো রয়ে গেছে
ফলে message মিথ্যা বলছে — R11 এর কোনো কোড নেই
```

**কেন ভুল:** `git rebase --continue` করার পর `git commit --amend` করে message ঠিক করা উচিত ছিল। এড়িয়ে গেছি।

**কীভাবে avoid করবেন:**
```bash
# Rebase-এর পর সবসময় commit message আপডেট করুন যদি conflict resolve করে থাকেন
git rebase --continue
# যদি content পরিবর্তন হয় থাকে, message ও আপডেট করুন
git commit --amend -m "fix(R10): register SSE routes only (R11 part dropped — already removed upstream)"

# অথবা rebase-এর সময়ই interactive মোড ব্যবহার করুন
git rebase -i origin/main
# reword / squash দিয়ে message ঠিক করে নিন
```

---

### ভুল #৫: Build/run না করেই push করা 🚀

**কী হয়েছিল:** ৯টা commit push করেছি কিন্তু একবারও `pytest` বা `uvicorn core.app:app` রান করিনি। ফলে runtime errors (যেমন `voice_service` import) ধরা পড়েনি।

**কেন ভুল:** Sandbox-এ dependencies ইনস্টল করা ছিল না (sqlalchemy, fastapi ইত্যাদি), তাই run করা যাচ্ছিল না। এটাকে excuse হিসেবে নিয়েছি।

**কীভাবে avoid করবেন:**
```bash
# Push করার আগে কমপক্ষে এই ৩টা করুন
cd backend && poetry install
poetry run pytest tests/core/test_intent_router.py -v          # unit test
poetry run python -c "from core.app import app; print('OK')"    # boot test
poetry run uvicorn core.app:app --port 8000 &                   # actually run
sleep 5
curl -s http://localhost:8000/health | grep -q "healthy"
kill %1

# যদি sandbox-এ dependencies না থাকে, সেটা জানান — push করা বন্ধ রাখুন
echo "⚠️ Cannot verify in sandbox — please verify in your local env before merge"
```

---

### ভুল #৬: "Claim" বনানো যা diff যাচাই করে না 🎭

**কী হয়েছিল:** commit message বলছে "R11 feature-flagged OFF" কিন্তু diff-এ শুধু SSE route registration আছে, R11 এর কোনো কোড নেই।

**কেন ভুল:** Verifier agents (V-A, V-B, V-C) findings-কে নিশ্চিত করে নিয়েছি — কিন্তু rebase-এর পর আবার verify করিনি।

**কীভাবে avoid করবেন:**
```bash
# প্রতিটা commit message এর সাথে diff মেলান
git show --stat HEAD              # কী পরিবর্তন হয়েছে
git log -1 --format=%B            # message কী বলছে
# দুটো মেলানো আছে কিনা যাচাই করুন

# আরও ভালো: commit করার আগেই message template বানান
git commit -m "fix(RXX): <action>

# Files changed in THIS commit:
# - file1.py: <what changed>
# - file2.py: <what changed>
#
# Verification:
# - <test name>: PASS
# - <import test>: PASS
"
```

---

## ভাগ ২: AI Agent-দের সাধারণ ভুল

নিচের anti-pattern গুলো AI agent-রা সাধারণত করে থাকে। প্রতিটার জন্য চিনহ্তা এবং প্রতিকার দেওয়া হলো।

---

### 🚨 Anti-Pattern ১: Imagined Imports (সবচেয়ে সাধারণ ভুল)

**লক্ষণ:** AI agent এমন import লেখে যা আসলে exists করে না।
```python
# AI লিখেছে
from services.voice_service import voice_service  # ❌ singleton নেই
from utils.helpers import smart_split              # ❌ এমন function নেই
from core.cache import cache                       # ❌ এমন module নেই
```

**কীভাবে ধরবেন:**
```bash
# Import করার আগে verify করুন
grep -E "^(class |def |^[a-z_]+ = )" backend/services/voice_service.py
# class VoiceService:           ← class আছে
# (কোনো singleton export নেই)

# তাহলে সঠিক import:
from services.voice_service import VoiceService
vs = VoiceService()
```

**Prevention rule:** প্রতিটা import statement-এর আগে একটা grep করে দেখুন যে symbol আসলে exists করে কিনা।

---

### 🚨 Anti-Pattern ২: Function Signature Hallucination

**লক্ষণ:** সঠিক function call কিন্তু ভুল arguments।
```python
# আসল signature:
def acompletion(self, prompt, task_type="chat", model=None, stream=False, ...)

# AI লিখেছে (ভুল kwargs):
await llm_gateway.acompletion(
    prompt=prompt,
    intent="chat",           # ❌ এমন kwarg নেই
    streaming=True,           # ❌ নাম ভুল (stream হবে)
    return_iterator=True,     # ❌ এমন kwarg নেই
)
```

**কীভাবে ধরবেন:**
```bash
# Function signature সবসময় দেখে নিন
grep -A 5 "def acompletion" backend/core/llm/llm_gateway.py
# async def acompletion(
#     self,
#     prompt: str | list | None = None,
#     task_type: str = "chat",
#     ...
#     stream: bool = False,
# )

# অথবা inspect ব্যবহার করুন
python -c "
import sys; sys.path.insert(0, 'backend')
from core.llm.llm_gateway import LLMGateway
import inspect
print(inspect.signature(LLMGateway.acompletion))
"
```

---

### 🚨 Anti-Pattern ৩: Wrong File Paths (Path Hallucination)

**লক্ষণ:** AI agent এমন path দেয় যা নেই।
```python
# AI লিখেছে
from backend.core.llm.llm_gateway import llm_gateway   # ❌ backend/ prefix ভুল
# সঠিক (যদি backend/ ই working directory হয়):
from core.llm.llm_gateway import llm_gateway
```

**কীভাবে ধরবেন:**
```bash
# Path লেখার আগে file আছে কিনা দেখুন
ls backend/core/llm/llm_gateway.py
# অথবা project structure দেখুন
find backend -name "llm_gateway.py" -type f
```

---

### 🚨 Anti-Pattern ৪: Database Schema Hallucination

**লক্ষণ:** AI agent এমন table বা column নাম ব্যবহার করে যা নেই।
```python
# AI লিখেছে
await db.execute("SELECT * FROM user_preferences WHERE user_id = $1", user_id)
# ❌ table নাম ভুল — আসলে হয়তো user_prefs বা users_preferences

# AI লিখেছে
class MemoryRecord(Base):
    __tablename__ = "ai_memories"   # ❌ আসলে ai_memory (singular)
```

**কীভাবে ধরবেন:**
```bash
# Migration files থেকে আসল table নাম দেখুন
ls backend/database/migrations/
grep -E "CREATE TABLE" backend/database/migrations/*.sql

# ORM models থেকে দেখুন
grep -E "__tablename__" backend/models/*.py

# অথবা alembic থেকে
ls backend/alembic_migrations/versions/
grep -E "create_table|add_column" backend/alembic_migrations/versions/*.py
```

---

### 🚨 Anti-Pattern ৫: Wrong HTTP Status Codes বা Methods

**লক্ষণ:** AI agent REST endpoint লেখে ভুল method দিয়ে।
```python
# AI লিখেছে
@router.patch("/users/{id}")      # ❌ PATCH হবে না, PUT হবে
async def update_user(...): ...

# AI লিখেছে
@router.get("/users/{id}/delete")  # ❌ DELETE হবে, GET নয়
```

**কীভাবে ধরবেন:**
- Project এর existing route conventions দেখুন
- `grep "@router\." backend/api/routes/ | head -20`
- HTTP method convention অনুসরণ করুন: GET=read, POST=create, PUT=update full, PATCH=update partial, DELETE=delete

---

### 🚨 Anti-Pattern ৬: Circular Import (Silent Killer)

**লক্ষণ:** Import করলে `ImportError: cannot import name X from partially initialized module Y`।
```python
# file_a.py
from file_b import something
def use(): return something()

# file_b.py
from file_a import use          # ❌ circular
def something(): return use()
```

**কীভাবে ধরবেন:**
- Module-level import এড়িয়ে চলুন যখন function-level import কাজ করবে
- `from __future__ import annotations` ব্যবহার করুন type hints এর জন্য
- Lazy import (function এর ভেতরে) ব্যবহার করুন heavy modules এর জন্য
- Test: `python -c "import file_a"` রান করে দেখুন আসলে import হয় কিনা

---

### 🚨 Anti-Pattern ৭: Async/Sync Boundary Confusion

**লক্ষণ:** Sync function কে async context থেকে call করা বা উল্টো।
```python
# ❌ async function এ sync blocking call
async def get_data():
    response = requests.get(url)  # blocks event loop!
    
# ✅ async client ব্যবহার করুন
async def get_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

# ❌ sync function এ await করা
def process(data):
    result = await async_func()  # SyntaxError!

# ✅ asyncio.to_thread দিয়ে wrap করুন
def process(data):
    result = asyncio.run(async_func())
    # অথবা
    result = asyncio.to_thread(sync_func)
```

**কীভাবে ধরবেন:**
- `requests`, `time.sleep`, `os.system`, `subprocess.run` — এগুলো sync, async context এ নিষিদ্ধ
- `httpx.AsyncClient`, `asyncio.sleep`, `asyncio.create_subprocess_exec` — async equivalents
- ESLint/Ruff এ `ASYNC100` rule enable করুন

---

### 🚨 Anti-Pattern ৮: Env Var Assumption

**লক্ষণ:** AI agent এমন env var ব্যবহার করে যা project convention-এ নেই।
```python
# AI লিখেছে
api_key = os.getenv("OPENAI_API_KEY")           # ❌ project convention
api_key = os.getenv("LLM_PROVIDER_KEYS")        # ❌ ভুল key (এটা JSON secret)
api_key = settings.openai_api_key                # ❌ এমন field নেই
```

**কীভাবে ধরবেন:**
```bash
# Settings class দেখুন প্রথমে
grep -E "(openai|anthropic|gemini|api_key)" backend/core/config.py
grep -E "^[a-z_]+: .* = Field" backend/core/config_fields.py

# অথবা env var convention দেখুন
grep -rE "os\.getenv|os\.environ" backend/core/ | head -20
```

---

### 🚨 Anti-Pattern ৯: Wrong ORM Method (Pydantic / SQLAlchemy confusion)

**লক্ষণ:** Pydantic v2 syntax ভুলে Pydantic v1 syntax ব্যবহার করা বা উল্টো।
```python
# ❌ Pydantic v1 syntax in v2 codebase
class MyModel(BaseModel):
    name: str
    
    class Config:
        orm_mode = True         # v2 তে এটা কাজ করবে না

# ✅ Pydantic v2
class MyModel(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True)

# ❌ SQLAlchemy 1.x in 2.x codebase
session.query(User).filter(User.id == 1).first()  # 1.x style

# ✅ SQLAlchemy 2.x
session.execute(select(User).where(User.id == 1)).scalar_one_or_none()
```

**কীভাবে ধরবেন:**
```bash
# Project কোন version ব্যবহার করছে দেখুন
grep -E "(pydantic|sqlalchemy)" backend/pyproject.toml
# অথবা
grep -E "^(pydantic|sqlalchemy)" backend/requirements*.txt

# তারপর ওই version এর docs দেখুন
```

---

### 🚨 Anti-Pattern ১০: Test File Wrong Framework

**লক্ষণ:** pytest style test লেখা unittest project এ বা উল্টো।
```python
# ❌ pytest style in unittest project
def test_something():
    assert func() == expected

# ✅ unittest style
class TestSomething(unittest.TestCase):
    def test_method(self):
        self.assertEqual(func(), expected)
```

**কীভাবে ধরবেন:**
```bash
# Test framework দেখুন
grep -E "(pytest|unittest)" backend/pyproject.toml
ls backend/tests/conftest.py 2>/dev/null && echo "uses pytest"
# অথবা existing tests দেখুন
head -10 backend/tests/core/test_*.py
```

---

### 🚨 Anti-Pattern ১১: Wrong Linting Convention

**লক্ষণ:** Project convention না মেনে নিজের পছন্দের style ব্যবহার করা।
```python
# Project double quotes ব্যবহার করে, AI single দিয়েছে
name = 'user'   # ❌
name = "user"   # ✅

# Project 4-space indent, AI 2-space দিয়েছে
def func():
  return None   # ❌
def func():
    return None  # ✅
```

**কীভাবে ধরবেন:**
```bash
# Project linting config দেখুন
cat backend/pyproject.toml | grep -A 20 "\[tool.ruff\]"
cat backend/.flake8 2>/dev/null
cat backend/.pre-commit-config.yaml 2>/dev/null

# Existing code থেকে convention দেখুন
head -50 backend/core/app.py  # style অনুকরণ করুন
```

---

### 🚨 Anti-Pattern ১২: Fake URL বা Endpoint

**লক্ষণ:** AI agent এমন URL বানায় যা আসলে কাজ করবে না।
```python
# ❌ Banned fake URL
fetch("http://localhost:3000/api/test")           # project rule violation
fetch("http://127.0.0.1:8000/api/v1/users")        # absolute path নিষিদ্ধ

# ✅ Correct relative path
fetch("/api/v1/users")                              # relative path
fetch("/api/test?XTransformPort=3030")              # different port via query
```

**কীভাবে ধরবেন:**
- Project README ও AGENTS.md পড়ুন — সবসময় সেখানে routing convention লেখা থাকে
- `grep -r "fetch\|axios\|http" frontend/src/ | head -20` দিয়ে existing pattern দেখুন

---

### 🚨 Anti-Pattern ১৩: Secrets বা Tokens Commit করা

**লক্ষণ:** API keys, JWT secrets, DB passwords সরাসরি code-এ লেখা।
```python
# ❌ Hardcoded secret
api_key = "sk-proj-abc123..."
db_url = "postgresql://user:pass@host:5432/db"

# ✅ Env var
api_key = os.getenv("OPENAI_API_KEY")
db_url = settings.database_url
```

**কীভাবে ধরবেন:**
```bash
# Pre-commit hook দিয়ে detect করুন
pip install detect-secrets
detect-secrets scan backend/

# অথবা gitleaks ব্যবহার করুন
gitleaks detect --source backend/

# CI তে যোগ করুন
# .github/workflows/ci.yml
# - name: Secret scan
#   run: gitleaks detect --source .
```

---

### 🚨 Anti-Pattern ১৪: Reinventing Existing Utility

**লক্ষণ:** Project এ ইতিমধ্যে function আছে, AI জানে না এবং নতুন বানায়।
```python
# Project এ আছে
def normalize_prompt(prompt): ...   # backend/core/prompt_handler.py

# AI নতুন বানিয়েছে
def clean_prompt(text):
    # 50 lines of duplicate logic
    ...
```

**কীভাবে ধরবেন:**
```bash
# Function লেখার আগে সবসময় search করুন
grep -rE "def (clean|normalize|format).*prompt" backend/
grep -rE "def (clean|normalize|format).*text" backend/

# অথবা semantic search
grep -rE "(prompt|text).*(clean|normalize|format)" backend/
```

---

### 🚨 Anti-Pattern ১৫: Wrong Test Isolation (Mock vs Real)

**লক্ষণ:** AI agent mock দিয়ে test লেখে কিন্তু mock ভুল signature দেয়।
```python
# ❌ Mock এ wrong return type
@pytest.fixture
def mock_llm():
    m = AsyncMock()
    m.acompletion.return_value = "text"   # ❌ আসলে dict return করে
    return m

# ✅ সঠিক mock
@pytest.fixture
def mock_llm():
    m = AsyncMock()
    m.acompletion.return_value = {
        "success": True,
        "text": "mocked response",
        "model": "test",
        "cost": 0.0,
    }
    return m
```

**কীভাবে ধরবেন:**
- আগে real function এর return type দেখুন (docstring, type hint, existing test)
- Mock signature সেটাই অনুসরণ করুন
- Test রান করে দেখুন pass হয় কিনা

---

### 🚨 Anti-Pattern ১৬: Inventing Config Keys

**লক্ষণ:** AI agent এমন settings field ব্যবহার করে যা Settings class এ নেই।
```python
# ❌ Invented config
if settings.enable_super_ai_mode: ...
if settings.max_concurrent_agents: ...

# ✅ Real config (যদি থাকে)
if settings.enable_tier8: ...
if settings.max_concurrent_tasks: ...
```

**কীভাবে ধরবেন:**
```bash
# Settings class এর সব field দেখুন
grep -E "^[a-z_]+:" backend/core/config.py
grep -E "^[a-z_]+: .* = Field" backend/core/config_fields.py
```

---

### 🚨 Anti-Pattern ১৭: Wrong Package Version Assumption

**লক্ষণ:** AI agent এমন API ব্যবহার করে যা project version এ নেই।
```python
# Project: FastAPI 0.95
# AI লিখেছে (FastAPI 0.100+ feature):
from fastapi import Annotated
def get_user(user: Annotated[User, Depends()]): ...
# ❌ Annotated 0.95 এ নেই
```

**কীভাবে ধরবেন:**
```bash
# Version সবসময় দেখুন
grep -E "(fastapi|pydantic|sqlalchemy|next|react)" backend/pyproject.toml frontend/package.json
# অথবা lockfile থেকে
grep -E "^(fastapi|pydantic|sqlalchemy) " backend/poetry.lock
```

---

### 🚨 Anti-Pattern ১৮: Wrong Decorator Order

**লক্ষণ:** Decorator order ভুল হলে behavior অদ্ভুত হয়।
```python
# ❌ wrong order
@router.get("/users")
@depends_on_auth  # ❌ এটা পরে
async def get_user(user=Depends(get_current_user)): ...

# ✅ correct order
@router.get("/users")
async def get_user(user=Depends(get_current_user)): ...
```

**কীভাবে ধরবেন:**
- Project এর existing routes দেখে pattern অনুসরণ করুন
- FastAPI docs-এ recommended order মেনে চলুন

---

### 🚨 Anti-Pattern ১৯: Breaking Existing Tests

**লক্ষণ:** Code পরিবর্তন করলে আগের tests fail করে।
```bash
# পরিবর্তন আগে
pytest tests/  # all pass

# পরিবর্তন পরে
pytest tests/  # 5 tests fail!
```

**কীভাবে ধরবেন:**
- প্রতিটা commit এর আগে ও পরে full test suite রান করুন
- যদি test fail করে, আগে ঠিক করুন তারপর commit করুন
- `pytest --tb=short -x` দিয়ে fail-fast mode ব্যবহার করুন

---

### 🚨 Anti-Pattern ২০: Not Understanding Free-Tier Constraints

**লক্ষণ:** AI agent এমন code লেখে যা free-tier এ কাজ করবে না।
```python
# ❌ Render free-tier এ crash
@app.on_event("startup")
async def load_heavy_model():
    model = torch.load("10gb_model.pt")  # OOM!

# ❌ 100s concurrent WebSocket connections
@app.websocket("/stream")
async def stream(ws): await ws.accept()  # connection limit hit!
```

**কীভাবে ধরবেন:**
- README ও STATUS.md পড়ুন — "free-tier" বা "zero-cost" শব্দ খুঁজুন
- Memory limit, CPU limit, connection limit সম্পর্কে সচেতন থাকুন
- Background jobs ব্যবহার করুন (Celery) heavy work এর জন্য
- Lazy loading ব্যবহার করুন optional dependencies এর জন্য

---

### 🚨 Anti-Pattern ২১: Misnaming Files (Convention Violation)

**লক্ষণ:** AI agent file এমন নামে save করে যা project convention না।
```
# Project convention: snake_case
backend/api/routes/user_routes.py     # ✅
backend/api/routes/UserRoutes.py      # ❌ PascalCase

# Frontend convention: kebab-case
frontend/src/components/user-card.tsx  # ✅
frontend/src/components/UserCard.tsx   # ❌ (যদি convention kebab-case হয়)
```

**কীভাবে ধরবেন:**
```bash
# Existing file naming দেখুন
ls backend/api/routes/ | head -10
ls frontend/src/components/ | head -10
# সেই pattern অনুসরণ করুন
```

---

### 🚨 Anti-Pattern ২২: Not Reading Project README/docs

**লক্ষণ:** AI agent সরাসরি code লিখতে শুরু করে README/docs না পড়ে।
```
# Project README-এ লেখা:
"IMPORTANT: use api instead of server action."
"IMPORTANT: z-ai-web-dev-sdk MUST be used in the backend!"
"never use bun run build."

# AI এগুলো না পড়ে server action ব্যবহার করে → convention violation
```

**কীভাবে ধরবেন:**
- সবসময় README.md, AGENTS.md, CONTRIBUTING.md, .cursorrules পড়ুন
- Project root এ docs/ folder থাকলে সেটাও দেখুন
- `STATUS.md`, `_INDEX.md`, `.agents/` ইত্যাদি special files খুঁজুন

---

### 🚨 Anti-Pattern ২৩: Wrong Git Branch Strategy

**লক্ষণ:** AI agent সরাসরি main branch-এ push করে।
```bash
# ❌ directly to main
git checkout main
git commit -m "..."
git push origin main

# ✅ feature branch + PR
git checkout -b feature/my-change
git commit -m "..."
git push origin feature/my-change
# তারপর PR open করুন
```

**কীভাবে ধরবেন:**
- Branch protection rules enable করুন main এ
- Pre-commit hook দিয়ে main branch-এ direct commit block করুন
- `git config branch.main.protected true`

---

### 🚨 Anti-Pattern ২৪: Hallucinated Library APIs

**লক্ষণ:** AI agent এমন library API call করে যা ওই version এ নেই।
```python
# ❌ langchain 0.1 API in langchain 0.2 project
from langchain.chat_models import ChatOpenAI  # 0.1
# 0.2 তে:
from langchain_openai import ChatOpenAI

# ❌ Pydantic v1 in v2 project
class M(BaseModel):
    class Config:
        orm_mode = True
# v2:
class M(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

**কীভাবে ধরবেন:**
```bash
# Lockfile থেকে exact version দেখুন
grep -E "^fastapi|^pydantic|^sqlalchemy|^langchain" backend/poetry.lock

# ওই version এর docs/changelog দেখুন breaking changes এর জন্য
```

---

### 🚨 Anti-Pattern ২৫: Not Handling Empty / Null Cases

**লক্ষণ:** AI agent শুধু happy path handle করে।
```python
# ❌ no null check
def get_user_name(user):
    return user.name.upper()  # AttributeError যদি user None হয়

# ✅ defensive
def get_user_name(user):
    if user is None:
        return ""
    return (user.name or "").upper()
```

**কীভাবে ধরবেন:**
- Type hints ব্যবহার করুন (`Optional[User]`, `User | None`)
- Edge cases এর জন্য unit test লেখুন
- `None`, `""`, `[]`, `{}`, `0` — সব falsy value test করুন

---

## ভাগ ৩: Verification Checklist

প্রতিটা commit করার আগে এই checklist অনুসরণ করুন। এটা ২ মিনিট সময় নেবে কিন্তু ৯০% ভুল ধরবে।

### Python (Backend) Checklist

```bash
# 1. Syntax check
python -c "import ast; ast.parse(open('your_file.py').read())"

# 2. Import check (CRITICAL — এটা ast.parse করে না)
cd backend
python -c "from your_module import your_function; print(your_function)"

# 3. Type check (যদি mypy installed থাকে)
mypy your_file.py --strict

# 4. Lint check
ruff check your_file.py
# অথবা
flake8 your_file.py

# 5. Unit test (যদি থাকে)
pytest tests/path/to/test_your_module.py -v

# 6. Full app boot test
python -c "from core.app import app; print(f'{len(app.routes)} routes loaded')"

# 7. Run server briefly
uvicorn core.app:app --port 8000 &
sleep 5
curl -s http://localhost:8000/health
kill %1
```

### TypeScript/React (Frontend) Checklist

```bash
# 1. Type check
cd frontend
pnpm run typecheck

# 2. Lint
pnpm run lint

# 3. Build
pnpm run build

# 4. Test
pnpm run test

# 5. Bundle size check
ls -lh dist/assets/*.js
```

### Git Pre-Commit Checklist

```bash
# 1. কী পরিবর্তন হচ্ছে দেখুন
git status
git diff --cached --stat

# 2. Commit message যাচাই করুন যে diff এর সাথে match করছে
git diff --cached --name-only
# এবং commit message এ যা বলা হয়েছে তা সত্যি হচ্ছে কিনা

# 3. Secrets নেই কিনা দেখুন
git diff --cached | grep -iE "(api_key|secret|password|token)" | grep -v "test\|example\|mock"

# 4. Tests pass করছে কিনা
pytest tests/ -x --tb=short

# 5. সঠিক branch এ আছেন কিনা
git branch --show-current
# main এ থাকলে সরাসরি commit করবেন না
```

---

## ভাগ ৪: AI Agent-কে prompt করার নিয়ম

যদি AI agent দিয়ে code লিখতে চান, তবে prompt-এ এই নিয়মগুলো enforce করুন:

### Rule ১: "GREP before WRITE"

```
PROMPT উদাহরণ:
"Before writing any function call, run grep to verify the function/method exists
with that exact name. Quote the grep output in your response. If you cannot find
the function, ASK me — do not guess."
```

### Rule ২: "IMPORT before CLAIM"

```
PROMPT উদাহরণ:
"After writing each new Python file, run:
   python -c 'from your_module import your_function'
and include the output. If it fails, FIX before continuing."
```

### Rule ৩: "DIFF before COMMIT"

```
PROMPT উদাহরণ:
"Before any git commit, run 'git diff --cached --stat' and verify
that every file mentioned in the commit message actually appears in
the diff. Quote the diff stat in your response."
```

### Rule ৪: "TEST before PUSH"

```
PROMPT উদাহরণ:
"Before pushing, run the test suite and include the summary line
(e.g., '47 passed in 12.3s'). If any test fails, do NOT push."
```

### Rule ৫: "QUOTE existing convention"

```
PROMPT উদাহরণ:
"Before writing any new endpoint, run:
   grep -E '@router\\.' backend/api/routes/ | head -20
and quote 3 existing examples. Match the same decorator pattern,
parameter style, and response format."
```

### Rule ৬: "READ project rules first"

```
PROMPT উদাহরণ:
"Before writing any code, read these files and quote the most
important rule from each:
  - README.md
  - AGENTS.md
  - CONTRIBUTING.md
  - .cursorrules (if exists)
Then explicitly confirm your code follows each rule."
```

---

## সারসংক্ষেপ

| # | Anti-Pattern | One-line Prevention |
|---|---|---|
| ১ | Imagined imports | `grep -E "^class\|^def\|^[a-z_]+ ="` আগে চালান |
| ২ | Wrong function signatures | `inspect.signature()` দিয়ে verify করুন |
| ৩ | Wrong file paths | `ls` বা `find` দিয়ে existence check |
| ৪ | Wrong DB schema | Migration files থেকে দেখুন |
| ৫ | Wrong HTTP methods | Project convention অনুসরণ করুন |
| ৬ | Circular imports | Lazy import ব্যবহার করুন |
| ৭ | Async/sync confusion | `httpx.AsyncClient` async, `requests` sync |
| ৮ | Env var assumption | Settings class থেকে দেখুন |
| ৯ | Wrong ORM version | pyproject.toml থেকে version দেখুন |
| ১০ | Wrong test framework | conftest.py বা existing tests দেখুন |
| ১১ | Wrong linting | Project config দেখুন |
| ১২ | Fake URLs | README তে routing rules পড়ুন |
| ১৩ | Secrets in code | gitleaks / detect-secrets দিয়ে scan |
| ১৪ | Reinventing utility | `grep -r "def"` আগে চালান |
| ১৫ | Wrong mocks | Real return type আগে দেখুন |
| ১৬ | Invented config keys | Settings class থেকে দেখুন |
| ১৭ | Wrong version API | Lockfile থেকে version দেখুন |
| ১৮ | Wrong decorator order | Existing patterns অনুকরণ করুন |
| ১৯ | Breaking tests | Full suite রান করুন commit এর আগে ও পরে |
| ২০ | Free-tier violations | README তে "free-tier" শব্দ খুঁজুন |
| ২১ | Wrong file naming | `ls` দিয়ে convention দেখুন |
| ২২ | Not reading docs | README, AGENTS.md, .cursorrules পড়ুন |
| ২৩ | Direct push to main | Branch protection enable করুন |
| ২৪ | Hallucinated library API | Version-specific docs দেখুন |
| ২৫ | No null handling | Type hints + edge case tests |

---

## 📌 শেষ কথা

আমাদের SupremeAI regression-fixes-zai branch-এ যে ভুলগুলো হয়েছে সেগুলো এই চেকলিস্ট অনুসরণ করলে ৯০% এড়ানো যেত। বিশেষ করে:

- **`ast.parse` কে verification ভাবা** → Import করে verify করলে ধরা যেত
- **Hallucinated method names** → `grep` করে দেখলে ধরা যেত
- **`git add` ভুল** → `git status` দেখলে ধরা যেত
- **Commit message mismatch** → `git diff --cached` দেখলে ধরা যেত

এই playbook টা future AI agents দের system prompt-এ যোগ করলে কাজের মান অনেক বাড়বে।

---

## ভাগ ৫: SupremeAI Core Directives

> **এগুলো শুধু guideline নয় — অলঙ্ঘনীয় (Non-Negotiable) Engineering Laws।**
> প্রতিটি agent, প্রতিটি commit, প্রতিটি code review-এ এই ৮টি principle enforce করতে হবে।
> লঙ্ঘন = automatic rejection।

---

### 🆓 Directive ১: 100% Zero Infrastructure Cost

**মূলনীতি:** প্রতিটি সমাধান Free-Tier-এ চলতে হবে। কোনো paid resource ব্যবহার করা যাবে না।

**Anti-Patterns (কী করা যাবে না):**
```python
# ❌ Paid tier resource assumption
redis_client = Redis(host="redis-premium.example.com")  # paid Redis
model = torch.load("models/llama-70b.pt")               # OOM on Render free
scheduler = celery.beat.PersistentScheduler(db="paid")  # paid persistent

# ❌ Always-on WebSocket without connection limits
@app.websocket("/ws")
async def ws_handler(ws): await ws.accept()  # unlimited connections = crash

# ❌ Storing large files on ephemeral disk
open("/app/cache/model_weights.bin", "wb").write(data)  # ephemeral!
```

**✅ Correct Approach:**
```python
# ✅ Free-tier safe: Upstash Redis (free), Supabase (free), Cloudflare (free)
redis_client = Redis.from_url(settings.upstash_redis_url)

# ✅ Lazy-load small models only, use LLM API instead of local models
async def get_embedding(text: str) -> list[float]:
    return await llm_gateway.embed(text)  # API call, no local model

# ✅ Connection pooling with hard limit
MAX_WS_CONNECTIONS = int(os.getenv("MAX_WS_CONNECTIONS", "50"))
```

**Enforcement Checklist:**
```bash
# কোনো paid service reference নেই কিনা
grep -rE "(premium|pro|paid|enterprise)" backend/ --include="*.py" | grep -v "test\|#"

# Memory-heavy operations নেই কিনা
grep -rE "(torch\.load|model\.fit|pickle\.load)" backend/ --include="*.py"

# Free-tier limits (Render: 512MB RAM, 0.1 CPU)
grep -rE "MAX_WORKERS|worker_count|max_connections" backend/core/config.py
```

---

### ⚡ Directive ২: High Performance — Lightweight & Super Fast

**মূলনীতি:** Response < 200ms (p95)। Memory leak শূন্য। Blocking call নিষিদ্ধ।

**Anti-Patterns:**
```python
# ❌ Synchronous blocking in async context
async def get_user(user_id: str):
    time.sleep(1)                          # blocks event loop!
    result = requests.get(api_url)         # sync HTTP in async!
    return result.json()

# ❌ N+1 query problem
async def get_all_users_with_agents():
    users = await db.execute(select(User))
    for user in users:
        agents = await db.execute(select(Agent).where(Agent.user_id == user.id))  # N+1!

# ❌ Loading entire table into memory
all_records = await db.execute(select(Memory))  # could be millions of rows!
return all_records.fetchall()

# ❌ No caching for repeated expensive calls
async def get_config():
    return await db.execute(select(Config))  # called every request!
```

**✅ Correct Approach:**
```python
# ✅ Async everywhere + connection pooling
async def get_user(user_id: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        result = await client.get(f"{settings.api_base}/users/{user_id}")
    return result.json()

# ✅ Eager loading to prevent N+1
users = await db.execute(
    select(User).options(selectinload(User.agents)).limit(100)
)

# ✅ Pagination always
async def list_memories(page: int = 1, size: int = 20):
    offset = (page - 1) * size
    return await db.execute(select(Memory).limit(size).offset(offset))

# ✅ In-memory cache with TTL (free: functools.lru_cache or cachetools)
from cachetools import TTLCache
_config_cache: TTLCache = TTLCache(maxsize=1, ttl=300)

async def get_config() -> dict:
    if "config" not in _config_cache:
        _config_cache["config"] = await db.execute(select(Config))
    return _config_cache["config"]
```

**Enforcement Checklist:**
```bash
# Sync calls in async functions
grep -rn "requests\." backend/ --include="*.py" | grep -v "test\|#\|httpx"
grep -rn "time\.sleep" backend/ --include="*.py" | grep -v "test\|#"

# Missing pagination
grep -rn "fetchall()\|\.all()" backend/api/ --include="*.py"

# Missing timeout on HTTP calls
grep -rn "AsyncClient()" backend/ --include="*.py" | grep -v "timeout"
```

---

### 🔧 Directive ৩: Self-Healing — Automatic Error Recovery

**মূলনীতি:** সিস্টেম নিজে নিজে recover করবে। কোনো single point of failure থাকবে না।

**Anti-Patterns:**
```python
# ❌ No retry logic
async def call_llm(prompt: str):
    return await llm_gateway.acompletion(prompt)  # fails once = fails forever

# ❌ No fallback provider
async def generate(prompt: str):
    return await openai.complete(prompt)  # OpenAI down = system down!

# ❌ Silent failure — swallowing errors
try:
    await store_memory(data)
except Exception:
    pass  # ❌ error silently lost!

# ❌ No circuit breaker
async def external_api_call():
    return await requests.get(external_url)  # keeps hammering down service
```

**✅ Correct Approach:**
```python
# ✅ Exponential backoff retry (use tenacity — zero cost)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def call_llm_with_retry(prompt: str) -> dict:
    return await llm_gateway.acompletion(prompt)

# ✅ Multi-provider fallback (dynamic from settings)
PROVIDER_PRIORITY: list[str] = settings.llm_provider_priority  # ["gemini", "groq", "together"]

async def generate_with_fallback(prompt: str) -> str:
    for provider in PROVIDER_PRIORITY:
        try:
            return await llm_gateway.acompletion(prompt, provider=provider)
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}, trying next...")
    raise RuntimeError("বাংলা: সব LLM provider ব্যর্থ হয়েছে")

# ✅ Structured error logging — never swallow
try:
    await store_memory(data)
except Exception as e:
    logger.error(f"Memory store failed: {e}", exc_info=True)
    # Inject to self-healing memory for future pattern detection
    await cascade_memory.inject_error_pattern(error=e, context=data)
```

**Enforcement Checklist:**
```bash
# Bare except or pass after except
grep -rn "except.*:\s*$\|except Exception:\s*$" backend/ --include="*.py" -A 1 | grep "pass"

# Missing retry on external calls
grep -rn "await.*gateway\|await.*client\." backend/api/ --include="*.py" | grep -v "retry\|@retry"

# No fallback in LLM calls
grep -rn "acompletion\|generate" backend/ --include="*.py" | grep -v "fallback\|try"
```

---

### 🧬 Directive ৪: Self-Evolution — System Rewrites Itself

**মূলনীতি:** প্রতিটি bug fix, performance gain, নতুন pattern — সিস্টেম নিজে শিখে ভবিষ্যতে apply করে।

**Anti-Patterns:**
```python
# ❌ Fix করো কিন্তু শিখো না
async def fix_bug():
    # just fix, nothing learned
    agent.method = new_method

# ❌ Evolution hardcoded — not dynamic
AGENT_SKILLS = ["skill_a", "skill_b", "skill_c"]  # ❌ hardcoded list!

# ❌ No fitness tracking — কোন agent ভালো কাজ করছে জানা নেই
async def run_agent(agent_id: str, task: str):
    result = await agent.run(task)
    return result  # no metrics recorded!

# ❌ New capability manually written only — no zero-gap pipeline
# "I'll manually add new features" — AI হাতে না লিখলে হবে না
```

**✅ Correct Approach:**
```python
# ✅ Post-fix DB injection — শেখা জ্ঞান pgvector-এ সংরক্ষণ
async def apply_fix_and_learn(error_pattern: str, fix_snippet: str, root_cause: str):
    # Fix apply করো
    await apply_fix(fix_snippet)
    # শেখা pgvector-এ inject করো
    await cascade_memory.inject({
        "type": "self_heal_lesson",
        "error_pattern": error_pattern,
        "root_cause": root_cause,
        "fix_snippet": fix_snippet,
        "timestamp": datetime.utcnow().isoformat(),
    })
    # LESSONS_LEARNED.md-তেও লিখে রাখো
    await append_lesson(root_cause=root_cause, fix=fix_snippet)

# ✅ Dynamic skill registry — no hardcoded lists
async def get_active_skills() -> list[str]:
    """DB থেকে dynamically skill list নাও"""
    result = await db.execute(
        select(Skill.name).where(Skill.is_active == True).order_by(Skill.fitness_score.desc())
    )
    return [row.name for row in result]

# ✅ Fitness tracking after every agent run
async def run_agent_with_tracking(agent_id: str, task: str) -> dict:
    start = time.monotonic()
    try:
        result = await agent.run(task)
        latency_ms = (time.monotonic() - start) * 1000
        await metrics.record(agent_id=agent_id, success=True, latency_ms=latency_ms)
        return result
    except Exception as e:
        await metrics.record(agent_id=agent_id, success=False, error=str(e))
        raise
```

**Enforcement Checklist:**
```bash
# Hardcoded skill/agent/provider lists
grep -rn "\[\".*\",.*\".*\"\]" backend/agents/ --include="*.py" | grep -v "test\|#"

# Missing fitness recording after agent run
grep -rn "await.*\.run(" backend/agents/ --include="*.py" -A 3 | grep -v "metrics\|record\|fitness"

# Missing LESSONS_LEARNED update after bug fix
grep -rn "def.*fix\|def.*repair\|def.*heal" backend/ --include="*.py" | grep -v "lesson\|memory\|inject"
```

---

### 🤖 Directive ৫: Automatic Learning — Better Every Interaction

**মূলনীতি:** প্রতিটি ইউজার interaction থেকে শেখা হবে। কোনো কথোপকথন নষ্ট হবে না।

**Anti-Patterns:**
```python
# ❌ User feedback collect করো না
async def chat(message: str) -> str:
    response = await llm.generate(message)
    return response  # feedback? কোথায়?

# ❌ Context/preference হারিয়ে যাওয়া
async def new_session(user_id: str):
    # fresh start every time — user আগে কী চাইত মনে নেই!
    return ConversationHistory(messages=[])

# ❌ Learning শুধু explicit feedback-এ — implicit signals ignore
# "thumbs up হলেই শিখব, otherwise না"

# ❌ Same mistake বারবার (no error memory)
async def handle_error(e: Exception):
    logger.error(str(e))  # log করলাম, শিখলাম না!
```

**✅ Correct Approach:**
```python
# ✅ Implicit + Explicit learning signals
async def post_interaction_learning(
    user_id: str,
    query: str,
    response: str,
    latency_ms: float,
    feedback_score: float | None = None,  # explicit: None if not given
) -> None:
    # Implicit signal: response length, latency suggests quality
    quality_estimate = feedback_score if feedback_score else (
        0.8 if latency_ms < 500 else 0.5
    )
    embedding = await llm_gateway.embed(f"{query} → {response}")
    await cascade_memory.upsert({
        "user_id": user_id,
        "query": query,
        "response_summary": response[:200],
        "embedding": embedding,
        "quality": quality_estimate,
        "memory_type": "interaction",
    })

# ✅ Long-term user preference recall
async def get_personalized_context(user_id: str, query: str) -> str:
    """pgvector semantic search থেকে user-র past preference নাও"""
    relevant = await cascade_memory.search(
        query=query,
        user_id=user_id,
        memory_type="preference",
        limit=5,
    )
    if not relevant:
        return ""
    return "\n".join(f"- {m['content']}" for m in relevant)
```

**Enforcement Checklist:**
```bash
# Missing memory/embedding after LLM response
grep -rn "return response\|return result" backend/api/ --include="*.py" -B 5 | grep -v "embed\|memory\|upsert"

# User interactions with no feedback mechanism
grep -rn "async def chat\|async def generate" backend/ --include="*.py" -A 20 | grep -v "feedback\|quality\|learn"
```

---

### 🏭 Directive ৬: Production-Ready Code — Zero Half-Baked

**মূলনীতি:** কোনো `TODO`, `# fix later`, mock data, placeholder — প্রোডাকশন কোডে সম্পূর্ণ নিষিদ্ধ।

**Anti-Patterns:**
```python
# ❌ TODO in production
async def process_payment(amount: float):
    # TODO: implement actual payment processing
    return {"status": "ok"}  # fake!

# ❌ Mock/stub data disguised as real
MOCK_USERS = [{"id": "1", "name": "Test User"}]  # ❌ in production routes!

async def get_users():
    return MOCK_USERS  # ❌

# ❌ Missing defensive programming
async def delete_agent(agent_id: str):
    await db.delete(Agent, agent_id)  # what if agent doesn't exist? no check!

# ❌ No input validation
@router.post("/agents")
async def create_agent(data: dict):  # ❌ raw dict, no Pydantic validation!
    agent = Agent(**data)
```

**✅ Correct Approach:**
```python
# ✅ Defensive + complete implementation
class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Agent নাম")
    model_config: dict = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

@router.post("/agents", status_code=201)
async def create_agent(
    data: CreateAgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """নতুন agent তৈরি করুন"""
    # Duplicate check
    existing = await db.execute(
        select(Agent).where(Agent.name == data.name, Agent.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="বাংলা: এই নামে agent ইতিমধ্যে আছে")

    agent = Agent(
        name=data.name,
        user_id=current_user.id,
        model_config=data.model_config,
        tools=data.tools,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse.model_validate(agent)
```

**Enforcement Checklist:**
```bash
# TODO / FIXME / HACK in production code
grep -rn "TODO\|FIXME\|HACK\|fix later\|temp\|placeholder" backend/ --include="*.py" | grep -v "test\|#.*TODO.*tracked"

# Raw dict in route handlers (no Pydantic)
grep -rn "async def.*data: dict" backend/api/ --include="*.py"

# Missing HTTPException for 404 cases
grep -rn "scalar_one_or_none()\|first()" backend/api/ --include="*.py" -A 2 | grep -v "raise\|if.*None\|404"
```

---

### 📐 Directive ৭: Follow Codebase Lint Format — Zero Deviation

**মূলনীতি:** Project-এর `pyproject.toml` / `.ruff.toml` / `eslint.config.js` — এগুলোই আইন। নিজের style চাপানো নিষিদ্ধ।

**Anti-Patterns:**
```python
# ❌ Ignoring project's ruff config
import os,sys                  # ruff: E401 — multiple imports on one line
x=1                            # ruff: E225 — missing whitespace around operator
def foo( x,y ):                # ruff: E201/E202 — extra spaces in brackets
    if x==None: return         # ruff: E711 — use `is None`
    l = [1,2,3]                # ruff: E231 — missing whitespace after ','

# ❌ Type hints missing (if project enforces them)
def process(data, user, config):  # no types!
    pass

# ❌ Frontend: ignoring ESLint rules
var x = 1                      // ESLint: no-var
console.log(data)              // ESLint: no-console (if configured)
```

**✅ Correct Approach:**
```python
# ✅ Read project config FIRST, then write code
# Step 1: Check lint rules
# cat backend/pyproject.toml | grep -A 30 "[tool.ruff"
# Step 2: Follow them exactly

import os
import sys
from typing import Any

x = 1

def foo(x: int, y: int) -> int:
    if x is None:
        return 0
    items: list[int] = [1, 2, 3]
    return x + y
```

**Pre-commit auto-fix (must run before every commit):**
```bash
# Backend — auto-fix with ruff
cd backend
poetry run ruff check . --fix
poetry run ruff format .

# Type check
poetry run mypy . --ignore-missing-imports

# Frontend — auto-fix
cd ../frontend
pnpm run lint --fix
pnpm run typecheck

# Verify zero lint errors remain
cd ../backend && poetry run ruff check . && echo "✅ Backend lint clean"
cd ../frontend && pnpm run lint && echo "✅ Frontend lint clean"
```

**Enforcement Checklist:**
```bash
# Check current lint errors count
cd backend && poetry run ruff check . --statistics 2>&1 | tail -5
# Should be: 0 errors

# Check type errors
cd backend && poetry run mypy . --ignore-missing-imports --no-error-summary 2>&1 | grep "error:" | wc -l
# Should be: 0
```

---

### 🔄 Directive ৮: Keep Every Value Dynamic — Zero Hardcoding

**মূলনীতি:** Config, limits, thresholds, feature flags, provider lists — সব কিছু DB বা `.env` থেকে নিতে হবে। Code-এ কোনো magic number বা hardcoded string নিষিদ্ধ।

**Anti-Patterns:**
```python
# ❌ Magic numbers scattered in code
if len(messages) > 50:          # ❌ why 50? not configurable!
    summarize_context()

MAX_RETRY = 3                   # ❌ hardcoded in function
time.sleep(1.5)                 # ❌ magic delay

# ❌ Hardcoded provider list
PROVIDERS = ["openai", "anthropic", "gemini"]  # ❌ needs code change to add new

# ❌ Hardcoded feature flags
if user.plan == "pro":          # ❌ plan names hardcoded!
    enable_feature_x()

# ❌ Hardcoded model names
model = "gpt-4-turbo"           # ❌ changes need code deploy!

# ❌ Hardcoded limits
MAX_AGENTS_PER_USER = 10        # ❌ hardcoded business rule
```

**✅ Correct Approach:**
```python
# ✅ All values from settings (loaded from .env / Infisical / DB)
from backend.core.config import settings  # single source of truth

# ✅ Context management
CONTEXT_SUMMARIZE_THRESHOLD: int = settings.context_summarize_threshold  # env: 50

if len(messages) > CONTEXT_SUMMARIZE_THRESHOLD:
    await summarize_context(messages)

# ✅ Dynamic provider list from DB
async def get_llm_providers() -> list[str]:
    result = await db.execute(
        select(LLMProvider.slug)
        .where(LLMProvider.is_active == True)
        .order_by(LLMProvider.priority.asc())
    )
    return [row.slug for row in result]

# ✅ Feature flags from DB — admin dashboard toggleable
async def is_feature_enabled(feature_key: str, user_id: str) -> bool:
    flag = await db.execute(
        select(FeatureFlag).where(
            FeatureFlag.key == feature_key,
            FeatureFlag.is_active == True,
        )
    )
    return flag.scalar_one_or_none() is not None

# ✅ All limits from settings
MAX_AGENTS_PER_USER: int = settings.max_agents_per_user  # env: MAX_AGENTS_PER_USER=10
```

**Enforcement Checklist:**
```bash
# Magic numbers in business logic (not in tests)
grep -rn "[^#]= [0-9]\{2,\}" backend/api/ backend/agents/ --include="*.py" | grep -v "test\|migration\|port\|status_code\|200\|201\|400\|404\|422\|500"

# Hardcoded model names
grep -rn '"gpt-\|"claude-\|"gemini-\|"llama-\|"mistral-' backend/ --include="*.py" | grep -v "test\|config\|#"

# Hardcoded plan/tier names
grep -rn '"pro"\|"free"\|"enterprise"\|"basic"' backend/api/ --include="*.py" | grep -v "test\|config\|#"

# Strings that should be in settings
grep -rn 'os\.getenv("' backend/ --include="*.py" | grep -v "settings\|config\|core/config"
# All env vars should go through settings class, not raw os.getenv scattered everywhere
```

---

## 🚨 সারসংক্ষেপ — Core Directives Quick Reference

| # | Directive | Anti-Pattern Trigger | One-line Fix |
|---|-----------|---------------------|--------------|
| ১ | Zero Cost | paid resource, `torch.load`, unlimited WS | Upstash+Supabase+free APIs only |
| ২ | High Performance | `requests.get` in async, N+1, no cache | `httpx.AsyncClient` + eager-load + TTLCache |
| ৩ | Self-Healing | bare `except: pass`, no retry, no fallback | `@retry` + multi-provider + `cascade_memory.inject` |
| ৪ | Self-Evolution | hardcoded skills, no fitness tracking | DB-driven registry + `metrics.record()` |
| ৫ | Auto Learning | response without embedding, no preference recall | `cascade_memory.upsert()` after every interaction |
| ৬ | Production-Ready | `TODO`, mock data, raw `dict` in routes | Pydantic models + defensive checks + complete impl |
| ৭ | Lint Format | own style, missing types, E-series errors | `ruff check --fix` before every commit |
| ৮ | Dynamic Values | magic numbers, hardcoded model/plan names | `settings.*` for everything |

> **Golden Rule:** কোনো value যদি ভবিষ্যতে পরিবর্তন হওয়ার সম্ভাবনা থাকে — সেটা কখনো code-এ লেখা যাবে না।
> Code change ছাড়া Admin Dashboard থেকে পরিবর্তন করা যাবে কিনা — এটাই পরীক্ষার মানদণ্ড।

---

## ভাগ ৬: Agent Golden Rules (Rules 101–105)

> এই rules গুলো শুধু human developers এর জন্য নয়। **প্রতিটি AI agent** যখন কাজ করে, তখন এই rules তার নিজের system prompt-এ থাকতে হবে — যাতে সে নিজেই জানতে পারে কোন rule সে break করছে।

---

### 🧠 Rule 101: Context Token Budget — 80% Limit

**মূলনীতি:** কোনো agent তার context window-এর ৮০% এর বেশি ব্যবহার করতে পারবে না।

**Anti-Pattern:**
```python
# ❌ Context window-এ সব কিছু গুঁজে দেওয়া
messages = [
    *entire_conversation_history,   # হাজার token!
    *all_codebase_files,            # আরও হাজার!
    *all_tool_results,              # আর ধরে না!
    {"role": "user", "content": prompt}
]
# Result: context overflow → model জবাব দিতে পারে না বা কেটে দেয়
```

**✅ Correct Approach:**
```python
# ✅ Token budget tracking + auto-archive
from backend.engine.compression.token_juice import TokenJuice

MAX_CONTEXT_RATIO = float(settings.max_context_ratio)  # 0.8 = 80%
MODEL_CTX_LIMIT = int(settings.model_context_limit)    # e.g., 128000

async def build_safe_context(history: list, new_message: str) -> list:
    compressor = TokenJuice(model=settings.default_model)
    budget = int(MODEL_CTX_LIMIT * MAX_CONTEXT_RATIO)

    # নতুন message এর token count
    used = compressor.count_tokens(new_message)

    # Budget শেষ হওয়ার আগেই পুরনো messages pgvector-এ archive করো
    safe_history = []
    for msg in reversed(history):
        msg_tokens = compressor.count_tokens(msg["content"])
        if used + msg_tokens > budget:
            # পুরনো context archive করো
            await cascade_memory.archive_conversation_chunk(history[:len(history) - len(safe_history)])
            break
        used += msg_tokens
        safe_history.insert(0, msg)

    return safe_history + [{"role": "user", "content": new_message}]
```

**Enforcement Check:**
```bash
# Context size tracking আছে কিনা
grep -rn "token\|context_limit\|budget" backend/agents/ --include="*.py" | grep -v "test\|#"
```

---

### 🔐 Rule 102: Action Verifiability — HITL for Sensitive Actions

**মূলনীতি:** Agent যেকোনো sensitive action নেওয়ার আগে human confirmation নিতে হবে।

**Sensitive Actions যা HITL দরকার:**
- File write / delete / modify
- External API call (POST/PUT/DELETE)
- Database modification
- Code execution
- Email/notification send
- Git push / deploy trigger

**Anti-Pattern:**
```python
# ❌ Agent নিজেই সরাসরি delete করে ফেলল
async def cleanup_old_agents():
    agents = await db.execute(select(Agent).where(Agent.last_active < cutoff))
    for agent in agents:
        await db.delete(agent)  # ❌ কোনো confirmation নেই!
    await db.commit()
```

**✅ Correct Approach:**
```python
# ✅ HITL queue-এ রাখো, human approve করলে তারপর execute
from backend.services.hitl_service import HITLService

async def request_cleanup_approval(agents_to_delete: list[Agent]) -> str:
    """Sensitive action: HITL approval চাও"""
    request_id = await HITLService.create_request(
        action_type="agent_bulk_delete",
        payload={
            "agent_ids": [a.id for a in agents_to_delete],
            "count": len(agents_to_delete),
            "reason": "Inactive > 30 days",
        },
        priority="medium",
        timeout_minutes=int(settings.hitl_timeout_minutes),
    )
    return request_id  # Frontend-এ notification যাবে

# HITL approved হলে execute করো
async def execute_after_approval(request_id: str):
    approval = await HITLService.get_approved(request_id)
    if approval.status != "approved":
        raise PermissionError("বাংলা: HITL approval ছাড়া এই action নিষিদ্ধ")
    # এখন safe to execute
    await perform_actual_deletion(approval.payload["agent_ids"])
```

---

### 📝 Rule 103: Fail-Safe Memory — Correction Log

**মূলনীতি:** Agent তার আগের ভুল মনে রাখবে এবং সেই ভুল দ্বিতীয়বার করবে না।

**Anti-Pattern:**
```python
# ❌ ভুল করল, log করল, আবার একই ভুল করল
async def try_approach(task: str):
    try:
        result = await use_broken_method(task)
    except Exception as e:
        logger.error(f"Failed: {e}")
        # ভুল শুধু log হলো, memory-তে গেল না
    # পরের বার আবার same broken method try করবে!
```

**✅ Correct Approach:**
```python
# ✅ Correction log in pgvector — ভুল একবারই হবে
async def try_approach_with_memory(task: str, context: dict):
    # আগে দেখো এই pattern-এ আগে ভুল হয়েছে কিনা
    past_failures = await cascade_memory.search(
        query=f"failed approach: {task[:100]}",
        memory_type="correction_log",
        limit=3,
    )
    if past_failures:
        # আগের ভুল থেকে শেখা
        avoided = [f["failed_approach"] for f in past_failures]
        logger.info(f"Avoiding past failures: {avoided}")

    try:
        result = await smart_approach(task, avoid=avoided if past_failures else [])
        return result
    except Exception as e:
        # ভুল pgvector-এ inject করো
        await cascade_memory.inject({
            "memory_type": "correction_log",
            "task_pattern": task[:100],
            "failed_approach": context.get("approach", "unknown"),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        })
        raise
```

---

### 🚫 Rule 104: Zero-Hallucination Policy

**মূলনীতি:** Agent ১০০% নিশ্চিত না হলে কোনো তথ্য invent করবে না।

**Anti-Pattern:**
```python
# ❌ Agent নিজে বানিয়ে বলল — hallucination
async def answer_question(question: str) -> str:
    # "মনে হচ্ছে" এই function আছে
    return f"হ্যাঁ, `user_service.get_premium_status()` call করুন"
    # কিন্তু এই method টা আসলে নেই!
```

**✅ Correct Approach:**
```python
# ✅ Verify before claiming — GREP before WRITE
async def answer_with_verification(question: str) -> str:
    # Step 1: pgvector থেকে semantic search
    known = await cascade_memory.search(query=question, limit=5)

    if not known or max(k["similarity"] for k in known) < float(settings.memory_confidence_threshold):
        # Step 2: নিশ্চিত না → সরাসরি codebase check করো
        return (
            "আমি নিশ্চিত নই। আমাকে codebase-এ search করে verify করতে হবে। "
            "এখনই inventing করা নিষিদ্ধ।"
        )

    # Step 3: শুধু verified info দিয়ে answer করো
    return build_answer_from_verified(known)

# File/method existence check — grep করো, guess করো না
async def verify_method_exists(file_path: str, method_name: str) -> bool:
    """Grep করে verify করো — hallucinate করো না"""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", f"def {method_name}", file_path],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())
```

---

### 🏰 Rule 105: Scope Isolation — Agent Domain Boundaries

**মূলনীতি:** প্রতিটি agent শুধু তার নিজের domain-এ কাজ করবে।

**Anti-Pattern:**
```python
# ❌ Payment agent হঠাৎ code execute করতে চাইল
class PaymentAgent:
    async def process_refund(self, user_id: str):
        # ❌ এই agent-এর কোনো কারণ নেই code execute করার
        await code_interpreter.run("import subprocess; subprocess.run(['ls'])")
        await send_refund(user_id)
```

**✅ Correct Approach:**
```python
# ✅ Domain boundaries enforce via allowed_tools
AGENT_DOMAIN_TOOLS: dict[str, list[str]] = {
    # settings বা DB থেকে load করো — hardcode নয়
}

async def load_agent_domain() -> dict[str, list[str]]:
    result = await db.execute(select(AgentDomainConfig).where(AgentDomainConfig.is_active == True))
    return {row.agent_type: row.allowed_tools for row in result}

class BaseAgent:
    def __init__(self, agent_type: str, allowed_tools: list[str]):
        self.agent_type = agent_type
        self.allowed_tools = allowed_tools  # DB থেকে loaded

    async def use_tool(self, tool_name: str, *args, **kwargs):
        if tool_name not in self.allowed_tools:
            raise PermissionError(
                f"বাংলা: {self.agent_type} agent এর '{tool_name}' tool ব্যবহারের অনুমতি নেই। "
                f"অনুমোদিত tools: {self.allowed_tools}"
            )
        return await TOOL_REGISTRY[tool_name](*args, **kwargs)
```

---

## ভাগ ৭: Real Production Lessons (LESSONS_LEARNED.md থেকে)

> এই section-এর প্রতিটি lesson **আমাদের নিজেদের codebase-এ real bug থেকে** শেখা। ভুলে গেলে আবার একই সমস্যা হবে।

---

### 🔒 Lesson P1: Lock Files Manual Edit সম্পূর্ণ নিষিদ্ধ

**কী হয়েছিল:** CVE fix করতে `poetry.lock`-এ manually version change করা হয়েছিল।
**ফলাফল:** CI-তে `pyproject.toml changed significantly since poetry.lock was last generated` error।

**❌ কখনো করবেন না:**
```bash
# ❌ poetry.lock manually edit করা
sed -i 's/setuptools 48.0.1/setuptools 50.0.0/' poetry.lock

# ❌ pnpm-lock.yaml hex edit
# (যেকোনো lock file manual edit = forbidden)
```

**✅ সঠিক পদ্ধতি:**
```bash
# Backend (Python)
# pyproject.toml এ constraint আপডেট করুন, তারপর:
poetry lock --no-update  # শুধু vulnerable package update
poetry install

# Frontend (Node)
pnpm update <vulnerable-package>
# lockfile auto-update হবে
```

---

### ⏰ Lesson P2: Generated Files-এ Timestamp রাখা নিষিদ্ধ

**কী হয়েছিল:** `generate_types.py`-তে `// Generated: <timestamp>` header ছিল। ফলে প্রতি CI run-এ checksum আলাদা → false drift detection।

**❌ Anti-Pattern:**
```python
# ❌ Timestamp in generated file header
header = f"""// Generated: {datetime.now().isoformat()}
// DO NOT EDIT - auto-generated from backend models
"""
```

**✅ Correct (Deterministic):**
```python
# ✅ Content hash based, no timestamp
import hashlib

def generate_deterministic_header(source_files: list[str]) -> str:
    content_hash = hashlib.md5("".join(source_files).encode()).hexdigest()[:8]
    return f"""// DO NOT EDIT — auto-generated from backend models
// Source hash: {content_hash}
"""
```

---

### 🪟 Lesson P3: PowerShell দিয়ে YAML/UTF-8 File Replace নিষিদ্ধ

**কী হয়েছিল:** PowerShell দিয়ে YAML replace করায় BOM + CRLF + encoding corruption হয়েছিল।

**❌ Never use PowerShell for file operations:**
```powershell
# ❌ PowerShell UTF-8 file write
Set-Content -Path "config.yaml" -Value $content  # BOM corruption!
```

**✅ Always use Python pathlib:**
```python
# ✅ Python pathlib — encoding safe
from pathlib import Path

Path("config.yaml").write_text(content, encoding="utf-8")  # no BOM, no CRLF issue
```

---

### ⚛️ Lesson P4: React setTimeout Stale Closure Bug

**কী হয়েছিল:** `DashboardShell.tsx`-এ `setTimeout` callback-এ stale `activeSessionId` ছিল। দ্রুত session change করলে ভুল tab-এ message যেত।

**❌ Anti-Pattern:**
```typescript
// ❌ Stale closure — activeSessionId captured at creation time
const [activeSessionId, setActiveSessionId] = useState<string>("");

useEffect(() => {
  const timer = setTimeout(() => {
    // activeSessionId এখানে stale হতে পারে!
    updateSession(activeSessionId, response);
  }, 1000);
}, [response]);
```

**✅ useRef দিয়ে latest value track করুন:**
```typescript
// ✅ useRef captures latest value
const activeSessionIdRef = useRef<string>("");
const [activeSessionId, setActiveSessionId] = useState<string>("");

// Sync ref with state
useEffect(() => {
  activeSessionIdRef.current = activeSessionId;
}, [activeSessionId]);

useEffect(() => {
  const timer = setTimeout(() => {
    // Ref always has latest value
    updateSession(activeSessionIdRef.current, response);
  }, 1000);
  return () => clearTimeout(timer);  // cleanup!
}, [response]);
```

---

### 🛡️ Lesson P5: Security Sandbox — Fail-CLOSED, Never Fail-Open

**কী হয়েছিল:** `chaos_worker.py`-তে `fuzz_sandbox` unavailable থাকলে silently skip করে gate unlock (fail-open) হয়ে যেত।

**❌ Fail-Open (Dangerous):**
```python
# ❌ Security check fail হলে তবুও চালিয়ে যাওয়া
async def security_audit(code: str) -> bool:
    try:
        result = await fuzz_sandbox.scan(code)
        return result.is_safe
    except Exception:
        return True  # ❌ FAIL-OPEN — যদি scanner down থাকে, সব allow!
```

**✅ Fail-Closed (Safe):**
```python
# ✅ Security check fail হলে BLOCK করো
async def security_audit(code: str) -> bool:
    try:
        result = await fuzz_sandbox.scan(code)
        return result.is_safe
    except Exception as e:
        logger.critical(f"Security scanner unavailable: {e} — BLOCKING execution")
        # ❌ নিরাপত্তা scanner কাজ না করলে execute BLOCK
        raise SecurityError(
            "বাংলা: Security scanner অনুপলব্ধ — নিরাপত্তার স্বার্থে execution ব্লক করা হয়েছে"
        )
```

---

### 🔄 Lesson P6: Module Refactoring-এর পর Mock Path Update করুন

**কী হয়েছিল:** `browser_agent.py` facade হয়ে গেলে tests-এ পুরনো path-এ `patch()` করা হচ্ছিল → `AttributeError`।

**Rule:**
```bash
# Refactoring-এর পর MUST run:
grep -r "patch(\"old.module.path" backend/tests/ --include="*.py"
# সব occurrences আপডেট করতে হবে নতুন module path-এ

# Example fix:
# Before: patch("tools.browser_agent.is_safe_url")
# After:  patch("core.agents.live.browser_agent.is_safe_url")
```

---

### 🔑 Lesson P7: Secrets Rotation — Register করো, শুধু Generate করলে হবে না

**কী হয়েছিল:** Infisical-এ CLIENT_SECRET generate করা হয়েছিল কিন্তু vault-এ register করা হয়নি → 401 error।

**Checklist — Secrets Rotation:**
```bash
# Step 1: Generate করো
new_secret=$(openssl rand -hex 32)

# Step 2: Infisical vault-এ store করো (API call!)
curl -X POST "https://app.infisical.com/api/v3/secrets/raw" \
  -H "Authorization: Bearer $INFISICAL_TOKEN" \
  -d "{\"secretKey\": \"INFISICAL_CLIENT_SECRET\", \"secretValue\": \"$new_secret\"}"

# Step 3: Render/platform-এ update করো
curl -X PUT "https://api.render.com/v1/services/$SERVICE_ID/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -d "[{\"key\": \"INFISICAL_CLIENT_SECRET\", \"value\": \"$new_secret\"}]"

# Step 4: Verify করো — deploy করার আগে
curl "https://api.render.com/v1/services/$SERVICE_ID/env-vars" | grep "INFISICAL_CLIENT_SECRET"
```

---

## ভাগ ৮: SupremeAI Operating Protocols

> এগুলো **process rules** — code লেখার সময় নয়, agent operate করার সময় follow করতে হবে।

---

### 🎯 Protocol A: Single Definite Root-Cause Rule

**নিষিদ্ধ:** Error হলে "সম্ভাব্য কারণ ১, ২, ৩..." লিস্ট দেওয়া।

**বাধ্যতামূলক:**
```
❌ ভুল উত্তর:
"এই CI failure-এর সম্ভাব্য কারণগুলো হতে পারে:
1. Poetry lock file stale
2. Env var missing
3. Network issue
4. ..."

✅ সঠিক উত্তর (Code trace করে একটি নিশ্চিত কারণ দাও):
"Root Cause: `poetry.lock`-এ `setuptools` manually patch করা হয়েছিল (line 1547)।
এটি `poetry.lock` hash mismatch করায় CI fail করছে।
Fix: `poetry lock --no-update` run করো।"
```

---

### ⏱️ Protocol B: Execution Time-Tracking & Hang Prevention

**Rule:** কোনো command চালানোর আগে **আনুমানিক সময় estimate করো**। Estimate-এর দ্বিগুণ বা ৩০ সেকেন্ডের বেশি লাগলে — log scan করো বা task kill করো।

```python
# Rough estimates (project-specific):
# Unit tests:    < 15 seconds
# Build:         < 30 seconds
# E2E tests:     < 120 seconds
# Deploy:        < 180 seconds

# যদি এর বেশি লাগে → network call unmocked থাকার সম্ভাবনা
# Fix: সব external routes mock করো test suite-এ

NETWORK_BLOCKERS = [
    "core.llm_router.LLMRouter",
    "services.supabase_client",
    "httpx.AsyncClient",
]
```

---

### 🔍 Protocol C: Homologous Scope-Wide Verification

**Rule:** একটা file-এ bug পাওয়া গেলে — শুধু সেই file fix করা যাবে না।

```bash
# Bug পাওয়ার পর — সব platform-এ grep করো
PATTERN="broken_method_name"

grep -rn "$PATTERN" \
  backend/ \
  frontend/src/ \
  tools/vscode-extension/src/ \
  --include="*.py" --include="*.ts" --include="*.tsx"

# সব জায়গায় একসাথে fix করো — partial fix নিষিদ্ধ
```

---

### 🏷️ Protocol D: Brand Exclusivity — Third-Party Names Never Exposed

**Rule:** OpenAI, Anthropic, Gemini, Groq — এই নামগুলো user-facing UI বা response-এ কখনো দেখানো যাবে না।

```python
# ❌ Provider name expose করা
return {"model": "gpt-4-turbo", "provider": "openai", "response": text}

# ✅ Brand abstraction
return {
    "model": settings.display_model_name,  # "SupremeAI Pro" বা "SupremeAI Standard"
    "response": text,
    # Provider info completely hidden
}
```

```typescript
// ❌ Frontend-এ provider name
const modelBadge = provider === "openai" ? "OpenAI GPT-4" : "Claude";

// ✅ Always use SupremeAI brand
const modelBadge = settings.modelDisplayName ?? "SupremeAI Engine";
```

---

### 🔄 Protocol E: 3-Strike Auto-Rollback

**Rule:** একই সমস্যা ৩ বার try করেও সমাধান না হলে — manual intervention, automatic rollback to `CHECKPOINT.md`.

```python
MAX_RETRY_ATTEMPTS = int(settings.max_auto_retry)  # default: 3

async def auto_fix_with_rollback(fix_fn, context: dict) -> bool:
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            await fix_fn(context)
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{MAX_RETRY_ATTEMPTS} failed: {e}")
            if attempt == MAX_RETRY_ATTEMPTS:
                logger.critical("3 attempts exhausted — triggering CHECKPOINT rollback")
                await rollback_to_checkpoint()
                await notify_admin(
                    subject="Auto-Fix Failed — Manual Intervention Required",
                    body=f"Context: {context}\nFinal error: {e}"
                )
                return False
    return False
```

---

### 🌐 Protocol F: Zero Browser Console Errors

**Rule:** যেকোনো frontend change-এর পর browser console ১০০% clean হতে হবে।

```bash
# Test করার command:
cd frontend
pnpm run build 2>&1 | grep -E "error|warning" | grep -v "node_modules"

# Runtime check (Playwright দিয়ে):
# tests/e2e/console_monitor.spec.ts
# page.on('console', msg => {
#   if (msg.type() === 'error') throw new Error(`Console error: ${msg.text()}`);
# });
```

```python
# Backend-এ console error check (Playwright):
ALLOWED_CONSOLE_TYPES = {"log", "info"}  # "error", "warn" নিষিদ্ধ

async def check_zero_console_errors(page):
    errors = []
    page.on("console", lambda msg: errors.append(msg) if msg.type not in ALLOWED_CONSOLE_TYPES else None)
    await page.goto(settings.frontend_url)
    assert not errors, f"Console errors found: {[e.text for e in errors]}"
```

---

## 📊 সম্পূর্ণ Anti-Pattern Master Table

| ভাগ | # | Anti-Pattern | Prevention |
|-----|---|---|---|
| ১ | ১ | ast.parse = verification | Real import test |
| ১ | ২ | Method hallucination | grep before write |
| ১ | ৩ | git add ভুলে যাওয়া | git status always |
| ২ | ১-২৫ | General AI anti-patterns | See ভাগ ২ |
| ৫ | ১ | Zero Cost violation | Free-tier only |
| ৫ | ২ | Blocking in async | httpx + pagination |
| ৫ | ৩ | No retry/fallback | @retry + multi-provider |
| ৫ | ৪ | Hardcoded skills | DB-driven registry |
| ৫ | ৫ | No learning loop | cascade_memory.upsert() |
| ৫ | ৬ | TODO in production | Complete impl always |
| ৫ | ৭ | Custom lint style | ruff check --fix |
| ৫ | ৮ | Magic numbers | settings.* always |
| ৬ | 101 | Context overflow | 80% budget limit |
| ৬ | 102 | No HITL for sensitive | HITLService.create_request() |
| ৬ | 103 | Repeat same mistake | correction_log in pgvector |
| ৬ | 104 | Hallucinating facts | grep/verify first |
| ৬ | 105 | Agent scope violation | Domain boundary enforcement |
| ৭ | P1 | Lock file manual edit | poetry lock / pnpm update |
| ৭ | P2 | Timestamp in generated | Deterministic content hash |
| ৭ | P3 | PowerShell UTF-8 write | Python pathlib always |
| ৭ | P4 | React stale closure | useRef for async callbacks |
| ৭ | P5 | Fail-open security | Always fail-CLOSED |
| ৭ | P6 | Mock path after refactor | grep old path → update all |
| ৭ | P7 | Secret generate ≠ register | Create + verify in vault |
| ৮ | A | Multiple root causes | One proven cause only |
| ৮ | B | Hang prevention | Time-track all commands |
| ৮ | C | Partial scope fix | Grep all platforms |
| ৮ | D | Provider name exposed | Brand abstraction always |
| ৮ | E | 3-strike rollback | CHECKPOINT.md auto-rollback |
| ৮ | F | Console errors | 0 errors, 0 warnings |



---

## পর্ব ৬: Zero-Cost, High-Performance & Self-Healing Architecture

> **লক্ষ্য:** ১০০% ফ্রি-টিয়ার ফ্রেন্ডলি, ফাস্ট এবং প্রোডাকশন-রেডি সিস্টেম তৈরি করা, যেখানে কোনো কিছুই হার্ডকোড থাকবে না এবং এজেন্টরা নিজের ভুল নিজে বুঝতে ও ঠিক করতে পারবে।

### ১. ১০০% Zero-Cost ও Infrastructure-Free
- **অ্যান্টি-প্যাটার্ন:** Celery বা Redis-এর মতো ভারী প্রসেস এবং পেইড সার্ভিস ব্যবহার করে ব্যাকগ্রাউন্ড টাস্ক হ্যান্ডেল করা।
- **সঠিক পদ্ধতি:** `asyncio` ভিত্তিক In-Process Queue এবং Upstash Redis (Free Tier)-এর মাধ্যমে ডিস্ট্রিবিউটেড কো-অর্ডিনেশন। কোনো আলাদা ওয়ার্কার প্রসেস রান করা যাবে না।

### ২. Self-Healing ও Adaptive Circuit Breakers
- **অ্যান্টি-প্যাটার্ন:** থার্ড-পার্টি এপিআই ফেইল করলে পুরো সিস্টেম ক্র্যাশ করানো বা অসীম সময়ের জন্য আটকে থাকা।
- **সঠিক পদ্ধতি:** প্রতিটি এজেন্টের জন্য নিজস্ব **Circuit Breaker** থাকতে হবে (যেমন `AdaptiveCircuitBreaker`)। ফেইল করলে এটি অটোমেটিকভাবে ফলব্যাক (fallback) মোডে চলে যাবে এবং সিস্টেমকে ক্র্যাশ করা থেকে রক্ষা করবে।

### ৩. Performance Learning ও Auto-Tuning
- **অ্যান্টি-প্যাটার্ন:** টাইমআউট, কনকারেন্সি লিমিট বা অন্যান্য কনফিগারেশন হার্ডকোড করে রাখা (যেমন `timeout = 300`)।
- **সঠিক পদ্ধতি:** **Performance Learning Engine** ব্যবহার করুন যা রানটাইমে টাস্কের এভারেজ এক্সিকিউশন টাইম এবং P95 ল্যাটেন্সি দেখে টাইমআউট এবং কনকারেন্সি অটোমেটিকভাবে অ্যাডজাস্ট (tune) করবে।

### ৪. Dynamic Values ও Zero-Hardcode Policy
- **অ্যান্টি-প্যাটার্ন:** কনফিগারেশন ভ্যালু, ফাইল পাথ বা থ্রেশহোল্ড সরাসরি কোডে লিখে রাখা।
- **সঠিক পদ্ধতি:** সমস্ত কনফিগারেশন (যেমন `QUEUE_MAX_CONCURRENT_TASKS`, `CB_FAILURE_THRESHOLD`) ডাইনামিক হতে হবে এবং Environment Variable (`.env`) বা **Infisical Vault** থেকে সিকিউরলি পড়তে হবে। ডিফল্ট ভ্যালু হিসেবে সেফ (Fail-Gentle) অপশন রাখতে হবে।

### ৫. Production-Ready ও Bug-Free Code
- **অ্যান্টি-প্যাটার্ন:** কোডে `TODO` বা `// fix later` রেখে দেওয়া এবং টেস্ট না করেই পুশ করা।
- **সঠিক পদ্ধতি:** ডে-১ থেকেই প্রোডাকশন-রেডি কোড লিখতে হবে। ডিফেন্সিভ প্রোগ্রামিং (Try-Catch, Timeouts) প্রয়োগ করতে হবে। কোড পুশ করার আগে অবশ্যই লোকাল টেস্ট ও লিন্টার (lint format) পাস হতে হবে।

### ৬. API Token Optimization ও Aggressive Caching
- **অ্যান্টি-প্যাটার্ন:** একই ডেটা বা প্রম্পটের জন্য বারবার LLM API বা থার্ড-পার্টি সার্ভিস কল করা (যা খরচ বাড়ায়)।
- **সঠিক পদ্ধতি:** Redis বা লোকাল মেমোরি ক্যাশে (Cache) ব্যবহার করে রেসপন্স সেভ করে রাখা। Zero-cost নিশ্চিত করতে অপ্রয়োজনীয় API call পরিহার করা।

### ৭. Thin Client ও Brand Exclusivity
- **অ্যান্টি-প্যাটার্ন:** ইউজারের সামনে থার্ড-পার্টি সার্ভিস (যেমন OpenAI, Render, Upstash) এর নাম বা এরর মেসেজ হুবহু তুলে ধরা।
- **সঠিক পদ্ধতি:** সমস্ত ক্লায়েন্ট ১০০% Thin Client হতে হবে এবং যেকোনো এরর মেসেজকে SupremeAI এর নিজস্ব ব্র্যান্ডিং অনুযায়ী কাস্টমাইজ করে காட்ட (show) হবে।
