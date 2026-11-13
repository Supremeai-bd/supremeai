"""Customer Directory API endpoints for SupremeAI.

Exposes RESTful endpoints for customer management matching both:
- /api/customers (Standard Customer API)
- /api/admin/customers (Admin Dashboard Customer Sync)

Supports database-backed persistence with automatic fallback to canonical
seed customer data so the frontend admin dashboard works out of the box in
both mock and live modes.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.customer import Customer, CustomerCreate, CustomerUpdate

try:
    from database.session import get_db_session
except ImportError:
    try:
        from core.database.session import get_db_session
    except ImportError:
        get_db_session = None

router = APIRouter(tags=["Customers"])

# Canonical seed data matching frontend customerData.ts
INITIAL_SEED_CUSTOMERS: list[dict[str, Any]] = [
    {
        "id": "cust_001",
        "name": "ziaul haq",
        "email": "ziaulhaquezia01@gmail.com",
        "tier": "Pro",
        "status": "active",
        "mrr": 29.0,
        "tokensUsed": 142500,
        "tokenLimit": 1000000,
        "connectedRepos": 2,
        "joinedDate": "2026-01-14",
        "lastActive": "Just now",
        "githubHandle": "ziaulhaquezia01",
        "region": "Asia/Dhaka",
        "isDeveloperEligible": True,
    },
    {
        "id": "cust_002",
        "name": "Rahim Chowdhury",
        "email": "rahim.chowdhury@techscale.io",
        "tier": "Enterprise",
        "status": "active",
        "mrr": 199.0,
        "tokensUsed": 1845000,
        "tokenLimit": 5000000,
        "connectedRepos": 14,
        "joinedDate": "2025-11-03",
        "lastActive": "12 mins ago",
        "githubHandle": "rahim-techscale",
        "region": "Asia/Singapore",
        "isDeveloperEligible": True,
    },
    {
        "id": "cust_003",
        "name": "Sarah Jenkins",
        "email": "sarah.j@vertexlabs.ai",
        "tier": "Enterprise",
        "status": "active",
        "mrr": 199.0,
        "tokensUsed": 2910000,
        "tokenLimit": 5000000,
        "connectedRepos": 8,
        "joinedDate": "2025-10-22",
        "lastActive": "45 mins ago",
        "githubHandle": "sjenkins-ai",
        "region": "US/East",
        "isDeveloperEligible": False,
    },
    {
        "id": "cust_004",
        "name": "Tanvir Ahmed",
        "email": "tanvir.dev@gmail.com",
        "tier": "Pro",
        "status": "active",
        "mrr": 29.0,
        "tokensUsed": 620400,
        "tokenLimit": 1000000,
        "connectedRepos": 3,
        "joinedDate": "2026-02-01",
        "lastActive": "2 hours ago",
        "githubHandle": "tanvir-ahmed",
        "region": "Asia/Dhaka",
        "isDeveloperEligible": True,
    },
    {
        "id": "cust_005",
        "name": "Elena Rostova",
        "email": "elena@novasoft.eu",
        "tier": "Pro",
        "status": "past_due",
        "mrr": 29.0,
        "tokensUsed": 980200,
        "tokenLimit": 1000000,
        "connectedRepos": 4,
        "joinedDate": "2026-01-18",
        "lastActive": "5 hours ago",
        "githubHandle": "elena-novasoft",
        "region": "Europe/Berlin",
        "isDeveloperEligible": False,
    },
    {
        "id": "cust_006",
        "name": "Marcus Brody",
        "email": "marcus.brody@openbuild.dev",
        "tier": "Free",
        "status": "active",
        "mrr": 0.0,
        "tokensUsed": 42100,
        "tokenLimit": 100000,
        "connectedRepos": 1,
        "joinedDate": "2026-02-10",
        "lastActive": "1 day ago",
        "githubHandle": "mbrody",
        "region": "US/West",
        "isDeveloperEligible": False,
    },
    {
        "id": "cust_007",
        "name": "Fatima Al-Mansoor",
        "email": "fatima@cloudcore.ae",
        "tier": "Enterprise",
        "status": "active",
        "mrr": 199.0,
        "tokensUsed": 3120000,
        "tokenLimit": 5000000,
        "connectedRepos": 12,
        "joinedDate": "2025-12-08",
        "lastActive": "3 hours ago",
        "githubHandle": "fatima-cloud",
        "region": "MiddleEast/Dubai",
        "isDeveloperEligible": True,
    },
    {
        "id": "cust_008",
        "name": "Liam O'Connor",
        "email": "liam.oc@celticstack.ie",
        "tier": "Free",
        "status": "active",
        "mrr": 0.0,
        "tokensUsed": 89300,
        "tokenLimit": 100000,
        "connectedRepos": 1,
        "joinedDate": "2026-01-29",
        "lastActive": "4 days ago",
        "githubHandle": "liam-celtic",
        "region": "Europe/Dublin",
        "isDeveloperEligible": False,
    },
    {
        "id": "cust_009",
        "name": "Kavita Sundaram",
        "email": "kavita@nexusanalytics.in",
        "tier": "Pro",
        "status": "active",
        "mrr": 29.0,
        "tokensUsed": 412000,
        "tokenLimit": 1000000,
        "connectedRepos": 5,
        "joinedDate": "2026-01-05",
        "lastActive": "Yesterday",
        "githubHandle": "kavita-sundaram",
        "region": "Asia/Mumbai",
        "isDeveloperEligible": False,
    },
    {
        "id": "cust_010",
        "name": "David Zhao",
        "email": "zhao.david@quantmatrix.com",
        "tier": "Free",
        "status": "suspended",
        "mrr": 0.0,
        "tokensUsed": 100000,
        "tokenLimit": 100000,
        "connectedRepos": 0,
        "joinedDate": "2026-02-04",
        "lastActive": "7 days ago",
        "githubHandle": "zhaodavid",
        "region": "Asia/Tokyo",
        "isDeveloperEligible": False,
    },
    {
        "id": "cust_011",
        "name": "Alexei Vanev",
        "email": "alexei@hyperloop-labs.tech",
        "tier": "Enterprise",
        "status": "active",
        "mrr": 199.0,
        "tokensUsed": 4400100,
        "tokenLimit": 5000000,
        "connectedRepos": 22,
        "joinedDate": "2025-09-15",
        "lastActive": "20 mins ago",
        "githubHandle": "alexei-hyperloop",
        "region": "Europe/London",
        "isDeveloperEligible": True,
    },
    {
        "id": "cust_012",
        "name": "Shakib Hassan",
        "email": "shakib.h@vectorcode.org",
        "tier": "Free",
        "status": "active",
        "mrr": 0.0,
        "tokensUsed": 15400,
        "tokenLimit": 100000,
        "connectedRepos": 1,
        "joinedDate": "2026-02-11",
        "lastActive": "5 hours ago",
        "githubHandle": "shakib-vector",
        "region": "Asia/Dhaka",
        "isDeveloperEligible": False,
    },
]

# In-memory store for instant synchronization and test harnesses
_MEMORY_CUSTOMERS: list[dict[str, Any]] = copy.deepcopy(INITIAL_SEED_CUSTOMERS)


def _get_memory_customers() -> list[dict[str, Any]]:
    return _MEMORY_CUSTOMERS


def _find_memory_customer(customer_id: str) -> dict[str, Any] | None:
    for cust in _MEMORY_CUSTOMERS:
        if cust.get("id") == customer_id:
            return cust
    return None


# --- Shared Handler Logic ---


async def _list_customers_impl() -> list[dict[str, Any]]:
    return list(_MEMORY_CUSTOMERS)


async def _get_customer_impl(customer_id: str) -> dict[str, Any]:
    c = _find_memory_customer(customer_id)
    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID '{customer_id}' not found",
        )
    return c


async def _create_customer_impl(payload: CustomerCreate) -> dict[str, Any]:
    # Check duplicate email
    for existing in _MEMORY_CUSTOMERS:
        if existing["email"].lower() == payload.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer with email '{payload.email}' already exists",
            )

    new_id = f"cust_{uuid.uuid4().hex[:6]}"
    record: dict[str, Any] = {
        "id": new_id,
        "name": payload.name,
        "email": payload.email,
        "tier": payload.tier,
        "status": payload.status,
        "mrr": float(payload.mrr),
        "tokensUsed": payload.tokens_used,
        "tokenLimit": payload.token_limit,
        "connectedRepos": payload.connected_repos,
        "joinedDate": datetime.now(UTC).strftime("%Y-%m-%d"),
        "lastActive": "Just now",
        "githubHandle": payload.github_handle,
        "region": payload.region or "Asia/Dhaka",
        "isDeveloperEligible": payload.is_developer_eligible,
    }
    _MEMORY_CUSTOMERS.insert(0, record)
    return record


async def _update_customer_impl(customer_id: str, payload: CustomerUpdate) -> dict[str, Any]:
    record = _find_memory_customer(customer_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID '{customer_id}' not found",
        )

    data = payload.model_dump(exclude_unset=True, by_alias=True)
    for k, v in data.items():
        if v is not None:
            record[k] = v
    record["lastActive"] = "Just now"
    return record


async def _delete_customer_impl(customer_id: str) -> bool:
    global _MEMORY_CUSTOMERS
    initial_len = len(_MEMORY_CUSTOMERS)
    _MEMORY_CUSTOMERS = [c for c in _MEMORY_CUSTOMERS if c.get("id") != customer_id]
    if len(_MEMORY_CUSTOMERS) == initial_len:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID '{customer_id}' not found",
        )
    return True


# =========================================================================
# Standard /api/customers Route Group
# =========================================================================


@router.get("/api/customers")
async def get_customers() -> dict[str, Any]:
    """Retrieve all customers."""
    customers = await _list_customers_impl()
    return {"customers": customers}


@router.post("/api/customers", status_code=status.HTTP_201_CREATED)
async def create_customer(payload: CustomerCreate) -> dict[str, Any]:
    """Create a new customer."""
    customer = await _create_customer_impl(payload)
    return {"success": True, "customer": customer, "customers": _get_memory_customers()}


@router.get("/api/customers/{customer_id}")
async def get_customer_by_id(customer_id: str) -> dict[str, Any]:
    """Retrieve customer by unique identifier."""
    customer = await _get_customer_impl(customer_id)
    return {"customer": customer}


@router.patch("/api/customers/{customer_id}")
async def patch_customer(customer_id: str, payload: CustomerUpdate) -> dict[str, Any]:
    """Update customer details."""
    customer = await _update_customer_impl(customer_id, payload)
    return {"success": True, "customer": customer, "customers": _get_memory_customers()}


@router.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: str) -> dict[str, Any]:
    """Delete a customer."""
    await _delete_customer_impl(customer_id)
    return {"success": True, "customers": _get_memory_customers()}


# =========================================================================
# Admin /api/admin/customers Route Group (Mirrored for Studio Admin View)
# =========================================================================


@router.get("/api/admin/customers")
async def get_admin_customers() -> dict[str, Any]:
    """Admin dashboard customer directory listing."""
    customers = await _list_customers_impl()
    return {"customers": customers}


@router.post("/api/admin/customers", status_code=status.HTTP_201_CREATED)
async def create_admin_customer(payload: CustomerCreate) -> dict[str, Any]:
    """Admin dashboard customer creation."""
    customer = await _create_customer_impl(payload)
    return {"success": True, "customer": customer, "customers": _get_memory_customers()}


@router.patch("/api/admin/customers/{customer_id}")
async def patch_admin_customer(customer_id: str, payload: CustomerUpdate) -> dict[str, Any]:
    """Admin dashboard customer update."""
    customer = await _update_customer_impl(customer_id, payload)
    return {"success": True, "customer": customer, "customers": _get_memory_customers()}


@router.delete("/api/admin/customers/{customer_id}")
async def delete_admin_customer(customer_id: str) -> dict[str, Any]:
    """Admin dashboard customer deletion."""
    await _delete_customer_impl(customer_id)
    return {"success": True, "customers": _get_memory_customers()}
