from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

try:
    from jose import JWTError, jwt
except ImportError:
    JWTError = Exception  # type: ignore[misc,assignment]
    jwt = None  # type: ignore[assignment]

from core.rbac import UserContext

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

SECRET_KEY = "supremeai-internal-secret"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

FAKE_USERS = {
    "admin": {"user_id": "u1", "role": "admin"},
    "owner": {"user_id": "u2", "role": "owner"},
    "viewer": {"user_id": "u3", "role": "viewer"},
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if jwt is None:
        raise RuntimeError("python-jose[cryptography] is required for token issuance")
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def optional_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[UserContext]:
    if not token or jwt is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub", "unknown")
        role = payload.get("role", "viewer")
        return UserContext(user_id=user_id, role=role)
    except Exception:
        return None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class MeResponse(BaseModel):
    user_id: str
    role: str
    scopes: tuple[str, ...] = ()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = FAKE_USERS.get(body.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user["user_id"], "role": user["role"]})
    return TokenResponse(access_token=token, user_id=user["user_id"], role=user["role"])


@router.get("/me", response_model=MeResponse)
async def me(current_user: Optional[UserContext] = Depends(optional_current_user)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return MeResponse(user_id=current_user.user_id, role=current_user.role, scopes=current_user.scopes)
