# গাইডলাইন ০৭ — ডেটাবেজ ও মাইগ্রেশন ম্যানেজমেন্ট

> **স্তর:** নতুন থেকে অভিজ্ঞ ডেভেলপার
> **প্রযোজ্য:** PostgreSQL, SQLAlchemy, Alembic

---

## ৭.১ — সবচেয়ে বিপজ্জনক DB ভুলগুলো

### ভুল ১ — `DROP TABLE ... CASCADE` data-loss risk

```python
# ❌ EXTREMELY DANGEROUS — production-এ কখনো এটা করবেন না
def reset_database():
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(f"DROP TABLE IF EXISTS {table.name} CASCADE")

# ✅ CORRECT — শুধু test/dev-এ, এবং explicit confirmation সহ
def reset_database_dev_only():
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("Cannot reset database in production!")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
```

### ভুল ২ — Migration ছাড়া Schema পরিবর্তন

```python
# ❌ WRONG — সরাসরি `create_all()` production-এ
Base.metadata.create_all(engine)
# এটা existing table-এ নতুন column যোগ করে না!

# ✅ CORRECT — Alembic migration দিয়ে
alembic upgrade head
```

---

## ৭.২ — Alembic Migration সঠিক ব্যবহার

```bash
# নতুন migration তৈরি (auto-detect model changes)
alembic revision --autogenerate -m "add_user_credits_column"

# Migration চালানো
alembic upgrade head

# একধাপ পেছানো
alembic downgrade -1

# বর্তমান version দেখা
alembic current

# Migration history
alembic history --verbose
```

### Migration ফাইল Review করুন আগেই

```python
# alembic/versions/xxx_add_user_credits_column.py
def upgrade() -> None:
    # ✅ nullable=True দিয়ে শুরু করুন — existing row-গুলো break হবে না
    op.add_column('users', sa.Column('credits', sa.Integer(), nullable=True, server_default='0'))

    # তারপর backfill করুন
    op.execute("UPDATE users SET credits = 0 WHERE credits IS NULL")

    # তারপর NOT NULL করুন
    op.alter_column('users', 'credits', nullable=False)

def downgrade() -> None:
    op.drop_column('users', 'credits')
```

### ⚠️ Migration এ কখনো করবেন না

```python
# ❌ WRONG — migration-এ model import করবেন না
from core.models.user import User
User.query.filter(...)  # migration আগে বা পরে model পরিবর্তন হলে break করবে

# ✅ CORRECT — raw SQL বা op ব্যবহার করুন
op.execute("UPDATE users SET role = 'admin' WHERE email LIKE '%@supremeai.com'")
```

---

## ৭.৩ — SQLAlchemy Model সঠিক Pattern

```python
# backend/models/user.py
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

class User(Base):
    __tablename__ = "users"

    # ✅ Typed columns (SQLAlchemy 2.0 style)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user")

    # Composite index — frequently queried together
    __table_args__ = (
        Index("ix_users_email_active", "email", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
```

---

## ৭.৪ — Async DB Session Management

```python
# backend/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings

# বাংলা: async engine তৈরি — synchronous create_engine ব্যবহার করবেন না
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # Dead connection detect করে
    echo=settings.environment == "development",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit-এর পরেও object access করা যাবে
)

async def get_db():
    """FastAPI dependency — request শেষে automatically close হয়।"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## ৭.৫ — N+1 Query সমস্যা এড়ানো

```python
# ❌ WRONG — N+1 query (1 query for users + N queries for each user's sessions)
users = await session.execute(select(User))
for user in users.scalars():
    print(user.sessions)  # এখানে প্রতিটা user-এর জন্য আলাদা query!

# ✅ CORRECT — eager loading
from sqlalchemy.orm import selectinload

result = await session.execute(
    select(User).options(selectinload(User.sessions))
)
users = result.scalars().all()
# এখন sessions already loaded — extra query নেই
```

---

## ৭.৬ — Index Strategy

```python
# Self-healing checklist — এই fields-এ index দিন:
# ✅ WHERE clause-এ frequently used fields
# ✅ JOIN-এ used foreign keys
# ✅ ORDER BY-এ used fields
# ✅ UNIQUE constraint যোগ করুন where applicable

# Composite index — order গুরুত্বপূর্ণ (most selective first)
Index("ix_audit_logs_user_created", "user_id", "created_at")
# user_id=X দিয়ে search → fast. user_id=X AND created_at>Y → fast. শুধু created_at → slow.
```

---

## চেকলিস্ট — DB Change করার আগে

- [ ] Production DB-তে `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` নেই
- [ ] নতুন column `nullable=True` দিয়ে শুরু, পরে backfill করে `NOT NULL`
- [ ] Alembic migration তৈরি করা হয়েছে (`--autogenerate`)
- [ ] Migration-এ `downgrade()` function লেখা আছে
- [ ] Migration-এ model import নেই, raw SQL/op ব্যবহার
- [ ] নতুন model-এ frequently queried fields-এ index আছে
- [ ] N+1 query নেই — `selectinload` বা `joinedload` ব্যবহার
- [ ] `get_db()` dependency দিয়ে session পাওয়া হচ্ছে, সরাসরি `AsyncSessionLocal()` নয়
