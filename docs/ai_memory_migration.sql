-- =====================================================
-- SupremeAI - AI Memory Table Migration (Phase C)
-- =====================================================
-- Supabase SQL Editor-এ এটা রান করুন।
-- pgvector extension আগে থেকে Supabase-এ enabled থাকে।

-- Step 1: pgvector extension enable করুন (যদি না থাকে)
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: ai_memory টেবিল তৈরি করুন
CREATE TABLE IF NOT EXISTS ai_memory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    agent_type  TEXT NOT NULL DEFAULT 'main',   -- 'main', 'subagent', 'reviewer'
    task_type   TEXT NOT NULL DEFAULT 'general', -- 'bug-fix', 'feature', 'deploy', 'ci' etc.
    summary     TEXT NOT NULL,                   -- Human-readable session summary
    embedding   VECTOR(384),                     -- all-MiniLM-L6-v2 dimension (384)
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: Performance index (IVFFlat for approximate nearest neighbor search)
CREATE INDEX IF NOT EXISTS ai_memory_embedding_idx
    ON ai_memory
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Step 4: Created_at index for time-based queries
CREATE INDEX IF NOT EXISTS ai_memory_created_at_idx
    ON ai_memory (created_at DESC);

-- Step 5: match_ai_memory RPC function (semantic search)
-- Python scripts/ai/memory_read.py এই function কল করে
CREATE OR REPLACE FUNCTION match_ai_memory(
    query_embedding VECTOR(384),
    match_threshold FLOAT DEFAULT 0.7,
    match_count     INT DEFAULT 5
)
RETURNS TABLE (
    id          UUID,
    session_id  TEXT,
    agent_type  TEXT,
    task_type   TEXT,
    summary     TEXT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ,
    similarity  FLOAT
)
LANGUAGE SQL STABLE
AS $$
    SELECT
        id,
        session_id,
        agent_type,
        task_type,
        summary,
        metadata,
        created_at,
        1 - (embedding <=> query_embedding) AS similarity
    FROM ai_memory
    WHERE 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Step 6: Row Level Security (RLS) — service role key ছাড়া কেউ access করতে পারবে না
ALTER TABLE ai_memory ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (backend only)
CREATE POLICY "Service role full access"
    ON ai_memory
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Step 7: Cleanup old memories (optional — 90 দিনের বেশি পুরানো মেমোরি delete করে)
-- Supabase Cron Job হিসেবে সেট করুন:
-- DELETE FROM ai_memory WHERE created_at < NOW() - INTERVAL '90 days';

-- =====================================================
-- Verification: টেবিল ঠিকমতো তৈরি হয়েছে কিনা চেক করুন
-- =====================================================
-- SELECT COUNT(*) FROM ai_memory;
-- SELECT * FROM ai_memory LIMIT 5;

-- =====================================================
-- Test insert (optional)
-- =====================================================
-- INSERT INTO ai_memory (session_id, agent_type, task_type, summary, embedding)
-- VALUES (
--     'test_session_001',
--     'main',
--     'general',
--     'Test memory entry for SupremeAI Context Mesh',
--     array_fill(0, ARRAY[384])::VECTOR(384)
-- );
