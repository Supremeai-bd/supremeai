"""Customer ORM and Pydantic schemas for SupremeAI Customer Directory.

বাংলা: কাস্টমার ডেটা মডেল ও স্কিমা যা ফ্রন্টএন্ড মক ডেটা (INITIAL_CUSTOMERS) এবং
রিয়েল ব্যাকএন্ড এপিআই (/api/admin/customers, /api/customers)-এর মধ্যে সংযোগ নিশ্চিত করে।
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    """Customer entity matching frontend CustomerRecord specification."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False).with_variant(String(64), "sqlite"),
        primary_key=True,
        default=lambda: f"cust_{uuid.uuid4().hex[:8]}",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="Free", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    mrr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_limit: Mapped[int] = mapped_column(Integer, default=100000, nullable=False)
    connected_repos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    joined_date: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.now(UTC).strftime("%Y-%m-%d"), nullable=False
    )
    last_active: Mapped[str] = mapped_column(String(100), default="Just now", nullable=False)
    github_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), default="Asia/Dhaka", nullable=True)
    is_developer_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "tier": self.tier,
            "status": self.status,
            "mrr": self.mrr,
            "tokensUsed": self.tokens_used,
            "tokenLimit": self.token_limit,
            "connectedRepos": self.connected_repos,
            "joinedDate": self.joined_date,
            "lastActive": self.last_active,
            "githubHandle": self.github_handle,
            "region": self.region,
            "isDeveloperEligible": self.is_developer_eligible,
        }


# --- Pydantic Request / Response Schemas ---


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Customer full name")
    email: str = Field(..., description="Customer unique email address")
    tier: str = Field(default="Free", description="Subscription tier: Free, Pro, Enterprise")
    status: str = Field(default="active", description="Account status: active, past_due, suspended")
    mrr: float = Field(default=0.0, ge=0.0, description="Monthly recurring revenue in USD")
    tokens_used: int = Field(default=0, ge=0, alias="tokensUsed")
    token_limit: int = Field(default=100000, ge=0, alias="tokenLimit")
    connected_repos: int = Field(default=0, ge=0, alias="connectedRepos")
    github_handle: str | None = Field(default=None, alias="githubHandle")
    region: str | None = Field(default="Asia/Dhaka")
    is_developer_eligible: bool = Field(default=False, alias="isDeveloperEligible")

    model_config = ConfigDict(populate_by_name=True)


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    tier: str | None = None
    status: str | None = None
    mrr: float | None = Field(default=None, ge=0.0)
    tokens_used: int | None = Field(default=None, ge=0, alias="tokensUsed")
    token_limit: int | None = Field(default=None, ge=0, alias="tokenLimit")
    connected_repos: int | None = Field(default=None, ge=0, alias="connectedRepos")
    github_handle: str | None = Field(default=None, alias="githubHandle")
    region: str | None = None
    is_developer_eligible: bool | None = Field(default=None, alias="isDeveloperEligible")

    model_config = ConfigDict(populate_by_name=True)


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    tier: str
    status: str
    mrr: float
    tokens_used: int = Field(alias="tokensUsed")
    token_limit: int = Field(alias="tokenLimit")
    connected_repos: int = Field(alias="connectedRepos")
    joined_date: str = Field(alias="joinedDate")
    last_active: str = Field(alias="lastActive")
    github_handle: str | None = Field(default=None, alias="githubHandle")
    region: str | None = None
    is_developer_eligible: bool = Field(default=False, alias="isDeveloperEligible")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
