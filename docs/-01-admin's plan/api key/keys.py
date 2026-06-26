"""
SupremeAI 2.0 — API Key Management Router
FastAPI endpoints for key CRUD, usage analytics, and admin operations.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from loguru import logger

from core.database import get_db
from core.auth import get_current_user, require_auth, require_scope
from core.rate_limiter import get_rate_limiter, RateLimitStatus
from core.security import (
    generate_api_key, hash_api_key, verify_api_key, 
    validate_key_format, extract_prefix_from_key, mask_key
)
from core.notifications import send_notification
from core.audit import log_key_event
from models.api_key import APIKey, APIKeyUsage, APIKeyEvent, KeyStatus, KeyScope, KeyQuotaAlert


router = APIRouter(prefix="/api/v1/keys", tags=["api-keys"])
security = HTTPBearer()


# ═══════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════

class KeyCreateRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the key")
    description: Optional[str] = Field(None, max_length=500)
    scopes: List[str] = Field(default=["inference"], description="Permission scopes")
    environment: str = Field(default="live", regex="^(live|test|dev)$")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")
    rate_limit_rpm: Optional[int] = Field(None, ge=1, le=10000)
    rate_limit_rpd: Optional[int] = Field(None, ge=1, le=1000000)
    monthly_quota: Optional[int] = Field(None, ge=1000, le=1_000_000_000)
    ip_whitelist: Optional[List[str]] = Field(None, description="Allowed IP ranges (CIDR notation)")

    @validator('scopes')
    def validate_scopes(cls, v):
        valid = {s.value for s in KeyScope}
        for scope in v:
            if scope not in valid:
                raise ValueError(f"Invalid scope: {scope}. Valid: {valid}")
        return v


class KeyCreateResponse(BaseModel):
    """Response after creating a key (includes the full key once)."""
    id: str
    name: str
    key: str = Field(..., description="FULL API KEY — COPY NOW, NEVER SHOWN AGAIN")
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[str]
    created_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Production Inference Key",
                "key": "sk_live_abc123de_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_xxxx",
                "key_prefix": "sk_live_abc123de",
                "scopes": ["inference"],
                "expires_at": "2026-09-26T00:00:00Z",
                "created_at": "2026-06-26T00:00:00Z",
            }
        }


class KeyResponse(BaseModel):
    """Standard key response (does not include full key)."""
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    rate_limit_rpm: int
    rate_limit_rpd: int
    monthly_quota: int
    quota_used: int
    quota_remaining: int
    quota_usage_percent: float
    expires_at: Optional[str]
    days_until_expiry: Optional[int]
    last_used_at: Optional[str]
    created_at: str
    status: str
    is_active: bool
    ip_whitelist: List[str]


class KeyListResponse(BaseModel):
    """Paginated list of keys."""
    keys: List[KeyResponse]
    total: int
    page: int
    page_size: int


class KeyUpdateRequest(BaseModel):
    """Request to update a key."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scopes: Optional[List[str]] = None
    rate_limit_rpm: Optional[int] = Field(None, ge=1, le=10000)
    rate_limit_rpd: Optional[int] = Field(None, ge=1, le=1000000)
    monthly_quota: Optional[int] = Field(None, ge=1000, le=1_000_000_000)
    status: Optional[str] = Field(None, regex="^(active|suspended)$")
    ip_whitelist: Optional[List[str]] = None


class KeyRotateResponse(BaseModel):
    """Response after rotating a key."""
    id: str
    new_key: str = Field(..., description="NEW FULL API KEY — COPY NOW")
    key_prefix: str
    rotated_at: str


class UsageStatsResponse(BaseModel):
    """Usage statistics for a key."""
    key_id: str
    total_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: Optional[float]
    success_rate: float
    top_endpoints: List[Dict[str, Any]]
    daily_usage: List[Dict[str, Any]]
    period: str = "30d"


class AdminKeyListFilters(BaseModel):
    """Filters for admin key listing."""
    status: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    scope: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    search: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

async def get_key_by_prefix(prefix: str, db: Session) -> Optional[APIKey]:
    """Look up key by prefix (used in auth middleware)."""
    return db.query(APIKey).filter(
        APIKey.key_prefix == prefix,
        APIKey.status == KeyStatus.ACTIVE.value
    ).first()


async def validate_key_ownership(key_id: UUID, user_id: UUID, db: Session) -> APIKey:
    """Verify user owns the key or has admin access."""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    if str(key.user_id) != str(user_id):
        # Check if user has admin scope
        # This would need to be checked via the requesting key's scopes
        raise HTTPException(status_code=403, detail="Not authorized to access this key")
    return key


async def check_key_limits(key: APIKey, db: Session) -> None:
    """Check if key has exceeded limits and update status if needed."""
    if key.quota_usage_percent >= 100:
        if key.status == KeyStatus.ACTIVE.value:
            key.status = KeyStatus.SUSPENDED.value
            db.commit()
            logger.warning(f"Key {key.id} suspended due to quota exhaustion")
            # Send notification
            await send_notification(
                user_id=key.user_id,
                title="API Key Quota Exceeded",
                message=f"Your key '{key.name}' has been suspended due to quota exhaustion.",
                channels=["email", "in_app"]
            )


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=KeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: Request,
    data: KeyCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new API key for the authenticated user.

    The full key is returned ONLY once. After creation, only the prefix is visible.
    """
    user_id = UUID(current_user["uid"])

    # Check key limit per user (free tier = 3, pro = 20, enterprise = unlimited)
    existing_count = db.query(APIKey).filter(
        APIKey.user_id == user_id,
        APIKey.status.in_([KeyStatus.ACTIVE.value, KeyStatus.SUSPENDED.value])
    ).count()

    # TODO: Get tier from user subscription
    max_keys = current_user.get("max_api_keys", 3)
    if existing_count >= max_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maximum API keys reached ({max_keys}). Upgrade your plan or revoke existing keys."
        )

    # Generate key
    full_key, prefix = generate_api_key(env=data.environment)
    key_hash = hash_api_key(full_key)

    # Calculate expiration
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)

    # Create key record
    api_key = APIKey(
        user_id=user_id,
        name=data.name,
        description=data.description,
        key_prefix=prefix,
        _key_hash=key_hash,
        scopes=data.scopes,
        rate_limit_rpm=data.rate_limit_rpm or 60,
        rate_limit_rpd=data.rate_limit_rpd or 1000,
        monthly_quota=data.monthly_quota or 1_000_000,
        expires_at=expires_at,
        ip_whitelist=data.ip_whitelist or [],
        metadata={
            "created_from_ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
        }
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    # Log event
    background_tasks.add_task(
        log_key_event,
        key_id=api_key.id,
        user_id=user_id,
        event_type="created",
        event_data={"name": data.name, "scopes": data.scopes, "expires_at": expires_at.isoformat() if expires_at else None},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )

    # Send notification
    background_tasks.add_task(
        send_notification,
        user_id=user_id,
        title="New API Key Created",
        message=f"Your API key '{data.name}' has been created successfully.",
        channels=["in_app"]
    )

    logger.info(f"API key created: {api_key.id} for user {user_id}")

    return KeyCreateResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=full_key,  # ONLY TIME FULL KEY IS SHOWN
        key_prefix=prefix,
        scopes=api_key.scopes,
        expires_at=expires_at.isoformat() if expires_at else None,
        created_at=api_key.created_at.isoformat(),
    )


@router.get("", response_model=KeyListResponse)
async def list_api_keys(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all API keys for the authenticated user."""
    user_id = UUID(current_user["uid"])

    query = db.query(APIKey).filter(APIKey.user_id == user_id)

    if status:
        query = query.filter(APIKey.status == status)

    total = query.count()
    keys = query.order_by(APIKey.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return KeyListResponse(
        keys=[KeyResponse(**k.to_dict()) for k in keys],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{key_id}", response_model=KeyResponse)
async def get_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific API key."""
    user_id = UUID(current_user["uid"])
    key = await validate_key_ownership(key_id, user_id, db)

    # Log view event
    await log_key_event(
        key_id=key.id,
        user_id=user_id,
        event_type="viewed",
        event_data={},
    )

    return KeyResponse(**key.to_dict())


@router.patch("/{key_id}", response_model=KeyResponse)
async def update_api_key(
    key_id: UUID,
    data: KeyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update an API key's settings."""
    user_id = UUID(current_user["uid"])
    key = await validate_key_ownership(key_id, user_id, db)

    # Track changes for audit log
    changes = {}

    if data.name is not None:
        changes["name"] = {"old": key.name, "new": data.name}
        key.name = data.name

    if data.description is not None:
        changes["description"] = {"old": key.description, "new": data.description}
        key.description = data.description

    if data.scopes is not None:
        changes["scopes"] = {"old": key.scopes, "new": data.scopes}
        key.scopes = data.scopes

    if data.rate_limit_rpm is not None:
        changes["rate_limit_rpm"] = {"old": key.rate_limit_rpm, "new": data.rate_limit_rpm}
        key.rate_limit_rpm = data.rate_limit_rpm

    if data.rate_limit_rpd is not None:
        changes["rate_limit_rpd"] = {"old": key.rate_limit_rpd, "new": data.rate_limit_rpd}
        key.rate_limit_rpd = data.rate_limit_rpd

    if data.monthly_quota is not None:
        changes["monthly_quota"] = {"old": key.monthly_quota, "new": data.monthly_quota}
        key.monthly_quota = data.monthly_quota

    if data.status is not None:
        changes["status"] = {"old": key.status, "new": data.status}
        key.status = data.status
        if data.status == KeyStatus.ACTIVE.value and key.status == KeyStatus.SUSPENDED.value:
            # Reactivating
            key.quota_used = 0  # Reset quota on reactivation? Or keep? Configurable.

    if data.ip_whitelist is not None:
        changes["ip_whitelist"] = {"old": key.ip_whitelist, "new": data.ip_whitelist}
        key.ip_whitelist = data.ip_whitelist

    db.commit()
    db.refresh(key)

    # Log event
    if changes:
        await log_key_event(
            key_id=key.id,
            user_id=user_id,
            event_type="updated",
            event_data={"changes": changes},
        )

    return KeyResponse(**key.to_dict())


@router.post("/{key_id}/rotate", response_model=KeyRotateResponse)
async def rotate_api_key(
    key_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Rotate an API key (generate new key, invalidate old one).

    The old key is immediately revoked. The new key is returned once.
    """
    user_id = UUID(current_user["uid"])
    key = await validate_key_ownership(key_id, user_id, db)

    # Generate new key
    env = key.key_prefix.split("_")[1] if "_" in key.key_prefix else "live"
    new_full_key, new_prefix = generate_api_key(env=env)
    new_hash = hash_api_key(new_full_key)

    # Store old hash for audit
    old_hash_prefix = key._key_hash[:20] + "..."

    # Update key
    key.key_prefix = new_prefix
    key._key_hash = new_hash
    key.status = KeyStatus.ACTIVE.value
    key.revoked_at = None
    key.revoked_reason = None
    key.revoked_by = None
    key.last_used_at = None
    key.quota_used = 0  # Reset quota on rotation
    key.updated_at = datetime.utcnow()

    # Reset rate limits in Redis
    rate_limiter = get_rate_limiter()
    await rate_limiter.reset_rate_limits(str(key.id))

    db.commit()
    db.refresh(key)

    # Log rotation event
    await log_key_event(
        key_id=key.id,
        user_id=user_id,
        event_type="rotated",
        event_data={"old_hash_prefix": old_hash_prefix},
        ip_address=request.client.host,
    )

    logger.info(f"API key rotated: {key.id}")

    return KeyRotateResponse(
        id=str(key.id),
        new_key=new_full_key,
        key_prefix=new_prefix,
        rotated_at=datetime.utcnow().isoformat(),
    )


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    reason: Optional[str] = "User initiated revocation",
):
    """Revoke an API key immediately."""
    user_id = UUID(current_user["uid"])
    key = await validate_key_ownership(key_id, user_id, db)

    if key.status == KeyStatus.REVOKED.value:
        raise HTTPException(status_code=400, detail="Key is already revoked")

    key.status = KeyStatus.REVOKED.value
    key.revoked_reason = reason
    key.revoked_at = datetime.utcnow()
    key.revoked_by = user_id

    db.commit()

    # Clear from Redis cache
    rate_limiter = get_rate_limiter()
    await rate_limiter.reset_rate_limits(str(key.id))

    # Log event
    await log_key_event(
        key_id=key.id,
        user_id=user_id,
        event_type="revoked",
        event_data={"reason": reason},
        ip_address=request.client.host,
    )

    logger.info(f"API key revoked: {key.id}")

    return {"status": "success", "message": "Key revoked successfully", "key_id": str(key.id)}


@router.get("/{key_id}/usage", response_model=UsageStatsResponse)
async def get_key_usage(
    key_id: UUID,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get usage statistics for a specific API key."""
    user_id = UUID(current_user["uid"])
    key = await validate_key_ownership(key_id, user_id, db)

    from_date = datetime.utcnow() - timedelta(days=days)

    # Aggregate stats
    stats = db.query(
        func.count(APIKeyUsage.id).label("total_requests"),
        func.coalesce(func.sum(APIKeyUsage.tokens_input), 0).label("total_input"),
        func.coalesce(func.sum(APIKeyUsage.tokens_output), 0).label("total_output"),
        func.coalesce(func.sum(APIKeyUsage.cost_usd), 0).label("total_cost"),
        func.avg(APIKeyUsage.latency_ms).label("avg_latency"),
    ).filter(
        APIKeyUsage.key_id == key_id,
        APIKeyUsage.created_at >= from_date
    ).first()

    # Success rate
    total = stats.total_requests or 0
    successes = db.query(func.count(APIKeyUsage.id)).filter(
        APIKeyUsage.key_id == key_id,
        APIKeyUsage.created_at >= from_date,
        APIKeyUsage.status_code < 400
    ).scalar() or 0

    success_rate = (successes / total * 100) if total > 0 else 100.0

    # Top endpoints
    top_endpoints = db.query(
        APIKeyUsage.endpoint,
        func.count(APIKeyUsage.id).label("count"),
        func.coalesce(func.sum(APIKeyUsage.tokens_total), 0).label("tokens"),
    ).filter(
        APIKeyUsage.key_id == key_id,
        APIKeyUsage.created_at >= from_date
    ).group_by(APIKeyUsage.endpoint).order_by(func.count(APIKeyUsage.id).desc()).limit(10).all()

    # Daily usage
    daily = db.query(
        func.date_trunc('day', APIKeyUsage.created_at).label("day"),
        func.count(APIKeyUsage.id).label("requests"),
        func.coalesce(func.sum(APIKeyUsage.tokens_total), 0).label("tokens"),
        func.coalesce(func.sum(APIKeyUsage.cost_usd), 0).label("cost"),
    ).filter(
        APIKeyUsage.key_id == key_id,
        APIKeyUsage.created_at >= from_date
    ).group_by(func.date_trunc('day', APIKeyUsage.created_at)).order_by("day").all()

    return UsageStatsResponse(
        key_id=str(key_id),
        total_requests=total,
        total_tokens_input=stats.total_input or 0,
        total_tokens_output=stats.total_output or 0,
        total_tokens=(stats.total_input or 0) + (stats.total_output or 0),
        total_cost_usd=(stats.total_cost or 0) / 1_000_000,
        avg_latency_ms=round(stats.avg_latency, 2) if stats.avg_latency else None,
        success_rate=round(success_rate, 2),
        top_endpoints=[{"endpoint": e.endpoint, "count": e.count, "tokens": e.tokens} for e in top_endpoints],
        daily_usage=[{"date": d.day.isoformat(), "requests": d.requests, "tokens": d.tokens, "cost": d.cost / 1_000_000} for d in daily],
        period=f"{days}d",
    )


@router.get("/{key_id}/events")
async def get_key_events(
    key_id: UUID,
    page: int = 1,
    page_size: int = 50,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get audit events for a specific API key."""
    user_id = UUID(current_user["uid"])
    key = await validate_key_ownership(key_id, user_id, db)

    query = db.query(APIKeyEvent).filter(APIKeyEvent.key_id == key_id)

    if event_type:
        query = query.filter(APIKeyEvent.event_type == event_type)

    total = query.count()
    events = query.order_by(APIKeyEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "events": [e.to_dict() for e in events],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ═══════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/all", response_model=KeyListResponse)
async def admin_list_all_keys(
    filters: AdminKeyListFilters = Depends(),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_scope(KeyScope.ADMIN)),
):
    """Admin: List all API keys across all users with filters."""
    query = db.query(APIKey)

    if filters.status:
        query = query.filter(APIKey.status == filters.status)
    if filters.user_id:
        query = query.filter(APIKey.user_id == UUID(filters.user_id))
    if filters.tenant_id:
        query = query.filter(APIKey.tenant_id == UUID(filters.tenant_id))
    if filters.scope:
        query = query.filter(APIKey.scopes.contains([filters.scope]))
    if filters.created_after:
        query = query.filter(APIKey.created_at >= filters.created_after)
    if filters.created_before:
        query = query.filter(APIKey.created_at <= filters.created_before)
    if filters.search:
        query = query.filter(
            (APIKey.name.ilike(f"%{filters.search}%")) |
            (APIKey.key_prefix.ilike(f"%{filters.search}%"))
        )

    total = query.count()
    keys = query.order_by(APIKey.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return KeyListResponse(
        keys=[KeyResponse(**k.to_dict()) for k in keys],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/admin/{key_id}/suspend")
async def admin_suspend_key(
    key_id: UUID,
    reason: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_scope(KeyScope.ADMIN)),
):
    """Admin: Suspend an API key."""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    key.status = KeyStatus.SUSPENDED.value
    key.revoked_reason = reason
    key.revoked_at = datetime.utcnow()
    key.revoked_by = UUID(current_user["uid"])

    db.commit()

    # Notify owner
    await send_notification(
        user_id=key.user_id,
        title="API Key Suspended",
        message=f"Your key '{key.name}' has been suspended by admin. Reason: {reason}",
        channels=["email", "in_app"],
        priority="high",
    )

    return {"status": "success", "message": "Key suspended", "key_id": str(key_id)}


@router.post("/admin/{key_id}/reactivate")
async def admin_reactivate_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_scope(KeyScope.ADMIN)),
):
    """Admin: Reactivate a suspended key."""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")

    if key.status != KeyStatus.SUSPENDED.value:
        raise HTTPException(status_code=400, detail="Key is not suspended")

    key.status = KeyStatus.ACTIVE.value
    key.revoked_reason = None
    key.revoked_at = None
    key.revoked_by = None

    db.commit()

    await send_notification(
        user_id=key.user_id,
        title="API Key Reactivated",
        message=f"Your key '{key.name}' has been reactivated by admin.",
        channels=["email", "in_app"],
    )

    return {"status": "success", "message": "Key reactivated", "key_id": str(key_id)}


@router.get("/admin/stats")
async def admin_get_global_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_scope(KeyScope.ADMIN)),
):
    """Admin: Get global API key statistics."""
    total_keys = db.query(APIKey).count()
    active_keys = db.query(APIKey).filter(APIKey.status == KeyStatus.ACTIVE.value).count()
    revoked_keys = db.query(APIKey).filter(APIKey.status == KeyStatus.REVOKED.value).count()
    expired_keys = db.query(APIKey).filter(APIKey.status == KeyStatus.EXPIRED.value).count()

    # Today's usage
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_requests = db.query(func.count(APIKeyUsage.id)).filter(APIKeyUsage.created_at >= today).scalar() or 0
    today_tokens = db.query(func.coalesce(func.sum(APIKeyUsage.tokens_total), 0)).filter(APIKeyUsage.created_at >= today).scalar() or 0
    today_cost = db.query(func.coalesce(func.sum(APIKeyUsage.cost_usd), 0)).filter(APIKeyUsage.created_at >= today).scalar() or 0

    # Top users by usage
    top_users = db.query(
        APIKeyUsage.user_id,
        func.count(APIKeyUsage.id).label("requests"),
        func.coalesce(func.sum(APIKeyUsage.tokens_total), 0).label("tokens"),
    ).filter(APIKeyUsage.created_at >= today).group_by(APIKeyUsage.user_id).order_by(func.count(APIKeyUsage.id).desc()).limit(10).all()

    return {
        "keys": {
            "total": total_keys,
            "active": active_keys,
            "revoked": revoked_keys,
            "expired": expired_keys,
            "suspended": total_keys - active_keys - revoked_keys - expired_keys,
        },
        "today": {
            "requests": today_requests,
            "tokens": today_tokens,
            "cost_usd": today_cost / 1_000_000,
        },
        "top_users": [{"user_id": str(u.user_id), "requests": u.requests, "tokens": u.tokens} for u in top_users],
    }
