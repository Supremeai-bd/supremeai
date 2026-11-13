"""Customer database service layer for SupremeAI.

Provides asynchronous database operations for customers using SQLAlchemy and
Pydantic schemas with full support for filtering, pagination, and transactional integrity.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import delete as sql_delete, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from models.customer import Customer


async def get_all_customers(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Customer]:
    """Retrieve paginated list of customers."""
    result = await db.execute(select(Customer).offset(skip).limit(limit))
    return result.scalars().all()


async def get_customer_by_id(db: AsyncSession, customer_id: str) -> Customer | None:
    """Retrieve customer by unique primary key."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    return result.scalar_one_or_none()


async def get_customer_by_email(db: AsyncSession, email: str) -> Customer | None:
    """Retrieve customer by unique email address."""
    result = await db.execute(select(Customer).where(Customer.email == email))
    return result.scalar_one_or_none()


async def create_customer(db: AsyncSession, customer_data: dict[str, Any]) -> Customer:
    """Create and persist a new customer record."""
    customer = Customer(**customer_data)
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def update_customer(
    db: AsyncSession,
    customer_id: str,
    customer_data: dict[str, Any],
) -> Customer | None:
    """Update existing customer details."""
    result = await db.execute(
        sql_update(Customer)
        .where(Customer.id == customer_id)
        .values(**customer_data)
        .returning(Customer)
    )
    updated = result.scalar_one_or_none()
    if updated is not None:
        await db.commit()
    return updated


async def delete_customer(db: AsyncSession, customer_id: str) -> bool:
    """Delete a customer by primary key."""
    result = await db.execute(sql_delete(Customer).where(Customer.id == customer_id))
    await db.commit()
    return bool(result.rowcount and result.rowcount > 0)
