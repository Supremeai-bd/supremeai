# গাইডলাইন ০৫ — Backend আর্কিটেকচার

> **স্তর:** Junior থেকে Senior ডেভেলপার
> **প্রযোজ্য:** FastAPI, Python, যেকোনো REST API

---

## ৫.১ — Layered Architecture (স্তরায়িত আর্কিটেকচার)

```
HTTP Request
     ↓
[Middleware]          ← auth, rate limit, logging, CORS
     ↓
[API Router]          ← শুধু HTTP — request parse, response format
     ↓
[Service/Core]        ← business logic — framework-independent
     ↓
[Repository]          ← DB access — query, transaction
     ↓
[Database/Cache]      ← PostgreSQL, Redis
```

**মূল নীতি:** প্রতিটা স্তর শুধু পরের স্তরকে কল করে। Skip করবেন না।

---

## ৫.২ — API Route — পাতলা রাখুন

```python
# ✅ CORRECT — route শুধু HTTP-র কাজ করে
from fastapi import APIRouter, Depends
from core.auth_service import AuthService
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(),
) -> LoginResponse:
    # route-এ কোনো business logic নেই
    return await auth_service.login(request.email, request.password)
```

```python
# ❌ WRONG — route-এ business logic
@router.post("/login")
async def login(request: LoginRequest):
    user = await db.execute("SELECT * FROM users WHERE email = ?", request.email)
    if not user:
        raise HTTPException(404)
    hashed = bcrypt.checkpw(request.password, user.password_hash)
    if not hashed:
        raise HTTPException(401)
    token = jwt.encode({"sub": user.id}, SECRET_KEY)
    await redis.set(f"session:{user.id}", token, ex=3600)
    return {"token": token}
    # এটা সব কিছু route-এ গুঁজে দিয়েছে — test করা কঠিন
```

---

## ৫.३ — Service Layer — Business Logic

```python
# backend/core/auth_service.py
from core.config import settings
from core.database import get_db
from core.cache import redis_manager
import bcrypt
import jwt

class AuthService:
    def __init__(self, db=Depends(get_db)):
        self.db = db

    async def login(self, email: str, password: str) -> dict:
        user = await self._get_user_by_email(email)
        if not user:
            raise UserNotFoundError(email)

        if not self._verify_password(password, user.password_hash):
            await self._record_failed_attempt(email)
            raise InvalidCredentialsError()

        token = self._create_token(user)
        await redis_manager.set_cache(f"session:{user.id}", token, ttl=3600)
        return {"token": token, "user_id": user.id}

    def _verify_password(self, plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())

    def _create_token(self, user) -> str:
        return jwt.encode(
            {"sub": user.id, "role": user.role},
            settings.secret_key,
            algorithm="HS256"
        )
```

---

## ৫.৪ — Dependency Injection সঠিক ব্যবহার

```python
# backend/api/dependencies.py — সব shared dependency এখানে
from fastapi import Depends, HTTPException, Header
from core.auth_service import AuthService

async def get_current_user(
    authorization: str = Header(...),
) -> dict:
    """JWT থেকে current user বের করুন।"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    token = authorization[7:]
    try:
        return verify_token(token)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

# Route-এ ব্যবহার
@router.get("/profile")
async def get_profile(
    user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(),
):
    return await auth_service.get_profile(user["sub"])
```

---

## ৫.৫ — Error Handling — Silent Failure নিষিদ্ধ

```python
# ❌ WRONG — bare except, সব error গিলে ফেলছে
def process_data(data):
    try:
        return transform(data)
    except:
        pass  # কী ভুল হলো জানার উপায় নেই!

# ❌ WRONG — exception log না করে return করছে
async def get_user(user_id: str):
    try:
        return await db.get(user_id)
    except Exception:
        return None  # caller জানছে না DB down কিনা, user নেই কিনা

# ✅ CORRECT — specific exception, log করুন, re-raise বা meaningful error
import logging
logger = logging.getLogger(__name__)

async def get_user(user_id: str):
    try:
        return await db.get(user_id)
    except DatabaseConnectionError as e:
        logger.error(f"DB connection failed for user {user_id}: {e}")
        raise ServiceUnavailableError("Database temporarily unavailable")
    except RecordNotFoundError:
        return None  # এটা valid case — None return করা ঠিক আছে
```

### Custom Exception Hierarchy

```python
# backend/core/exceptions.py
class SupremeAIError(Exception):
    """Base exception."""
    pass

class AuthenticationError(SupremeAIError):
    """Authentication failed."""
    pass

class AuthorizationError(SupremeAIError):
    """Insufficient permissions."""
    pass

class ResourceNotFoundError(SupremeAIError):
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")

class ServiceUnavailableError(SupremeAIError):
    """External service (DB, Redis, etc.) unavailable."""
    pass

# FastAPI exception handler
@app.exception_handler(ResourceNotFoundError)
async def not_found_handler(request, exc: ResourceNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": str(exc), "resource": exc.resource}
    )
```

---

## ৫.৬ — Database — Repository Pattern

```python
# backend/core/repositories/user_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str):
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()   # ID generate হবে
        return user

    async def get_by_email(self, email: str):
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
```

```python
# Transaction management
async def transfer_credits(from_user_id: str, to_user_id: str, amount: int):
    async with db.begin():   # ← transaction শুরু
        from_user = await user_repo.get_by_id(from_user_id)
        to_user = await user_repo.get_by_id(to_user_id)

        if from_user.credits < amount:
            raise InsufficientCreditsError()

        from_user.credits -= amount
        to_user.credits += amount
        # exception হলে automatically rollback হবে
```

---

## ৫.৭ — Async সঠিক ব্যবহার

```python
# ❌ WRONG — sync function কে async wrapper দিয়ে fake async বানানো
async def get_data():
    return sync_heavy_function()  # event loop block করছে!

# ✅ CORRECT — CPU-bound কাজ thread pool-এ পাঠান
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def get_data():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_heavy_function)

# ✅ CORRECT — IO-bound কাজ সত্যিই async
async def fetch_from_redis(key: str):
    return await redis_client.get(key)  # non-blocking

# ✅ CORRECT — parallel async operations
async def get_user_dashboard(user_id: str):
    # এই তিনটা call একসাথে চলবে, একটার পর একটা নয়
    profile, stats, notifications = await asyncio.gather(
        get_profile(user_id),
        get_stats(user_id),
        get_notifications(user_id),
    )
    return {"profile": profile, "stats": stats, "notifications": notifications}
```

---

## ৫.৮ — Caching Strategy

```python
# backend/core/cache.py
from functools import wraps
import json

def cache_result(key_pattern: str, ttl: int = 300):
    """Simple cache decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_pattern.format(*args, **kwargs)
            cached = await redis_manager.get_cache(key)
            if cached:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            await redis_manager.set_cache(key, json.dumps(result), ttl=ttl)
            return result
        return wrapper
    return decorator

# ব্যবহার
@cache_result("user:profile:{0}", ttl=600)
async def get_user_profile(user_id: str) -> dict:
    return await user_repo.get_profile(user_id)
```

---

## চেকলিস্ট — নতুন Feature যোগ করার সময়

- [ ] Route: শুধু HTTP parsing/response — business logic নেই
- [ ] Business logic: `core/` এ, framework-independent
- [ ] DB access: Repository pattern এ
- [ ] Exception: specific type ধরা, bare `except:` নেই
- [ ] Async: CPU-bound কাজ thread pool-এ
- [ ] Cache: frequently-read data Redis-এ
- [ ] Dependency: FastAPI `Depends()` দিয়ে inject
