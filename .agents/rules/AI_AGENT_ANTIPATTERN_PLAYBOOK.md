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
