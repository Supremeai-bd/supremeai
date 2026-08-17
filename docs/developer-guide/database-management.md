# Database Management

## Overview

SupremeAI 2.0 uses a **multi-pool database connection architecture** to handle different types of database access patterns. This document explains the connection pools, their sizing strategies, and the consolidation roadmap.

## Connection Pools

### 1. SQLAlchemy Async Engine (`database/session.py`)

**Purpose:** ORM-based database access using SQLAlchemy models
**Pool Type:** `create_async_engine` with `asyncpg` dialect
**Sync/Async:** Async
**Usage:** Primary request-serving database operations (user data, agent state, etc.)

**Pool Sizing (Role-Aware):**

| Role | Pool Size | Max Overflow | Total Max |
|------|-----------|--------------|-----------|
| `admin` | 1 | 2 | 3 |
| `user` (default) | 2 | 13 | 15 |

**Key Features:**
- Lazy initialization (engine created on first access)
- SQLite fallback for local development (`sqlite+aiosqlite:///:memory:`)
- PostgreSQL URL auto-conversion (`postgresql://` → `postgresql+asyncpg://`)
- Pool recycling every 1800 seconds (30 minutes)

**Usage:**
```python
from database.session import get_async_session

async for session in get_async_session():
    result = await session.execute(select(User).where(User.id == user_id))
```

### 2. asyncpg Connection Pool (`core/pgbouncer_pool.py`)

**Purpose:** Raw SQL queries with minimal overhead (no ORM)
**Pool Type:** `asyncpg.create_pool()`
**Sync/Async:** Async
**Usage:** High-performance raw SQL queries (analytics, bulk operations)

**Pool Sizing (Role-Aware):**

| Role | Min Size | Max Size |
|------|----------|----------|
| `admin` | 1 | 3 |
| `user` (default) | 3 | 12 |

**Key Features:**
- Singleton pattern with asyncio.Lock for thread safety
- Exponential backoff retry (`get_db_pool_with_retry`)
- Connection release/acquire methods
- Proxy methods for `execute`, `fetch`, `fetchrow`, `fetchval`
- CPU-bound task offloading via `asyncio.to_thread`

**Usage:**
```python
from core.pgbouncer_pool import get_db_pool

pool = await get_db_pool()
rows = await pool.fetch("SELECT * FROM users WHERE id = $1", user_id)
```

### 3. psycopg2 Sync Pool (`core/persistence/pooled_pg.py`)

**Purpose:** Synchronous database access for secondary subsystems
**Pool Type:** `psycopg2.pool.ThreadedConnectionPool`
**Sync/Async:** Sync
**Usage:** Checkpoint manager, error pattern DB, audit logger, memory service

**Pool Sizing:**

| Parameter | Value |
|-----------|-------|
| Min Connections | 1 |
| Max Connections | 4 (configurable via `PERSISTENCE_PG_POOL_MAX`) |

**Key Features:**
- Thread-safe with `threading.Lock`
- Sticky unavailable flag (prevents repeated failed connection attempts)
- Context manager for safe connection acquisition/release
- Automatic cleanup via `atexit`
- SQLite fallback detection

**Usage:**
```python
from core.persistence.pooled_pg import get_sync_connection

with get_sync_connection() as conn:
    conn.execute("INSERT INTO checkpoints ...")
```

## Pool Sizing Strategy

The three pools work together to ensure total connections stay within Supabase's free-tier PgBouncer limits:

```
Total Max Connections = SQLAlchemy (15) + asyncpg (12) + psycopg2 (4) = 31
```

This budget ensures:
- Primary request traffic (SQLAlchemy) gets the largest share
- Raw SQL queries (asyncpg) get a moderate share
- Secondary subsystems (psycopg2) get a small, bounded share

## Database Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                     │
│  FastAPI Routes | Agent Swarm | Tools | Workflows         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   CONNECTION MANAGER                     │
│  Unified interface for all database access patterns      │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ SQLAlchemy   │ │ asyncpg      │ │ psycopg2     │
│ Async Engine │ │ Raw SQL Pool │ │ Sync Pool    │
│ (ORM)        │ │ (High Perf)  │ │ (Legacy)     │
└──────────────┘ └──────────────┘ └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
              ┌─────────────────────────┐
              │   Supabase PostgreSQL   │
              │   (PgBouncer Pooler)    │
              └─────────────────────────┘
```

## Consolidation Roadmap

### Phase 1: Documentation (Completed)
- ✅ Created this database management guide
- ✅ Documented all three pools and their sizing strategies

### Phase 2: Unified Connection Manager
- **Goal:** Create a `ConnectionManager` class that wraps all three pools
- **Approach:** Additive — does not modify existing pool implementations
- **Interface:** Single `get_connection()` method that routes to the appropriate pool

### Phase 3: Pool Consolidation
- **Goal:** Reduce from 3 pools to 2 (async + sync)
- **Strategy:**
  - Merge asyncpg pool into SQLAlchemy engine for raw SQL needs
  - Keep psycopg2 pool for sync legacy subsystems
  - Or: Convert sync subsystems to async and eliminate psycopg2 pool

### Phase 4: Lazy Initialization
- **Goal:** All pools initialize lazily on first access
- **Benefit:** Faster cold start, no DB connection during boot

## Best Practices

### 1. Use the Right Pool

- **SQLAlchemy Engine**: For ORM models, migrations, and standard CRUD
- **asyncpg Pool**: For high-performance raw SQL (analytics, bulk inserts)
- **psycopg2 Pool**: Only for sync legacy code that can't be converted to async

### 2. Respect Pool Sizing

Never exceed the configured max connections. The pools are sized to work together:

```python
# ✅ Good - uses existing pool
pool = await get_db_pool()
result = await pool.fetch(query)

# ❌ Bad - creates new connection outside pool
conn = await asyncpg.connect(dsn)
```

### 3. Handle Connection Failures

Always use retry logic for connection acquisition:

```python
from core.pgbouncer_pool import get_db_pool_with_retry

pool = await get_db_pool_with_retry(max_retries=3)
```

### 4. Clean Up Resources

Always release connections back to the pool:

```python
# asyncpg
conn = await pool.acquire()
try:
    result = await conn.fetch(query)
finally:
    await pool.release(conn)

# psycopg2 (context manager handles this)
with get_sync_connection() as conn:
    conn.execute(query)
```

## Related Files

| File | Pool Type | Description |
|------|-----------|-------------|
| `database/session.py` | SQLAlchemy | Async ORM engine |
| `database/multi_db_router.py` | Router | Multi-database routing |
| `core/pgbouncer_pool.py` | asyncpg | Raw SQL connection pool |
| `core/persistence/pooled_pg.py` | psycopg2 | Sync connection pool |
| `core/persistence/write_behind.py` | Writer | Write-behind cache for sync pool |
| `backend/config/routing_policy.json` | Config | Database routing policies |
