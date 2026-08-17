# SupremeAI 2.0 — Database Documentation

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## 🗄️ Database Architecture Overview

SupremeAI 2.0 uses a **polyglot persistence** architecture, selecting the optimal database technology for each specific use case. This approach maximizes performance, scalability, and feature availability while maintaining zero-cost operation.

### Database Technologies

| Database | Purpose | Provider | Free Tier | Status |
|----------|---------|----------|-----------|--------|
| **PostgreSQL** | Primary relational database | Supabase | 500MB | ✅ Active |
| **Redis** | Caching, sessions, rate limiting | Upstash | 10K req/day | ✅ Active |
| **Neo4j** | Graph database for knowledge graphs | Aura | 10K nodes | ✅ Active |
| **Qdrant** | Vector database for embeddings | Cloud | 1GB | ✅ Active |
| **SQLite** | Local task queue, fallback | Local | Unlimited | ✅ Active |
| **MongoDB** | Document storage (optional) | - | - | ⚠️ Optional |
| **Elasticsearch** | Full-text search (optional) | - | - | ⚠️ Optional |

---

## 🐘 PostgreSQL (Supabase)

### Purpose
Primary relational database for structured data storage, user management, agent configurations, execution logs, and audit trails.

### Connection Configuration

**Connection String Pattern**:
```
postgresql+asyncpg://user:password@host:port/database
```

**Connection Pooling**:
- **Engine**: AsyncEngine with lazy initialization
- **Pool Size**: 5-20 connections (configurable)
- **Pool Class**: QueuePool
- **Max Overflow**: 10
- **Pool Recycle**: 3600 seconds
- **Pool Pre-Ping**: True

**Configuration File**: `backend/database/session.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

### Database Schema

#### Core Tables

**users**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    roles JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
```

**agents**
```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}',
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_agents_user_id ON agents(user_id);
CREATE INDEX idx_agents_is_active ON agents(is_active);
CREATE INDEX idx_agents_config ON agents USING GIN(config);
```

**executions**
```sql
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- pending, running, completed, failed, cancelled
    input JSONB NOT NULL DEFAULT '{}',
    output JSONB DEFAULT '{}',
    error TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_executions_agent_id ON executions(agent_id);
CREATE INDEX idx_executions_user_id ON executions(user_id);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_started_at ON executions(started_at);
```

**api_keys**
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    hashed_key VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL, -- First 20 chars for identification
    permissions JSONB DEFAULT '[]',
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
```

**audit_logs**
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    signature VARCHAR(255) NOT NULL -- SHA-256 hash chain
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
```

**memories**
```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(1536), -- pgvector extension
    memory_type VARCHAR(50) NOT NULL, -- short_term, long_term, experience
    importance FLOAT DEFAULT 0.5,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_agent_id ON memories(agent_id);
CREATE INDEX idx_memories_type ON memories(memory_type);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
```

**tools**
```sql
CREATE TABLE tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}',
    parameters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tools_name ON tools(name);
CREATE INDEX idx_tools_is_active ON tools(is_active);
```

**workflows**
```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}',
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_workflows_user_id ON workflows(user_id);
CREATE INDEX idx_workflows_is_active ON workflows(is_active);
```

**pipelines**
```sql
CREATE TABLE pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}',
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_pipelines_user_id ON pipelines(user_id);
CREATE INDEX idx_pipelines_is_active ON pipelines(is_active);
```

### PostgreSQL Extensions

**pgvector** (Vector embeddings):
```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Used for memory embeddings
CREATE INDEX idx_memories_embedding ON memories 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**uuid-ossp** (UUID generation):
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Used for ID generation
-- Note: Project uses gen_random_uuid() from pgcrypto instead
```

**pgcrypto** (Cryptographic functions):
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Used for:
-- gen_random_uuid() - UUID generation
-- crypt() - Password hashing
-- digest() - Hashing
```

### Database Migrations

**Tool**: Alembic

**Configuration**: `backend/alembic.ini`

**Migration Directory**: `backend/alembic/versions/`

**Migration Commands**:
```bash
# Create migration
cd backend && alembic revision --autogenerate -m "description"

# Apply migrations
cd backend && alembic upgrade head

# Rollback migration
cd backend && alembic downgrade -1

# Show current version
cd backend && alembic current
```

**Migration Naming Convention**:
```
{timestamp}_{description}.py
Example: 20250104_120000_add_user_table.py
```

---

## 🔴 Redis (Upstash)

### Purpose
Caching, session storage, rate limiting, and distributed locking.

### Connection Configuration

**Connection Pattern**:
```
redis://:password@host:port
```

**Configuration**:
```python
import redis

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)
```

### Data Structures

#### 1. Session Storage

**Key Pattern**: `session:{session_id}`

**Value**: JSON string
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "roles": ["user"],
  "created_at": "2025-01-04T00:00:00Z",
  "expires_at": "2025-01-05T00:00:00Z"
}
```

**TTL**: 24 hours

**Operations**:
```python
# Store session
redis_client.setex(
    f"session:{session_id}",
    86400,  # 24 hours
    json.dumps(session_data)
)

# Retrieve session
session_data = redis_client.get(f"session:{session_id}")

# Delete session
redis_client.delete(f"session:{session_id}")
```

#### 2. Rate Limiting

**Key Pattern**: `rate_limit:{user_id}:{endpoint}`

**Value**: Counter (integer)

**TTL**: 60 seconds (1 minute window)

**Operations**:
```python
# Increment counter
count = redis_client.incr(f"rate_limit:{user_id}:{endpoint}")

# Set TTL on first request
if count == 1:
    redis_client.expire(f"rate_limit:{user_id}:{endpoint}", 60)

# Check limit
if count > MAX_REQUESTS_PER_MINUTE:
    raise RateLimitExceeded()
```

#### 3. Token Blacklist

**Key Pattern**: `token_blacklist:{jti}`

**Value**: "1" (exists)

**TTL**: 24 hours (matches JWT expiration)

**Operations**:
```python
# Add to blacklist
redis_client.setex(
    f"token_blacklist:{jti}",
    86400,  # 24 hours
    "1"
)

# Check if blacklisted
is_blacklisted = redis_client.exists(f"token_blacklist:{jti}")
```

#### 4. Query Cache

**Key Pattern**: `cache:{hash}`

**Value**: JSON string (cached result)

**TTL**: 300 seconds (5 minutes)

**Operations**:
```python
# Generate cache key from query
import hashlib
cache_key = hashlib.md5(query.encode()).hexdigest()

# Try to get from cache
cached = redis_client.get(f"cache:{cache_key}")
if cached:
    return json.loads(cached)

# Execute query and cache result
result = execute_query(query)
redis_client.setex(
    f"cache:{cache_key}",
    300,  # 5 minutes
    json.dumps(result)
)
return result
```

#### 5. Feature Flags

**Key Pattern**: `feature_flag:{flag_name}`

**Value**: JSON string
```json
{
  "enabled": true,
  "rollout_percentage": 100,
  "target_users": [],
  "created_at": "2025-01-04T00:00:00Z"
}
```

**TTL**: No expiration (manual updates)

#### 6. Distributed Locks

**Key Pattern**: `lock:{resource_id}`

**Value**: Lock owner ID

**TTL**: 30 seconds (auto-release)

**Operations**:
```python
# Acquire lock
lock_acquired = redis_client.set(
    f"lock:{resource_id}",
    lock_id,
    nx=True,  # Only set if not exists
    ex=30  # Auto-release after 30s
)

if lock_acquired:
    try:
        # Perform operation
        pass
    finally:
        # Release lock
        redis_client.delete(f"lock:{resource_id}")
```

### Redis Commands Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `SETEX` | Set with TTL | `SETEX key 300 value` |
| `GET` | Get value | `GET key` |
| `DEL` | Delete key | `DEL key` |
| `EXISTS` | Check existence | `EXISTS key` |
| `INCR` | Increment counter | `INCR key` |
| `EXPIRE` | Set TTL | `EXPIRE key 300` |
| `TTL` | Get remaining TTL | `TTL key` |
| `KEYS` | Find keys (pattern) | `KEYS rate_limit:*` |
| `FLUSHDB` | Clear all keys | `FLUSHDB` |

---

## 🕸️ Neo4j (Aura)

### Purpose
Graph database for knowledge graphs, agent collaboration networks, and relationship mapping.

### Connection Configuration

**Connection Pattern**:
```
neo4j://host:port
```

**Configuration**:
```python
from neo4j import AsyncGraphDatabase

driver = AsyncGraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)
```

### Graph Schema

#### Node Labels

**User**
```cypher
CREATE (u:User {
  id: "uuid",
  email: "user@example.com",
  created_at: "2025-01-04T00:00:00Z"
})
```

**Agent**
```cypher
CREATE (a:Agent {
  id: "uuid",
  name: "Agent Name",
  config: {},
  created_at: "2025-01-04T00:00:00Z"
})
```

**Tool**
```cypher
CREATE (t:Tool {
  id: "uuid",
  name: "Tool Name",
  description: "Tool description",
  version: "1.0.0"
})
```

**Knowledge**
```cypher
CREATE (k:Knowledge {
  id: "uuid",
  content: "Knowledge content",
  source: "source_id",
  embedding: [0.1, 0.2, ...]
})
```

**Execution**
```cypher
CREATE (e:Execution {
  id: "uuid",
  status: "completed",
  started_at: "2025-01-04T00:00:00Z",
  completed_at: "2025-01-04T00:01:00Z"
})
```

#### Relationship Types

**OWNS** (User → Agent)
```cypher
MATCH (u:User {id: $user_id}), (a:Agent {id: $agent_id})
CREATE (u)-[:OWNS {
  created_at: datetime()
}]->(a)
```

**USES** (Agent → Tool)
```cypher
MATCH (a:Agent {id: $agent_id}), (t:Tool {id: $tool_id})
CREATE (a)-[:USES {
  usage_count: 0,
  last_used: datetime()
}]->(t)
```

**DEPENDS_ON** (Agent → Agent)
```cypher
MATCH (a1:Agent {id: $agent1_id}), (a2:Agent {id: $agent2_id})
CREATE (a1)-[:DEPENDS_ON {
  dependency_type: "input"
}]->(a2)
```

**EXECUTED** (Agent → Execution)
```cypher
MATCH (a:Agent {id: $agent_id}), (e:Execution {id: $execution_id})
CREATE (a)-[:EXECUTED {
  started_at: datetime()
}]->(e)
```

**RELATED_TO** (Knowledge → Knowledge)
```cypher
MATCH (k1:Knowledge {id: $knowledge1_id}), (k2:Knowledge {id: $knowledge2_id})
CREATE (k1)-[:RELATED_TO {
  similarity: 0.95,
  relationship_type: "semantic"
}]->(k2)
```

**PART_OF** (Knowledge → Agent)
```cypher
MATCH (k:Knowledge {id: $knowledge_id}), (a:Agent {id: $agent_id})
CREATE (k)-[:PART_OF {
  added_at: datetime()
}]->(a)
```

### Common Queries

**Find all agents for a user**:
```cypher
MATCH (u:User {id: $user_id})-[:OWNS]->(a:Agent)
RETURN a
ORDER BY a.created_at DESC
```

**Find agent collaboration graph**:
```cypher
MATCH path = (a1:Agent)-[:DEPENDS_ON*1..3]-(a2:Agent)
WHERE a1.id = $agent_id
RETURN path
```

**Find related knowledge**:
```cypher
MATCH (k:Knowledge {id: $knowledge_id})-[:RELATED_TO]-(related:Knowledge)
RETURN related
ORDER BY related.similarity DESC
LIMIT 10
```

**Find agent execution history**:
```cypher
MATCH (a:Agent {id: $agent_id})-[:EXECUTED]->(e:Execution)
RETURN e
ORDER BY e.started_at DESC
LIMIT 100
```

---

## 🔍 Qdrant (Vector Database)

### Purpose
Vector database for semantic search, RAG (Retrieval-Augmented Generation), and memory retrieval.

### Connection Configuration

**Connection Pattern**:
```
https://{cluster_id}.{region}.qdrant.tech
```

**Configuration**:
```python
from qdrant_client import QdrantClient

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)
```

### Collections

#### 1. Memory Embeddings

**Collection Name**: `memories`

**Vector Size**: 1536 dimensions

**Distance Metric**: Cosine

**Schema**:
```python
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],  # 1536 dimensions
  "payload": {
    "user_id": "uuid",
    "agent_id": "uuid",
    "content": "Memory content",
    "memory_type": "short_term|long_term|experience",
    "importance": 0.8,
    "created_at": "2025-01-04T00:00:00Z"
  }
}
```

**Index Configuration**:
```python
client.create_collection(
    collection_name="memories",
    vectors_config=VectorParams(
        size=1536,
        distance=Distance.COSINE
    ),
    optimizers_config=OptimizersConfigDiff(
        indexing_threshold=20000
    )
)
```

**Operations**:
```python
# Upsert memory
client.upsert(
    collection_name="memories",
    points=[
        PointStruct(
            id=memory_id,
            vector=embedding,
            payload=payload
        )
    ]
)

# Search similar memories
results = client.search(
    collection_name="memories",
    query_vector=query_embedding,
    limit=10,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            )
        ]
    )
)
```

#### 2. Knowledge Base

**Collection Name**: `knowledge`

**Vector Size**: 1536 dimensions

**Distance Metric**: Cosine

**Schema**:
```python
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],  # 1536 dimensions
  "payload": {
    "document_id": "uuid",
    "chunk_id": "uuid",
    "content": "Knowledge chunk",
    "source": "document.pdf",
    "page": 5,
    "tenant_id": "uuid",
    "created_at": "2025-01-04T00:00:00Z"
  }
}
```

**Operations**:
```python
# Search knowledge base
results = client.search(
    collection_name="knowledge",
    query_vector=query_embedding,
    limit=5,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=tenant_id)
            )
        ]
    )
)
```

#### 3. Code Embeddings

**Collection Name**: `code`

**Vector Size**: 1536 dimensions

**Distance Metric**: Cosine

**Schema**:
```python
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],  # 1536 dimensions
  "payload": {
    "file_path": "src/main.py",
    "function_name": "main",
    "class_name": "MainClass",
    "code": "def main(): ...",
    "language": "python",
    "project_id": "uuid"
  }
}
```

---

## 🗃️ SQLite (Local)

### Purpose
Local task queue, offline operation fallback, and lightweight data storage.

### Location
`backend/data/pending_tasks.db`

### Schema

**pending_tasks**
```sql
CREATE TABLE IF NOT EXISTS pending_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type VARCHAR(100) NOT NULL,
    payload TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_pending_tasks_status ON pending_tasks(status);
CREATE INDEX idx_pending_tasks_created_at ON pending_tasks(created_at);
```

**local_cache**
```sql
CREATE TABLE IF NOT EXISTS local_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    ttl INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_local_cache_ttl ON local_cache(ttl);
```

### Operations

**Connection**:
```python
import aiosqlite

async def get_local_db():
    db = await aiosqlite.connect('data/pending_tasks.db')
    db.row_factory = aiosqlite.Row
    return db
```

**Insert Task**:
```python
async def insert_task(db, task_type, payload):
    await db.execute(
        "INSERT INTO pending_tasks (task_type, payload) VALUES (?, ?)",
        (task_type, json.dumps(payload))
    )
    await db.commit()
```

**Get Pending Tasks**:
```python
async def get_pending_tasks(db, limit=100):
    async with db.execute(
        "SELECT * FROM pending_tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

---

## 🔄 Database Relationships

```mermaid
erDiagram
    USERS ||--o{ AGENTS : owns
    USERS ||--o{ EXECUTIONS : executes
    USERS ||--o{ API_KEYS : has
    USERS ||--o{ AUDIT_LOGS : creates
    
    AGENTS ||--o{ EXECUTIONS : has
    AGENTS ||--o{ MEMORIES : stores
    AGENTS ||--o{ TOOLS : uses
    
    EXECUTIONS ||--o{ EXECUTION_LOGS : generates
    
    USERS {
        uuid id PK
        string email UK
        string hashed_password
        jsonb roles
        boolean is_active
        timestamp created_at
    }
    
    AGENTS {
        uuid id PK
        string name
        jsonb config
        uuid user_id FK
        boolean is_active
        timestamp created_at
    }
    
    EXECUTIONS {
        uuid id PK
        uuid agent_id FK
        uuid user_id FK
        string status
        jsonb input
        jsonb output
        timestamp started_at
        timestamp completed_at
    }
    
    API_KEYS {
        uuid id PK
        uuid user_id FK
        string name
        string hashed_key UK
        jsonb permissions
        timestamp expires_at
        boolean is_active
    }
    
    AUDIT_LOGS {
        uuid id PK
        uuid user_id FK
        string action
        string resource_type
        uuid resource_id
        jsonb details
        timestamp timestamp
        string signature
    }
    
    MEMORIES {
        uuid id PK
        uuid user_id FK
        uuid agent_id FK
        text content
        vector embedding
        string memory_type
        timestamp created_at
    }
    
    TOOLS {
        uuid id PK
        string name UK
        jsonb config
        boolean is_active
        timestamp created_at
    }
```

---

## 📊 Database Performance

### Query Optimization

**Indexes**:
- All foreign keys indexed
- Frequently queried fields indexed
- JSONB fields use GIN indexes
- Vector fields use ivfflat indexes

**Connection Pooling**:
- Min: 5 connections
- Max: 20 connections
- Overflow: 10 connections
- Recycle: 3600 seconds

**Query Patterns**:
```sql
-- Use indexes
SELECT * FROM agents WHERE user_id = $1 AND is_active = true;

-- Avoid N+1 queries
SELECT u.*, a.* 
FROM users u
LEFT JOIN agents a ON a.user_id = u.id
WHERE u.id = $1;

-- Use JSONB efficiently
SELECT * FROM agents WHERE config @> '{"type": "chatbot"}';
```

### Caching Strategy

**Redis Caching**:
- Query results: 5 minutes TTL
- Sessions: 24 hours TTL
- Rate limits: 60 seconds TTL
- Feature flags: No expiration

**Cache Invalidation**:
```python
# Invalidate on update
async def update_agent(db, agent_id, updates):
    # Update database
    await db.execute(
        "UPDATE agents SET config = config || $1 WHERE id = $2",
        (json.dumps(updates), agent_id)
    )
    await db.commit()
    
    # Invalidate cache
    cache_key = hashlib.md5(f"agent:{agent_id}".encode()).hexdigest()
    redis_client.delete(f"cache:{cache_key}")
```

---

## 🔐 Database Security

### Access Control

**Row-Level Security (RLS)**:
```sql
-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
CREATE POLICY user_isolation ON users
    FOR ALL
    USING (id = current_user_id());
```

**Connection Security**:
- SSL/TLS required for all connections
- Connection pooling with PgBouncer
- IP whitelisting (Supabase)
- Password rotation (90 days)

### Data Encryption

**At Rest**:
- Supabase provides encryption at rest
- Sensitive fields encrypted with Fernet
- Passwords hashed with bcrypt

**In Transit**:
- TLS 1.3 for all connections
- Certificate validation
- No plaintext credentials

### Backup Strategy

**Automated Backups**:
- Daily backups (Supabase)
- 7-day retention
- Point-in-time recovery

**Manual Backups**:
```bash
# Export database
pg_dump -h host -U user -d database > backup.sql

# Import database
psql -h host -U user -d database < backup.sql
```

---

## 🔄 Data Flow

```mermaid
graph LR
    subgraph "Application"
        API[API Layer]
        SERVICES[Service Layer]
        MODELS[Models]
    end

    subgraph "Cache Layer"
        REDIS[(Redis)]
    end

    subgraph "Primary Database"
        PG[(PostgreSQL)]
    end

    subgraph "Vector Database"
        QDRANT[(Qdrant)]
    end

    subgraph "Graph Database"
        NEO4J[(Neo4j)]
    end

    subgraph "Local Storage"
        SQLITE[(SQLite)]
    end

    API --> REDIS
    API --> SERVICES
    SERVICES --> MODELS
    MODELS --> PG
    
    SERVICES --> REDIS
    SERVICES --> QDRANT
    SERVICES --> NEO4J
    SERVICES --> SQLITE
    
    PG --> QDRANT
    PG --> NEO4J
```

---

## 🛠️ Database Management

### Monitoring

**Key Metrics**:
- Connection pool utilization
- Query execution time
- Cache hit rate
- Database size
- Slow queries

**Queries**:
```sql
-- Check connection count
SELECT count(*) FROM pg_stat_activity;

-- Check slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check table sizes
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename))
FROM pg_tables
WHERE schemaname = 'public';
```

### Maintenance

**Vacuum**:
```sql
-- Auto-vacuum is enabled
-- Manual vacuum if needed
VACUUM ANALYZE users;
VACUUM ANALYZE agents;
VACUUM ANALYZE executions;
```

**Reindex**:
```sql
-- Reindex if needed
REINDEX INDEX idx_users_email;
REINDEX INDEX idx_agents_user_id;
```

**Cleanup**:
```sql
-- Delete old audit logs (older than 90 days)
DELETE FROM audit_logs 
WHERE timestamp < NOW() - INTERVAL '90 days';

-- Delete old executions (older than 30 days)
DELETE FROM executions 
WHERE started_at < NOW() - INTERVAL '30 days'
AND status IN ('completed', 'failed', 'cancelled');
```

---

## 🔗 Related Documents

- [03-ARCHITECTURE.md](03-ARCHITECTURE.md) - System architecture
- [04-FOLDER_STRUCTURE.md](04-FOLDER_STRUCTURE.md) - Directory organization
- [05-MODULE_DOCUMENTATION.md](05-MODULE_DOCUMENTATION.md) - Module details
- [08-CONFIGURATION_DOCUMENTATION.md](08-CONFIGURATION_DOCUMENTATION.md) - Configuration
- [11-API_DOCUMENTATION.md](11-API_DOCUMENTATION.md) - API layer

---

## ✅ Database Documentation Verification

**How to verify database documentation**:

1. **Check Database Connection**:
   ```bash
   # PostgreSQL
   psql -h host -U user -d database -c "SELECT version();"
   
   # Redis
   redis-cli ping
   
   # Neo4j
   cypher-shell "RETURN 1"
   
   # Qdrant
   curl https://qdrant-url/healthz
   ```

2. **Verify Tables Exist**:
   ```bash
   # PostgreSQL
   psql -h host -U user -d database -c "\dt"
   
   # SQLite
   sqlite3 backend/data/pending_tasks.db ".tables"
   ```

3. **Test Queries**:
   ```bash
   # PostgreSQL
   psql -h host -U user -d database -c "SELECT count(*) FROM users;"
   
   # Redis
   redis-cli dbsize
   
   # Neo4j
   cypher-shell "MATCH (n) RETURN count(n)"
   ```

4. **Check Indexes**:
   ```bash
   # PostgreSQL
   psql -h host -U user -d database -c "\di"
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: Database Team

---

## বাংলা সংস্করণ (Bengali Version)

# সুপ্রিম AI 2.0 — ডাটাবেস ডকুমেন্টেশন

**ভার্সন**: 2.0.0  
**শেষ আপডেট**: 2025-01-04  
**স্ট্যাটাস**: লিভিং ডকুমেন্ট  
**ক্লাসিফিকেশন**: ইন্টার্নাল  

---

## 🗄️ ডাটাবেস ওভারভিউ

সুপ্রিম AI 2.0 **পলিগ্লট পেরসিস্টেন্স আর্কিটেকচার** অনুসরণ করে, যার মানে প্রতিটি নির্দিষ্ট ব্যবহারের ক্ষেত্রে সেরা ডাটাবেস টেকনোলজি ব্যবহার করা হয়। এই পদ্ধতি অপ্টিমাল পারফরম্যান্স, বিশেষায়িত ফিচার এবং ভবিষ্যত-প্রুফ স্কেলিং প্রদান করে।

### ডাটাবেস স্ট্যাক

```mermaid
graph TB
    subgraph "PostgreSQL (Supabase)"
        PG_USERS[Users]
        PG_AGENTS[Agents]
        PG_EXECUTIONS[Executions]
        PG_MEMORIES[Memories]
        PG_AUDIT[Audit Logs]
    end

    subgraph "Redis (Upstash)"
        REDIS_SESSIONS[Sessions]
        REDIS_CACHE[Query Cache]
        REDIS_RATE[Rate Limits]
        REDIS_BLACKLIST[Token Blacklist]
    end

    subgraph "Neo4j (Aura)"
        NEO4J_GRAPH[Knowledge Graph]
        NEO4J_RELATIONS[Relationships]
    end

    subgraph "Qdrant (Cloud)"
        QDRANT_VECTORS[Vector Embeddings]
        QDRANT_SEARCH[Semantic Search]
    end

    subgraph "SQLite (Local)"
        SQLITE_TASKS[Pending Tasks]
    end

    PG_USERS --> REDIS_SESSIONS
    PG_AGENTS --> QDRANT_VECTORS
    PG_MEMORIES --> NEO4J_GRAPH
```

---

## 🐘 PostgreSQL (Supabase)

**উদ্দেশ্য**: প্রাইমারি রিলেশনাল ডাটাবেস

**কানেকশন স্ট্রিং**:
```
postgresql+asyncpg://user:password@host:5432/supremeai
```

**ফিচার**:
- JSONB ফর ফ্লেক্সিবল স্কিমা
- UUIDv7 ফর IDs
- pgvector ফর embeddings (1536 ডাইমেনশন)
- রো-লেভেল সিকিউরিটি
- কানেকশন পুলিং

**ফ্রি টিয়ার**: 500MB স্টোরেজ

---

### মূল টেবিল

#### 1. Users টেবিল

**উদ্দেশ্য**: ইউজার অ্যাকাউন্ট স্টোরেজ

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    roles JSONB DEFAULT '["user"]',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);
```

**কলাম**:
| কলাম | টাইপ | নিয়ম | বিবরণ |
|-------|------|-------|--------|
| id | UUID | PK | ইউজার আইডি |
| email | VARCHAR(255) | UNIQUE, NOT NULL | ইমেইল অ্যাড্রেস |
| hashed_password | VARCHAR(255) | NOT NULL | বCrypt হ্যাশড পাসওয়ার্ড |
| roles | JSONB | DEFAULT ['user'] | রোল লিস্ট |
| is_active | BOOLEAN | DEFAULT true | অ্যাকাউন্ট সক্রিয় |
| created_at | TIMESTAMP | DEFAULT now() | নিবন্ধন তারিখ |
| updated_at | TIMESTAMP | DEFAULT now() | আপডেট তারিখ |

**রিলেশন**:
- ১-to-Many: agents
- ১-to-Many: executions
- ১-to-Many: api_keys
- ১-to-Many: audit_logs

---

#### 2. Agents টেবিল

**উদ্দেশ্য**: AI এজেন্ট কনফিগারেশন

```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_agents_user_id ON agents(user_id);
CREATE INDEX idx_agents_created_at ON agents(created_at);
```

**কলাম**:
| কলাম | টাইপ | নিয়ম | বিবরণ |
|-------|------|-------|--------|
| id | UUID | PK | এজেন্ট আইডি |
| user_id | UUID | FK → users.id | মালিকানার ইউজার |
| name | VARCHAR(255) | NOT NULL | এজেন্ট নাম |
| description | TEXT | NULL | বিবরণ |
| config | JSONB | NOT NULL | এজেন্ট কনফিগারেশন |
| is_active | BOOLEAN | DEFAULT true | সক্রিয় |
| created_at | TIMESTAMP | DEFAULT now() | তৈরি তারিখ |
| updated_at | TIMESTAMP | DEFAULT now() | আপডেট তারিখ |

**config JSONB স্ট্রাকচার**:
```json
{
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 4096,
  "tools": ["web_search", "code_executor"],
  "memory": {
    "enabled": true,
    "type": "cascade",
    "ttl": 3600
  },
  "system_prompt": "You are a helpful assistant..."
}
```

---

#### 3. Executions টেবিল

**উদ্দেশ্য**: এজেন্ট এক্সিকিউশন লগ

```sql
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    user_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(50) NOT NULL,
    input JSONB NOT NULL,
    output JSONB,
    error TEXT,
    started_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP,
    duration_ms INTEGER
);

CREATE INDEX idx_executions_agent_id ON executions(agent_id);
CREATE INDEX idx_executions_user_id ON executions(user_id);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_started_at ON executions(started_at);
```

**কলাম**:
| কলাম | টাইপ | নিয়ম | বিবরণ |
|-------|------|-------|--------|
| id | UUID | PK | এক্সিকিউশন আইডি |
| agent_id | UUID | FK → agents.id | এজেন্ট |
| user_id | UUID | FK → users.id | ইউজার |
| status | VARCHAR(50) | NOT NULL | স্ট্যাটাস (pending, running, completed, failed) |
| input | JSONB | NOT NULL | ইনপুট ডাটা |
| output | JSONB | NULL | আউটপুট ডাটা |
| error | TEXT | NULL | এরর মেসেজ |
| started_at | TIMESTAMP | DEFAULT now() | শুরু |
| completed_at | TIMESTAMP | NULL | শেষ |
| duration_ms | INTEGER | NULL | সময় (মিলিসেকেন্ড) |

---

#### 4. Memories টেবিল

**উদ্দেশ্য**: এজেন্ট মেমরি স্টোরেজ

```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    agent_id UUID REFERENCES agents(id),
    content TEXT NOT NULL,
    embedding vector(1536),
    memory_type VARCHAR(50) NOT NULL,
    importance FLOAT DEFAULT 0.5,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT now(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_agent_id ON memories(agent_id);
CREATE INDEX idx_memories_type ON memories(memory_type);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
```

**কলাম**:
| কলাম | টাইপ | নিয়ম | বিবরণ |
|-------|------|-------|--------|
| id | UUID | PK | মেমরি আইডি |
| user_id | UUID | FK → users.id | ইউজার |
| agent_id | UUID | FK → agents.id | এজেন্ট (NULL = গ্লোবাল) |
| content | TEXT | NOT NULL | মেমরি কনটেন্ট |
| embedding | vector(1536) | NULL | ভেক্টর এমবেডিং |
| memory_type | VARCHAR(50) | NOT NULL | টাইপ (short_term, long_term, experience) |
| importance | FLOAT | DEFAULT 0.5 | গুরুত্ব (0-1) |
| metadata | JSONB | DEFAULT {} | অতিরিক্ত ডাটা |
| created_at | TIMESTAMP | DEFAULT now() | তৈরি |
| expires_at | TIMESTAMP | NULL | মেয়াদ শেষ |

---

#### 5. API Keys টেবিল

**উদ্দেশ্য**: API কী ম্যানেজমেন্ট

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    hashed_key VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    permissions JSONB DEFAULT '[]',
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);
```

**কলাম**:
| কলাম | টাইপ | নিয়ম | বিবরণ |
|-------|------|-------|--------|
| id | UUID | PK | API কী আইডি |
| user_id | UUID | FK → users.id | মালিকানার ইউজার |
| name | VARCHAR(255) | NOT NULL | কী নাম |
| hashed_key | VARCHAR(255) | UNIQUE, NOT NULL | HMAC-SHA256 হ্যাশ |
| key_prefix | VARCHAR(20) | NOT NULL | লুকআপ প্রিফিক্স |
| permissions | JSONB | DEFAULT [] | পারমিশন লিস্ট |
| expires_at | TIMESTAMP | NULL | মেয়াদ শেষ |
| last_used_at | TIMESTAMP | NULL | শেষ ব্যবহার |
| usage_count | INTEGER | DEFAULT 0 | ব্যবহার গণনা |
| is_active | BOOLEAN | DEFAULT true | সক্রিয় |
| created_at | TIMESTAMP | DEFAULT now() | তৈরি |

---

#### 6. Audit Logs টেবিল

**উদ্দেশ্য**: ক্রিপ্টোগ্রাফিক অডিট ট্রেইল

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT now(),
    signature VARCHAR(255) NOT NULL
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
```

**কলাম**:
| কলাম | টাইপ | নিয়ম | বিবরণ |
|-------|------|-------|--------|
| id | UUID | PK | লগ আইডি |
| user_id | UUID | FK → users.id | ইউজার (NULL = সিস্টেম) |
| action | VARCHAR(100) | NOT NULL | অ্যাকশন (create, update, delete) |
| resource_type | VARCHAR(100) | NOT NULL | রিসোর্স টাইপ (agent, user) |
| resource_id | UUID | NULL | রিসোর্স আইডি |
| details | JSONB | DEFAULT {} | বিস্তারিত |
| ip_address | INET | NULL | IP অ্যাড্রেস |
| user_agent | TEXT | NULL | ইউজার এজেন্ট |
| timestamp | TIMESTAMP | DEFAULT now() | সময় |
| signature | VARCHAR(255) | NOT NULL | SHA-256 স্বাক্ষর |

---

## 🔴 Redis (Upstash)

**উদ্দেশ্য**: ক্যাচিং, সেশন, রেট লিমিটিং

**কানেকশন স্ট্রিং**:
```
redis://:password@host:6379
```

**ফিচার**:
- TTL-বেসড এক্সপায়ারেশন
- অ্যাটমিক অপারেশন
- Pub/sub

**ফ্রি টিয়ার**: 10,000 রিকোয়েস্ট/দিন

---

### কী প্যাটার্ন

#### সেশন স্টোরেজ
```
Key: session:{session_id}
TTL: 86400 seconds (24 hours)
Value: JSON
{
  "user_id": "uuid",
  "email": "user@example.com",
  "roles": ["user"],
  "created_at": "2025-01-04T00:00:00Z"
}
```

#### রেট লিমিটিং
```
Key: rate_limit:{user_id}:{minute}
TTL: 60 seconds
Value: INTEGER (কাউন্টার)
```

#### ক্যাচিং
```
Key: cache:{hash}
TTL: 3600 seconds (1 hour)
Value: JSON (API রেসপন্স)
```

#### টোকেন ব্ল্যাকলিস্ট
```
Key: token_blacklist:{jti}
TTL: 86400 seconds (24 hours)
Value: "1"
```

---

## 🕸️ Neo4j (Aura)

**উদ্দেশ্য**: নলেজ গ্রাফের জন্য গ্রাফ ডাটাবেস

**কানেকশন স্ট্রিং**:
```
neo4j://host:7687
```

**ফিচার**:
- Cypher কুয়ারি ল্যাঙ্গুয়েজ
- গ্রাফ অ্যালগরিদম
- রিলেশনশিপ ট্রাভার্সাল

**ফ্রি টিয়ার**: 10,000 নোড

---

### নোড টাইপ

#### User নোড
```cypher
CREATE (u:User {
  id: "uuid",
  email: "user@example.com",
  created_at: "2025-01-04T00:00:00Z"
})
```

#### Agent নোড
```cypher
CREATE (a:Agent {
  id: "uuid",
  name: "My Agent",
  user_id: "uuid",
  created_at: "2025-01-04T00:00:00Z"
})
```

#### Tool নোড
```cypher
CREATE (t:Tool {
  id: "uuid",
  name: "web_search",
  category: "search"
})
```

#### Knowledge নোড
```cypher
CREATE (k:Knowledge {
  id: "uuid",
  content: "Knowledge content",
  embedding: [0.1, 0.2, ...]
})
```

---

### রিলেশনশিপ

```cypher
// ইউজার এজেন্ট তৈরি করে
(u:User)-[:CREATED]->(a:Agent)

// এজেন্ট টুল ব্যবহার করে
(a:Agent)-[:USES]->(t:Tool)

// এজেন্ট মেমরি স্টোর করে
(a:Agent)-[:STORES]->(m:Memory)

// নলেজ রিলেশনশিপ
(k1:Knowledge)-[:RELATED_TO]->(k2:Knowledge)

// এজেন্ট কলাবোরেশন
(a1:Agent)-[:COLLABORATES_WITH]->(a2:Agent)
```

---

## 🔍 Qdrant (Cloud)

**উদ্দেশ্য**: এমবেডিংসের জন্য ভেক্টর ডাটাবেস

**কানেকশন স্ট্রিং**:
```
https://cluster.qdrant.tech
```

**ফিচার**:
- 1536-ডাইমেনশনাল ভেক্টর
- Cosine সিমিলারিটি
- পেলোড ফিল্টারিং
- হরিজন্টাল স্কেলিং

**ফ্রি টিয়ার**: 1GB স্টোরেজ

---

### কালেকশন

#### Memories কালেকশন
```python
{
  "vectors": [0.1, 0.2, ...],  # 1536 dimensions
  "payload": {
    "user_id": "uuid",
    "agent_id": "uuid",
    "content": "Memory content",
    "memory_type": "long_term",
    "importance": 0.8,
    "created_at": "2025-01-04T00:00:00Z"
  }
}
```

#### Knowledge কালেকশন
```python
{
  "vectors": [0.1, 0.2, ...],
  "payload": {
    "user_id": "uuid",
    "content": "Knowledge content",
    "source": "web",
    "category": "technology",
    "created_at": "2025-01-04T00:00:00Z"
  }
}
```

---

## 📊 ডাটাবেস ER Diagram

```mermaid
erDiagram
    USERS ||--o{ AGENTS : owns
    USERS ||--o{ EXECUTIONS : executes
    USERS ||--o{ API_KEYS : has
    USERS ||--o{ AUDIT_LOGS : creates
    USERS ||--o{ MEMORIES : stores
    
    AGENTS ||--o{ EXECUTIONS : has
    AGENTS ||--o{ MEMORIES : stores
    
    USERS {
        uuid id PK
        string email UK
        string hashed_password
        jsonb roles
        boolean is_active
        timestamp created_at
    }
    
    AGENTS {
        uuid id PK
        uuid user_id FK
        string name
        jsonb config
        boolean is_active
        timestamp created_at
    }
    
    EXECUTIONS {
        uuid id PK
        uuid agent_id FK
        uuid user_id FK
        string status
        jsonb input
        jsonb output
        timestamp started_at
    }
    
    MEMORIES {
        uuid id PK
        uuid user_id FK
        uuid agent_id FK
        text content
        vector embedding
        string memory_type
        timestamp created_at
    }
    
    API_KEYS {
        uuid id PK
        uuid user_id FK
        string hashed_key UK
        jsonb permissions
        timestamp expires_at
        boolean is_active
    }
    
    AUDIT_LOGS {
        uuid id PK
        uuid user_id FK
        string action
        string resource_type
        timestamp timestamp
        string signature
    }
```

---

## 🔄 ডাটাবেস কানেকশন

### কানেকশন পুল কনফিগারেশন

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Usage
async with async_session() as session:
    result = await session.execute(select(User))
    users = result.scalars().all()
```

---

## 📊 ডাটাবেস মাইগ্রেশন

### Alembিক কনফিগারেশন

**ফাইল**: `backend/core/database/migrations/env.py`

```python
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        
        with context.begin_transaction():
            context.run_migrations()
```

### মাইগ্রেশন কমান্ড

```bash
# Create migration
alembic revision --autogenerate -m "Add users table"

# Run migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🔍 ডাটাবেস ভেরিফিকেশন

**ভেরিফাই করার উপায়**:

1. **কানেকশন টেস্ট**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/api/v1/health/database
   # Should return: {"status": "healthy", "database": "connected"}
   ```

2. **টেবিল লিস্ট**:
   ```bash
   psql $DATABASE_URL -c "\dt"
   # Should show: users, agents, executions, memories, api_keys, audit_logs
   ```

3. **রেকর্ড কাউন্ট**:
   ```bash
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
   ```

4. **ইনডেক্স চেক**:
   ```bash
   psql $DATABASE_URL -c "\di idx_*"
   # Should show all indexes
   ```

---

## 🔗 সম্পর্কিত ডকুমেন্ট

- [03-ARCHITECTURE_bn.md](03-ARCHITECTURE_bn.md) - সিস্টেম আর্কিটেকচার
- [04-FOLDER_STRUCTURE_bn.md](04-FOLDER_STRUCTURE_bn.md) - ফোল্ডার সংগঠন
- [07-DEPENDENCY_DOCUMENTATION_bn.md](07-DEPENDENCY_DOCUMENTATION_bn.md) - ডিপেন্ডেন্সি
- [11-API_DOCUMENTATION_bn.md](11-API_DOCUMENTATION_bn.md) - API রেফারেন্স

---

## ✅ ডাটাবেস ডকুমেন্টেশন ভেরিফিকেশন

**ভেরিফাই করার উপায়**:

1. **স্কিমা ভেরিফাই**:
   ```bash
   # Check all tables exist
   psql $DATABASE_URL -c "\dt"
   
   # Check table structures
   psql $DATABASE_URL -d supremeai -c "\d users"
   psql $DATABASE_URL -d supremeai -c "\d agents"
   ```

2. **রিলেশন ভেরিফাই**:
   ```bash
   # Check foreign keys
   psql $DATABASE_URL -c "
   SELECT conname, conrelid::regclass, confrelid::regclass 
   FROM pg_constraint 
   WHERE contype = 'f';
   "
   ```

3. **ইনডেক্স ভেরিফাই**:
   ```bash
   # Check indexes
   psql $DATABASE_URL -c "\di"
   ```

---

**ডকুমেন্ট স্ট্যাটাস**: ✅ সম্পূর্ণ এবং ভেরিফাইড  
**পরবর্তী রিভিউ**: 2025-02-04  
**অনার**: ডাটাবেস টিম  
**ক্লাসিফিকেশন**: ইন্টার্নাল
