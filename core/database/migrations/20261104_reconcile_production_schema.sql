-- =============================================================================
-- SupremeAI Production Database Reconciliation Migration (Finding #6)
-- Target: Supabase PostgreSQL (Public Schema)
-- Generated: 2026-11-04
-- =============================================================================

BEGIN;

-- 1. Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS "vector";
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector extension could not be enabled, continuing...';
END $$;

-- -----------------------------------------------------------------------------
-- 2. USERS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL DEFAULT '',
    role VARCHAR(50) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin', 'operator', 'agent_operator')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);

-- -----------------------------------------------------------------------------
-- 3. API KEYS TABLE (Required by schema_contract.yaml)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL DEFAULT 'default',
    key_hash VARCHAR(255) NOT NULL,
    key_masked VARCHAR(64) NOT NULL,
    key_prefix VARCHAR(16) NOT NULL,
    scopes JSONB NOT NULL DEFAULT '["read", "write"]',
    rate_limit_rps INTEGER NOT NULL DEFAULT 60,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON public.api_keys(key_hash);

-- -----------------------------------------------------------------------------
-- 4. CONVERSATION CONTEXT TABLE (Required by schema_contract.yaml)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversation_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    messages JSONB NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_context_session_id ON public.conversation_context(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_context_user_id ON public.conversation_context(user_id);

-- -----------------------------------------------------------------------------
-- 5. TASK HISTORY TABLE (Required by schema_contract.yaml)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.task_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(100) NOT NULL DEFAULT 'general',
    prompt TEXT NOT NULL DEFAULT '',
    provider VARCHAR(100) NOT NULL DEFAULT 'internal',
    cost NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    result JSONB NOT NULL DEFAULT '{}',
    success BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_history_task_type ON public.task_history(task_type);
CREATE INDEX IF NOT EXISTS idx_task_history_created_at ON public.task_history(created_at DESC);

-- -----------------------------------------------------------------------------
-- 6. TENANT LIMITS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tenant_limits (
    tenant_id TEXT PRIMARY KEY,
    org_name TEXT,
    requests_per_minute INTEGER DEFAULT 60,
    max_tokens_per_day INTEGER DEFAULT 100000,
    max_concurrent_sessions INTEGER DEFAULT 5,
    billing_tier TEXT DEFAULT 'free',
    stripe_customer_id TEXT,
    custom_limits JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 7. TENANT USAGE TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tenant_usage (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES public.tenant_limits(tenant_id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    requests_today INTEGER DEFAULT 0,
    tokens_today INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_usage_tenant_date UNIQUE (tenant_id, date)
);

CREATE INDEX IF NOT EXISTS idx_tenant_usage_date ON public.tenant_usage(tenant_id, date);

-- -----------------------------------------------------------------------------
-- 8. AUTOMATION EXECUTIONS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.automation_executions (
    id VARCHAR(36) PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL,
    workflow_key VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    attempt INTEGER DEFAULT 1,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    http_status INTEGER,
    external_execution_id VARCHAR(100),
    trace_id VARCHAR(100),
    correlation_id VARCHAR(128),
    tenant_id TEXT,
    error_code VARCHAR(100),
    error_message VARCHAR(1024),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_automation_executions_event_id ON public.automation_executions(event_id);
CREATE INDEX IF NOT EXISTS ix_automation_executions_workflow_key ON public.automation_executions(workflow_key);
CREATE INDEX IF NOT EXISTS ix_automation_executions_status ON public.automation_executions(status);
CREATE INDEX IF NOT EXISTS ix_automation_executions_trace_id ON public.automation_executions(trace_id);
CREATE INDEX IF NOT EXISTS ix_automation_executions_created_at ON public.automation_executions(created_at DESC);

-- -----------------------------------------------------------------------------
-- 9. AI MEMORY TABLE (Vector Store)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.ai_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_type TEXT NOT NULL DEFAULT 'main',
    task_type TEXT NOT NULL DEFAULT 'general',
    summary TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_memory_created_at ON public.ai_memory(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_memory_session_id ON public.ai_memory(session_id);

-- -----------------------------------------------------------------------------
-- 10. TASK CHECKPOINTS TABLE (Fail-closed schema gate required table)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.task_checkpoints (
    task_id TEXT PRIMARY KEY,
    step_index INTEGER,
    state TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resumed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_task_checkpoints_created_at ON public.task_checkpoints(created_at DESC);

-- -----------------------------------------------------------------------------
-- 11. ROW LEVEL SECURITY (RLS) POLICIES
-- -----------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.automation_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_checkpoints ENABLE ROW LEVEL SECURITY;

-- Allow service_role full access across all tables
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('users', 'api_keys', 'conversation_context', 'task_history', 'tenant_limits', 'tenant_usage', 'automation_executions', 'ai_memory', 'task_checkpoints')
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS service_role_all ON public.%I', tbl);
        EXECUTE format('CREATE POLICY service_role_all ON public.%I FOR ALL USING (auth.role() = ''service_role'')', tbl);
    END LOOP;
END $$;

COMMIT;
