# গাইডলাইন ০৪ — সিকিউরিটি হার্ডেনিং

> **স্তর:** সব ডেভেলপার — নতুন থেকে অভিজ্ঞ
> **প্রযোজ্য:** Web API, Authentication, Infrastructure

---

## ৪.১ — সিকিউরিটির সবচেয়ে বড় ভুলগুলো (শুরু থেকেই এড়ান)

### ভুল ১ — Hardcoded Secret

```python
# ❌ WRONG — এটা git history-তে চিরকাল থাকবে
NATS_TOKEN = "su-admin-token-12345"
API_KEY = "sk-abc123xyz"
DATABASE_URL = "postgresql://admin:password@prod-db.com/mydb"

# ✅ CORRECT — environment variable থেকে পড়ুন
from core.config import settings
nats_token = settings.nats_token
```

```bash
# যদি ভুলে commit হয়ে যায়:
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/file' HEAD
# তারপর force push — কিন্তু secret অবশ্যই rotate করুন
```

### ভুল ২ — Redis/DB Public Expose

```yaml
# ❌ WRONG — Redis সরাসরি host port-এ
services:
  redis:
    ports:
      - "6379:6379"   # যেকেউ connect করতে পারবে

# ✅ CORRECT — internal network-এ
services:
  redis:
    # ports expose করা নেই — শুধু internal service access করতে পারবে
  backend:
    depends_on:
      - redis
    environment:
      REDIS_URL: redis://redis:6379  # service name দিয়ে connect
```

### ভুল ৩ — Fail-open Authentication

```python
# ❌ WRONG — Exception হলে user ভেতরে ঢুকে যাচ্ছে
def verify_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY)
    except Exception:
        return {"role": "admin"}  # ভয়ংকর!

# ✅ CORRECT — Exception হলে deny
def verify_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### ভুল ৪ — File Upload Path Traversal

```python
# ❌ WRONG — filename সরাসরি ব্যবহার
filename = request.headers.get("X-Filename")
path = f"/uploads/{filename}"  # "../../../etc/passwd" দিলে?

# ✅ CORRECT — basename নিন, UUID দিয়ে rename করুন
import os
from uuid import uuid4

safe_name = f"{uuid4().hex}_{os.path.basename(filename)}"
# অথবা extension যাচাই করুন
allowed = {".jpg", ".png", ".pdf"}
ext = Path(filename).suffix.lower()
if ext not in allowed:
    raise ValueError("File type not allowed")
```

---

## ৪.২ — Authentication & Authorization

### JWT সঠিক ব্যবহার

```python
from datetime import datetime, timedelta
import jwt
from core.config import settings

def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=30),  # short-lived
        "iat": datetime.utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def verify_token(token: str) -> dict:
    # algorithm whitelist আবশ্যক — "none" algorithm attack ঠেকায়
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=["HS256"],   # শুধু HS256, ["HS256", "none"] নয়!
    )
```

### RBAC (Role-Based Access Control)

```python
from enum import Enum
from fastapi import Depends, HTTPException

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    AGENT = "agent"

def require_role(*roles: Role):
    def dependency(current_user = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Required role: {roles}"
            )
        return current_user
    return dependency

# Route-এ ব্যবহার
@router.post("/admin/action")
async def admin_action(user = Depends(require_role(Role.ADMIN))):
    ...
```

---

## ৪.৩ — Input Validation

```python
from pydantic import BaseModel, validator, constr
import re

class UserInput(BaseModel):
    email: str
    message: constr(max_length=1000)  # length limit আবশ্যক
    phone: str | None = None

    @validator("email")
    def validate_email(cls, v):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError("Invalid email")
        return v.lower().strip()

    @validator("message")
    def sanitize_message(cls, v):
        # HTML injection ঠেকানো
        dangerous = ["<script", "javascript:", "on load=", "onerror="]
        for pattern in dangerous:
            if pattern.lower() in v.lower():
                raise ValueError("Invalid content detected")
        return v
```

---

## ৪.৪ — Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")   # ← login এ rate limit
async def login(request: Request, ...):
    ...

@router.post("/auth/otp/verify")
@limiter.limit("3/minute")   # ← OTP verify এ আরো কড়া
async def verify_otp(request: Request, ...):
    ...
```

---

## ৪.৫ — Secret Scanner (pre-commit + CI)

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.4.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']
```

```yaml
# CI workflow
- name: Secret Scan
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: ${{ github.event.repository.default_branch }}
    head: HEAD
    extra_args: --only-verified
```

---

## ৪.৬ — CORS সঠিক কনফিগ

```python
from fastapi.middleware.cors import CORSMiddleware

# ❌ WRONG — সব origin allow
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# ✅ CORRECT — explicit whitelist
ALLOWED_ORIGINS = [
    "https://app.supremeai.com",
    "https://admin.supremeai.com",
]
if settings.environment == "development":
    ALLOWED_ORIGINS.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## ৪.৭ — Docker Security

```dockerfile
# ✅ Non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# ✅ Read-only filesystem
RUN chmod -R go-w /app/.venv

# ✅ Sensitive file cleanup
RUN rm -rf /app/.git /app/.env* /app/secrets.sh || true

# ✅ Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -sf http://localhost:${PORT:-8080}/health || exit 1

# ❌ WRONG — latest tag অস্থির
FROM python:latest

# ✅ CORRECT — pinned version
FROM python:3.11.9-slim
```

---

## ৪.৮ — সিকিউরিটি চেকলিস্ট (PR আগে)

- [ ] কোনো hardcoded secret, token, password নেই
- [ ] সব external input Pydantic দিয়ে validate হচ্ছে
- [ ] Auth endpoint-এ rate limiting আছে
- [ ] File upload-এ extension check + path traversal protection আছে
- [ ] JWT decode-এ algorithm whitelist আছে
- [ ] Exception handler fail-closed (deny on error)
- [ ] CORS explicit whitelist, `*` নয়
- [ ] Docker container non-root user দিয়ে চলছে
- [ ] Redis/DB internal network-এ, public port expose নেই
- [ ] `detect-secrets` pre-commit hook active
