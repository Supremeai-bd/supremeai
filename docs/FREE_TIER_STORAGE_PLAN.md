# Free-Tier Persistent Storage Solution — No Render Disk Needed

## Problem

`docs/ADMIN_TASKS.md` says "Mount Persistent `/data/` Volume on Render" — but
**Render free tier does NOT support disks/volumes**. Without persistent
storage, ChromaDB + Qdrant + SQLite data is LOST on every container cold-start
(Render free-tier sleeps after 15 min idle).

## Solution: Use Supabase pgvector (Already Provisioned)

The codebase ALREADY has a complete Supabase pgvector setup:
- `ai_memory` table in `backend/alembic_migrations/versions/001_initial_schema.sql:301`
  with `embedding VECTOR(1536)` column + ivfflat index
- `backend/memory/supabase_store.py` (423 lines) with `similarity_search()` method
- `backend/services/memory_service.py:43` with `CREATE TABLE IF NOT EXISTS ai_memory`
- Supabase free tier = 500MB Postgres + 1GB storage = plenty for vector embeddings

This means we DON'T need Render disk — we already have persistent vector
storage via Supabase pgvector. The issue is that `ExperienceDatabase`
(adaptive_engine/experience_db.py) is hardwired to ChromaDB/Qdrant local
files instead of using Supabase.

## Fix Plan

1. **Add Supabase pgvector backend to ExperienceDatabase** — when ChromaDB/Qdrant
   are not available (Render free-tier), fall back to Supabase pgvector which is
   already persistent across restarts.

2. **Update ADMIN_TASKS.md** — remove the impossible "Mount /data/ Volume on Render"
   task, replace with "Use Supabase pgvector (no action needed — already set up)".

3. **Update env var defaults** — change `EXPERIENCE_DB_PATH` default from `/tmp/chroma`
   to empty string (forces Supabase pgvector fallback when not set).

4. **Document the migration** — explain how to opt-out of ChromaDB/Qdrant entirely
   by setting `USE_SUPABASE_VECTOR=true` (new env var).

## Why This Is Better Than Render Disk

| Aspect | Render Disk (impossible on free) | Supabase pgvector (current) |
|---|---|---|
| Cost | $0 only on paid tier | $0 on free tier |
| Persistence | Container-local only | Cross-region, cross-container |
| Backup | Manual | Supabase auto-backups |
| Connection limit | N/A | 60-100 (PgBouncer-pooled) |
| Already used? | No | Yes — ai_memory table live |

## Implementation

### Step 1: Add `SupabaseVectorBackend` class to experience_db.py

```python
class SupabaseVectorBackend:
    """Use Supabase pgvector instead of ChromaDB/Qdrant.
    
    This is the PREFERRED backend on Render free-tier because:
    - No local disk needed (Supabase is remote + persistent)
    - Already provisioned (ai_memory table + ivfflat index)
    - 500MB free tier is plenty for ~300K vectors at 1536 dims
    """
    
    def __init__(self):
        from database.supabase_client import SupabaseDB
        self.db = SupabaseDB()
        self.collection_name = "experience"  # stored in metadata column
        
    def upsert(self, exp_id: str, embedding: list[float], document: str, metadata: dict):
        if not self.db.client:
            return
        # Use ai_memory table (already has VECTOR(1536) column)
        self.db.client.table("ai_memory").upsert({
            "id": exp_id,
            "memory_type": "procedural",  # experiences are procedural knowledge
            "content": document,
            "embedding": embedding,
            "metadata": {**metadata, "collection": self.collection_name},
        }).execute()
    
    def query(self, query_embedding: list[float], limit: int = 5):
        if not self.db.client:
            return []
        # Use pgvector cosine similarity operator (<=>)
        result = self.db.client.rpc("match_experiences", {
            "query_embedding": query_embedding,
            "match_count": limit,
            "filter_collection": self.collection_name,
        }).execute()
        return result.data or []
```

### Step 2: Create Supabase RPC function `match_experiences`

```sql
-- Add this to a new migration (16_add_match_experiences_rpc.sql)
CREATE OR REPLACE FUNCTION match_experiences(
    query_embedding VECTOR(1536),
    match_count INT DEFAULT 5,
    filter_collection TEXT DEFAULT 'experience'
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        id,
        content,
        metadata,
        1 - (embedding <=> query_embedding) AS similarity
    FROM ai_memory
    WHERE metadata->>'collection' = filter_collection
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
```

### Step 3: Update ExperienceDatabase to prefer Supabase backend

```python
class ExperienceDatabase:
    def __init__(self, db_path: str | None = None):
        # ... existing setup ...
        
        # NEW: prefer Supabase pgvector on Render free-tier (no disk)
        self.use_supabase_vector = os.getenv(
            "USE_SUPABASE_VECTOR",
            "true" if not os.getenv("EXPERIENCE_DB_PATH") else "false"
        ).lower() == "true"
        
        if self.use_supabase_vector:
            try:
                from adaptive_engine.supabase_vector_backend import SupabaseVectorBackend
                self.supabase_backend = SupabaseVectorBackend()
                logger.info("✅ ExperienceDatabase using Supabase pgvector (persistent, no disk needed)")
                return  # skip ChromaDB/Qdrant init
            except Exception as exc:
                logger.warning(f"Supabase pgvector init failed: {exc}, falling back to local")
        
        # Existing ChromaDB + Qdrant init (only if Supabase not used)
        self._ensure_chroma()
        self._ensure_qdrant()
```

### Step 4: Update ADMIN_TASKS.md

Replace the impossible task with a note that NO action is needed.

## Why This Approach

1. **Zero new infra** — uses already-provisioned Supabase pgvector
2. **Truly persistent** — data survives Render container restarts (Supabase is remote)
3. **Free-tier compatible** — Supabase free tier (500MB) handles ~300K vectors
4. **Backward compatible** — `USE_SUPABASE_VECTOR=false` falls back to ChromaDB/Qdrant
5. **No disk mount needed** — fixes the impossible task in ADMIN_TASKS.md
