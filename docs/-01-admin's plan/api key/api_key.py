"""
SupremeAI 2.0 — API Key Management Models
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime, 
    Text, ForeignKey, JSON, ARRAY, Index, CheckConstraint,
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, INET
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from core.database import Base, db_session
from core.security import bcrypt_hash, bcrypt_verify, generate_api_key


class KeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class KeyScope(str, Enum):
    INFERENCE = "inference"
    TRAINING = "training"
    ADMIN = "admin"
    BILLING = "billing"
    READ_ONLY = "read_only"
    WEBHOOK = "webhook"


class APIKey(Base):
    """Production-grade API key model with full audit trail."""

    __tablename__ = "api_keys"

    # Primary identification
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)

    # Key identification (what user sees vs what we store)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    key_prefix = Column(String(12), nullable=False, index=True)  # e.g., "sk_live_abc1"
    _key_hash = Column("key_hash", String(255), nullable=False)

    # Scopes & permissions
    scopes = Column(JSONB, nullable=False, default=lambda: [KeyScope.INFERENCE.value])

    # Rate limiting configuration
    rate_limit_rpm = Column(Integer, nullable=False, default=60)
    rate_limit_rpd = Column(Integer, nullable=False, default=1000)

    # Quota management
    monthly_quota = Column(BigInteger, nullable=False, default=1_000_000)  # tokens
    quota_used = Column(BigInteger, nullable=False, default=0)
    quota_reset_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Lifecycle
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Status management
    status = Column(String(20), nullable=False, default=KeyStatus.ACTIVE.value)
    revoked_reason = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Advanced security
    metadata = Column(JSONB, nullable=False, default=dict)
    ip_whitelist = Column(JSONB, nullable=False, default=list)  # ["192.168.1.0/24", "10.0.0.0/8"]

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="api_keys")
    revoker = relationship("User", foreign_keys=[revoked_by])
    usage_records = relationship("APIKeyUsage", back_populates="api_key", cascade="all, delete-orphan")
    events = relationship("APIKeyEvent", back_populates="api_key", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired', 'suspended')",
            name="valid_key_status"
        ),
        CheckConstraint(
            "jsonb_array_length(scopes) > 0",
            name="valid_scopes_array"
        ),
        Index("idx_api_keys_active", "status", "expires_at"),
        Index("idx_api_keys_user_status", "user_id", "status"),
        Index("idx_api_keys_tenant", "tenant_id"),
    )

    @hybrid_property
    def is_active(self) -> bool:
        """Check if key is currently active and not expired."""
        if self.status != KeyStatus.ACTIVE.value:
            return False
        if self.expires_at and self.expires_at <= datetime.now(self.expires_at.tzinfo):
            return False
        return True

    @hybrid_property
    def quota_remaining(self) -> int:
        """Remaining quota for current period."""
        return max(0, self.monthly_quota - self.quota_used)

    @hybrid_property
    def quota_usage_percent(self) -> float:
        """Percentage of quota used."""
        if self.monthly_quota == 0:
            return 100.0
        return (self.quota_used / self.monthly_quota) * 100

    @hybrid_property
    def days_until_expiry(self) -> Optional[int]:
        """Days until key expires."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now(self.expires_at.tzinfo)
        return max(0, delta.days)

    @hybrid_property
    def display_key(self) -> str:
        """Masked key for display (only prefix + ...)."""
        return f"{self.key_prefix}..."

    @validates('scopes')
    def validate_scopes(self, key, scopes):
        """Ensure all scopes are valid."""
        valid = {s.value for s in KeyScope}
        for scope in scopes:
            if scope not in valid:
                raise ValueError(f"Invalid scope: {scope}. Must be one of {valid}")
        return scopes

    @validates('rate_limit_rpm', 'rate_limit_rpd')
    def validate_rate_limits(self, key, value):
        """Ensure rate limits are positive."""
        if value <= 0:
            raise ValueError(f"{key} must be positive")
        return value

    def verify_key(self, full_key: str) -> bool:
        """Verify a full API key against stored hash."""
        return bcrypt_verify(full_key, self._key_hash)

    def has_scope(self, scope: KeyScope) -> bool:
        """Check if key has a specific scope."""
        return scope.value in self.scopes

    def can_access_endpoint(self, endpoint: str, method: str) -> bool:
        """Check if key can access a specific endpoint."""
        # Admin scope allows everything
        if self.has_scope(KeyScope.ADMIN):
            return True

        # Read-only scope allows GET only
        if self.has_scope(KeyScope.READ_ONLY) and method.upper() == "GET":
            return True

        # Inference scope allows inference endpoints
        if self.has_scope(KeyScope.INFERENCE) and endpoint.startswith("/api/v1/inference"):
            return True

        # Training scope allows training endpoints
        if self.has_scope(KeyScope.TRAINING) and endpoint.startswith("/api/v1/training"):
            return True

        # Billing scope allows billing endpoints
        if self.has_scope(KeyScope.BILLING) and endpoint.startswith("/api/v1/billing"):
            return True

        # Webhook scope allows webhook endpoints
        if self.has_scope(KeyScope.WEBHOOK) and endpoint.startswith("/api/v1/webhooks"):
            return True

        return False

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "name": self.name,
            "description": self.description,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "rate_limit_rpm": self.rate_limit_rpm,
            "rate_limit_rpd": self.rate_limit_rpd,
            "monthly_quota": self.monthly_quota,
            "quota_used": self.quota_used,
            "quota_remaining": self.quota_remaining,
            "quota_usage_percent": round(self.quota_usage_percent, 2),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "days_until_expiry": self.days_until_expiry,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "is_active": self.is_active,
            "metadata": self.metadata,
            "ip_whitelist": self.ip_whitelist,
        }
        if include_sensitive:
            data["_key_hash"] = self._key_hash[:20] + "..."  # Never expose full hash
        return data

    def __repr__(self):
        return f"<APIKey(id={self.id}, prefix={self.key_prefix}, status={self.status})>"


class APIKeyUsage(Base):
    """Usage tracking for API keys with monthly partitioning."""

    __tablename__ = "api_key_usage"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key_id = Column(PGUUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    request_id = Column(String(64), nullable=False, unique=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)

    tokens_input = Column(BigInteger, nullable=False, default=0)
    tokens_output = Column(BigInteger, nullable=False, default=0)
    tokens_total = Column(BigInteger, nullable=False, default=0)

    cost_usd = Column(BigInteger, nullable=False, default=0)  # Stored in micro-cents (1/1000000 of a cent)
    latency_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=False)

    model_used = Column(String(100), nullable=True)
    provider_used = Column(String(50), nullable=True)

    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    country = Column(String(2), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    api_key = relationship("APIKey", back_populates="usage_records")

    __table_args__ = (
        Index("idx_usage_key_created", "key_id", "created_at"),
        Index("idx_usage_user_created", "user_id", "created_at"),
        Index("idx_usage_endpoint", "endpoint"),
        Index("idx_usage_created_at", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key_id": str(self.key_id),
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "tokens": {
                "input": self.tokens_input,
                "output": self.tokens_output,
                "total": self.tokens_total,
            },
            "cost_usd": self.cost_usd / 1_000_000,  # Convert to dollars
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "model_used": self.model_used,
            "provider_used": self.provider_used,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class APIKeyEvent(Base):
    """Immutable audit log for all API key lifecycle events."""

    __tablename__ = "api_key_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key_id = Column(PGUUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, nullable=False, default=dict)

    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    api_key = relationship("APIKey", back_populates="events")

    __table_args__ = (
        Index("idx_events_key", "key_id", "created_at"),
        Index("idx_events_user", "user_id", "created_at"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key_id": str(self.key_id) if self.key_id else None,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KeyQuotaAlert(Base):
    """Tracks sent quota alerts to prevent duplicate notifications."""

    __tablename__ = "key_quota_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key_id = Column(PGUUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(50), nullable=False)  # "80_percent", "100_percent", "expired"

    sent_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("key_id", "alert_type", name="unique_key_alert"),
    )
